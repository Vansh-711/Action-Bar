import time
import json
import os
import difflib
import client_app
import groq_brain
import sys
from dotenv import load_dotenv

# Try importing Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

load_dotenv()

MEMORY_FILE = "agent_memory.json"

class KnowledgeBase:
    def __init__(self):
        self.use_cloud = False
        self.supabase = None
        
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        
        if SUPABASE_AVAILABLE and url and key:
            try:
                self.supabase = create_client(url, key)
                self.use_cloud = True
            except Exception:
                pass
        
        if not self.use_cloud:
            self.local_data = self._load_local()

    def _load_local(self):
        if not os.path.exists(MEMORY_FILE): return []
        try:
            with open(MEMORY_FILE, 'r') as f: return json.load(f)
        except: return []

    def _save_local(self):
        with open(MEMORY_FILE, 'w') as f: json.dump(self.local_data, f, indent=2)

    def add_skill(self, user_goal, plan, tips):
        entry = {"goal": user_goal, "plan": plan, "tips": tips, "timestamp": time.time()}
        if self.use_cloud:
            try: self.supabase.table("skills").insert(entry).execute()
            except: pass
        else:
            self.local_data.append(entry)
            self._save_local()

    def retrieve_context(self, current_goal):
        best_match = None
        if self.use_cloud:
            try: data = self.supabase.table("skills").select("*").execute().data
            except: data = []
        else: data = self.local_data

        highest_score = 0.0
        for entry in data:
            score = difflib.SequenceMatcher(None, current_goal.lower(), entry["goal"].lower()).ratio()
            if score > 0.5 and score > highest_score:
                highest_score = score
                best_match = entry
        return best_match

KB = KnowledgeBase()

class UniversalAgent:
    def __init__(self):
        self.os_platform = "macOS" if "darwin" in sys.platform else "Windows"
        
    def plan_task(self, user_goal, feedback_history="", previous_steps_done=None):
        """Generates a plan. If feedback exists, it's a correction."""
        
        # 1. RAG Retrieval
        memory_context = "No prior knowledge."
        if not feedback_history: 
            past_experience = KB.retrieve_context(user_goal)
            if past_experience:
                memory_context = f"Similar Task: '{past_experience['goal']}'\nTip: {json.dumps(past_experience['plan'][0:2])}..."

        # 2. Construct Prompt
        continuation_instruction = ""
        if previous_steps_done:
            continuation_instruction = f"""
### 🟢 STATUS: PARTIAL SUCCESS
The following steps have ALREADY been executed successfully. DO NOT include them in your plan.
{json.dumps(previous_steps_done, indent=2)}

### 🔴 CURRENT ISSUE
The next step FAILED.
Feedback: {feedback_history}

### ⚡ YOUR TASK
Generate the REST of the plan, starting with a FIXED version of the failed step, followed by the remaining steps to achieve the goal.
"""

        UNIVERSAL_PROMPT = f"""You are the Groq Universal Desktop Agent.
Your goal is to execute the user's request on {self.os_platform}.

### 🧠 MEMORY
{memory_context}

### ❌ FEEDBACK / ISSUES
{feedback_history}

{continuation_instruction}

### 🛠️ TOOL GUIDELINES
1. **open_app**: 
   - INTELLIGENT LAUNCHER.
   - Use this for ALL app launches.
   - ⛔ NEVER simulate "Cmd+Space" manually. The 'open_app' tool handles the Spotlight sequence atomically (Open -> Type -> Enter) so focus isn't lost.
   - Example: `{"action": "open_app", "name": "Brave"}` (CORRECT) vs `[{"key": "cmd+space"}, {"type": "Brave"}]` (WRONG).
2. **Web Browsers**: 


### 🎯 USER GOAL
"{user_goal}"

Output a JSON plan.
"""
        return groq_brain.get_action_plan(UNIVERSAL_PROMPT, model_id=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))

    def execute_step(self, step):
        """Executes a single step."""
        action = step.get("action") or step.get("tool") or list(step.keys())[0]
        params = step.get("params") or step.get("args") or step
        
        if action == "open_app" and isinstance(params, str):
            params = {"name": params}

        if action:
            client_app.execute_step(action, params, context={})
            return True
        return False
        
    def summarize_and_save(self, goal, final_plan):
        """Asks AI to flatten and clean up the plan for SQL."""
        print("   🧠 Finalizing skill for Cloud Memory...")
        
        summary_prompt = f"""
        User Goal: {goal}
        Raw Execution Log: {json.dumps(final_plan)}
        
        Your Job: Create a CLEAN, LINEAR "Golden Path" for this task.
        1. Remove any 'if_condition', 'read_screen', or failed attempts.
        2. Remove redundant waits.
        3. Flatten the structure (just a list of simple actions).
        4. Ensure it reads like a tutorial: "open_app" -> "click" -> "type".
        
        Output ONLY the JSON list.
        """
        
        clean_plan = groq_brain.get_action_plan(summary_prompt, model_id=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
        
        steps = []
        if clean_plan:
            steps = clean_plan if isinstance(clean_plan, list) else clean_plan.get("plan") or clean_plan.get("actions") or []
        
        if steps:
            KB.add_skill(goal, steps, "Optimized Linear Plan")
        else:
            KB.add_skill(goal, final_plan, "Raw Plan")
