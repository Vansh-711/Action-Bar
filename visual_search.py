import pyautogui
import pytesseract
from PIL import Image
import time

# Function to set tesseract path if needed (usually auto-detected on Mac)
# pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'

def visual_find_and_click(target_text):
    print(f"[Visual] Taking screenshot to find '{target_text}'...")
    
    # 1. Take Screenshot
    screenshot = pyautogui.screenshot()
    
    # 2. Run OCR (Get Data with Boxes)
    print("[Visual] Analyzing text...")
    data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
    
    # 3. Search for the word(s)
    # Tesseract splits "Google Search" into "Google" and "Search".
    # We look for the first word match for simplicity in this V1.
    
    target_words = target_text.split()
    found_indices = []
    
    n_boxes = len(data['text'])
    for i in range(n_boxes):
        word = data['text'][i].strip()
        # Case insensitive match
        if target_words[0].lower() in word.lower():
            # Potential match. If target is multi-word, check next words?
            # For V1, we just click the first word found.
            
            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]
            
            # Retina Scaling Correction
            # Screenshot is usually 2x size of PyAutoGUI points on Retina.
            # We need to divide by 2 if your screen is Retina.
            # Let's detect scaling roughly.
            screen_w, _ = pyautogui.size()
            img_w = screenshot.width
            scale = img_w / screen_w
            
            center_x = (x + w/2) / scale
            center_y = (y + h/2) / scale
            
            # FILTER: Ignore the top of the screen (Tabs, URL bar, Menubar)
            # Usually top 150 points covers most browser toolbars
            if center_y < 150:
                # print(f"[Visual] Skipping '{word}' found in toolbar area.")
                continue
            
            print(f"[Visual] Found text '{word}' at ({center_x}, {center_y})")
            
            pyautogui.moveTo(center_x, center_y, duration=0.5)
            pyautogui.click()
            return True
            
    print(f"[Visual] Could not find text '{target_text}'")
    return False

if __name__ == "__main__":
    print("--- VISUAL SEARCH TEST ---")
    print("Switch to Brave (Google.com) in 5 seconds...")
    time.sleep(5)
    
    # Test
    visual_find_and_click("Google Search")
