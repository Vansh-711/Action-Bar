import json
import os
from datasets import load_dataset

# We switch to the robust Salesforce dataset you confirmed exists
DATASET_NAME = "Salesforce/grounding_dataset" 

def download_data():
    print(f"Streaming samples from {DATASET_NAME}...")
    
    # "streaming=True" is CRITICAL. It means we don't download 500GB.
    # We just peek at the first file.
    try:
        ds = load_dataset(DATASET_NAME, split="train", streaming=True)
    except Exception as e:
        print(f"Error connecting to Hugging Face: {e}")
        return

    output_dir = "eval_data"
    os.makedirs(output_dir, exist_ok=True)
    
    samples = []
    count = 0
    max_samples = 20 # Small test batch
    
    print("Iterating through stream...")
    for item in ds:
        # Check structure
        # Salesforce dataset usually has 'image' (PIL object) and 'bbox' or 'ground_truth'
        
        # We look for valid image + valid annotation
        if 'image' not in item:
            continue
            
        # Try to find the instruction and bbox keys
        # Different datasets name them differently.
        instruction = item.get('instruction', item.get('text', 'Click the element'))
        
        # Bbox might be in 'bbox', 'label', 'ground_truth'
        bbox = item.get('bbox', item.get('ground_truth', None))
        
        if bbox is None:
            continue
            
        if count >= max_samples:
            break
            
        img_filename = f"image_{count}.png"
        img_path = os.path.join(output_dir, img_filename)
        
        # Save Image
        item['image'].save(img_path)
        
        samples.append({
            "id": count,
            "image_path": img_path,
            "instruction": instruction,
            "ground_truth_bbox": bbox
        })
        
        count += 1
        print(f"Saved {count}/{max_samples}", end="\r")

    # Save the "Answer Key"
    with open(os.path.join(output_dir, "ground_truth.json"), "w") as f:
        json.dump(samples, f, indent=2)
        
    print(f"\n\nSuccess! Downloaded {count} examples to '{output_dir}/'.")

if __name__ == "__main__":
    download_data()
