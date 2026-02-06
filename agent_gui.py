import tkinter as tk
import threading
import queue
import time
import json
import universal_agent

class MinimalAgentGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Groq HUD")
        self.root.geometry("600x180+50+50") # Taller for details
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#121212")

        # --- STATE ---
        self.agent = universal_agent.UniversalAgent()
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.completed_steps = []
        self.planned_steps = []
        self.current_step_index = 0
        self.user_goal = ""
        self.feedback_history = ""
        self.state = "READY" 

        # --- UI LAYOUT ---
        
        # 1. Status Bar (Top)
        self.status_frame = tk.Frame(root, bg="#121212")
        self.status_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.status_label = tk.Label(self.status_frame, text="Ready. Enter Goal:", bg="#121212", fg="#00BFFF", font=("Consolas", 11, "bold"), anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.stop_btn = tk.Button(self.status_frame, text="🛑 STOP", command=self.stop_task, bg="#FF4500", fg="white", font=("Arial", 10, "bold"), width=8, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT)

        # 2. Detail Area (Middle) - Shows Full JSON of current step
        self.detail_label = tk.Label(root, text="", bg="#1E1E1E", fg="#90EE90", font=("Consolas", 9), anchor="w", justify=tk.LEFT, wraplength=580)
        self.detail_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 3. Action Bar (Bottom)
        self.input_frame = tk.Frame(root, bg="#121212")
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.input_entry = tk.Entry(self.input_frame, bg="#333333", fg="white", insertbackground="white", font=("Arial", 12), relief=tk.FLAT)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5)
        # Bind Enter only when allowed
        self.input_entry.bind("<Return>", lambda e: self.handle_submit())
        self.input_entry.focus()

        self.go_btn = tk.Button(self.input_frame, text="🚀 PLAN", command=self.handle_submit, bg="#32CD32", fg="white", font=("Arial", 11, "bold"), width=12)
        self.go_btn.pack(side=tk.RIGHT)

        self.check_queue()

    def set_status(self, text, color="#00BFFF"):
        self.status_label.config(text=text, fg=color)

    def set_detail(self, text):
        self.detail_label.config(text=text)

    def check_queue(self):
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                if msg_type == "status":
                    self.set_status(content[0], content[1])
                elif msg_type == "detail":
                    self.set_detail(content)
                elif msg_type == "finish":
                    self.on_finish(content)
                elif msg_type == "review_plan":
                    self.on_review_plan(content)
                elif msg_type == "ask_feedback":
                    self.ask_feedback()
                elif msg_type == "step_done":
                    self.on_step_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def handle_submit(self):
        text = self.input_entry.get().strip()
        
        # Disable double-clicks
        if self.go_btn['state'] == tk.DISABLED: return

        if self.state == "READY":
            if not text: return
            self.start_task(text)
        elif self.state == "REVIEW":
            self.start_execution()
        elif self.state == "EXECUTING":
            self.execute_next_step()
        elif self.state == "FEEDBACK":
            if not text: return
            self.submit_feedback(text)

    # --- PHASE 1: PLANNING ---

    def start_task(self, goal):
        self.user_goal = goal
        self.input_entry.delete(0, tk.END)
        self.state = "PLANNING"
        self.go_btn.config(state=tk.DISABLED, bg="#555555", text="Wait...")
        self.set_status("🧠 Planning...", "#FFD700")
        self.set_detail("Consulting Universal Agent...")
        
        print(f"\n📝 User Goal: {goal}")
        threading.Thread(target=self.run_planning_logic, args=(goal,)).start()

    def run_planning_logic(self, goal, is_fix=False):
        try:
            prev_steps = self.completed_steps if is_fix else None
            
            print("   🤔 Sending request to Universal Agent...")
            plan_data = self.agent.plan_task(goal, self.feedback_history, prev_steps)
            
            steps = []
            if plan_data:
                steps = plan_data if isinstance(plan_data, list) else plan_data.get("plan") or plan_data.get("actions") or []

            if not steps:
                print("❌ ERROR: Agent returned empty plan.")
                self.msg_queue.put(("status", ("❌ Plan failed.", "#FF4500")))
                self.msg_queue.put(("finish", False))
                return
            
            print(f"   ✅ Plan Generated ({len(steps)} steps):")
            print(json.dumps(steps, indent=2))
            
            self.planned_steps = steps
            self.msg_queue.put(("review_plan", steps))
        except Exception as e:
            print(f"❌ Planning Error: {e}")
            self.msg_queue.put(("status", (f"Error: {e}", "#FF4500")))
            self.msg_queue.put(("finish", False))

    def on_review_plan(self, steps):
        self.state = "REVIEW"
        self.current_step_index = 0
        
        first_step = steps[0]
        first_action = first_step.get("action")
        
        self.set_status(f"Plan Ready ({len(steps)} steps).", "#FFD700")
        self.set_detail(f"First Step: {json.dumps(first_step)}")
        self.go_btn.config(text="▶ START", state=tk.NORMAL, bg="#32CD32")

    # --- PHASE 2: STEP-BY-STEP EXECUTION ---

    def start_execution(self):
        self.state = "EXECUTING"
        self.stop_btn.config(state=tk.NORMAL)
        self.execute_next_step()

    def execute_next_step(self):
        if self.current_step_index >= len(self.planned_steps):
            self.msg_queue.put(("finish", True))
            return

        step = self.planned_steps[self.current_step_index]
        
        # UPDATE UI: Show full JSON of step
        self.set_status(f"Running Step {self.current_step_index+1}/{len(self.planned_steps)}...", "#00BFFF")
        self.set_detail(json.dumps(step))
        
        # Disable button to prevent rapid-fire
        self.go_btn.config(text="RUNNING...", state=tk.DISABLED, bg="#555555")
        
        # Run in thread
        threading.Thread(target=self.run_single_step, args=(step,)).start()

    def run_single_step(self, step):
        try:
            print(f"👉 Executing: {step}")
            success = self.agent.execute_step(step)
            
            if success:
                self.completed_steps.append(step)
                self.msg_queue.put(("step_done", None))
            else:
                print("   ❌ Step Failed.")
                self.msg_queue.put(("ask_feedback", None))
        except Exception as e:
            print(f"❌ Execution Error: {e}")
            self.msg_queue.put(("ask_feedback", None))

    def on_step_done(self):
        self.current_step_index += 1
        if self.current_step_index >= len(self.planned_steps):
            self.on_finish(True)
        else:
            # Ready for next step
            next_step = self.planned_steps[self.current_step_index]
            self.set_status(f"Step {self.current_step_index} Done.", "#32CD32")
            self.set_detail(f"Next: {json.dumps(next_step)}")
            self.go_btn.config(text="NEXT STEP >", state=tk.NORMAL, bg="#32CD32")

    # --- FEEDBACK LOOP ---

    def stop_task(self):
        self.stop_event.set()
        self.stop_btn.config(state=tk.DISABLED)
        self.ask_feedback()

    def ask_feedback(self):
        self.state = "FEEDBACK"
        self.set_status("🛑 Paused/Failed. What happened?", "#FF4500")
        self.set_detail("Type your feedback below to fix the plan.")
        self.input_entry.delete(0, tk.END)
        self.input_entry.focus()
        self.go_btn.config(text="🔧 FIX", state=tk.NORMAL, bg="#FFD700")
        self.stop_btn.config(state=tk.DISABLED)

    def submit_feedback(self, feedback):
        print(f"\n🔄 Feedback: {feedback}")
        self.feedback_history += f"\nStep {self.current_step_index+1} Failed. User: {feedback}"
        self.input_entry.delete(0, tk.END)
        
        self.set_status("🔄 Re-Planning...", "#FFD700")
        self.set_detail("Consulting Agent...")
        self.go_btn.config(state=tk.DISABLED, bg="#555555")
        
        # Re-plan from where we left off
        threading.Thread(target=self.run_planning_logic, args=(self.user_goal, True)).start()

    def on_finish(self, success):
        self.state = "READY"
        self.go_btn.config(text="NEW GOAL", state=tk.NORMAL, bg="#32CD32")
        self.stop_btn.config(state=tk.DISABLED)
        if success:
            self.set_status("✅ All Steps Done!", "#32CD32")
            self.set_detail("Saving perfect plan to Cloud Memory...")
            print("   🧠 Optimizing & Saving to Cloud...")
            threading.Thread(target=self.agent.summarize_and_save, args=(self.user_goal, self.completed_steps)).start()
        else:
            self.set_status("❌ Stopped.", "#FF4500")
            self.set_detail("Enter new goal.")
        
        self.completed_steps = []
        self.feedback_history = ""
        self.current_step_index = 0

if __name__ == "__main__":
    root = tk.Tk()
    gui = MinimalAgentGUI(root)
    root.mainloop()
