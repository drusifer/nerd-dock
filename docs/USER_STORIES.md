# User Stories — Nerd-Dock

**Author:** Cypher (Product Manager)  
**Date:** 2026-05-20  

---

### **US-1: System Tray Indicator Applet & Visual Decorations**
*As a writer who dictates frequently, I want a highly visible, state-decorated tray icon in my GNOME top panel, so that I can see the exact state of my dictation tool at a glance and quickly trigger commands.*

- **Acceptance Criteria:**
  - An Ayatana AppIndicator icon is instantiated in the top panel.
  - The icon dynamically updates according to system state:
    - **Gray microphone:** State is `STOPPED`. Hover tooltip: "Nerd-Dictation: Stopped (Ready)".
    - **Glowing red microphone:** State is `RECORDING`. Hover tooltip: "Nerd-Dictation: Recording...". Fires system desktop notification upon activation.
    - **Orange/amber pause icon:** State is `SUSPENDED`. Hover tooltip: "Nerd-Dictation: Paused (Muted)".
  - Right-clicking the tray icon opens a structured dropdown menu.
  - Menu options include: **Start Dictation**, **Pause Dictation**, **Resume Dictation**, **Stop Dictation**, and **Quit**.
  - Selecting any menu option invokes the corresponding `nerd-dictation` command immediately.
  - Menu items are contextually greyed out/disabled based on state (e.g., cannot pause if already stopped).

---

### **US-2: Global State Auto-Synchronization**
*As a user who triggers dictation via keyboard shortcuts or CLI terminal, I want the Nerd-Dock widgets to stay perfectly synchronized in real-time, so that my visual status indicators are never out-of-date.*

- **Acceptance Criteria:**
  - A background monitor loop runs every 250ms thread-safely.
  - The loop checks the existence and content of `/tmp/nerd-dictation.cookie` to detect external triggers.
  - The loop verifies process existence for the PID written in the cookie to handle abrupt crashes gracefully.
  - UI icons, menus, and tooltips update automatically within 300ms of any external trigger.

---

### **US-3: Makefile Linting & Static Analysis Suite**
*As a developer, I want build targets for a comprehensive set of linting and static analysis tools, so that I can easily verify code style, complexity, duplication, dead code, and security issues.*

- **Acceptance Criteria:**
  - Root `Makefile.prj` has a comprehensive `make lint` target containing:
    - **Style:** `ruff check` and `ruff format` to verify styling and import sorting.
    - **Complexity:** `radon cc` with McCabe complexity limits.
    - **Dead Code:** `vulture` scanning for unused methods and variables.
    - **Security:** `bandit` checking for common Python security weaknesses.
    - **Duplication:** `pylint --disable=all --enable=duplicate-code` scanning for duplicate code blocks.
  - Running `make lint` executes all linters and fails the build on any violations.

---

### **US-4: Robust Mock-Based Test Harness**
*As an SDET, I want to verify the application logic without needing active microphones or a running display server, so that unit tests can run head-lessly in CI environment.*

- **Acceptance Criteria:**
  - Unit tests mock all subprocess execution calls for `/home/drusifer/.local/bin/nerd-dictation`.
  - Unit tests mock file system calls for `/tmp/nerd-dictation.cookie`.
  - System test coverage matches at least 80% of `controller.py` and `monitor.py` logic.
