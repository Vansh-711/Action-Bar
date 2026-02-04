import time
import pyautogui
import groq_brain
import json
import sys
import pytesseract
from PIL import Image
import client_app  # Import the dispatcher logic we already built

# Safety fail-safe
pyautogui.FAILSAFE = True

def verify_success(user_goal):
    """
    Takes a screenshot and asks Groq if the goal appears to be met.
    """
    print("\n🕵️ Verifying success...")
    
    # 1. Read the screen
    screen_text = client_app.handle_read_screen()
    # Truncate to avoid token limits (keep last 4000 chars - usually relevant info is at bottom/center)
    screen_context = screen_text[-4000:]
    
    # 2. Ask the Brain
    verification_prompt = f"""
    I executed a plan for the User Goal: "{user_goal}".
    
    Here is the text I currently see on the screen (OCR scan):
    ---
    {screen_context}
    ---
    
    Based ONLY on this text, has the goal likely been achieved?
    For example:
    - If goal is "Open Spotify" and you see "Home", "Library", "Spotify", answer YES.
    - If goal is "Install VS Code" and you see "Installation Complete" or "Visual Studio Code", answer YES.
    - If you see "Error", "Not Found", or the screen looks unchanged, answer NO.
    
    OUTPUT FORMAT:
    Return valid JSON:
    {{
      "success": true/false,
      "reason": "Why you think so",
      "fix_suggestion": "If false, what should I try next? (e.g. 'Use Spotlight instead of Dock', 'Wait longer')"
    }}
    """
    
    print("   🧠 Asking Judge (Groq)...")
    try:
        response = groq_brain.get_action_plan(verification_prompt) # Reuse our robust JSON fetcher
        return response
    except Exception as e:
        print(f"   ❌ Verification failed: {e}")
        return {"success": True, "reason": "Judge crashed, assuming success."}

def main_loop():
    print("🤖 Groq Self-Healing Agent (v2)")
    print("-------------------------------")
    
    context = {"screen_data": ""}
    
    while True:
        user_input = input("\n📝 What should I do? (or 'q' to quit): ").strip()
        if user_input.lower() == 'q': break
        
        # --- ATTEMPT 1 ---
        print("\n🚀 ATTEMPT 1: Generating Plan...")
        plan_data = groq_brain.get_action_plan(user_input)
        
        if not plan_data:
            print("❌ Failed to generate initial plan.")
            continue
            
        steps = plan_data if isinstance(plan_data, list) else plan_data.get("plan", [])
        print(json.dumps(steps, indent=2))
        
        if input("\n▶️ Execute Attempt 1? (y/n): ").lower() != 'y':
            continue
            
        client_app.run_plan_loop(steps, context)
        
        # --- VERIFICATION & HEALING ---
        # Wait a moment for UI to settle
        time.sleep(2)
        
        result = verify_success(user_input)
        
        if result.get("success"):
            print(f"\n✅ SUCCESS CONFIRMED: {result.get('reason')}")
        else:
            print(f"\n⚠️ TASK FAILED: {result.get('reason')}")
            print(f"   💡 Fix Suggestion: {result.get('fix_suggestion')}")
            
            if input("\n🚑 Attempt Self-Healing (Retry)? (y/n): ").lower() == 'y':
                
                # --- ATTEMPT 2 (Healing) ---
                fix_prompt = f"""
                Previous plan FAILED.
                Goal: {user_input}
                Reason for failure: {result.get('reason')}
                Suggestion: {result.get('fix_suggestion')}
                
                Generate a NEW, ROBUST plan to fix this. Use fallback methods (e.g. if Dock failed, use Spotlight).
                """
                
                print("\n🚑 Generating Fix Plan...")
                fix_plan_data = groq_brain.get_action_plan(fix_prompt)
                
                if fix_plan_data:
                    fix_steps = fix_plan_data if isinstance(fix_plan_data, list) else fix_plan_data.get("plan", [])
                    print(json.dumps(fix_steps, indent=2))
                    
                    if input("▶️ Execute Fix? (y/n): ").lower() == 'y':
                        client_app.run_plan_loop(fix_steps, context)
                else:
                    print("❌ Failed to generate fix plan.")

if __name__ == "__main__":
    main_loop()
