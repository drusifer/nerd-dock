# Recent Decisions
- **Tray-Only Architecture:** Based on user feedback, dropped the floating GTK4 widget. Focus exclusively on the Ayatana AppIndicator system tray icon.
- **Dynamic Taskbar Icon Decoration:** Implement highly expressive tray states: Stopped (monochrome icon, "Stopped (Ready)" tooltip), Recording (colored red icon, "Recording..." tooltip, system notifications), Suspended (orange pause circle icon, "Paused (Muted)" tooltip).
- **Static Analysis pipeline:** Added build targets to the development Makefile for Ruff (style), Radon (complexity), Vulture (dead code), Bandit (security), and Pylint (duplication).

# Key Findings
- **nerd-dictation Path:** Executable is at `/home/drusifer/.local/bin/nerd-dictation`.
- **Command Support:** Supports begin, end, cancel, suspend, and resume.
- **State Mechanism:** Driven by a cookie file at `/tmp/nerd-dictation.cookie` storing the active PID.

# Important Notes
- Ensure virtualenv `--system-site-packages` is utilized in the setup to cleanly link system `gi` GObject introspection bindings.

---
*Last updated: 2026-05-20T12:33:00-04:00*
