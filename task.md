# Sprint Backlog — Nerd-Dock Implementation

We have decomposed the **Nerd-Dock** controller utility into **4 short, focused phases**. Each phase is fully independent and contains 3 distinct tasks that take the system from setup through to the completed decorated tray UI and QA gate.

---

## Sprint Goals
- **High-level Objective:** Create a fully functional, premium system-wide top-panel tray indicator for `nerd-dictation` on Ubuntu 26.04, equipped with dynamic icon decorations, tooltip state indicators, and a comprehensive static analysis and testing pipeline.

---

## 📋 Phase 1: Environment Setup & Dev Tools
- [x] **Task 1.1:** Create `pyproject.toml` (PEP 518) and a comprehensive development `Makefile.prj` containing build targets for static analysis: `ruff`, `radon`, `vulture`, `bandit`, and `pylint`.
- [x] **Task 1.2:** Initialize python virtual environment (`venv`) with the `--system-site-packages` flag to link system GObject Introspection bindings.
- [x] **Task 1.3:** Set up headless unit test harness structures under `tests/` with robust mock classes for `subprocess` and `os` file modules.

---

## 📋 Phase 2: Controller & Monitor Core Logic
- [x] **Task 2.1:** Implement `NerdDockController` state machine and safe subprocess execution calls (`begin`, `end`, `suspend`, `resume`, `cancel`).
- [x] **Task 2.2:** Implement `NerdDictationMonitor` background thread watching `/tmp/nerd-dictation.cookie` and scanning running process PIDs.
- [x] **Task 2.3:** Run and pass core logic unit tests (`test_controller.py`, `test_monitor.py`) with 80%+ coverage.

---

## 📋 Phase 3: GNOME Tray Icon & State Decorations
- [x] **Task 3.1:** Implement `NerdDockIndicator` using GObject `AyatanaAppIndicator3`, including dynamic icon states (gray microphone for Stopped, red for Recording, amber pause circle for Suspended).
- [x] **Task 3.2:** Build dynamic tray dropdown menus, disabling invalid triggers based on the controller's active state.
- [x] **Task 3.3:** Implement interactive state tooltips (e.g., "Nerd-Dictation: Listening...") and system desktop notifications on state transition.

---

## 📋 Phase 4: Static Analysis & Dynamic Sync Verification
- [x] **Task 4.1:** Finalize `make lint` pipeline, ensuring the codebase passes all checks for style (`ruff`), complexity (`radon`), dead code (`vulture`), security vulnerabilities (`bandit`), and duplication (`pylint`).
- [x] **Task 4.2:** Integrate the background monitor thread-safely with the tray applet using `GLib.idle_add` to handle external triggers.
- [-] **Task 4.3:** Perform end-to-end manual verification, ensuring that running `nerd-dictation begin` or `end` in a terminal instantly updates the top panel tray applet.
