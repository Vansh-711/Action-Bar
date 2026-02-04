import time
import pyautogui
import groq_brain
import json
import sys
import pytesseract
from PIL import Image

# Import "Hands"
try:
    import screen_search
    import visual_search
    scanner = screen_search.ScreenScanner()
    print("✅ Hands Loaded: Accessibility Scanner & Visual OCR ready.")
except ImportError as e:
    print(f"⚠️ Warning: Could not load search modules: {e}")
    scanner = None

pyautogui.FAILSAFE = True

# --- ACTION HANDLERS ---

def handle_open_app(name):
    """Opens an app using Dock scan first, then OS-specific search."""
    # Clean up path if model provided one (e.g. /Apps/Brave.app -> Brave)
    if "/" in name or "\\" in name:
        name = os.path.basename(name).replace(".app", "").replace(".exe", "")

    print(f"   📂 Opening App: '{name}'")
    
    # 1. Try Dock/Screen Scan (Reliable for running apps)
    if scanner and scanner.find_and_click(name):
        print(f"   ✅ Found '{name}' in Dock/Screen.")
        return True

    # 2. OS-Specific Search Fallback
    if sys.platform == "darwin":
        print(f"   ⌨️ [Mac] Using Spotlight to launch '{name}'...")
        pyautogui.hotkey('command', 'space')
    else:
        print(f"   ⌨️ [Windows] Using Start Menu to launch '{name}'...")
        pyautogui.press('win')
        
    time.sleep(0.5)
    pyautogui.write(name, interval=0.05)
    time.sleep(0.5)
    pyautogui.press('enter')
    return True

def handle_click_text(text):
    """Clicks text using Accessibility Tree first, then OCR."""
    print(f"   🖱️ Clicking Text: '{text}'")
    
    # 1. Accessibility Tree (Fast, precise)
    if scanner and scanner.find_and_click(text):
        print("   ✅ Clicked via Accessibility Tree.")
        return True
        
    # 2. Visual OCR (Slow, sees pixels)
    print("   👁️ Accessibility failed. Scanning pixels (OCR)...")
    if visual_search.visual_find_and_click(text):
        print("   ✅ Clicked via OCR.")
        return True
        
    print(f"   ❌ Failed to find '{text}'.")
    return False

def handle_type_text(text):
    print(f"   ⌨️ Typing: '{text}'")
    pyautogui.write(text, interval=0.05)
    return True

def handle_press_key(key):
    # Normalize common model typos
    key_map = {
        "volumemup": "volumeup",
        "volumedown": "volumedown", # Already correct
        "enter": "enter",
        "return": "enter",
        "ctrl": "command" if sys.platform == "darwin" else "ctrl" # Auto-fix ctrl on Mac
    }
    
    key = key.lower()
    if key in key_map:
        key = key_map[key]

    print(f"   🎹 Pressing: '{key}'")
    
    if "+" in key:
        modifiers = key.split("+")
        pyautogui.hotkey(*modifiers)
    else:
        if key not in pyautogui.KEY_NAMES:
             print(f"   ⚠️ WARNING: '{key}' might not be a valid PyAutoGUI key.")
        pyautogui.press(key)
    return True

def handle_read_screen():
    """Reads screen for logic checks."""
    print("   👀 Reading screen (OCR)...")
    screenshot = pyautogui.screenshot()
    text = pytesseract.image_to_string(screenshot)
    clean_text = " ".join(text.split()).lower()
    return clean_text

# --- MAIN DISPATCHER ---

def execute_step(action, params, context):
    """
    Routes a single step to the correct handler.
    'context' is a dict used to store state (like read_screen results).
    """
    if action == "open_app":
        return handle_open_app(params.get("name"))
        
    elif action == "click_text":
        return handle_click_text(params.get("text"))
        
    elif action == "type_text":
        return handle_type_text(params.get("text"))
        
    elif action == "press_key":
        # Handle list args: ["enter"]
        if isinstance(params, list) and len(params) > 0:
            key = params[0]
        else:
            key = params.get("key")
        return handle_press_key(key)
        
    elif action == "wait":
        # Handle list args: [5]
        if isinstance(params, list) and len(params) > 0:
            sec = int(params[0])
        else:
            sec = int(params.get("seconds", 1))
        print(f"   ⏳ Waiting {sec}s...")
        time.sleep(sec)
        return True
        
    elif action == "read_screen":
        context["screen_data"] = handle_read_screen()
        return True
        
    elif action == "if_condition":
        # ... existing logic ...
        condition = params.get("condition", "").lower()
        # ...
        return True
        
    elif action == "loop":
        # Handle list args: [30, [...]]
        if isinstance(params, list) and len(params) >= 2:
            count = int(params[0])
            sub_plan = params[1]
        else:
            count = int(params.get("count", 1))
            sub_plan = params.get("actions", [])
            
        print(f"   🔁 Looping {count} times...")
        for _ in range(count):
            run_plan_loop(sub_plan, context) # Recursion
        return True

    print(f"   ⚠️ Unknown Action: {action}")
    return False

def run_plan_loop(steps, context):
    """Iterates through a list of steps."""
    
    # Handle wrapped "actions" list (e.g. {"actions": [...]})
    if isinstance(steps, dict) and "actions" in steps:
        steps = steps["actions"]
    
    if not isinstance(steps, list):
        print(f"❌ Invalid plan format: {type(steps)}")
        return

    for i, step in enumerate(steps):
        # 1. Normalize "Lazy JSON" (e.g. {"press_key": "enter"})
        action = None
        params = {}
        
        # Check if the keys themselves are actions
        known_actions = ["open_app", "click_text", "type_text", "press_key", "wait", "read_screen", "loop", "if_condition"]
        
        for k, v in step.items():
            if k in known_actions:
                action = k
                # If value is simple (str/int), map it to the default param
                if isinstance(v, (str, int, float)):
                    if k == "open_app": params = {"name": v}
                    elif k == "click_text": params = {"text": v}
                    elif k == "type_text": params = {"text": v}
                    elif k == "press_key": params = {"key": v}
                    elif k == "wait": params = {"seconds": v}
                elif isinstance(v, dict):
                    params = v
                elif isinstance(v, list): # Handle loop/if args
                    params = v 
                break
        
        # Fallback to standard format
        if not action:
            action = step.get("action") or step.get("tool")
            # CRITICAL FIX: Map 'parameters' to 'params'
            params = step.get("params") or step.get("args") or step.get("parameters") or step
            
        if params is None:
            params = {}
            
        print(f"👉 Step {i+1}: {action}")
        execute_step(action, params, context)
        time.sleep(0.5)

def main():
    print("🤖 Groq Desktop Agent (Cloud Brain)")
    print("-----------------------------------")
    
    context = {"screen_data": ""}
    
    while True:
        user_input = input("\n📝 What should I do? (or 'q' to quit): ").strip()
        if user_input.lower() == 'q': break
            
        print("🤔 Thinking...")
        plan_data = groq_brain.get_action_plan(user_input)
        
        if plan_data:
            # Handle List vs Dict response (plan/actions)
            if isinstance(plan_data, list):
                steps = plan_data
            else:
                steps = plan_data.get("plan") or plan_data.get("actions") or []
            
            print(json.dumps(steps, indent=2))
            if input("\n▶️ Execute? (y/n): ").lower() == 'y':
                run_plan_loop(steps, context)
        else:
            print("❌ Brain failed to generate a plan.")

if __name__ == "__main__":
    main()