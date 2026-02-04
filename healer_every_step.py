import time
import pyautogui
import groq_brain
import json
import client_app  # Reuse our action handlers
import sys

# Update System Prompt for Step-by-Step Logic
REACTIVE_PROMPT = """You are a Real-Time Desktop Agent.
You see the current screen state and the user's ultimate goal.
Your job is to output the SINGLE NEXT ACTION to move closer to the goal.

AVAILABLE ACTIONS:
- open_app(name="App Name")
- click_text(text="Button Label")
- type_text(text="Hello World")
- press_key(key="Enter")
- wait(seconds=2)
- stop(reason="Task Complete")

LOGIC GUIDELINES:
1. BROWSER: If the goal is to open a URL, and you see a browser is already open with a different page, press 'command+t' (Mac) or 'ctrl+t' (Win) first.
2. CHECKING: If you just opened an app, wait/check if it's actually visible.
3. TYPING: If you need to type, ensure the focus is in the right place (click first if needed).
4. COMPLETION: When the goal is fully achieved, output 'stop'.

OUTPUT FORMAT (JSON):
{
  "thought": "I see Brave is open but displaying Google. I need to open a new tab before typing the Youtube URL.",
  "action": "press_key",
  "params": { "key": "command+t" }
}
"""

def get_next_step(user_goal, screen_text, history):
    # Construct a dynamic prompt with context
    state_prompt = f"""
    GOAL: {user_goal}    
    CURRENT SCREEN TEXT (OCR):
    ---
    {screen_text[-2000:]} 
    ---
    
    ACTION HISTORY (Last 3 steps):
    {history[-3:]}
    
    What is the IMMEDIATE next step?
    """
    
    # We temporarily swap the system prompt in groq_brain logic
    # (In a real app, we'd pass it as a param, but for this hack we modify the global or pass explicit messages)
    
    return groq_brain.client.chat.completions.create(
        model=groq_brain.MODEL_ID,
        messages=[
            {"role": "system", "content": REACTIVE_PROMPT},
            {"role": "user", "content": state_prompt}
        ],
        temperature=0.0,
        stream=False
    ).choices[0].message.content

def main():
    print("🤖 Groq Healer Agent (Step-by-Step)")
    print("-----------------------------------")
    
    user_goal = input("\n📝 What is your goal? ").strip()
    history = []
    
    while True:
        # 1. OBSERVE
        print("\n👀 Scanning Screen...")
        screen_text = client_app.handle_read_screen()
        
        # 2. THINK
        print("🧠 Thinking...")
        try:
            response_text = get_next_step(user_goal, screen_text, history)
            
            # Parse JSON (Handle <think> tags if Qwen)
            if "<think>" in response_text:
                response_text = response_text.split("</think>")[-1].strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
                
            step = json.loads(response_text)
            
        except Exception as e:
            print(f"❌ Brain Error: {e}")
            time.sleep(2)
            continue

        # 3. ACT
        action = step.get("action")
        params = step.get("params") or {}
        
        print(f"💡 Thought: {step.get('thought')}")
        print(f"▶️ Executing: {action} {params}")
        
        if action == "stop":
            print(f"✅ DONE: {params.get('reason')}")
            break
            
        # Execute using our robust dispatcher
        client_app.execute_step(action, params, context={})
        
        # Add to history
        history.append(f"{action}({params})")
        
        # Small pause for UI to react
        time.sleep(1.0)

if __name__ == "__main__":
    main()
