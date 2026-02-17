import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import threading
import queue
import time
import json
import os
import agent_compiler
import client_app
import toolbox_logger
import sys
import pyautogui

class AgentHUDV3:
    """
    The orchestrator for V1.3 (Context-Aware).
    Drives the AgentCompiler through stages 1-6 and manages block-level execution.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Groq Agent V1.3")
        self.root.geometry("650x220+50+50")
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#121212")

        # --- ENGINES ---
        self.compiler = agent_compiler.AgentCompiler()
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()

        # --- STATE ---
        self.user_goal = ""
        self.current_plan = []
        self.completed_steps = []
        self.high_level_blocks = []
        self.current_block_idx = 0
        self.execution_state = "IDLE" # IDLE, COMPILING, REVIEW, RUNNING, VERIFYING, FIXING

        self._setup_ui()
        self._check_queue()
        print("\n" + "="*40)
        print("🚀 HUD V1.3 ONLINE")
        print("="*40 + "\n")

    def _setup_ui(self):
        # 1. Header (Status & ProgressBar)
        self.header_frame = tk.Frame(self.root, bg="#121212")
        self.header_frame.pack(fill=tk.X, padx=15, pady=(15, 5))

        self.status_label = tk.Label(self.header_frame, text="READY", bg="#121212", fg="#00BFFF", font=("Consolas", 12, "bold"), anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(self.root, orient=tk.HORIZONTAL, length=620, mode='determinate')
        self.progress.pack(padx=15, pady=5)

        # 2. Detail Area (Block/Step info)
        self.detail_label = tk.Label(self.root, text="Enter your goal below to begin.", bg="#1E1E1E", fg="#90EE90", font=("Consolas", 10), anchor="w", justify=tk.LEFT, wraplength=600, height=3)
        self.detail_label.pack(fill=tk.X, padx=15, pady=5)

        # 3. Control Bar
        self.footer_frame = tk.Frame(self.root, bg="#121212")
        self.footer_frame.pack(fill=tk.X, padx=15, pady=10)

        self.input_entry = tk.Entry(self.footer_frame, bg="#333333", fg="white", insertbackground="white", font=("Arial", 12), relief=tk.FLAT)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5)
        self.input_entry.bind("<Return>", lambda e: self.on_go_clicked())
        self.input_entry.focus()

        self.go_btn = tk.Button(self.footer_frame, text="GO", command=self.on_go_clicked, bg="#32CD32", fg="white", font=("Arial", 11, "bold"), width=12)
        self.go_btn.pack(side=tk.RIGHT)

        self.stop_btn = tk.Button(self.header_frame, text="🛑 STOP", command=self.on_stop_clicked, bg="#FF4500", fg="white", font=("Arial", 10, "bold"), width=8, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT)

    # --- MAIN ENGINE CONTROL ---

    def on_go_clicked(self):
        text = self.input_entry.get().strip()
        
        if self.execution_state == "IDLE":
            if not text: return
            self.user_goal = text
            self.completed_steps = [] # CLEAR HISTORY for new goal
            print(f"\n📝 NEW GOAL: {text}")
            self.input_entry.delete(0, tk.END)
            self.start_compilation()
            
        elif self.execution_state == "REVIEW":
            self.start_execution()
            
        elif self.execution_state == "VERIFYING":
            val = text.lower()
            if val in ["y", "yes"]:
                print("\n✅ USER CONFIRMED SUCCESS")
                self.input_entry.delete(0, tk.END)
                self.on_finish(True)
            elif val in ["n", "no"]:
                print("\n❌ USER REPORTED FAILURE")
                self.input_entry.delete(0, tk.END)
                self.msg_queue.put(("ask_feedback", "Task finished but user reported issues."))
            else:
                self.set_status("TYPE 'y' OR 'n':", "#FFD700")
                
        elif self.execution_state == "FIXING":
            if text:
                print(f"\n🔄 FEEDBACK RECEIVED: {text}")
                self.input_entry.delete(0, tk.END)
                self.run_fix(text)

    def on_stop_clicked(self):
        print("\n🛑 STOP REQUESTED BY USER")
        self.stop_event.set()
        self.set_status("INTERRUPTING...", "#FF4500")

    def set_status(self, text, color="#00BFFF"):
        self.status_label.config(text=text, fg=color)

    def set_detail(self, text):
        self.detail_label.config(text=text)

    # --- THREADED LOGIC ---

    def start_compilation(self):
        self.execution_state = "COMPILING"
        self.go_btn.config(state=tk.DISABLED, text="Planning...")
        self.set_status("🧠 COMPILING REASONING...", "#FFD700")
        self.progress['value'] = 0
        
        threading.Thread(target=self._compilation_thread).start()

    def _compilation_thread(self):
        try:
            print("   --- Reasoning Pipeline Started ---")
            # Stage 1
            print("   [1/4] Breaking down main task...")
            self.msg_queue.put(("detail", "Stage 1: Breaking down task..."))
            self.high_level_blocks = self.compiler.stage_1_main_breakdown(self.user_goal)
            self.msg_queue.put(("progress", 25))

            # Stage 2 & 3
            print("   [2/4] Expanding semantic keywords & fetching tools...")
            self.msg_queue.put(("detail", "Stage 2 & 3: Finding relevant tools..."))
            self.compiler.stage_2_semantic_search(self.user_goal)
            self.compiler.stage_3_available_tools()
            self.msg_queue.put(("progress", 50))

            # Stage 4
            print("   [3/4] Composing final execution plan...")
            self.msg_queue.put(("detail", "Stage 4: Composing final execution plan..."))
            self.current_plan = self.compiler.stage_4_final_execution(self.user_goal)
            self.msg_queue.put(("progress", 100))

            print("   [4/4] Plan ready for review.")
            print("\n📋 COMPILED PLAN:")
            print(json.dumps(self.current_plan, indent=2))
            print("-" * 20)

            self.msg_queue.put(("state_change", "REVIEW"))
        except Exception as e:
            print(f"   ❌ COMPILATION ERROR: {e}")
            self.msg_queue.put(("error", str(e)))

    def start_execution(self):
        self.execution_state = "RUNNING"
        self.go_btn.config(state=tk.DISABLED, text="Executing...")
        self.stop_btn.config(state=tk.NORMAL)
        self.current_block_idx = 0
        self.completed_steps = []
        toolbox_logger.clear_log()
        
        print("\n🚀 STARTING EXECUTION")
        # Ensure focus is away from HUD
        self.switch_focus()
        threading.Thread(target=self._execution_loop).start()

    def switch_focus(self):
        """Returns focus to the previous application."""
        print("   🖱️ Switching focus back to workspace...")
        if sys.platform == "darwin":
            pyautogui.keyDown('command')
            time.sleep(0.1)
            pyautogui.press('tab')
            time.sleep(0.1)
            pyautogui.keyUp('command')
        else:
            pyautogui.keyDown('alt')
            time.sleep(0.1)
            pyautogui.press('tab')
            time.sleep(0.1)
            pyautogui.keyUp('alt')
        time.sleep(0.5) # Wait for animation

    def _execution_loop(self):
        """Executes the plan from Stage 4 block by block."""
        try:
            plan = self.current_plan
            session_context = {"last_read": ""} # Persistent context for the whole run
            
            for i, step in enumerate(plan):
                if self.stop_event.is_set():
                    print("\n⚠️ EXECUTION PAUSED FOR FEEDBACK")
                    self.msg_queue.put(("ask_feedback", "Execution stopped by user."))
                    return

                action = step.get("action") or list(step.keys())[0]
                print(f"👉 Step {i+1}/{len(plan)}: {action} | {step}")
                
                self.msg_queue.put(("status", (f"RUNNING STEP {i+1}/{len(plan)}", "#00BFFF")))
                self.msg_queue.put(("detail", f"Action: {action}\nData: {json.dumps(step)}"))
                
                # Execute with persistent context
                toolbox_logger.log_action(action, step)
                success = client_app.execute_step(action, step, context=session_context)
                toolbox_logger.log_result(success)
                
                if success:
                    self.completed_steps.append(step)
                else:
                    print(f"   ❌ STEP FAILED: {action}")
                    self.msg_queue.put(("ask_feedback", f"Step {i+1} failed: {action}"))
                    return
                
                time.sleep(0.5)

            print("\n✅ EXECUTION LOOP FINISHED")
            self.msg_queue.put(("state_change", "VERIFYING"))
        except Exception as e:
            print(f"   ❌ EXECUTION ERROR: {e}")
            self.msg_queue.put(("error", str(e)))

    def run_fix(self, feedback):
        self.execution_state = "COMPILING"
        self.go_btn.config(state=tk.DISABLED, text="Planning...")
        self.set_status("🔄 RE-PLANNING FIX...", "#FFD700")
        print("\n🧠 SURGICAL RE-PLANNING INITIATED")
        threading.Thread(target=self._fix_thread, args=(feedback,)).start()

    def _fix_thread(self, feedback):
        try:
            toolbox_logger.log_feedback(feedback)
            # Stage 5
            print("   [1/1] Generating corrective plan based on feedback...")
            new_remaining_plan = self.compiler.stage_5_surgical_fix(self.user_goal, feedback, self.completed_steps)
            if new_remaining_plan:
                # We overwrite the current plan with the fix
                self.current_plan = new_remaining_plan 
                self.completed_steps = [] # RESET HISTORY so the trace stays clean
                print("\n📋 NEW CORRECTIVE PLAN (Full Sequence):")
                print(json.dumps(self.current_plan, indent=2))
                print("-" * 20)
                # Reset stop event so we can run again
                self.stop_event.clear()
                # Ensure focus is back to workspace
                self.switch_focus()
                self.msg_queue.put(("state_change", "REVIEW"))
            else:
                print("   ❌ FIX GENERATION FAILED")
                self.msg_queue.put(("error", "Failed to generate fix plan."))
        except Exception as e:
            print(f"   ❌ FIX ERROR: {e}")
            self.msg_queue.put(("error", str(e)))

    # --- UI SYNC ---

    def _check_queue(self):
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                if msg_type == "status":
                    self.set_status(content[0], content[1])
                elif msg_type == "detail":
                    self.set_detail(content)
                elif msg_type == "progress":
                    self.progress['value'] = content
                elif msg_type == "state_change":
                    self.execution_state = content
                    if content == "REVIEW":
                        self.set_status("PLAN READY. CLICK START.", "#32CD32")
                        self.go_btn.config(state=tk.NORMAL, text="START", bg="#32CD32")
                        self.stop_btn.config(state=tk.DISABLED)
                    elif content == "VERIFYING":
                        self.set_status("FINISHED. DID IT WORK? (y/n):", "#FFD700")
                        self.go_btn.config(text="YES/NO", state=tk.NORMAL, bg="#FFD700")
                        self.input_entry.focus()
                elif msg_type == "ask_feedback":
                    self.execution_state = "FIXING"
                    self.set_status("STOPPED. ENTER FEEDBACK:", "#FF4500")
                    self.detail_label.config(text=content)
                    self.go_btn.config(state=tk.NORMAL, text="FIX", bg="#FFD700")
                    self.stop_btn.config(state=tk.DISABLED)
                    self.input_entry.focus()
                elif msg_type == "finish":
                    self.on_finish(content)
                elif msg_type == "error":
                    messagebox.showerror("Error", content)
                    self.on_finish(False)
        except queue.Empty:
            pass
        finally:
            # Check every 100ms
            self.root.after(100, self._check_queue)

    def on_finish(self, success):
        self.execution_state = "IDLE"
        self.go_btn.config(state=tk.NORMAL, text="GO", bg="#32CD32")
        self.stop_btn.config(state=tk.DISABLED)
        self.progress['value'] = 0
        
        if success:
            self.set_status("✅ TASK COMPLETE", "#32CD32")
            print("\n" + "="*40)
            print("✨ TASK ACHIEVED")
            print("="*40)
            # Stage 6: Generalize and Save
            print("   🧠 Running Stage 6: Collective Learning...")
            threading.Thread(target=self.compiler.stage_6_generalize, args=(self.user_goal, self.completed_steps)).start()
        else:
            self.set_status("READY", "#00BFFF")

if __name__ == "__main__":

    root = tk.Tk()

    app = AgentHUDV3(root)

    root.mainloop()
