import json
import os
import re
import mlx.core as mx
from mlx_vlm import load
from mlx_vlm.utils import load_config
from PIL import Image

# Configuration
DATA_DIR = "eval_data"
METADATA_FILE = os.path.join(DATA_DIR, "ground_truth.json")
MODEL_PATH = "mlx-community/Qwen2-VL-2B-Instruct-4bit"

def calculate_iou(boxA, boxB):
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    interArea = max(0, xB - xA) * max(0, yB - yA)
    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    iou = interArea / float(boxAArea + boxBArea - interArea + 1e-6)
    return iou

def parse_model_output(output_str):
    match = re.search(r"[[\](\d+),\s*(\d+),\s*(\d+),\s*(\d+)]", output_str)
    if match: return [int(g) for g in match.groups()]
    match_special = re.search(r"\((\d+),(\d+)\),\((\d+),(\d+)\)", output_str)
    if match_special: return [int(g) for g in match_special.groups()]
    return None

def run_evaluation():
    print(f"Loading Model {MODEL_PATH}...")
    model, processor = load(MODEL_PATH)
    config = load_config(MODEL_PATH)
    
    with open(METADATA_FILE, "r") as f:
        dataset = json.load(f)
        
    correct = 0
    total_iou = 0.0
    count = 0
    
    print("\n--- Starting Evaluation ---")
    
    for item in dataset:
        try:
            # 1. Prepare Inputs using the Library's CLI Logic (Replicated)
            # This logic comes directly from mlx_vlm.generate source code
            
            # 1. Prepare Inputs
            image = Image.open(item['image_path'])
            
            # RESIZE
            if max(image.size) > 1024:
                image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            
            # prompt = f"<|image_1|>\nRef: {item['instruction']} Box:" # OLD MANUAL WAY
            
            # NEW: Use the correct Chat Template (like the CLI)
            # We explicitly ask for the format in the prompt
            prompt_text = f"Find the bounding box for '{item['instruction']}' and return it in [ymin, xmin, ymax, xmax] format."
            
            conversation = [
                {"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt_text}]}
            ]
            
            formatted_prompt = processor.apply_chat_template(
                conversation,
                add_generation_prompt=True
            )
            
            # Use the processor to get tensors
            inputs = processor(
                images=[image],
                text=[formatted_prompt],
                padding=True,
                return_tensors="np"
            )
            
            # Convert to MLX
            input_ids = mx.array(inputs["input_ids"])
            pixel_values = mx.array(inputs["pixel_values"])
            mask = mx.array(inputs["attention_mask"])
            image_grid_thw = mx.array(inputs["image_grid_thw"])

            # 2. Generate
            curr_ids = input_ids
            gen_tokens = []
            
            for _ in range(20): # Short generation for coordinates
                outputs = model(curr_ids, pixel_values, mask=mask, image_grid_thw=image_grid_thw)
                logits = outputs.logits
                next_token = mx.argmax(logits[:, -1, :], axis=-1)
                
                curr_ids = mx.concatenate([curr_ids, next_token[None]], axis=1)
                mask = mx.concatenate([mask, mx.array([[1]])], axis=1)
                gen_tokens.append(next_token.item())
                
                if next_token.item() == processor.tokenizer.eos_token_id:
                    break
            
            output_text = processor.tokenizer.decode(gen_tokens)
            
            # 3. Evaluate
            gt_norm = [int(c * 1000) for c in item['ground_truth_bbox']]
            if len(gt_norm) == 2: 
                gt_norm = [gt_norm[0]-20, gt_norm[1]-20, gt_norm[0]+20, gt_norm[1]+20]

            pred = parse_model_output(output_text)
            iou = 0.0
            status = "❌"
            
            if pred:
                pred_std = [pred[1], pred[0], pred[3], pred[2]]
                iou = calculate_iou(pred_std, gt_norm)
                total_iou += iou
                if iou > 0.5:
                    correct += 1
                    status = "✅"
            
            print(f"Sample {item['id']}: {status} (IoU: {iou:.2f}) | Out: {output_text.strip()}")
            count += 1
            
        except Exception as e:
            print(f"Error on sample {item['id']}: {e}")

    if count > 0:
        print(f"\nFinal Accuracy: {(correct/count)*100:.2f}%")

if __name__ == "__main__":
    run_evaluation()
