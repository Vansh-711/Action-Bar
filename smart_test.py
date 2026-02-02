from mlx_lm import load, generate
import json
import re
import os
from pathlib import Path

# --- PATHS ---
# We use pathlib to resolve the absolute path explicitly
BASE_MODEL = Path("/Users/apple/Desktop/access_tree_+_ocr_+_yolo_hybrid_text_model_planner/main_brain_model/testing/main_brain_model/models/Qwen2.5-Coder-1.5B-Instruct-4bit").resolve()
ADAPTER_PATH = Path("lora_model").resolve()

def test_smart_brain():
    print(f"🧠 Loading Base: {BASE_MODEL}")
    print(f"🧠 Loading Adapter: {ADAPTER_PATH}")
    
    if not BASE_MODEL.exists():
        print(f"❌ Error: Base model path not found at: {BASE_MODEL}")
        return
        
    if not ADAPTER_PATH.exists():
        print(f"❌ Error: Adapter path not found at: {ADAPTER_PATH}")
        print("Did you move the 'lora_model' folder into this directory?")
        return

    print("🧠 Fusing LoRA Adapter with Base Model...")
    
    # Converting Path objects to strings to ensure compatibility
    model, tokenizer = load(str(BASE_MODEL), adapter_path=str(ADAPTER_PATH))
    
    print("✅ Model is now SMART.")
    
    # Test with the hardest prompt
    user_goal = "Open Instagram and create a collection of posts of kedarnath with over 10k likes."
    
    # Use the EXACT prompt format from training
    system_msg = "You are a desktop automation agent. Output reasoning in 'Thought:' then strict JSON steps."
    
    prompt = f"""<|im_start|>system
{system_msg}<|im_end|>
<|im_start|>user
{user_goal}<|im_end|>
<|im_start|>assistant
"""

    print(f"\n--- Planning: {user_goal} ---")
    response = generate(model, tokenizer, prompt=prompt, max_tokens=500, verbose=True)
    
    print("\n--- Final Analysis ---")
    if "Thought:" in response:
        print("🚀 SUCCESS: Model followed the trained pattern!")
        
        # Try to parse
        try:
            match = re.search(r"```json\n(.*?)\n```", response, re.DOTALL)
            if match:
                print(match.group(1))
            else:
                print("Could not extract JSON block.")
        except:
            pass
    else:
        print("⚠️ Model ignored the pattern. Check training data.")

if __name__ == "__main__":
    test_smart_brain()