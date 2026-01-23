import json
import os
import subprocess
import re
import math

# Configuration
DATA_DIR = "eval_data"
METADATA_FILE = os.path.join(DATA_DIR, "ground_truth.json")
MODEL_PATH = "mlx-community/Qwen2-VL-2B-Instruct-4bit"

def calculate_iou(boxA, boxB):
    # Determine the (x, y) - coordinates of the intersection rectangle
    # Box format: [xmin, ymin, xmax, ymax] (Standardizing order for calculation)
    
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    # Compute the area of intersection rectangle
    interArea = max(0, xB - xA) * max(0, yB - yA)

    # Compute the area of both the prediction and ground-truth rectangles
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    # Compute the intersection over union
    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou

def parse_model_output(output_str):
    # The model returns something like:
    # "The box is [100, 200, 150, 250]"
    # or just "[100, 200, 150, 250]"
    
    # We look for the pattern [num, num, num, num]
    # Qwen2-VL usually outputs 0-1000 scale.
    match = re.search(r"[0-9]+, [0-9]+, [0-9]+, [0-9]+", output_str)
    if match:
        # Extract numbers from the matched string
        nums_str = match.group(0).replace('[', '').replace(']', '').split(',')
        return [int(n.strip()) for n in nums_str]
    return None

def run_evaluation():
    print(f"Loading Ground Truth from {METADATA_FILE}...")
    with open(METADATA_FILE, "r") as f:
        dataset = json.load(f)
        
    correct_predictions = 0
    total_iou = 0.0
    valid_samples = 0
    
    print("--- Starting Evaluation Loop ---")
    
    for item in dataset:
        img_path = item['image_path']
        instruction = item['instruction']
        
        # ScreenSpot bbox is usually [x, y] point or [x1, y1, x2, y2]. 
        # If it's 2 numbers, it's a point. If 4, it's a box.
        gt = item['ground_truth_bbox'] 
        
        # Note: ScreenSpot data is often 0-1 float relative.
        # Qwen outputs 0-1000 int.
        # We need to normalize GT to 0-1000.
        gt_norm = [int(c * 1000) for c in gt]
        
        # If GT is a point [x, y], convert to small box [x-10, y-10, x+10, y+10]
        if len(gt_norm) == 2:
            gt_norm = [gt_norm[0]-20, gt_norm[1]-20, gt_norm[0]+20, gt_norm[1]+20]
        
        # Qwen2-VL Grounding Syntax:
        # We give it the 'Ref' (Reference text) and ask for the 'Box'.
        # This is the magic format that wakes up the grounding head.
        prompt = f"Ref: {instruction} Box:"
        
        # Run MLX CLI
        cmd = [
            "python3", "-m", "mlx_vlm.generate",
            "--model", MODEL_PATH,
            "--image", img_path,
            "--prompt", prompt,
            "--max-tokens", "50",
            "--temp", "0.0"
        ]
        
        try:
            print(f"Thinking on sample {item['id']}...", end="\r")
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout
            
            # DEBUG: Print what the model actually said
            # print(f"\nRAW OUTPUT {item['id']}: {output}\n")
            
            # Extract prediction
            # Qwen outputs [ymin, xmin, ymax, xmax]
            pred = parse_model_output(output)
            
            if pred:
                # Convert Qwen [y, x, y, x] to Standard [x, y, x, y] for IoU calc
                pred_standard = [pred[1], pred[0], pred[3], pred[2]]
                
                iou = calculate_iou(pred_standard, gt_norm)
                total_iou += iou
                
                # We count it as "Correct" if IoU > 0.5
                is_correct = iou > 0.5
                if is_correct:
                    correct_predictions += 1
                
                status = "✅" if is_correct else "❌"
                print(f"Sample {item['id']}: {status} (IoU: {iou:.2f}) | Goal: {instruction}")
            else:
                # Print the failure for debugging
                print(f"Sample {item['id']}: ⚠️ Failed to parse. Raw output snippet: {output[-200:].strip()}")
                
            valid_samples += 1
            
        except Exception as e:
            print(f"Error on sample {item['id']}: {e}")

    # Final Report
    if valid_samples > 0:
        accuracy = (correct_predictions / valid_samples) * 100
        avg_iou = total_iou / valid_samples
        print("\n==============================")
        print(f"FINAL ACCURACY: {accuracy:.2f}%")
        print(f"AVERAGE IOU:    {avg_iou:.2f}")
        print("==============================")
    else:
        print("No samples processed.")

if __name__ == "__main__":
    run_evaluation()
