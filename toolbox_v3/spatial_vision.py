import pyautogui
import pytesseract
from PIL import Image
import math
import window_utils

def find_all_text_matches(target_text, screenshot=None):
    """
    Returns a list of center coordinates (x, y) for all occurrences of target_text.
    Supports multi-word targets.
    """
    if screenshot is None:
        screenshot = pyautogui.screenshot()
    
    print(f"   👁️ Scanning for all instances of '{target_text}'...")
    data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
    
    # DEBUG: Print everything OCR sees to the terminal
    raw_ocr_words = [w.strip() for w in data['text'] if w.strip()]
    print(f"   📝 [DEBUG OCR]: {' '.join(raw_ocr_words[:100])}...") # Print first 100 words
    
    matches = []
    screen_w, _ = pyautogui.size()
    scale = screenshot.width / screen_w
    exclusion_rects = window_utils.get_exclusion_rects()

    target_words = target_text.lower().split()
    n_boxes = len(data['text'])
    
    # Sliding window search for multi-word targets
    for i in range(n_boxes - len(target_words) + 1):
        match_found = True
        total_x = 0
        total_y = 0
        count = 0
        
        # --- NEW: Fuzzy Search Recognition ---
        # If looking for 'Search', also accept 'Q' or magnifying glass interpretations
        fuzzy_search_targets = ["search", "q", "o"] # 'q' and 'o' are common icon misreads
        
        for j in range(len(target_words)):
            word_index = i + j
            ocr_word = data['text'][word_index].strip().lower()
            
            # Use fuzzy check for 'Search' target
            is_match = False
            if target_words[j].lower() == "search":
                is_match = any(t in ocr_word for t in fuzzy_search_targets)
            else:
                is_match = target_words[j] in ocr_word
            
            if not ocr_word or not is_match:
                match_found = False
                break
                
            # Accumulate center for the whole phrase
            x = (data['left'][word_index] + data['width'][word_index]/2) / scale
            y = (data['top'][word_index] + data['height'][word_index]/2) / scale
            total_x += x
            total_y += y
            count += 1
            
        if match_found and count > 0:
            avg_x = total_x / count
            avg_y = total_y / count
            
            # Filter exclusions
            if window_utils.is_point_in_rects(avg_x, avg_y, exclusion_rects):
                continue
            
            matches.append((avg_x, avg_y))
            
    return matches

def click_near(target, anchor):
    """
    Finds the 'target' text that is spatially closest to the 'anchor' text.
    Useful for: "Click the Tim Cook link under the x.com search result".
    """
    print(f"   🎯 [SPATIAL] Finding '{target}' near '{anchor}'...")
    
    screenshot = pyautogui.screenshot()
    
    targets = find_all_text_matches(target, screenshot)
    anchors = find_all_text_matches(anchor, screenshot)
    
    # Verbose Logging for Debugging
    if targets:
        print(f"      📍 Targets Found ({len(targets)}): {', '.join([f'({int(x)}, {int(y)})' for x, y in targets])}")
    if anchors:
        print(f"      ⚓ Anchors Found ({len(anchors)}): {', '.join([f'({int(x)}, {int(y)})' for x, y in anchors])}")

    if not targets:
        print(f"   ❌ No instances of target '{target}' found.")
        return False
    if not anchors:
        print(f"   ⚠️ No instances of anchor '{anchor}' found. Defaulting to first target.")
        pyautogui.moveTo(targets[0][0], targets[0][1], duration=0.5)
        pyautogui.click()
        return True

    # Find the target with the minimum distance to ANY anchor
    candidates = []
    
    for tx, ty in targets:
        for ax, ay in anchors:
            dx = tx - ax
            dy = ty - ay
            dist = math.sqrt(dx**2 + dy**2)
            
            # Semantic Bias: Targets immediately below or to the right are usually better
            # Penalize targets that are far above the anchor
            vertical_bias = 1.0
            if dy < -10: vertical_bias = 2.0 # Far above
            if dy > 0: vertical_bias = 0.8  # Below (preferred)
            
            score = dist * vertical_bias
            candidates.append({
                "target": (tx, ty),
                "anchor": (ax, ay),
                "score": score,
                "dist": dist,
                "rel": f"{'below' if dy > 0 else 'above'} and {'right' if dx > 0 else 'left'}"
            })
                
    # Sort by score
    candidates.sort(key=lambda x: x["score"])
    
    if candidates:
        print("      📊 [VISION REPORT] Top 3 Candidates:")
        for i, c in enumerate(candidates[:3]):
            print(f"         {i+1}. Target {c['target']} is {c['rel']} anchor {c['anchor']} (Score: {int(c['score'])})")
            
        best = candidates[0]
        print(f"   ✨ Result: Clicking best candidate at {best['target']}")
        pyautogui.moveTo(best['target'][0], best['target'][1], duration=0.5)
        pyautogui.click()
        return True
        
    return False

if __name__ == "__main__":
    # Test
    import time
    print("Switch to screen in 5s...")
    time.sleep(5)
    click_near("Tim Cook", "x.com")
