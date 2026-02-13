import datetime
import os

LOG_FILE = "session_log.txt"

def clear_log():
    with open(LOG_FILE, "w") as f:
        f.write(f"SESSION STARTED: {datetime.datetime.now()}\n")

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