import datetime
import os
import json

LOG_FILE = "session_log.txt"
EXECUTION_DIR = "execution_files"

# Ensure execution directory exists
os.makedirs(EXECUTION_DIR, exist_ok=True)

def clear_log():
    """Clears the main session log and execution files for a new session."""
    with open(LOG_FILE, "w") as f:
        f.write(f"SESSION STARTED: {datetime.datetime.now()}\n")
    
    # Optionally clear previous execution files
    for f in os.listdir(EXECUTION_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(EXECUTION_DIR, f))

def log_action(action, params):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] ACTION: {action} | PARAMS: {params}\n"
    print(entry.strip())
    with open(LOG_FILE, "a") as f:
        f.write(entry)

def log_result(success, details=""):
    status = "SUCCESS" if success else "FAILED"
    entry = f"   -> RESULT: {status} | {details}\n"
    with open(LOG_FILE, "a") as f:
        f.write(entry)

def log_feedback(feedback):
    entry = f"\n[USER FEEDBACK]: {feedback}\n"
    with open(LOG_FILE, "a") as f:
        f.write(entry)

def read_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return f.read()
    return "No history."

# --- STAGE FILE MANAGEMENT (The 6-JSON Trail) ---

def save_stage_file(filename, data):
    """Saves data to one of the 1.json - 6.json stages."""
    path = os.path.join(EXECUTION_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    
    # Also log that this stage was completed
    log_action("STAGE_SAVED", filename)
    return data

def read_stage_file(filename):
    """Reads data from a stage file."""
    path = os.path.join(EXECUTION_DIR, filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

def log_tools_used(new_tools, old_tools):
    """
    Saves a specific log of which tools were reused and which were newly invented.
    """
    data = {
        "timestamp": str(datetime.datetime.now()),
        "new_tools_invented": new_tools,
        "old_tools_reused": old_tools
    }
    save_stage_file("tools_usage_log.json", data)
