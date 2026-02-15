import time
import pyautogui
import os
import subprocess
import sys
import pytesseract
from PIL import Image
import groq_brain

# Safety
pyautogui.FAILSAFE = True

# --- POWER PRIMITIVES (V1.2) ---

def power_launch(app_name):
    """
    Robust app launcher. Checks focus first, then uses Spotlight.
    """
    print(f"   🚀 [POWER] Attempting to launch/focus: {app_name}")
    
    # 1. Check if already focused
    if sys.platform == "darwin":
        try:
            frontmost = subprocess.check_output(["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true']).decode().strip()
            if app_name.lower() in frontmost.lower():
                print(f"   ✨ '{app_name}' is already frontmost. Skipping launch.")
                return True
        except: pass

    # 2. Spotlight Launch
    print(f"   ⌨️  Using Spotlight for {app_name}...")
    pyautogui.keyDown('command')
    time.sleep(0.2)
    pyautogui.press('space')
    time.sleep(0.2)
    pyautogui.keyUp('command')
    
    time.sleep(0.5)
    pyautogui.write(app_name, interval=0.05)
    time.sleep(0.5)
    pyautogui.press('enter')
    
    # Wait for app to appear
    time.sleep(3.0)
    return True

def power_navigate(url):
    """
    Robust browser navigation. Handles Cmd+L and URL typing.
    """
    print(f"   🌐 [POWER] Navigating to: {url}")
    # Focus address bar
    pyautogui.keyDown('command')
    time.sleep(0.1)
    pyautogui.press('l')
    time.sleep(0.1)
    pyautogui.keyUp('command')
    
    time.sleep(0.5)
    pyautogui.write(url, interval=0.02)
    time.sleep(0.5)
    pyautogui.press('enter')
    return True

# --- BASE EXECUTION DISPATCHER ---

def execute_step(action, params, context=None):
    """
    The 'Hands' of the agent. Converts JSON into system actions.
    """
    # 0. Focus Protection: If we are about to type/press, ensure HUD isn't stealing focus
    if action in ["type_text", "press_key"]:
        if sys.platform == "darwin":
            try:
                frontmost = subprocess.check_output(["osascript", "-e", 'tell application "System Events" to get name of first process whose frontmost is true']).decode().strip()
                if "python" in frontmost.lower() or "hud" in frontmost.lower():
                    # HUD is focused! Switch back.
                    pyautogui.keyDown('command')
                    pyautogui.press('tab')
                    pyautogui.keyUp('command')
                    time.sleep(0.5)
            except: pass

    # 1. Variable Resolution
    if action == "type_text" and context and "last_read" in context:
        text = params.get("text", "")
        # Replace $LAST_READ or ANY {{placeholder}}
        import re
        resolved_text = text.replace("$LAST_READ", context["last_read"])
        resolved_text = re.sub(r"\{\{.*?\}\}", context["last_read"], resolved_text)
        params["text"] = resolved_text

    # 1. Normalize params
    if not isinstance(params, dict):
        # Handle string params
        if action == "open_app": params = {"name": params}
        elif action == "type_text": params = {"text": params}
        elif action == "click_text": params = {"text": params}
        elif action == "press_key": params = {"key": params}
        elif action == "wait": params = {"seconds": params}
        else: params = {}

    try:
        if action == "open_app":
            app_name = params.get("name")
            return power_launch(app_name)

        elif action == "type_text":
            text = params.get("text")
            print(f"   ⌨️  Typing: {text}")
            pyautogui.write(text, interval=0.05)
            return True

        elif action == "click_text":
            text = params.get("text")
            print(f"   🖱️  Clicking: {text}")
            # Try accessibility first if available
            try:
                import screen_search
                scanner = screen_search.ScreenScanner()
                if scanner.find_and_click(text):
                    return True
            except: pass
            
            # Try OCR fallback
            try:
                import visual_search
                if visual_search.visual_find_and_click(text):
                    return True
            except: pass
            
            print(f"   ❌ Failed to find text: {text}")
            return False

        elif action == "press_key":
            key = params.get("key", "").lower()
            print(f"   🎹 Pressing: {key}")
            
            # Map common names
            if key == "cmd": key = "command"
            
            if "+" in key:
                mods = key.split("+")
                for m in mods[:-1]: 
                    if m == "cmd": m = "command"
                    pyautogui.keyDown(m)
                time.sleep(0.1)
                pyautogui.press(mods[-1])
                time.sleep(0.1)
                for m in reversed(mods[:-1]):
                    if m == "cmd": m = "command"
                    pyautogui.keyUp(m)
            else:
                pyautogui.press(key)
            return True

        elif action == "wait":
            sec = float(params.get("seconds", 1))
            print(f"   ⏳ Waiting {sec}s...")
            time.sleep(sec)
            return True

        elif action == "read_screen":
            print("   👀 Reading screen...")
            screenshot = pyautogui.screenshot()
            text = pytesseract.image_to_string(screenshot)
            clean_text = " ".join(text.split()).lower()
            if context is not None:
                context["last_read"] = clean_text
            return True

        elif action == "extract_info":
            description = params.get("description", "the main value")
            print(f"   🧠 [POWER] Extracting: {description} (using 120B model)...")
            
            # 1. Get raw text
            screenshot = pyautogui.screenshot()
            raw_text = pytesseract.image_to_string(screenshot)
            
            # 2. Ask precision AI to filter
            filter_prompt = f"""
            RAW OCR TEXT:
            ---
            {raw_text}
            ---
            
            TASK: Extract {description} from the text above.
            RULES:
            - Output ONLY the value (e.g. "96,432.10" or "45°F").
            - DO NOT output sentences, labels, or extra words.
            - If not found, output "Not Found".
            """
            # Use get_raw_text for simple string extraction
            val_str = groq_brain.get_raw_text(filter_prompt, model_id="openai/gpt-oss-120b")
            
            print(f"   ✨ Extracted Value: {val_str}")
            if context is not None:
                context["last_read"] = val_str
            return True

        elif action == "if_condition":
            condition = params.get("condition", "").lower()
            print(f"   🤔 Evaluating: '{condition}'")
            last_read = context.get("last_read", "") if context else ""
            
            # Simple heuristic: is the text present?
            if condition in last_read or "true" in condition:
                print("   ✅ Condition Met. Running sub-actions...")
                true_actions = params.get("true_actions", [])
                for sub_step in true_actions:
                    execute_step(sub_step.get("action"), sub_step, context)
            else:
                print("   ⏩ Condition Not Met. Skipping.")
            return True

        elif action == "loop":
            count = int(params.get("count", 1))
            actions = params.get("actions", [])
            print(f"   🔁 Looping {count} times...")
            for _ in range(count):
                for sub_step in actions:
                    execute_step(sub_step.get("action"), sub_step, context)
            return True

        print(f"   ⚠️  Unknown action: {action}")
        return False

    except Exception as e:
        print(f"   ❌ Execution Error: {e}")
        return False
