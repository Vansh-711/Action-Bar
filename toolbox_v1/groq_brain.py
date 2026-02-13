import os
import json
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
MODEL_ID = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

if not API_KEY or API_KEY.startswith("gsk_replace"):
    raise ValueError("❌ ERROR: You must set your GROQ_API_KEY in the .env file!")

client = Groq(api_key=API_KEY)

SYSTEM_PROMPT = """You are a Desktop Automation Architect.
Your job is to provide a COMPLETE, end-to-end JSON execution plan.

AVAILABLE ACTIONS:
- open_app(name): Open apps, URLs, or file paths (e.g. "C:\\\\Downloads\\\\setup.exe").
- click_text(text): Click buttons/labels.
- type_text(text): Input text.
- press_key(key): e.g. "enter", "ctrl+l", "pagedown".
- wait(seconds): Use for loading screens.
- read_screen(): Scans view. REQUIRED before using if_condition.
- loop(count, actions): Use large counts (e.g. 1000) for finding empty rows/data.
- if_condition(condition, true_actions): Logic based on read_screen().

RULES:
1. COMPLETE TASKS: If installing software, you MUST include: Browser -> Download -> Open Installer -> Click Next/Finish -> Verify App Opens. Do NOT stop at the download.
2. JSON SAFETY: ALWAYS escape backslashes in paths using double backslashes (\\\\).
4. ROBUSTNESS: Use wait(5) after opening apps and wait(2) between clicks.
5. OS CONTEXT: Check the 'OS:' prefix. Use 'command' for Mac, 'ctrl' for Windows.
6. APP NAMES: Always use simple names for open_app (e.g., "Brave", "Spotify", "Chrome"). Do NOT use full file paths like "/Applications/..." or "C:\\\\...".
7. SYSTEM SETTINGS: For Volume/Brightness on Mac, use 'press_key' with 'volumeup', 'volumedown', 'brightnessup'.
8. Output ONLY valid JSON.
"""

import sys

def get_action_plan(user_prompt, model_id=None):
    # Allow overriding the model (e.g. use Small model for fast checks)
    target_model = model_id if model_id else MODEL_ID
    
    platform_name = "macOS" if sys.platform == "darwin" else "Windows"
    print(f"🧠 Sending to Groq ({target_model}) | OS: {platform_name}...")
    
    full_user_prompt = f"OS: {platform_name}\nUser Goal: {user_prompt}"
    
    # Only use JSON mode for Llama models
    params = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": full_user_prompt}
        ],
        "temperature": 0.0,
        "stream": False
    }
    
    # Llama models support this flag explicitly
    if "llama" in target_model.lower():
        params["response_format"] = {"type": "json_object"}

    try:
        completion = client.chat.completions.create(**params)
        
        response_text = completion.choices[0].message.content
        print(f"🔍 DEBUG RAW RESPONSE:\n{response_text}\n" + "-"*20) # DEBUG LINE
        
        # Clean up <think> tags (Reasoning models)
        if "<think>" in response_text:
            response_text = response_text.split("</think>")[-1].strip()

        # Clean up potential markdown wrappers (```json ... ```)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        return json.loads(response_text)

    except Exception as e:
        print(f"❌ Groq API Error: {e}")
        return None

if __name__ == "__main__":
    test_prompt = input("🔍 Enter a test goal (e.g. 'Install VS Code'): ")
    plan = get_action_plan(test_prompt)
    if plan:
        print("\n🚀 GENERATED PLAN:")
        print(json.dumps(plan, indent=2))
    else:
        print("❌ Failed to generate plan.")
