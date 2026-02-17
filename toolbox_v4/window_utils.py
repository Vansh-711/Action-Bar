import os
import sys
import subprocess

def get_exclusion_rects():
    """
    Returns a list of (x, y, w, h) rectangles for windows that should be ignored by OCR.
    Currently targets: The Python HUD and the Terminal (iTerm2/Terminal.app).
    """
    rects = []
    
    if sys.platform == "darwin":
        try:
            from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
            
            # Get current process PID and its parent (likely the terminal)
            my_pid = os.getpid()
            parent_pid = os.getppid()
            
            pids_to_exclude = {my_pid, parent_pid}
            
            for window in window_list:
                pid = window.get('kCGWindowOwnerPID')
                if pid in pids_to_exclude:
                    bounds = window.get('kCGWindowBounds')
                    if bounds:
                        rects.append((
                            bounds['X'],
                            bounds['Y'],
                            bounds['Width'],
                            bounds['Height']
                        ))
        except ImportError:
            print("⚠️ pyobjc-framework-Quartz not installed. HUD exclusion disabled.")
        except Exception as e:
            print(f"⚠️ Error getting exclusion rects: {e}")
            
    return rects

def is_point_in_rects(x, y, rects):
    """Checks if a coordinate (x, y) falls inside any of the exclusion rectangles."""
    for (rx, ry, rw, rh) in rects:
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            return True
    return False

if __name__ == "__main__":
    # Test: Print exclusion zones
    r = get_exclusion_rects()
    print(f"Exclusion Rects: {r}")
