# Product Requirements Document (PRD) — Nerd-Dock

**Author:** Cypher (Product Manager)  
**Date:** 2026-05-20  
**Status:** Approved for Implementation  

---

## 1. Product Vision
**Nerd-Dock** is an elegant, system-wide tray controller designed specifically for the lightweight, offline speech-to-text utility **nerd-dictation** on Ubuntu 26.04 (GNOME 50). By wrapping the command-line subcommands in a premium, responsive system tray applet, Nerd-Dock provides instant control and highly visible state indications for starting, stopping, pausing, and resuming dictation.

---

## 2. Key Objectives
- **Zero Overhead Control:** Provide easy-to-use visual triggers for starting, stopping, pausing, and resuming dictation directly from the GNOME top bar.
- **Dynamic State Synchronization:** Keep the tray icon instantly synchronized in real-time, even when dictation is triggered via command-line or system keyboard shortcuts outside of Nerd-Dock.
- **Vibrant Status Decorations:** Provide high-quality monochrome and colored icons with interactive, informative tooltips and desktop notifications to reflect Stopped/Recording/Paused states immediately.
- **Robust Integration:** Leverage GObject Introspection bindings for a seamless, native GNOME desktop integration that doesn't require third-party shell extensions for GTK window rendering.

---

## 3. Core Features & Specifications

### 3.1. Decorated System Tray Applet (Ayatana AppIndicator)
- Native system tray integration in the GNOME top bar.
- **Status-Driven Tray Icons & Tooltips:**
  - `STOPPED`: Gray/monochrome microphone. Hover tooltip: "Nerd-Dictation: Stopped (Ready)".
  - `RECORDING`: Glowing, vibrant red microphone. Hover tooltip: "Nerd-Dictation: Recording...". Displays system desktop notifications on start.
  - `SUSPENDED (PAUSED)`: Steady amber/orange pause circle. Hover tooltip: "Nerd-Dictation: Paused (Muted)".
- **Interactive Context Menu:**
  - **Start Dictation** (fires `nerd-dictation begin`) - Enabled when STOPPED.
  - **Pause Dictation** (fires `nerd-dictation suspend`) - Enabled when RECORDING.
  - **Resume Dictation** (fires `nerd-dictation resume`) - Enabled when SUSPENDED.
  - **Stop Dictation** (fires `nerd-dictation end`) - Enabled when RECORDING/SUSPENDED.
  - **Quit** - Exits Nerd-Dock completely.

### 3.2. Real-Time State Monitor & Subprocess Controller
- Spawns `/home/drusifer/.local/bin/nerd-dictation` safely inside standard subprocess wrappers.
- Runs a 250ms polling loop/monitor thread checking:
  1. The existence and contents of `/tmp/nerd-dictation.cookie`.
  2. The process name in the active process table to verify whether the PID inside the cookie matches a live running process.
- Instantly updates tray icon and menu states thread-safely when changes are detected using `GLib.idle_add`.

---

## 4. System States

| State | Process Status | Cookie Exists? | Description |
|---|---|---|---|
| `STOPPED` | Not running | No | Dictation is completely off. No audio input or model loaded. |
| `RECORDING` | Running (active) | Yes | Dictation is active, model is loaded, capturing audio and typing keystrokes. |
| `SUSPENDED` | Running (paused) | Yes | Dictation is active, model is in memory, but audio capture and keystroke injection are suspended (no CPU overhead). |
| `TRANSITIONING` | Spawning/killing | - | Internal lock state to prevent race conditions during button click execution. |

---

## 5. Development & Verification Automation
- **Style & Code Quality:** `ruff check` and `ruff format` to maintain PEP 8 compliance.
- **Complexity Analysis:** `radon cc` to guarantee low cognitive complexity.
- **Dead Code:** `vulture` to locate unused functions/variables.
- **Security:** `bandit` to identify security risks.
- **Duplication Checker:** `pylint --disable=all --enable=duplicate-code` to identify copy-paste code.
