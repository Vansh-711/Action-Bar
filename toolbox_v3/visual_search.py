import pyautogui
import pytesseract
from PIL import Image
import time
import window_utils # NEW: Import our exclusion logic

def visual_find_and_click(target_text):
    print(f"[Visual] Taking screenshot to find '{target_text}'...")
    
    # Get exclusion zones (HUD, Terminal)
    exclusion_rects = window_utils.get_exclusion_rects()
    
    # 1. Take Screenshot
    screenshot = pyautogui.screenshot()
    
    # 2. Run OCR (Get Data with Boxes)
    print("[Visual] Analyzing text...")
    data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
    
    # DEBUG: Print raw OCR to terminal
    raw_ocr_words = [w.strip() for w in data['text'] if w.strip()]
    print(f"   📝 [DEBUG OCR]: {' '.join(raw_ocr_words[:100])}...")

    target_words = target_text.lower().split()
    n_boxes = len(data['text'])
    
    # Retina Scaling Correction
    screen_w, _ = pyautogui.size()
    img_w = screenshot.width
    scale = img_w / screen_w

    # Sliding window search for multi-word targets
    for i in range(n_boxes - len(target_words) + 1):
        match_found = True
        total_x = 0
        total_y = 0
        count = 0
        
        for j in range(len(target_words)):
            word_index = i + j
            ocr_word = data['text'][word_index].strip().lower()
            
            if not ocr_word or target_words[j] not in ocr_word:
                match_found = False
                break
            
            # Accumulate center
            x = (data['left'][word_index] + data['width'][word_index]/2) / scale
            y = (data['top'][word_index] + data['height'][word_index]/2) / scale
            total_x += x
            total_y += y
            count += 1
            
        if match_found and count > 0:
            center_x = total_x / count
            center_y = total_y / count
            
            # --- NEW: EXCLUSION CHECK ---
            if window_utils.is_point_in_rects(center_x, center_y, exclusion_rects):
                continue
            
            # FILTER: Ignore the very top of the screen (Menubar)
            if center_y < 30:
                continue
            
            print(f"[Visual] Found multi-word match '{target_text}' at ({center_x}, {center_y})")
            
            pyautogui.moveTo(center_x, center_y, duration=0.5)
            pyautogui.click()
            return True
            
    print(f"[Visual] Could not find text '{target_text}' outside exclusion zones.")
    return False

if __name__ == "__main__":
    print("--- VISUAL SEARCH TEST ---")
    print("Switch to Brave (Google.com) in 5 seconds...")
    time.sleep(5)
    
    # Test
    visual_find_and_click("Google Search")
