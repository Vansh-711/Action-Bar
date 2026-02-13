import os
import json
import time
import client_app
import groq_brain
import toolbox_db
import toolbox_logger
import sys
from dotenv import load_dotenv

load_dotenv()

DB = toolbox_db.ToolboxDB()

# 1. ROUTER PROMPT: Break goal into Tools vs Primitives
ROUTER_PROMPT = """You are the Groq Toolbox Router.
Your goal is to decompose the user goal into a sequence of HIGH-LEVEL TOOLS.

### 🧰 AVAILABLE TOOLS (Sorted Newest to Oldest)
{tool_list}

### 🎯 USER GOAL
"{user_goal}"

### 🧠 TOOL SELECTION STRATEGY
1. **Specificity Wins:** If user asks for "Brave", use `open_youtube_in_brave` instead of `open_youtube`.
2. **Recency Wins:** If two tools look similar, pick the first one in the list (it is the newest).
3. **Parameter Matching:** Ensure the tool parameters match the user's intent.

### 🧠 DATA TRANSFER RULE
- ⛔ DO NOT rely on Copy/Paste (Cmd+C/V) for data transfer. It is unreliable.
- ✅ INSTEAD: Use `read_screen` to see the information, then simply `type_text` that information in the next step.
- Example: "The Bitcoin price is $96,000" should be typed directly after reading.

### 📝 INSTRUCTIONS
1. Decompose the goal into steps.
2. If a Tool exists for a step, use `call_tool("name", params={{...}})`.
3. If NO Tool exists, use `primitive_block(description="Describe steps here")`.
4. Output a JSON list.

Example:
[
  {{"action": "call_tool", "name": "open_youtube_in_brave"}},
  {{"action": "primitive_block", "description": "Search for Gangnam Style"}}
]
"""

# 2. PRIMITIVE PLANNER: Expand a description into raw steps
PRIMITIVE_PROMPT = """You are the Groq Primitive Planner.
Convert this description into raw PyAutoGUI-style actions.

DESCRIPTION: {description}
OS: {os_platform}
CURRENT STATE: Active App is "{active_app}".

### ⛔ CRITICAL RULES:
1. If Active App is ALREADY the correct app (e.g. Brave), DO NOT use `open_app` again. Just type/click.
2. If Active App is a browser, DO NOT open 'Chrome' or 'Safari'. Use the active browser.
3. Only use `open_app` if the description EXPLICITLY says "Open [App]".

ACTIONS: open_app, click_text, type_text, press_key, wait.

Output a JSON list of raw actions.
"""

# 3. CONSOLIDATOR: Create a clean "Golden Tool" from successful execution
CONSOLIDATOR_PROMPT = """You are the Groq Tool Optimizer.
The user achieved: "{user_goal}".
Execution Trace: {trace}

### 🎯 YOUR MISSION:
Extract the SINGLE MOST EFFICIENT, GENERALIZED path to achieve this goal.

### ⛔ GENERALIZATION RULES:
1. IDENTIFY THE SUBJECT: If the user searched for 'Nvidia' or 'Bitcoin', replace that specific term with a variable like `{{query}}` or `{{asset_name}}`.
2. PARAMETERIZE: Define these variables in the "parameters" list.
3. DEDUPLICATE: Remove failed attempts. Keep only the final successful path.
4. LINEAR: Result should be a clean sequence.

Output JSON:
{{
  "name": "generalized_task_name",
  "description": "Describe the pattern (e.g. Search any stock price and note it)",
  "parameters": ["query"],
  "body": [ ...use {{query}} in steps... ]
}}
"""

# 4. SURGICAL FIX PROMPT: Re-plan a specific tool/block with context
FIX_PROMPT = """You are the Groq Surgical Fixer.
A plan failed. You must fix it based on the EXECUTION LOG.

### 🎯 MAIN GOAL: "{user_goal}"

### 📜 SESSION LOG (Ground Truth):
{session_log}

### ⚡ YOUR TASK:
1. Analyze the LOG. Identify where it deviated from the goal.
2. Output a sequence of HIGH-LEVEL BLOCKS to finish the task.
3. ⛔ DO NOT REPEAT WORK that was successfully confirmed.
4. 🏗️ STRUCTURE: Break the fix into 2-3 logical `primitive_block` items with clear descriptions (e.g. "Navigate to YouTube", "Search for Video").
5. ⛔ NO RAW LISTS: Do NOT output actions at the top level. Wrap them in `primitive_block`.

Example Output:
[
  {{"action": "primitive_block", "description": "Open new tab and go to Google", "steps": [...]}},
  {{"action": "call_tool", "name": "..."}}
]
"""

class ToolboxAgent:
    def __init__(self):
        self.os_platform = "macOS" if "darwin" in sys.platform else "Windows"
        self.DB = DB # Expose DB to GUI
        self.active_app = "Unknown" # Session state
        self.session_memory = "" # To store last read_screen data

    def normalize_plan(self, plan):
        """Groups raw actions into small, logical primitive blocks."""
        if not isinstance(plan, list): return []
        
        normalized = []
        raw_buffer = []
        
        for step in plan:
            action = step.get("action")
            if action in ["call_tool", "primitive_block"]:
                if raw_buffer:
                    # Create a smaller block from buffer
                    desc = f"Steps: {raw_buffer[0].get('action')} to {raw_buffer[-1].get('action')}"
                    normalized.append({"action": "primitive_block", "description": desc, "steps": raw_buffer})
                    raw_buffer = []
                normalized.append(step)
            else:
                raw_buffer.append(step)
                # Split raw buffer if it gets too long to maintain logical chunks
                if len(raw_buffer) >= 5:
                    normalized.append({"action": "primitive_block", "description": "Logical Chunk", "steps": raw_buffer})
                    raw_buffer = []
                
        if raw_buffer:
             normalized.append({"action": "primitive_block", "description": "Final Steps", "steps": raw_buffer})
             
        return normalized

    def plan_fix(self, user_goal, full_plan, block_num, feedback):
        """Step 5: Surgical Re-planning using SESSION LOG."""
        # Read the ground truth log
        session_log_content = toolbox_logger.read_log()
        
        all_tools = self.DB.get_all_tools()
        detailed_tools = []
        for t in all_tools:
            t["body"] = self.DB.get_tool_body(t["name"])
            detailed_tools.append(t)
            
        prompt = FIX_PROMPT.format(
            user_goal=user_goal,
            session_log=session_log_content, # INJECTED LOG
            tool_definitions=json.dumps(detailed_tools, indent=2), # Keep tool context
            feedback=feedback
        )
        
        print(f"   🧠 Analyzing Session Log for Fix...")
        raw_fix = groq_brain.get_action_plan(prompt, model_id=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        return self.normalize_plan(raw_fix)

    def find_relevant_tools(self, query):
        """Finds tools matching keywords or action patterns."""
        keywords = query.lower().split()
        # Common action verbs to increase matching probability
        action_verbs = ["open", "search", "play", "get", "type", "check", "find"]
        found_verbs = [v for v in action_verbs if v in keywords]
        
        matches = []
        all_tools = self.DB.get_all_tools()
        
        for tool in all_tools:
            text_corpus = (tool["name"] + " " + tool.get("description", "")).lower()
            score = 0
            # Match specific keywords
            for word in keywords:
                if word in text_corpus: score += 2 # Subject match is high priority
            
            # Match action verbs
            for verb in found_verbs:
                if verb in text_corpus: score += 1 # Action match is secondary
            
            if score > 0:
                matches.append(tool)
                
        return matches

    def decompose_goal(self, user_goal):
        """Step 1: Get high-level plan (Tools or Primitive Blocks)."""
        relevant_tools = DB.find_relevant_tools(user_goal)
        tool_list_str = json.dumps(relevant_tools, indent=2) if relevant_tools else "No custom tools yet."

        prompt = ROUTER_PROMPT.format(tool_list=tool_list_str, user_goal=user_goal)
        print("   🧠 Routing goal to tools...")
        plan = groq_brain.get_action_plan(prompt, model_id=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        
        return self.normalize_plan(plan)

    def expand_primitive(self, block):
        """Step 2: Return raw steps directly if available, or expand description."""
        if "steps" in block:
            return block["steps"]
            
        description = block.get("description", "")
        
        # Include session memory (truncated) to keep tokens low
        memory_snippet = self.session_memory[-3000:] if self.session_memory else "Nothing captured yet."
        
        prompt = PRIMITIVE_PROMPT.format(
            description=description, 
            os_platform=self.os_platform,
            active_app=self.active_app
        )
        
        # ADD MEMORY CONTEXT
        full_prompt = f"{prompt}\n\n### 📄 SESSION MEMORY (Last Read Screen):\n{memory_snippet}"
        
        print(f"   🧠 Planning primitive block: {description} (Context: {self.active_app})...")
        steps = groq_brain.get_action_plan(full_prompt, model_id=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        return steps if isinstance(steps, list) else []

    def expand_tool(self, tool_name, params):
        """Step 3: Get tool steps and fill parameters (Recursive Expansion)."""
        # Update context if tool opens app
        if "app_name" in params:
            self.active_app = params["app_name"]
            
        body = DB.get_tool_body(tool_name)
        if not body: return []
        
        # 1. Parameter Substitution
        body_str = json.dumps(body)
        for k, v in params.items():
            body_str = body_str.replace(f"{{{k}}}", str(v))
        
        raw_steps = json.loads(body_str)
        
        # 2. Recursive Expansion
        final_steps = []
        for step in raw_steps:
            if step.get("action") == "call_tool":
                # Recursion!
                nested_steps = self.expand_tool(step["name"], step.get("params", {}))
                final_steps.extend(nested_steps)
            else:
                final_steps.append(step)
                
        return final_steps

    def execute_step(self, step):
        """Executes a single step with robust 'Lazy JSON' and String normalization."""
        # 0. Handle String Format: "wait(5)" or "read_screen()"
        if isinstance(step, str):
            step = step.strip()
            if "(" in step and ")" in step:
                action = step.split("(")[0]
                val = step.split("(")[1].split(")")[0].strip("'\" ")
                if action == "wait": step = {"action": "wait", "seconds": val}
                elif action == "open_app": step = {"action": "open_app", "name": val}
                elif action == "type_text": step = {"action": "type_text", "text": val}
                elif action == "press_key": step = {"action": "press_key", "key": val}
                elif action == "click_text": step = {"action": "click_text", "text": val}
            else:
                step = {"action": step}

        # 1. Determine Action
        action = step.get("action") or step.get("tool")
        params = step.get("params") or step.get("args")
        
        # 2. Handle Lazy Format: {"open_app": "Brave"}
        if not action:
            known_actions = ["open_app", "click_text", "type_text", "press_key", "wait", "read_screen"]
            for k, v in step.items():
                if k in known_actions:
                    action = k
                    if isinstance(v, (str, int, float)):
                        if k == "open_app": params = {"name": v}
                        elif k in ["click_text", "type_text"]: params = {"text": v}
                        elif k == "press_key": params = {"key": v}
                        elif k == "wait": params = {"seconds": v}
                    elif isinstance(v, dict):
                        params = v
                    break
        if params is None: params = step

        # 4. Secondary Normalization and Context Tracking
        if action == "open_app":
            if isinstance(params, dict) and "name" not in params:
                if action in params: params["name"] = params[action]
            if isinstance(params, dict) and "name" in params:
                self.active_app = params["name"]

        if action:
            # SPECIAL: Handle read_screen memory
            if action == "read_screen":
                import pytesseract
                import pyautogui
                print("   👀 Capturing screen memory...")
                screenshot = pyautogui.screenshot()
                text = pytesseract.image_to_string(screenshot)
                self.session_memory = " ".join(text.split())
                # Return True here, primitive in client_app will also run but we've stored it.
                return True
                
            return client_app.execute_step(action, params, context={})
        return False

    def consolidate_and_save(self, user_goal, full_trace):
        """Step 4: Create a new tool from the successful trace."""
        print("   🧠 Consolidating successful run into a new Tool...")
        prompt = CONSOLIDATOR_PROMPT.format(user_goal=user_goal, trace=json.dumps(full_trace))
        new_tool = groq_brain.get_action_plan(prompt, model_id=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        
        if new_tool and "name" in new_tool:
            # FORCE UPDATE: Overwrite existing tool if it has the same goal/name
            print(f"   💡 Saving Golden Tool: {new_tool['name']}")
            DB.save_tool(new_tool["name"], new_tool["description"], new_tool.get("parameters", []), new_tool["body"])
            return new_tool["name"]
        return None
