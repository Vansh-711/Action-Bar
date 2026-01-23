import subprocess
import time
import re
import pyautogui
from PIL import Image
import os

MODEL_PATH = "mlx-community/Qwen2-VL-2B-Instruct-4bit"
SCREENSHOT_PATH = "screenshot_mlx.png"

def benchmark_mlx_cli():
    print(f"--- Starting MLX CLI Benchmark with {MODEL_PATH} ---")
    
    # 1. Capture Screenshot
    print("Capturing screenshot...")
    screenshot = pyautogui.screenshot()
    
    # Resize (Crucial for speed)
    base_width = 1000
    w_percent = (base_width / float(screenshot.size[0]))
    h_size = int((float(screenshot.size[1]) * float(w_percent)))
    screenshot = screenshot.resize((base_width, h_size), Image.Resampling.LANCZOS)
    screenshot.save(SCREENSHOT_PATH)
    
    prompt = "Find the Apple logo icon in the top left corner and return coordinates in [ymin, xmin, ymax, xmax] format."
    
    # 2. Construct the CLI Command
    # This calls the library's built-in script which handles all the complex tokenization correctly.
    command = [
        "python3", "-m", "mlx_vlm.generate",
        "--model", MODEL_PATH,
        "--image", SCREENSHOT_PATH,
        "--prompt", prompt,
        "--max-tokens", "50",
        "--temp", "0.0" # Deterministic
    ]
    
    print("Running Inference via CLI (This guarantees correct tokenization)...")
    start_time = time.time()
    
    # Run the command and capture output
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        total_time = time.time() - start_time
        
        print("\n--- RAW OUTPUT ---")
        print(result.stdout)
        print("------------------")
        
        # Parse speed from output if available, or just use total time
        print(f"\nTotal Execution Time (including loading): {total_time:.2f}s")
        
        # Look for "Generation time" in the output
        match = re.search(r"Generation time: ([\d\.]+)s", result.stdout)
        if match:
            print(f"Pure Inference Speed: {match.group(1)}s (This is the number that matters for the Agent)")
        else:
            print("Could not parse exact generation time, check raw output above.")
            
    except subprocess.CalledProcessError as e:
        print("Error running command:")
        print(e.stderr)

if __name__ == "__main__":
    benchmark_mlx_cli()
