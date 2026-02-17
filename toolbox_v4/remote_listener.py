import os
import time
import subprocess
import sys
import threading
from dotenv import load_dotenv

# --- CONFIGURATION ---
# Try loading from current dir, then parent dir
if os.path.exists(".env"):
    load_dotenv(".env")
elif os.path.exists("../.env"):
    load_dotenv("../.env")
else:
    print("⚠️ Warning: .env file not found in current or parent directory.")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Missing SUPABASE_URL or SUPABASE_KEY in .env file.")
    sys.exit(1)

if not SUPABASE_ANON_KEY:
    print("⚠️ WARNING: SUPABASE_ANON_KEY not found in .env. Using SUPABASE_KEY for frontend.")
    print("   This is insecure if SUPABASE_KEY is a service_role key.")
    SUPABASE_ANON_KEY = SUPABASE_KEY

# Generate config for frontend
def generate_frontend_config():
    # Use absolute path based on this script's location
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "web", "assets", "js", "env.js")
    
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        # We give the frontend the ANON key
        f.write(f'window.ENV = {{ SUPABASE_URL: "{SUPABASE_URL}", SUPABASE_KEY: "{SUPABASE_ANON_KEY}" }};')
    print(f"✅ Generated frontend config: {config_path}")

generate_frontend_config()
# ---------------------

try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Error: Missing libraries.")
    print("Please run: pip install supabase")
    sys.exit(1)

# Initialize Sync Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

AGENT_ID = None

def get_agent_id():
    """
    Retrieves or prompts for the Agent ID (User Email).
    """
    global AGENT_ID
    id_file = ".agent_id"
    
    if os.path.exists(id_file):
        with open(id_file, "r") as f:
            AGENT_ID = f.read().strip()
            print(f"🔑 Loaded Agent ID: {AGENT_ID}")
    else:
        print("\n👋 First time setup!")
        AGENT_ID = input("📧 Enter your Agent Email (from the website): ").strip()
        with open(id_file, "w") as f:
            f.write(AGENT_ID)
        print("✅ Saved Agent ID securely.")
    
    return AGENT_ID

def push_log_to_cloud(message):
    """
    Sends a log line to Supabase for the web UI to see.
    """
    try:
        if not message.strip(): return
        
        payload = {
            "log_message": message.strip(),
            "timestamp": time.time()
        }
        # Attempt to tag with user_email if AGENT_ID is set
        if AGENT_ID:
            payload["user_email"] = AGENT_ID

        supabase.table("agent_logs").insert(payload).execute()
    except Exception as e:
        # If user_email column is missing in logs table, this might fail. 
        # But we catch it silently to keep the agent running.
        pass 

def stream_process_output(process):
    """
    Reads stdout/stderr from the agent process and pushes CLEAN logs to cloud.
    """
    # User-friendly prefixes we want to show
    KEEP_PREFIXES = ("👉", "🧠", "🚀", "✅", "❌", "⚠️", "⌨️", "🖱️", "🌐", "👀", "⏳")
    
    # Use iter(callable, sentinel) to read line by line until empty byte string
    for line in iter(process.stdout.readline, b''):
        decoded_line = line.decode('utf-8', errors='replace').strip()
        if decoded_line:
            # Always print locally for debugging
            print(f"[AGENT] {decoded_line}") 
            
            # Filter for Cloud (Web UI)
            # Remove [AGENT] prefix if it exists in the line itself (though usually we added it)
            clean_msg = decoded_line.replace("[AGENT] ", "")
            
            # Check if it starts with an emoji/status we care about
            if any(clean_msg.startswith(p) for p in KEEP_PREFIXES):
                push_log_to_cloud(clean_msg)
            
    process.stdout.close()

def launch_agent():
    print("\n🚀 LAUNCH COMMAND RECEIVED!")
    push_log_to_cloud("🚀 Launching Agent GUI...")
    
    try:
        # Detect OS for correct python command
        python_cmd = "python3" if sys.platform == "darwin" else "python"
        
        # Get absolute path to agent_gui_v2.py (same dir as this script)
        base_dir = os.path.dirname(os.path.abspath(__file__))
        agent_path = os.path.join(base_dir, "agent_gui_v2.py")
        
        # RUN AGENT AS SUBPROCESS (Unbuffered)
        proc = subprocess.Popen(
            [python_cmd, "-u", agent_path], 
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT # Merge stderr into stdout
        )
        
        # Start background thread to stream logs
        t = threading.Thread(target=stream_process_output, args=(proc,))
        t.daemon = True
        t.start()
        
        print("✅ Agent Launched.")
        # Try to update status with user_email
        status_payload = {"status": "ONLINE"}
        if AGENT_ID: status_payload["user_email"] = AGENT_ID
        supabase.table("agent_status").insert(status_payload).execute()
        
    except Exception as e:
        err_msg = f"❌ Failed to launch agent: {e}"
        print(err_msg)
        push_log_to_cloud(err_msg)

def poll_for_commands():
    # 1. Get Identity
    get_agent_id()

    print(f"--- 🌉 TOOLBOX REMOTE BRIDGE (Polling: {AGENT_ID}) ---")
    print("Waiting for web commands...")
    
    last_checked_id = 0
    
    # Get the latest ID to avoid re-running old commands
    try:
        # Filter by user_email
        query = supabase.table("agent_commands").select("id").eq("user_email", AGENT_ID).order("id", desc=True).limit(1)
        latest = query.execute()
        if latest.data:
            last_checked_id = latest.data[0]['id']
            print(f"   (Ignoring commands prior to ID {last_checked_id})")
    except Exception as e:
        print(f"⚠️ Could not fetch initial state: {e}")

    while True:
        try:
            # Poll for new commands FOR THIS USER
            response = supabase.table("agent_commands")\
                .select("*")\
                .eq("user_email", AGENT_ID)\
                .gt("id", last_checked_id)\
                .order("id", desc=False)\
                .execute()
            
            commands = response.data
            
            for cmd in commands:
                cmd_text = cmd.get("command")
                print(f"📩 RECEIVED COMMAND: {cmd_text}")
                
                if cmd_text == "START":
                    launch_agent()
                
                # Update last checked ID
                last_checked_id = cmd['id']
            
            time.sleep(1) # Poll every 1s
            
        except Exception as e:
            print(f"⚠️ Polling Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    try:
        poll_for_commands()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by User.")
