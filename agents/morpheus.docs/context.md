# Recent Decisions
- **Threading Model:** Designed a thread-safe background monitoring architecture. The scanner thread will schedule all UI/indicator status updates via `GLib.idle_add` to prevent GUI deadlocks in the non-thread-safe GTK4 thread.
- **Glassmorphism Styling:** Standardized on Gtk.CssProvider loading external translucent custom CSS rules to decouple presentation from UI structure.
- **Subprocess Decoupling:** Subprocess invocation wraps direct CLI paths, allowing both widget and OS execution to coexist.
- **Sprint Plan Verification:** Conducted final review of Mouse's task breakdown (`task.md`). Confirmed that Phase 1 (environment/test harness) correctly includes `--system-site-packages` setup and headless testing hooks. Verified that core logic (Phase 2) is fully implemented and unit-tested before UI layers (Phases 3 & 4) are added.

# Key Findings
- **GTK4/Libadwaita integration:** PyGObject bindings allow rich visual UI customization via Libadwaita styling helpers.
- **Auto-Sync:** Process and cookie checking can run reliably at 250ms polling cycles with minimal CPU overhead.

# Important Notes
- Ensure virtualenv `--system-site-packages` links are correctly set up to prevent missing `gi` GObject package failures during local test runs.

---
*Last updated: 2026-05-20T12:26:20-04:00*
