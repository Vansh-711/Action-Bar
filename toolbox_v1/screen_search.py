import ApplicationServices
import Cocoa
import pyautogui
import time
import re
import os

class ScreenScanner:
    def __init__(self):
        # Initialize the system-wide UI element
        self.system_wide = ApplicationServices.AXUIElementCreateSystemWide()
        
    def _get_attribute(self, element, attribute):
        """Helper to safely get an attribute value from an AXUIElement."""
        error, value = ApplicationServices.AXUIElementCopyAttributeValue(element, attribute, None)
        if error == 0:
            return value
        return None

    def _unpack_pos(self, ax_value):
        """Robustly extracts (x, y) from AXValueRef."""
        try:
            return (ax_value.x, ax_value.y)
        except:
            pass
        
        text = str(ax_value)
        match = re.search(r"x:([\d\.]+)\s+y:([\d\.]+)", text)
        if match:
            return (float(match.group(1)), float(match.group(2)))
        return (0, 0)

    def _unpack_size(self, ax_value):
        """Robustly extracts (w, h) from AXValueRef."""
        try:
            return (ax_value.width, ax_value.height)
        except:
            pass
            
        text = str(ax_value)
        match = re.search(r"w:([\d\.]+)\s+h:([\d\.]+)", text)
        if match:
            return (float(match.group(1)), float(match.group(2)))
        return (0, 0)

    def scan_recursive(self, element, target_name, depth=0, max_depth=10):
        """Recursively searches the accessibility tree for an element matching target_name."""
        if depth > max_depth:
            return None

        # 1. Check current element's properties
        title = self._get_attribute(element, "AXTitle")
        desc = self._get_attribute(element, "AXDescription")
        value = self._get_attribute(element, "AXValue")
        role = self._get_attribute(element, "AXRole")

        # Skip generic containers if they have no useful info
        # But we must dive into them.
        
        # Check match
        search_terms = [str(title), str(desc), str(value)]
        if any(target_name.lower() in term.lower() for term in search_terms if term != "None"):
            
            # FILTER: Ignore text areas
            if role in ['AXTextArea', 'AXStaticText', 'AXTextField'] and target_name.lower() not in str(value).lower():
                pass 
            else:
                pos_val = self._get_attribute(element, "AXPosition")
                size_val = self._get_attribute(element, "AXSize")
                
                if pos_val and size_val:
                    x, y = self._unpack_pos(pos_val)
                    w, h = self._unpack_size(size_val)
                    
                    # VALIDATION: Ignore ghost elements at (0,0) or (0, height) or size 0
                    screen_w, screen_h = pyautogui.size()
                    if (x == 0 and (y == 0 or y >= screen_h - 50)) or (w <= 1 or h <= 1):
                        # print(f"Skipping ghost/hidden element at ({x}, {y})")
                        pass
                    else:
                        return {"element": element, "position": pos_val, "size": size_val, "role": role}

        # 2. Search Children
        error, children = ApplicationServices.AXUIElementCopyAttributeValue(element, "AXChildren", None)
        if error == 0 and children:
            for child in children:
                result = self.scan_recursive(child, target_name, depth + 1, max_depth)
                if result:
                    return result
        
        return None

    def find_and_click(self, name):
        """Finds an element by name and clicks its center."""
        print(f"Searching for: '{name}'...")
        
        workspace = Cocoa.NSWorkspace.sharedWorkspace()
        running_apps = workspace.runningApplications()
        my_pid = os.getpid()
        
        # Sort apps: Active first, then Dock/Finder, then others
        # "Dock" usually has bundle ID 'com.apple.dock'
        # Handle None bundleIdentifier safely
        def app_priority(a):
            if a.isActive(): return 0
            bid = a.bundleIdentifier()
            if bid and "dock" in bid.lower(): return 1
            return 2
            
        running_apps = sorted(running_apps, key=app_priority)

        for app in running_apps:
            if app.processIdentifier() == my_pid:
                continue
                
            # Skip background daemons (no UI) to speed up
            if app.activationPolicy() == Cocoa.NSApplicationActivationPolicyProhibited:
                continue
                
            print(f"Scanning app: {app.localizedName()}...")
            app_element = ApplicationServices.AXUIElementCreateApplication(app.processIdentifier())
            
            # INCREASE DEPTH for Browser internal elements
            # Web elements are often nested 8-12 levels deep
            result = self.scan_recursive(app_element, name, max_depth=15)
            
            if result:
                self._click_result(result, name)
                return True
        
        print(f"Error: Could not find '{name}' on screen.")
        return False

    def _click_result(self, result, name):
        pos_raw = result["position"]
        size_raw = result["size"]
        
        x, y = self._unpack_pos(pos_raw)
        w, h = self._unpack_size(size_raw)
        
        center_x = x + (w / 2)
        center_y = y + (h / 2)
        
        screen_w, screen_h = pyautogui.size()
        print(f"DEBUG: Found {result.get('role')} at ({center_x}, {center_y})")
        
        if center_y > screen_h or center_x > screen_w:
             print("WARNING: Off-screen match ignored.")
             return

        print(f"Clicking '{name}'...")
        pyautogui.moveTo(center_x, center_y, duration=0.5)
        pyautogui.click()

if __name__ == "__main__":
    import os 
    scanner = ScreenScanner()
    # Test
    target = "Visual Studio Code" 
    
    print(f"--- READY ---")
    print(f"You have 5 seconds to switch to the window you want to test...")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
        
    scanner.find_and_click(target)
