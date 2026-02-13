import tkinter as tk
from tkinter import messagebox, simpledialog
import threading
import queue
import time
import json
import sys
import pyautogui
import toolbox_agent
import toolbox_logger # NEW

class ToolboxHUDV2:
    """
    Refactored State Machine GUI for stable Tool-based execution.
    States: READY, PLANNING, REVIEW, EXECUTING, VERIFYING, FIXING, SAVING
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Groq Toolbox HUD v2")
        self.root.geometry("600x180+50+50")
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#121212")

        # --- AGENT ENGINE ---
        self.agent = toolbox_agent.ToolboxAgent()
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()

        # --- STATE DATA ---
        self.user_goal = ""
        self.high_level_plan = [] # List of Tools/PrimitiveBlocks
        self.current_block_index = 0
        self.execution_history = [] # List of lists (one per block)
        self.state = "READY"

        # --- UI ELEMENTS ---
        self._build_ui()
        self._check_queue()
        
        self.log("HUD v2 Initialized. Enter Goal.", "info")

    def _build_ui(self):
        # 1. Header (Status & Stop)
        self.header_frame = tk.Frame(self.root, bg="#121212")
        self.header_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.status_label = tk.Label(self.header_frame, text="Ready.", bg="#121212", fg="#00BFFF", font=("Consolas", 11, "bold"), anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.stop_btn = tk.Button(self.header_frame, text="🛑 STOP", command=self.on_stop_clicked, bg="#FF4500", fg="white", font=("Arial", 10, "bold"), width=10, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT)

        # 2. Detail Area (Current Step Info)
        self.detail_label = tk.Label(self.root, text="", bg="#1E1E1E", fg="#90EE90", font=("Consolas", 9), anchor="w", justify=tk.LEFT, wraplength=580, height=3)
        self.detail_label.pack(fill=tk.X, padx=10, pady=5)

        # 3. Footer (Input & GO)
        self.footer_frame = tk.Frame(self.root, bg="#121212")
        self.footer_frame.pack(fill=tk.X, padx=10, pady=10)

        self.input_entry = tk.Entry(self.footer_frame, bg="#333333", fg="white", insertbackground="white", font=("Arial", 12), relief=tk.FLAT)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5)
        self.input_entry.bind("<Return>", lambda e: self.on_go_clicked())
        self.input_entry.focus()

        self.go_btn = tk.Button(self.footer_frame, text="🚀 GO", command=self.on_go_clicked, bg="#32CD32", fg="white", font=("Arial", 11, "bold"), width=15)
        self.go_btn.pack(side=tk.RIGHT)

    # --- STATE HANDLERS ---

    def set_state(self, new_state, status_text=None, color=None):
        self.state = new_state
        if status_text:
            self.status_label.config(text=status_text)
        if color:
            self.status_label.config(fg=color)
        
        # Adjust button visibility
        if new_state == "READY":
            self.go_btn.config(text="🚀 GO", state=tk.NORMAL, bg="#32CD32")
            self.stop_btn.config(state=tk.DISABLED)
        elif new_state == "PLANNING":
            self.go_btn.config(text="Wait...", state=tk.DISABLED, bg="#555555")
            self.stop_btn.config(state=tk.DISABLED)
        elif new_state == "REVIEW":
            self.go_btn.config(text="▶ START", state=tk.NORMAL, bg="#32CD32")
            self.stop_btn.config(state=tk.DISABLED)
        elif new_state == "EXECUTING":
            self.go_btn.config(text="Running...", state=tk.DISABLED, bg="#555555")
            self.stop_btn.config(state=tk.NORMAL)
        elif new_state == "VERIFYING":
            self.go_btn.config(text="NEXT TOOL >", state=tk.NORMAL, bg="#32CD32")
            self.stop_btn.config(state=tk.DISABLED)
        elif new_state == "FIXING":
            self.go_btn.config(text="🔧 FIX", state=tk.NORMAL, bg="#FFD700")
            self.stop_btn.config(state=tk.DISABLED)

    def log(self, msg, type="info"):
        """Prints formatted logs to terminal."""
        prefix = "[HUD]"
        if type == "error": prefix = "❌ [ERROR]"
        elif type == "success": prefix = "✅ [SUCCESS]"
        elif type == "plan": prefix = "🧠 [PLAN]"
        print(f"{prefix} {msg}")

    # --- UI INTERACTION ---

    def on_go_clicked(self):
        if self.state == "READY":
            goal = self.input_entry.get().strip()
            if not goal: return
            self.user_goal = goal
            self.input_entry.delete(0, tk.END)
            self.start_planning()
        
        elif self.state == "REVIEW":
            self.start_execution()
            
        elif self.state == "VERIFYING":
            self.move_to_next_block()
            
        elif self.state == "FIXING":
            feedback = self.input_entry.get().strip()
            if not feedback: return
            self.input_entry.delete(0, tk.END)
            self.start_fix(feedback)

    def on_stop_clicked(self):
        self.stop_event.set()
        self.log("Manual stop requested.", "error")
        # Trigger feedback manually
        self.root.after(100, self.ask_feedback)

    # --- LOGIC THREADS ---

    def start_planning(self):
        toolbox_logger.clear_log() # Clear previous session history
        self.set_state("PLANNING", "🧠 Analyzing Goal...", "#FFD700")
        self.detail_label.config(text="Decomposing into Tools/Blocks...")
        self.current_block_index = 0
        self.execution_history = []
        
        threading.Thread(target=self._plan_thread).start()

    def _plan_thread(self):
        try:
            plan = self.agent.decompose_goal(self.user_goal)
            if plan:
                self.high_level_plan = plan
                # Initialize execution history slots
                self.execution_history = [[] for _ in range(len(plan))]
                self.log(f"Plan Decomposed:\n{json.dumps(plan, indent=2)}", "plan")
                self.msg_queue.put(("transition", "REVIEW"))
            else:
                self.msg_queue.put(("error", "Failed to generate plan."))
        except Exception as e:
            self.msg_queue.put(("error", f"Planning Error: {e}"))

    def start_execution(self):
        self.set_state("EXECUTING", f"Running Block {self.current_block_index+1}...", "#00BFFF")
        self.stop_event.clear()
        threading.Thread(target=self._execution_thread).start()

    def switch_focus(self):
        """Switches focus to the last active window (Cmd+Tab / Alt+Tab)."""
        self.log("Switching focus to target app...", "info")
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

    def _execution_thread(self):
        try:
            # 0. Ensure Focus is NOT on HUD
            self.switch_focus()
            
            block = self.high_level_plan[self.current_block_index]
            self.log(f"Starting Block: {block.get('name') or block.get('description')}")
            
            # 1. Expand
            if block.get("action") == "call_tool":
                steps = self.agent.expand_tool(block["name"], block.get("params", {}))
            else:
                steps = self.agent.expand_primitive(block)
            
            if not steps:
                self.msg_queue.put(("error", "Failed to expand block steps."))
                return

            # Temporary storage for this block's run
            block_steps = []

            # 2. Loop through steps
            for i, step in enumerate(steps):
                if self.stop_event.is_set(): return
                
                # SAFE LOGGING: Handle both dict and str steps
                if isinstance(step, dict):
                    action_name = step.get("action") or step.get("tool") or list(step.keys())[0]
                else:
                    action_name = str(step).split("(")[0]
                
                self.msg_queue.put(("detail", f"Step {i+1}/{len(steps)}: {action_name}"))
                
                # LOG ACTION
                toolbox_logger.log_action(action_name, step)
                
                success = self.agent.execute_step(step)
                
                # LOG RESULT
                toolbox_logger.log_result(success)

                if success:
                    block_steps.append(step)
                else:
                    self.log(f"Step Failed: {step}", "error")
                    self.msg_queue.put(("ask_feedback", None)) # Trigger FIXING loop
                    return # Exit this specific execution thread, but stay in the task
                
                time.sleep(0.5)
            
            # 3. Success! Store steps for this block index
            if len(self.execution_history) <= self.current_block_index:
                self.execution_history.append(block_steps)
            else:
                self.execution_history[self.current_block_index] = block_steps

            # 4. Finish Block
            self.msg_queue.put(("ask_verification", None))
            
        except Exception as e:
            self.msg_queue.put(("error", f"Exec Error: {e}"))

    def ask_verification(self):
        if self.current_block_index >= len(self.high_level_plan):
            return

        block_name = self.high_level_plan[self.current_block_index].get("name") or "Primitive Block"
        ans = messagebox.askyesno("Verify", f"Did Tool/Block '{block_name}' work perfectly?")
        
        if ans:
            self.set_state("VERIFYING", f"Block {self.current_block_index+1} SUCCESS.", "#32CD32")
            self.detail_label.config(text="Click 'NEXT TOOL' to continue or 'STOP' to finish early.")
        else:
            self.ask_feedback()

    def move_to_next_block(self):
        self.current_block_index += 1
        if self.current_block_index >= len(self.high_level_plan):
            self.finalize_task()
        else:
            self.start_execution()

    def ask_feedback(self):
        self.set_state("FIXING", "🛑 Block Failed. What went wrong?", "#FF4500")
        self.detail_label.config(text="Describe the issue below (e.g. 'Open new tab first').")
        self.input_entry.focus()

    def start_fix(self, feedback):
        toolbox_logger.log_feedback(feedback) # Log feedback for AI
        self.log(f"Feedback for Block {self.current_block_index+1}: {feedback}", "error")
        self.set_state("PLANNING", "🔄 Surgical Re-planning...", "#FFD700")
        
        threading.Thread(target=self._fix_thread, args=(feedback,)).start()

    def _fix_thread(self, feedback):
        try:
            # Plan replacement for REMAINING steps
            new_remaining = self.agent.plan_fix(
                self.user_goal, 
                self.high_level_plan, 
                self.current_block_index, 
                feedback
            )
            
            if new_remaining:
                self.log(f"New Remaining Plan:\n{json.dumps(new_remaining, indent=2)}", "plan")
                # Update plan stack
                self.high_level_plan = self.high_level_plan[:self.current_block_index] + new_remaining
                
                # Resize execution history slots to match new plan length
                self.execution_history = self.execution_history[:self.current_block_index] + [[] for _ in range(len(new_remaining))]
                
                # Transition back to REVIEW so user can see the fix
                self.msg_queue.put(("transition", "REVIEW"))
            else:
                self.msg_queue.put(("error", "Surgical re-planning failed."))
        except Exception as e:
            self.msg_queue.put(("error", f"Fix Error: {e}"))

    def finalize_task(self):
        self.set_state("SAVING", "✅ ALL DONE! Finalizing...", "#32CD32")
        self.log("Task successful! Running auto-learn...", "success")
        
        # Flatten history
        final_trace = [step for block in self.execution_history for step in block]
        
        # Save to DB in background
        threading.Thread(target=self.agent.consolidate_and_save, args=(self.user_goal, final_trace)).start()
        
        self.root.after(2000, lambda: self.set_state("READY", "Success! Enter new Goal:", "#32CD32"))

    # --- QUEUE MONITOR ---

    def _check_queue(self):
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                if msg_type == "transition":
                    if content == "REVIEW": self.set_state("REVIEW", "Plan Ready. Review in Terminal.", "#FFD700")
                elif msg_type == "detail":
                    self.detail_label.config(text=content)
                elif msg_type == "ask_verification":
                    self.ask_verification()
                elif msg_type == "error":
                    self.log(content, "error")
                    self.set_state("READY", f"Error: {content[:30]}...", "#FF4500")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self._check_queue)

if __name__ == "__main__":
    root = tk.Tk()
    hud = ToolboxHUDV2(root)
    root.mainloop()