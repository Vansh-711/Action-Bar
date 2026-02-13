import toolbox_db
import json

def seed():
    db = toolbox_db.ToolboxDB()
    
    # 1. THE PERFECT OPEN_APP TOOL (Mac Spotlight)
    open_app_body = [
        {"action": "press_key", "key": "command+space"},
        {"action": "wait", "seconds": 1.0},
        {"action": "type_text", "text": "{app_name}"},
        {"action": "wait", "seconds": 1.0},
        {"action": "press_key", "key": "enter"},
        {"action": "wait", "seconds": 5.0}
    ]
    
    print("🚀 Seeding 'open_app_spotlight' to Toolbox...")
    db.save_tool(
        name="open_app_spotlight",
        description="Reliably opens any application using macOS Spotlight search.",
        parameters=["app_name"],
        body=open_app_body
    )
    
    # 2. THE PERFECT YOUTUBE TOOL
    yt_body = [
        {"action": "call_tool", "name": "open_app_spotlight", "params": {"app_name": "Brave"}},
        {"action": "wait", "seconds": 2.0},
        {"action": "press_key", "key": "command+l"},
        {"action": "type_text", "text": "https://www.youtube.com"},
        {"action": "press_key", "key": "enter"},
        {"action": "wait", "seconds": 5.0}
    ]
    
    print("🚀 Seeding 'open_youtube' to Toolbox...")
    db.save_tool(
        name="open_youtube",
        description="Opens the Brave browser and navigates to YouTube.",
        parameters=[],
        body=yt_body
    )

    print("\n✅ Seeding Complete! Your Agent is now smarter.")

if __name__ == "__main__":
    seed()
