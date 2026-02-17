# 🛠️ Toolbox V3 (Version 1.3): The Context-Aware Agent

## 📜 History & Evolution

### **Version 1.2 (The Multi-Stage Compiler)**
*   **Goal:** Move from "One-Shot" planning to a structured reasoning pipeline using 6 JSON stages.
*   **Innovations:** `1.json` to `6.json`, Paper Trail, Multi-Model Tiering.
*   **Problems Faced:**
    *   **Context Loss:** AI often forgot the active browser when moving between blocks (e.g., switching to Chrome in the middle of a Brave session).
    *   **Focus Stealing:** The HUD window stayed focused, causing keystrokes to land in the agent's own GUI instead of the target app.
    *   **Hallucination:** LLM used its own placeholders like `{{price}}` instead of the system variable `$LAST_READ`.

### **Version 1.2.1 (The Surgical Fix)**
*   **Changes:**
    *   **Ground Truth Logger:** Implemented `session_log.txt`. The agent now reads this file to understand the "Reality" of the session before re-planning.
    *   **Dynamic Variable Shield:** Updated `client_app.py` to hard-catch ANY curly braces `{{ }}` and replace them with the actual $LAST_READ value.
    *   **Focus Switcher:** The GUI now triggers a `Command+Tab` (Mac) or `Alt+Tab` (Win) before every block execution to return focus to the work environment.

### **Version 1.2.2 (Browser Robustness)**
*   **Changes:**
    *   **`navigate(url)` Tool:** Replaced raw address-bar typing with an atomic tool.
    *   **History Bypass:** The `navigate` tool now types a **Space** after the URL to stop browsers from auto-suggesting history items.

---

## 🚀 Toolbox V3: V1.3 Goals (The Context-Aware Agent)

### **The Problems We Are Solving Now:**
1.  **Contextual Blindness:** The agent sees "Tim Cook" on Google but doesn't know which link is Twitter vs Wikipedia. It clicks the first one it sees.
2.  **HUD Reflection:** The OCR often "sees" its own terminal logs or GUI buttons and clicks on itself (Ghost Interactions).
3.  **Spatial Relation Deficiency:** The AI cannot currently say "Click the button *next to* this text."

### **V1.3 Key Features:**
1.  **Anchor-Based Clicking:** New primitive `click_near(target, anchor)`. Find "Tim Cook" closest to "x.com".
2.  **Environment Self-Awareness:** Update vision modules to **Ignore the HUD and Terminal** processes.
3.  **Intent Compilation:** Move more complex human behaviors (like "Search in YouTube") into robust Python Power Primitives.
