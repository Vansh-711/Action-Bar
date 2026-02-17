import os
import json
import groq_brain
import system_monitor
import toolbox_db
import toolbox_logger

# Configuration
STORAGE_DIR = "execution_files"
os.makedirs(STORAGE_DIR, exist_ok=True)

class AgentCompiler:
    """
    Implements the V1.2 Multi-Stage Reasoning Pipeline.
    Manages 1.json through 6.json via toolbox_logger.
    """
    def __init__(self):
        self.db = toolbox_db.ToolboxDB()
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    # --- STAGE 1: THE ARCHITECT ---
    def stage_1_main_breakdown(self, user_goal):
        """Breaks goal into high-level blocks."""
        system_context = system_monitor.get_system_context_string()
        
        prompt = f"""This is the task that needs to be performed on Mac/Win: "{user_goal}".
{system_context}

Zoom out of the scope of what to do. 
First break the main task into convenient groups or blocks of task. 
Make a list of all the needed groups/blocks.

Output ONLY a JSON list of descriptions.
Example: ["Open Browser", "Search for Nvidia", "Extract Price", "Save to Notes"]
"""
        print("   🧠 [Stage 1] Breaking down task...")
        result = groq_brain.get_action_plan(prompt, model_id=self.model)
        return toolbox_logger.save_stage_file("1_main_breakdown.json", result)

    # --- STAGE 2: SEMANTIC EXPANSION ---
    def stage_2_semantic_search(self, user_goal):
        """Generates similar keywords for DB lookup."""
        prompt = f"""User Goal: "{user_goal}"
Make a small list of words in English that are similar to the key terms in the prompt.
This will be used to search a tool database.

Output ONLY a JSON list of words.
Example: ["nvidia", "stock", "price", "notes", "finance", "fetch", "save"]
"""
        print("   🧠 [Stage 2] Generating search keywords...")
        result = groq_brain.get_action_plan(prompt, model_id=self.model)
        return toolbox_logger.save_stage_file("2_semantic_search.json", result)

    # --- STAGE 3: TOOL RETRIEVAL (Python Logic) ---
    def stage_3_available_tools(self):
        """Queries the database using keywords from Stage 2."""
        keywords_list = toolbox_logger.read_stage_file("2_semantic_search.json")
        if not keywords_list: return []

        print("   🧠 [Stage 3] Querying SQL Database for relevant tools...")
        # PASS LIST DIRECTLY for optimized DB search
        matches = self.db.find_relevant_tools(keywords_list)
        
        # Also fetch bodies for these tools to make the next stage smarter
        detailed_tools = []
        old_tools_names = []
        for t in matches:
            t["body"] = self.db.get_tool_body(t["name"])
            detailed_tools.append(t)
            old_tools_names.append(t["name"])

        # Log tool usage
        toolbox_logger.log_tools_used(new_tools=[], old_tools=old_tools_names)

        return toolbox_logger.save_stage_file("3_available_tools.json", detailed_tools)

    # --- STAGE 4: COMPOSITION ---
    def stage_4_final_execution(self, user_goal):
        """Composes and EXPANDS the final plan."""
        breakdown = toolbox_logger.read_stage_file("1_main_breakdown.json")
        tools = toolbox_logger.read_stage_file("3_available_tools.json")
        system_context = system_monitor.get_system_context_string()

        prompt = f"""USER GOAL: "{user_goal}"
TASK BREAKDOWN: {json.dumps(breakdown)}
AVAILABLE TOOLS: {json.dumps(tools)}
{system_context}

YOUR TASK:
Using the available tools and breakdown, create a final execution plan.
- 🚫 BROWSER SEARCH: NEVER use `command+f` inside a web browser (Brave/Chrome). It searches the HTML, not the app's messages. Use manual clicking or `click_near` instead.
- 🎯 CONTEXTUAL CLICKING: NEVER use `click_text` for search results or contact names. ALWAYS use `click_near(target="...", anchor="...")`.
- 🏢 ANCHORS: For Instagram/WhatsApp, use anchors like "Chats", "Messages", or "Direct" to find the correct contact link.
- 💾 FILE SAVING SAFETY: macOS Save dialogs are slow. Always use `wait(2)` before typing a filename and `press_key("enter")` TWICE.
- 🏗️ LINEARITY: Output a clean, linear list of actions.
- 🌐 NAVIGATION: Use `navigate(url="...")` for all website navigation.
- 💎 DATA EXTRACTION: Use `extract_info(description="...")`.
- 💎 DYNAMIC DATA: Use "$LAST_READ" for typed information.
- Example: 
  1. `{{"action": "navigate", "url": "https://google.com"}}`
  2. `{{"action": "click_near", "target": "Tim Cook", "anchor": "x.com"}}`
  3. `{{"action": "extract_info", "description": "the stock price"}}`
- ⛔ NO CUSTOM VARIABLES: Do NOT use `{{extracted_price}}`, `{{value}}`, or any other placeholders. 
- ⛔ NO CURLY BRACES: Using `{{ }}` will cause an execution error.
- Example: `{{"action": "type_text", "text": "The price is $LAST_READ"}}`

Output ONLY a JSON list of actions.
"""
        print("   🧠 [Stage 4] Composing high-level plan...")
        raw_plan = groq_brain.get_action_plan(prompt, model_id=self.model)
        
        # --- NEW: EXPANSION LOGIC ---
        print("   🔧 [Stage 4] Expanding tool calls into primitives...")
        expanded_plan = self.expand_plan_recursive(raw_plan, tools)
        
        return toolbox_logger.save_stage_file("4_final_execution.json", expanded_plan)

    def expand_plan_recursive(self, plan, tools_list):
        """Recursively flattens call_tool into primitive actions."""
        if not isinstance(plan, list): return []
        
        # Create a lookup map for the tools we have
        tool_map = {t["name"]: t for t in tools_list}
        
        final_plan = []
        for step in plan:
            if not isinstance(step, dict): continue
            
            action = step.get("action")
            if action == "call_tool":
                # Be flexible: check 'name' or 'tool'
                tool_name = step.get("name") or step.get("tool")
                params = step.get("params", {})
                
                if tool_name in tool_map:
                    # 1. Get tool body
                    body = tool_map[tool_name].get("body", [])
                    # 2. Parameter Substitution
                    body_str = json.dumps(body)
                    for k, v in params.items():
                        body_str = body_str.replace(f"{{{k}}}", str(v))
                    
                    expanded_steps = json.loads(body_str)
                    # 3. Recurse (in case of nested tools)
                    final_plan.extend(self.expand_plan_recursive(expanded_steps, tools_list))
                else:
                    print(f"   ⚠️  Warning: Tool '{tool_name}' not found in available tools list.")
                    final_plan.append(step) # Keep it as is (will likely fail later)
            else:
                final_plan.append(step)
                
        return final_plan

    # --- STAGE 5: SURGICAL FIX ---
    def stage_5_surgical_fix(self, user_goal, feedback, steps_done):
        """Generates a corrective plan based on feedback."""
        full_plan = toolbox_logger.read_stage_file("4_final_execution.json")
        tools = toolbox_logger.read_stage_file("3_available_tools.json")
        
        prompt = f"""### 🎯 MAIN GOAL: "{user_goal}"
### 📋 PREVIOUS PLAN: {json.dumps(full_plan)}
### 🟢 COMPLETED STEPS: {json.dumps(steps_done)}
### 🔴 ERROR/USER FEEDBACK: "{feedback}"
### 🧰 AVAILABLE TOOLS: {json.dumps(tools)}

YOUR TASK:
Refer to the original plan and the feedback. You MUST fix the error.
- 🧱 MANDATORY FEEDBACK: You MUST follow the User Feedback word-for-word. If they said "open brave", you CANNOT use "Chrome".
- 🏗️ FULL SEQUENCE: Output the FULL corrected plan from start to finish.
- 🏢 APP CONSISTENCY: ALWAYS use the same browser/apps mentioned in the feedback or the original successful steps.
- 🚫 BROWSER SEARCH: NEVER use `command+f` in a browser.
- 🎯 CONTEXTUAL CLICKING: NEVER use `click_text` for search results. ALWAYS use `click_near(target="...", anchor="...")`.
- 🏗️ LINEARITY: Output a clean, linear list of actions.
- 🌐 NAVIGATION: Use `navigate(url="...")` for all website navigation.
- 💎 DATA EXTRACTION: Use `extract_info(description="...")`.
- 💎 DYNAMIC DATA: Use "$LAST_READ" for typed data.
- Output ONLY a JSON list.
"""
        print("   🧠 [Stage 5] Generating surgical fix...")
        result = groq_brain.get_action_plan(prompt, model_id=self.model)
        return toolbox_logger.save_stage_file("5_surgical_fix.json", result)

    # --- STAGE 6: GENERALIZATION ---
    def stage_6_generalize(self, user_goal, successful_trace):
        """Cleans up and parameterizes the successful plan for SQL."""
        if not successful_trace:
            print("   ⚠️  Stage 6 Skipped: No successful steps to learn from.")
            return None

        prompt = f"""### User Goal: "{user_goal}"
### Successful Trace: {json.dumps(successful_trace)}

YOUR TASK:
1. Remove all specific names (like 'Nvidia', 'Brave', 'https://...') that can be replaced by variables.
2. Create a generalized Tool definition.
3. Replace names with placeholders like `{{query}}`, `{{browser}}`, `{{url}}`.
4. ⛔ STABILITY: Remove any "Trial and Error" steps. Only keep the final successful sequence.
5. ⛔ CLEANLINESS: Ensure the 'body' actions contain NO commentary or extra text. 

Output JSON Format:
{{
  "name": "generalized_name",
  "description": "...",
  "parameters": ["query", "url"],
  "body": [...]
}}
"""
        print("   🧠 [Stage 6] Generalizing tool for SQL storage...")
        result = groq_brain.get_action_plan(prompt, model_id=self.model)
        
        if result and isinstance(result, dict) and "name" in result:
            print(f"   ✨ Stage 6 Success: Generalizing as tool '{result['name']}'")
            self.db.save_tool(result["name"], result["description"], result.get("parameters", []), result["body"])
        else:
            print(f"   ❌ Stage 6 Failure: Model returned invalid generalization format: {result}")
            
        return toolbox_logger.save_stage_file("6_generalized_tool.json", result)

if __name__ == "__main__":
    # Test sequence
    c = AgentCompiler()
    goal = "search Nvidia stock price on google and save the prices in notes"
    c.stage_1_main_breakdown(goal)
    c.stage_2_keywords(goal)
    c.stage_3_available_tools()
    c.stage_4_final_execution(goal)
