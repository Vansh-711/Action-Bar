from mlx_lm import load, generate
import json
import re
import time
import os
import pyautogui

# Import our custom modules
from screen_search import ScreenScanner
from visual_search import visual_find_and_click

# CONFIGURATION
MODEL_PATH = "main_brain_model/trained_2/agent_brain_v1"

class DesktopAgent:
    def __init__(self):
        print("🧠 Loading the Trained Brain...")
        self.model, self.tokenizer = load(MODEL_PATH)
        self.scanner = ScreenScanner()
        print("✅ Agent is ONLINE.")

    def get_plan(self, user_goal):
        system_msg = "You are a desktop automation agent. Output reasoning in 'Thought:' then strict JSON steps."
        prompt = f"<|im_start|>system
{system_msg}<|im_end|>
<|im_start|>user
{user_goal}<|im_end|>
<|im_start|>assistant
"
        response = generate(self.model, self.tokenizer, prompt=prompt, max_tokens=500, temp=0.0)
        
        # Parse JSON from response
        try:
            match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            return None
        except:
            return None

    def execute_step(self, step):
        tool = step.get("tool")
        args = step.get("args")
        
        print(f"\n🚀 Executing: {tool}({args})")
        
        if tool == "open_app":
            # Command + Space -> Type Name -> Enter
            pyautogui.hotkey('command', 'space')
            time.sleep(0.5)
            pyautogui.write(args)
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(2) # Wait for app to open
            
        elif tool == "click_text":
            # Try Accessibility first
            success = self.scanner.find_and_click(args)
            if not success:
                # Fallback to Visual OCR
                print(f"⚠️ Native search failed. Trying Visual OCR for '{args}'...")
                success = visual_find_and_click(args)
            return success

        elif tool == "type_text":
            pyautogui.write(args)
            
        elif tool == "press_key":
            pyautogui.press(args)
            
        elif tool == "wait":
            time.sleep(float(args))
            
        return True

    def run(self, user_goal):
        print(f"\n--- 📝 Goal: {user_goal} ---")
        plan = self.get_plan(user_goal)
        
        if not plan:
            print("❌ Brain failed to generate a valid plan.")
            return

        print(f"Plan received ({len(plan)} steps). Starting execution...")
        
        for step in plan:
            success = self.execute_step(step)
            if not success:
                print(f"❌ Failed to execute step: {step}")
                # We could add an AI 'Re-plan' logic here
                break
            time.sleep(1) # Gap between steps

if __name__ == "__main__":
    agent = DesktopAgent()
    
    while True:
        goal = input("\n🤖 Enter your command (or 'exit'): ")
        if goal.lower() == 'exit':
            break
        agent.run(goal)
