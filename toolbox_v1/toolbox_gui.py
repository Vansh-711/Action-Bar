import tkinter as tk
from tkinter import messagebox, simpledialog
import threading
import queue
import time
import json
import toolbox_agent

class ToolboxGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Groq Toolbox HUD")
        self.root.geometry("600x200+50+50")
        self.root.attributes('-topmost', True)
        self.root.configure(bg="#121212")

        # --- STATE ---
        self.agent = toolbox_agent.ToolboxAgent()
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.user_goal = ""
        self.high_level_plan = []
        self.current_tool_index = 0
        self.full_execution_trace = []
        self.state = "READY" # READY, PLANNING, EXECUTION, VERIFICATION

        # --- UI ---
        self.status_frame = tk.Frame(root, bg="#121212")
        self.status_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.status_label = tk.Label(self.status_frame, text="Ready. Enter Goal:", bg="#121212", fg="#00BFFF", font=("Consolas", 11, "bold"), anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.stop_btn = tk.Button(self.status_frame, text="🛑 STOP", command=self.stop_task, bg="#FF4500", fg="white", font=("Arial", 9, "bold"), width=8, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.RIGHT)

        self.detail_label = tk.Label(root, text="", bg="#1E1E1E", fg="#90EE90", font=("Consolas", 9), anchor="w", justify=tk.LEFT, wraplength=580)
        self.detail_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.input_frame = tk.Frame(root, bg="#121212")
        self.input_frame.pack(fill=tk.X, padx=10, pady=10)

        self.input_entry = tk.Entry(self.input_frame, bg="#333333", fg="white", insertbackground="white", font=("Arial", 12), relief=tk.FLAT)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10), ipady=5)
        self.input_entry.bind("<Return>", lambda e: self.handle_submit())
        self.input_entry.focus()

        self.go_btn = tk.Button(self.input_frame, text="🚀 GO", command=self.handle_submit, bg="#32CD32", fg="white", font=("Arial", 11, "bold"), width=15)
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
                if msg_type == "status": self.set_status(content[0], content[1])
                elif msg_type == "detail": self.set_detail(content)
                elif msg_type == "finish": self.on_task_finish(content)
                elif msg_type == "verify_tool": self.verify_tool_execution()
        except queue.Empty: pass
        finally: self.root.after(100, self.check_queue)

    def handle_submit(self):
        text = self.input_entry.get().strip()
        if self.go_btn['state'] == tk.DISABLED: return

        if self.state == "READY":
            if not text: return
            self.user_goal = text
            self.input_entry.delete(0, tk.END)
            self.start_planning()
        elif self.state == "EXECUTION":
            self.run_current_tool()

    def start_planning(self):
        self.state = "PLANNING"
        self.set_status("🧠 Decomposing Goal...", "#FFD700")
        self.go_btn.config(state=tk.DISABLED, bg="#555555")
        self.current_tool_index = 0
        self.full_execution_trace = []
        threading.Thread(target=self.do_planning).start()

    def do_planning(self):
        print(f"\n🧠 [PLANNER] Analyzing Goal: '{self.user_goal}'")
        plan = self.agent.decompose_goal(self.user_goal)
        if not plan:
            print("❌ [PLANNER] Failed to generate plan.")
            self.msg_queue.put(("status", ("❌ Planning failed.", "#FF4500")))
            self.msg_queue.put(("finish", False))
            return
        
        print(f"✅ [PLANNER] Plan Generated:\n{json.dumps(plan, indent=2)}")
        self.high_level_plan = plan
        self.msg_queue.put(("status", (f"Plan Ready: {len(plan)} Tools/Blocks", "#32CD32")))
        self.msg_queue.put(("detail", f"Next: {json.dumps(plan[0])}"))
        self.state = "EXECUTION"
        self.root.after(100, lambda: self.go_btn.config(text="▶ RUN TOOL", state=tk.NORMAL, bg="#32CD32"))

    def run_current_tool(self):
        if self.current_tool_index >= len(self.high_level_plan):
            self.msg_queue.put(("finish", True))
            return

        self.go_btn.config(state=tk.DISABLED, bg="#555555")
        self.stop_btn.config(state=tk.NORMAL)
        threading.Thread(target=self.do_tool_execution).start()

    def do_tool_execution(self):
        block = self.high_level_plan[self.current_tool_index]
        action = block.get("action")
        
        print(f"\n🚀 [EXECUTOR] Starting Block {self.current_tool_index+1}: {block.get('name') or block.get('description')}")

        # 1. Expand Block to Raw Steps
        if action == "call_tool":
            print(f"   🔧 Expanding Tool: {block['name']}...")
            steps = self.agent.expand_tool(block["name"], block.get("params", {}))
        else:
            print(f"   🔧 Expanding Primitive Block...")
            steps = self.agent.expand_primitive(block)

        if not steps:
            print("   ❌ Expansion failed.")
            self.msg_queue.put(("status", ("❌ Expansion failed.", "#FF4500")))
            self.msg_queue.put(("finish", False))
            return

        print(f"   📋 Execution Trace ({len(steps)} steps):")

        # 2. Execute All Steps in Block
        for i, step in enumerate(steps):
            if self.stop_event.is_set(): 
                print("   🛑 Execution Aborted.")
                return
            
            print(f"   👉 {i+1}/{len(steps)}: {step}")
            self.msg_queue.put(("status", (f"Tool {self.current_tool_index+1}: Step {i+1}/{len(steps)}", "#00BFFF")))
            self.msg_queue.put(("detail", json.dumps(step)))
            
            success = self.agent.execute_step(step)
            if success:
                self.full_execution_trace.append(step)
            else:
                print("   ❌ Step Execution Failed.")
                self.msg_queue.put(("status", ("❌ Step failed.", "#FF4500")))
                self.msg_queue.put(("finish", False))
                return
            time.sleep(0.5)

        print("   ✅ Block Completed.")
        self.msg_queue.put(("verify_tool", None))

    def verify_tool_execution(self):
        if self.current_tool_index >= len(self.high_level_plan):
            return # Safety check

        block = self.high_level_plan[self.current_tool_index]
        name = block.get("name") or block.get("description")
        
        ans = messagebox.askyesno("Verify", f"Did Tool/Block '{name}' execute perfectly?")
        if ans:
            self.current_step_index = 0 # Reset local step index
            self.current_tool_index += 1
            if self.current_tool_index >= len(self.high_level_plan):
                self.on_task_finish(True)
            else:
                next_block = self.high_level_plan[self.current_tool_index]
                self.set_status(f"Tool {self.current_tool_index} Done.", "#32CD32")
                self.set_detail(f"Next: {json.dumps(next_block)}")
                self.go_btn.config(text="▶ RUN NEXT TOOL", state=tk.NORMAL, bg="#32CD32")
        else:
            self.ask_for_fix()

    def ask_for_fix(self):
        if self.current_tool_index >= len(self.high_level_plan):
            return

        feedback = simpledialog.askstring("Fix", "What went wrong? Suggest a fix:")
        if feedback:
            print(f"\n🔄 [FIX] User Feedback: {feedback}")
            self.set_status("🔄 Surgically Re-planning...", "#FFD700")
            
            # Request a re-plan of the REMAINING part of the plan
            new_remaining = self.agent.plan_fix(
                self.user_goal, 
                self.high_level_plan, 
                self.current_tool_index, 
                feedback
            )
            
            if new_remaining:
                print(f"✅ [FIX] New Remaining Plan:\n{json.dumps(new_remaining, indent=2)}")
                # Replace the old remaining part with the new one
                self.high_level_plan = self.high_level_plan[:self.current_tool_index] + new_remaining
                # Note: self.current_tool_index remains the same, so run_current_tool will pick up the new block
                self.run_current_tool()
            else:
                print("❌ [FIX] Re-planning failed.")
                self.on_task_finish(False)
        else:
            self.on_task_finish(False)

    def on_task_finish(self, success):
        self.state = "READY"
        self.go_btn.config(text="🚀 GO", state=tk.NORMAL, bg="#32CD32")
        self.stop_btn.config(state=tk.DISABLED)
        
        if success:
            ans = messagebox.askyesno("Save", "Task Complete! Save this workflow as a Golden Tool in SQL?")
            if ans:
                threading.Thread(target=self.agent.consolidate_and_save, args=(self.user_goal, self.full_execution_trace)).start()
            self.set_status("✅ Finished!", "#32CD32")
        else:
            self.set_status("❌ Task Abandoned.", "#FF4500")
        
        self.current_tool_index = 0
        self.high_level_plan = []

    def stop_task(self):
        self.stop_event.set()
        self.on_task_finish(False)

if __name__ == "__main__":
    root = tk.Tk()
    gui = ToolboxGUI(root)
    root.mainloop()