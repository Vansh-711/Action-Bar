import sys
import io
import time
import json
import threading
from contextlib import redirect_stdout

# --- CONFIGURATION ---
SUPABASE_URL = "YOUR_SUPABASE_URL"
SUPABASE_KEY = "YOUR_SUPABASE_KEY"
# ---------------------

try:
    from supabase import create_client, Client
except ImportError:
    print("❌ Error: Missing 'supabase' library.")
    sys.exit(1)

# Initialize Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class SupabaseStream(io.StringIO):
    """
    Custom Stream that intercepts print() statements and pushes them to the Cloud.
    """
    def __init__(self, table_name="agent_logs"):
        super().__init__()
        self.table_name = table_name

    def write(self, message):
        if message.strip(): # Ignore empty newlines
            # 1. Print locally (so user still sees it)
            sys.__stdout__.write(message + "
")
            
            # 2. Push to Cloud (Async ideally, but sync for demo)
            try:
                supabase.table(self.table_name).insert({
                    "log_message": message.strip(),
                    "timestamp": time.time()
                }).execute()
            except Exception as e:
                pass # Silent fail to avoid loops

class HeadlessAgent:
    def __init__(self):
        self.running = False
        self.cloud_stream = SupabaseStream()

    def start_listening(self):
        print("🤖 HEADLESS AGENT ONLINE")
        print("   Listening for commands on Supabase...")
        
        # Subscribe to 'agent_commands' table
        channel = supabase.channel('public:agent_commands')
        channel.on(
            'postgres_changes', 
            {'event': 'INSERT', 'schema': 'public', 'table': 'agent_commands'}, 
            self.handle_remote_command
        ).subscribe()
        
        # Keep alive
        while True:
            time.sleep(1)

    def handle_remote_command(self, payload):
        new_cmd = payload.get('new', {}).get('command')
        user = payload.get('new', {}).get('user_email')
        
        if new_cmd:
            print(f"
📩 REMOTE COMMAND: {new_cmd} (from {user})")
            
            # Execute the command and capture output
            with redirect_stdout(self.cloud_stream):
                self.run_task(new_cmd)

    def run_task(self, goal):
        # Simulate Agent Logic (This would call agent_compiler.py)
        print(f"🧠 Analyzing Goal: '{goal}'")
        time.sleep(1)
        print("   [Stage 1] Breaking down task...")
        time.sleep(1)
        print("   [Stage 2] Searching tools...")
        time.sleep(1)
        print("   ✅ Task Complete.")

if __name__ == "__main__":
    agent = HeadlessAgent()
    agent.start_listening()
