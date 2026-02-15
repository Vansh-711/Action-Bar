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
    Manages 1.json through 6.json.
    """
    def __init__(self):
        self.db = toolbox_db.ToolboxDB()
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

    def _save_json(self, filename, data):
        path = os.path.join(STORAGE_DIR, filename)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        return data

    def _read_json(self, filename):
        path = os.path.join(STORAGE_DIR, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return None

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
        return self._save_json("1_main_breakdown.json", result)

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
        return self._save_json("2_semantic_search.json", result)

    # --- STAGE 3: TOOL RETRIEVAL (Python Logic) ---
    def stage_3_available_tools(self):
        """Queries the database using keywords from Stage 2."""
        keywords_list = self._read_json("2_semantic_search.json")
        if not keywords_list: return []

        print("   🧠 [Stage 3] Querying SQL Database for relevant tools...")
        # We join keywords into a string for our existing find_relevant_tools logic
        query_str = " ".join(keywords_list)
        matches = self.db.find_relevant_tools(query_str)
        
        # Also fetch bodies for these tools to make the next stage smarter
        detailed_tools = []
        for t in matches:
            t["body"] = self.db.get_tool_body(t["name"])
            detailed_tools.append(t)

        return self._save_json("3_available_tools.json", detailed_tools)

    # --- STAGE 4: COMPOSITION ---
    def stage_4_final_execution(self, user_goal):
        """Composes and EXPANDS the final plan."""
        breakdown = self._read_json("1_main_breakdown.json")
        tools = self._read_json("3_available_tools.json")
        system_context = system_monitor.get_system_context_string()

        prompt = f"""USER GOAL: "{user_goal}"
TASK BREAKDOWN: {json.dumps(breakdown)}
AVAILABLE TOOLS: {json.dumps(tools)}
{system_context}

YOUR TASK:
Using the available tools and breakdown, create a final execution plan.
- If a tool fits a step, use `call_tool("name", params={{...}})`.
- If no tool fits, write the raw primitive steps (open_app, type_text, click_text, press_key, wait).
- 💎 DATA EXTRACTION: If you need to retrieve a specific value from the screen (e.g. a price), use `extract_info(description="the price of Nvidia")`. This is superior to `read_screen`.
- 💎 DYNAMIC DATA: If you need to type information that was read/extracted from the screen, use the special variable "$LAST_READ".
- Example: 
  1. `{{"action": "extract_info", "description": "the stock price"}}`
  2. `{{"action": "type_text", "text": "The price is $LAST_READ"}}`
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
        
        return self._save_json("4_final_execution.json", expanded_plan)

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
                tool_name = step.get("name")
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
        full_plan = self._read_json("4_final_execution.json")
        tools = self._read_json("3_available_tools.json")
        
        prompt = f"""### 🎯 MAIN GOAL: "{user_goal}"
### 📋 PREVIOUS PLAN: {json.dumps(full_plan)}
### 🟢 COMPLETED STEPS: {json.dumps(steps_done)}
### 🔴 ERROR FACED: "{feedback}"
### 🧰 AVAILABLE TOOLS: {json.dumps(tools)}

YOUR TASK:
Refer to the original plan and the error. What should be done to make the execution successful?
- 🏗️ LINEARITY: Output a clean, linear list of actions. Avoid `if_condition` or nesting if possible.
- 💎 DATA EXTRACTION: If you need to retrieve a specific value from the screen (e.g. a price), use `extract_info(description="the price of Nvidia")`. This is superior to `read_screen`.
- 💎 DYNAMIC DATA: If you need to type information read from the screen, use "$LAST_READ".
- ⛔ NO CUSTOM VARIABLES: Do NOT use `{{extracted_price}}`, `{{value}}`, or any other placeholders. 
- Output ONLY a JSON list.
"""
        print("   🧠 [Stage 5] Generating surgical fix...")
        result = groq_brain.get_action_plan(prompt, model_id=self.model)
        return self._save_json("5_surgical_fix.json", result)

    # --- STAGE 6: GENERALIZATION ---
    def stage_6_generalize(self, user_goal, successful_trace):
        """Cleans up and parameterizes the successful plan for SQL."""
        prompt = f"""### User Goal: "{user_goal}"
### Successful Trace: {json.dumps(successful_trace)}

YOUR TASK:
1. Remove all specific names (like 'Nvidia', 'Brave', 'https://...') that can be replaced by variables.
2. Create a generalized Tool definition.
3. Replace names with placeholders like `{{query}}`, `{{browser}}`, `{{url}}`.
4. ⛔ STABILITY: Remove any "Trial and Error" steps. Only keep the final successful sequence.
5. ⛔ CLEANLINESS: Ensure the 'body' actions contain NO commentary or extra text like "expected price". 

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
        
        if result and "name" in result:
            self.db.save_tool(result["name"], result["description"], result.get("parameters", []), result["body"])
            
        return self._save_json("6_generalized_tool.json", result)

if __name__ == "__main__":
    # Test sequence
    c = AgentCompiler()
    goal = "search Nvidia stock price on google and save the prices in notes"
    c.stage_1_main_breakdown(goal)
    c.stage_2_keywords(goal)
    c.stage_3_available_tools()
    c.stage_4_final_execution(goal)
