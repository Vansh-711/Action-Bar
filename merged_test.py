from mlx_lm import load, generate
import json
import re
import os
from pathlib import Path

# --- PATH TO YOUR MERGED MODEL (4-BIT) ---
MODEL_PATH = "main_brain_model/trained_2/agent_brain_v1_4bit"

def test_merged_brain():
    print(f"🧠 Loading Quantized Brain from: {MODEL_PATH}...")
    
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Error: Model folder not found!")
        return

    model, tokenizer = load(MODEL_PATH)
    print("✅ Fast Brain loaded. Ready to plan.")
    
    user_goal = "I want to install vs code in my computer"
    
    # SYSTEM PROMPT V2: The "Micro-Manager"
    system_msg = """You are an expert desktop automation architect. 
Your goal is to generate a comprehensive, fail-safe execution plan.

GUIDELINES:
1. Do NOT skip steps. Assume the user has nothing open.
2. Validate actions (e.g., "read_screen" to check if the site loaded).
3. Handle file operations explicitly (e.g., "open_app Finder", "type_text Downloads", "press_key enter" to find the file).
4. If downloading, assume it's a zip and include steps to unzip/install.
5. Output reasoning in 'Thought:' then strict JSON steps.
6. To install new software, ALWAYS start by opening 'Google Chrome' or 'Safari'. Do not assume the app exists.

TOOLS:
- open_app(name)
- click_text(text)
- type_text(text)
- press_key(key)
- read_screen()
- wait(seconds)
- loop(count, actions)
- if_condition(condition, true_actions)
"""
    
    prompt = f"""<|im_start|>system
{system_msg}<|im_end|>
<|im_start|>user
{user_goal}<|im_end|>
<|im_start|>assistant
"""

    print(f"\n--- 🤖 Planning: {user_goal} ---")
    
    # Increase max tokens for long plans
    response = generate(
        model, 
        tokenizer, 
        prompt=prompt, 
        max_tokens=800, 
        verbose=True
    )
    
    print("\n\n--- 🏁 Verification ---")
    
    # CUT OFF after the first JSON block end
    if "```json" in response:
        parts = response.split("```json")
        if len(parts) > 1:
            clean_json = parts[1].split("```")[0].strip()
            print("🚀 SUCCESS! Extracted Clean JSON:")
            # print(clean_json) # Optional: Print raw JSON
            
            try:
                plan = json.loads(clean_json)
                print(f"✅ Parsed into {len(plan)} steps.")
            except:
                print("⚠️ JSON Syntax Error")
    else:
        print("⚠️ Model ignored the pattern.")

if __name__ == "__main__":
    test_merged_brain()