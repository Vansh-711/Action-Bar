import subprocess
import sys
import os

def get_active_window_info():
    """
    Returns a dictionary containing the frontmost app name and window title.
    Supports macOS (darwin) and Windows (win32).
    """
    info = {"app": "Unknown", "title": "Unknown"}
    
    if sys.platform == "darwin":
        try:
            # Get frontmost app name
            app_script = 'tell application "System Events" to get name of first process whose frontmost is true'
            app_name = subprocess.check_output(['osascript', '-e', app_script]).decode().strip()
            
            # Get window title
            title_script = 'tell application "System Events" to get name of first window of (first process whose frontmost is true)'
            window_title = subprocess.check_output(['osascript', '-e', title_script]).decode().strip()
            
            info["app"] = app_name
            info["title"] = window_title
        except Exception:
            pass # Fallback to Unknown
            
    elif sys.platform == "win32":
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window:
                info["title"] = window.title
                # On Windows, process name is harder, but title often contains app name
                info["app"] = window.title.split(" - ")[-1]
        except ImportError:
            print("⚠️ pygetwindow not installed. Windows support limited.")
            
    return info

def get_system_context_string():
    """Formatted string for AI prompts."""
    ctx = get_active_window_info()
    return f"CURRENT SYSTEM STATE:\n- Frontmost App: {ctx['app']}\n- Window Title: {ctx['title']}"

if __name__ == "__main__":
    # Test
    print(get_system_context_string())
