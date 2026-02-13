# 🧠 The Groq Toolbox Architecture: Deep Dive

This document details the complete internal workflow of our current Desktop Agent, explaining every file, function, and decision point in the system.

---

## 1. Core Philosophy: The "LEGO" Model
Unlike traditional agents that generate long scripts for every task, our agent relies on **Composable Tools**.
- **Primitives:** Atomic actions (`click`, `type`, `wait`).
- **Tools:** Reusable sequences of primitives (`open_youtube`, `search_google`).
- **Plans:** A list of Tools.

This approach allows for **Semantic Search**, **Cloud Memory**, and **Surgical Fixing**.

---

## 2. File Structure & Responsibilities

### **A. `toolbox_hud_v2.py` (The Interface)**
This is the "Cockpit" for the user. It uses a **Strict State Machine** to manage the complexity of interaction.

*   **State Machine:**
    *   `READY`: Idle, waiting for input.
    *   `PLANNING`: Background thread is consulting the AI.
    *   `REVIEW`: Plan is ready, waiting for user approval.
    *   `EXECUTING`: Running a block of steps.
    *   `VERIFYING`: Asking user "Did that work?".
    *   `FIXING`: Handling user feedback and re-planning.
*   **Thread Safety:** Uses a `queue.Queue` to pass messages from the AI Worker Thread to the GUI Main Thread. This prevents the GUI from freezing.
*   **Logic:** It does NOT contain AI logic. It only handles display, input, and state transitions. It delegates all thinking to `toolbox_agent.py`.

### **B. `toolbox_agent.py` (The Brain)**
This is the intelligent core that connects the GUI to the LLM and the Database.

*   **`decompose_goal(goal)`:**
    1.  **Search:** Calls `DB.find_relevant_tools(goal)` to get a list of matching "LEGO blocks" from Supabase.
    2.  **Prompt:** Sends Goal + Tool List to Groq (120B).
    3.  **Normalize:** Ensures the output is always a list of high-level blocks (Tools or Primitive Blocks), wrapping raw steps if necessary.
*   **`expand_tool(name)`:**
    *   Fetches the JSON body of a tool from the DB.
    *   **Recursion:** If a tool body contains *another* tool call, it expands that too. This allows for nested skills (e.g., `watch_video` calls `search_video` calls `open_browser`).
*   **`plan_fix(goal, plan, block_index, feedback)`:**
    *   The "Surgical" Re-planner.
    *   Sends the **Full Context** (Main Goal + Original Plan + Failure Point + Tool Definition) to the AI.
    *   Asks it to generate *only* the remaining steps, modifying the failed block based on user feedback.
*   **`execute_step(step)`:**
    *   The "Translator" that converts JSON logic into actual Python function calls (`client_app.py`).
    *   Includes **"Lazy JSON" Handling:** Maps short-hand like `{"press_key": "enter"}` to standard `{"action": "press_key", "params": {"key": "enter"}}`.

### **C. `toolbox_db.py` (The Memory)**
The persistent storage layer.

*   **Hybrid Mode:** Tries to connect to Supabase (Cloud). If keys are missing or network fails, falls back to a local `toolbox_memory.json` file.
*   **`find_relevant_tools(query)`:** Performs a keyword match on tool names/descriptions to filter the thousands of possible tools down to the few relevant ones for the current prompt (RAG).

### **D. `client_app.py` (The Hands)**
The low-level execution engine.

*   **PyAutoGUI:** Handles mouse/keyboard interaction.
*   **Accessibility API (`screen_search.py`):** Uses macOS Accessibility scanning to find UI elements by name (100% accurate) rather than using visual OCR.
*   **OCR (`visual_search.py`):** Fallback vision system.

---

## 3. The Execution Flow (Step-by-Step)

### **Phase 1: Planning**
1.  **User Input:** "Open YT in Brave".
2.  **DB Search:** Finds `open_youtube` tool.
3.  **LLM Router:** "I see `open_youtube`. I will use it."
4.  **Result:** `[{"action": "call_tool", "name": "open_youtube"}]`.

### **Phase 2: Execution & Expansion**
1.  **GUI:** Sees `call_tool`. Calls `agent.expand_tool`.
2.  **Expansion:** `open_youtube` becomes 10 primitive steps (`press cmd+space`, `type Brave`, ...).
3.  **Loop:** The GUI executes Step 1, waits 0.5s, executes Step 2...

### **Phase 3: The "Surgical Fix" (If it fails)**
1.  **Failure:** Step 5 fails (e.g., `cmd+space` didn't open Spotlight).
2.  **User Feedback:** "Spotlight didn't open."
3.  **State Change:** The specific Block in the plan is converted from a rigid `call_tool` to a flexible `primitive_block`.
4.  **Context Injection:** The Agent sends the original tool's body (so the AI sees it *was* trying to use Brave) + the User Feedback to Groq.
5.  **Re-Plan:** Groq generates a new sequence of primitives that includes a fix (e.g., "Wait longer before typing").
6.  **Resume:** The GUI replaces the rest of the plan with this new sequence and resumes execution.

### **Phase 4: Learning (Auto-Save)**
1.  **Success:** User confirms "Job Done."
2.  **Consolidation:** `agent.consolidate_and_save` takes the final, successful execution trace.
3.  **Generalization:** It asks Groq to clean it up ("Remove error steps") and parameterize it (replace specific URL with `{url}`).
4.  **Save:** The new Tool is written to Supabase `toolbox` table.
5.  **Impact:** Next time *any* user asks for this, the optimized tool is used immediately.

---

## 4. Comparison: `toolbox_gui.py` vs `toolbox_hud_v2.py`

| Feature | `toolbox_gui.py` (V1) | `toolbox_hud_v2.py` (V2) |
| :--- | :--- | :--- |
| **State Management** | Loose. Relied on global flags. Prone to `IndexError` when fixing plans. | **Strict State Machine.** Transitions are rigid (Planning -> Review -> Executing). |
| **Execution Flow** | "Run Next Step" button. Hard to follow macro-level progress. | **Block-Based.** Runs a whole Tool, then pauses for verification. |
| **Feedback Loop** | Basic. Just re-ran the block with a new description. | **Surgical.** Fully re-plans the remaining stack with context injection. |
| **Stability** | Moderate. Crashed on "Lazy JSON" or empty plans. | **High.** Includes robust Normalization and Validation layers. |

**Current Status:** `toolbox_hud_v2.py` is the production-ready candidate.
