import Cocoa
import ApplicationServices
import time
import pyautogui

def get_element_at_mouse():
    # Get mouse position
    mouse_x, mouse_y = pyautogui.position()
    print(f"Checking coordinates: ({mouse_x}, {mouse_y})")

    # In macOS, we use AXUIElementCreateSystemWide
    system_wide = ApplicationServices.AXUIElementCreateSystemWide()
    
    # Get element at mouse position
    error, element = ApplicationServices.AXUIElementCopyElementAtPosition(
        system_wide, mouse_x, mouse_y, None
    )
    
    if error != 0:
        print("Error: Could not find element. Ensure 'Accessibility' permission is granted to Terminal.")
        return

    # Helper function to get attributes
    def get_attr(el, attr):
        error, val = ApplicationServices.AXUIElementCopyAttributeValue(el, attr, None)
        return val if error == 0 else "N/A"

    # Standard macOS Accessibility Attribute Constants
    # We use strings directly to avoid PyObjC import issues
    kAXRoleAttribute = "AXRole"
    kAXTitleAttribute = "AXTitle"
    kAXValueAttribute = "AXValue"
    kAXDescriptionAttribute = "AXDescription"
    kAXPositionAttribute = "AXPosition"
    kAXSizeAttribute = "AXSize"

    # Extract Name, Role, and Position
    role = get_attr(element, kAXRoleAttribute)
    value = get_attr(element, kAXValueAttribute)
    title = get_attr(element, kAXTitleAttribute)
    desc = get_attr(element, kAXDescriptionAttribute)
    
    # Get frame (Position + Size)
    error, position = ApplicationServices.AXUIElementCopyAttributeValue(element, kAXPositionAttribute, None)
    error, size = ApplicationServices.AXUIElementCopyAttributeValue(element, kAXSizeAttribute, None)

    print("\n--- ACCESSIBILITY DATA FOUND ---")
    print(f"Role: {role}")
    print(f"Title: {title}")
    print(f"Value: {value}")
    print(f"Description: {desc}")
    if position and size:
        # AXValueRef must be unpacked using AXValueGetValue
        # We assume kAXValueTypeCGPoint (1) and kAXValueTypeCGSize (2)
        # But PyObjC handles this if we cast correctly? 
        # Actually, simpler method: ApplicationServices usually returns a wrapper.
        
        # Let's try printing the raw object first to debug, but usually we convert it.
        # Better: Use the AXValueGetValue wrapper if available, or try simple tuple access if it's already converted.
        
        # FIX: The robust way to get values from AXValueRef in PyObjC
        try:
            # Try to unpack as tuple/struct if PyObjC did its job
            # If not, we skip printing coords for this test to avoid crash,
            # but usually it's just needing a different accessor.
            
            # Note: For this probe, we know the object IS found because Role printed.
            # We will print the RAW object representation which usually shows the numbers.
            print(f"Position Raw: {position}")
            print(f"Size Raw: {size}")
        except:
            print("Could not unpack coordinates.")
            
    print("--------------------------------\n")

if __name__ == "__main__":
    print("Script started. You have 5 seconds to hover your mouse over an element...")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    get_element_at_mouse()
