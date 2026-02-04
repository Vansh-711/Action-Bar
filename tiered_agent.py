import time
import json
import client_app
import groq_brain

# CONFIGURATION
ARCHITECT_MODEL = "openai/gpt-oss-120b"
SCOUT_MODEL = "llama-3.1-8b-instant"

SCOUT_PROMPT = """You are a High-Speed Execution Scout.
Your job is to check the screen state and execute the next step from the Master Plan.

CURRENT STEP: {current_step}
SCREEN TEXT: {screen_text}

DECISION LOGIC:
1. OPENING APPS: If the step is 'open_app', output the step IMMEDIATELY. Do not check screen.
2. CHECKING: If the step is 'type_text' or 'click', check if the app looks open.
   - If YES: Output the original step.
   - If NO (e.g. still in Terminal): Output {{"action": "open_app", "name": "Brave"}} (or whatever app is needed).
3. UNCERTAIN? Output the original step. Do not just 'read_screen'.

OUTPUT ONLY JSON.
"""

def main():
    print("🤖 Groq Tiered Agent (Architect + Scout)")
    print(f"   🧠 Architect: {ARCHITECT_MODEL}")
    print(f"   ⚡ Scout: {SCOUT_MODEL}")
    print("-----------------------------------")
    
    user_goal = input("\n📝 What is your goal? ").strip()
    if not user_goal: return

    # PHASE 1: THE ARCHITECT (Big Brain)
    print("\n🧠 Architect is planning...")
    master_plan = groq_brain.get_action_plan(user_goal, model_id=ARCHITECT_MODEL)
    
    if not master_plan:
        print("❌ Architect failed.")
        return

    # Extract steps list
    steps = []
    if isinstance(master_plan, dict):
        steps = master_plan.get("plan") or master_plan.get("actions") or []
    elif isinstance(master_plan, list):
        steps = master_plan
        
    print(f"\n📋 Master Plan ({len(steps)} steps generated). handing over to Scout.\n")
    
    # PHASE 2: THE SCOUT (Fast Execution Loop)
    context = {"screen_data": ""}
    
    for i, step in enumerate(steps):
        print(f"\n🔹 Processing Step {i+1}/{len(steps)}: {step.get('action')}")
        
        # 1. Observe (Fast OCR)
        screen_text = client_app.handle_read_screen()
        # Truncate for speed
        screen_text = screen_text[-1500:] 
        
        # 2. Scout Check (Fast Model)
        # We wrap the step in a string to pass it to the prompt
        step_str = json.dumps(step)
        
        # Dynamic Prompt
        formatted_prompt = SCOUT_PROMPT.format(current_step=step_str, screen_text=screen_text)
        
        # Ask Scout
        # We bypass the 'get_action_plan' wrapper slightly by passing the raw prompt as the 'goal'
        # This is a hack to reuse the function, but it works because we override the model.
        print("   ⚡ Scout is checking state...")
        scout_response = groq_brain.get_action_plan(formatted_prompt, model_id=SCOUT_MODEL)
        
        # 3. Execute whatever the Scout says
        # (It might be the original step, OR a fix like 'Cmd+T')
        
        final_action = scout_response
        if isinstance(scout_response, dict) and "plan" in scout_response:
             final_action = scout_response["plan"] # Handle if Scout wraps it
             
        # Normalize to list for the runner
        if isinstance(final_action, dict):
            final_action = [final_action]
            
        if final_action:
            print(f"   ▶️ Executing: {final_action}")
            client_app.run_plan_loop(final_action, context)
        else:
            print("   ⚠️ Scout failed to decide. Forcing original step.")
            client_app.run_plan_loop([step], context)
            
        time.sleep(0.5)

if __name__ == "__main__":
    main()
