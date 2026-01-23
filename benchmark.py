import ollama
import pyautogui
import time
from PIL import Image
import io
import os

# 1. Configuration - CHANGE THIS TO MATCH THE MODEL YOU PULLED
MODEL = "qwen3-vl:2b" 
SCREENSHOT_PATH = "screenshot.png"

def benchmark():
    print(f"--- Starting Benchmark with {MODEL} ---")
    
    # 2. Capture Screenshot
    print("Capturing screenshot...")
    start_time = time.time()
    screenshot = pyautogui.screenshot()
    
    # OPTIMIZATION: Shrink image for speed. 
    # VLModels handle lower res much faster on local GPUs.
    base_width = 1000
    w_percent = (base_width / float(screenshot.size[0]))
    h_size = int((float(screenshot.size[1]) * float(w_percent)))
    screenshot = screenshot.resize((base_width, h_size), Image.Resampling.LANCZOS)
    
    screenshot.save(SCREENSHOT_PATH, optimize=True, quality=50)
    screenshot_size = os.path.getsize(SCREENSHOT_PATH) / 1024
    print(f"Optimized Screenshot saved ({screenshot.width}x{screenshot.height}, {screenshot_size:.1f} KB)")

    # 3. Prepare Prompt
    # We ask the model to find the Apple icon (top left) to test accuracy.
    prompt = "Find the Apple logo icon in the top left corner of the screen and provide its coordinates in [ymin, xmin, ymax, xmax] format."

    print(f"Sending to {MODEL} via Ollama...")
    
    # 4. Inference
    try:
        response = ollama.chat(
            model=MODEL,
            messages=[
                {
                    'role': 'user',
                    'content': prompt,
                    'images': [SCREENSHOT_PATH]
                }
            ]
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print("\n--- RESULTS ---")
        print(f"Time Taken: {duration:.2f} seconds")
        print(f"Model Response: {response['message']['content']}")
        print("----------------\n")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have run 'ollama run qwen2-vl:2b' first!")

if __name__ == "__main__":
    benchmark()
