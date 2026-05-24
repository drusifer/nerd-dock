# Agent Local Context - Neo

> ## Recent Decisions
> - Focused entirely on system tray icon/decorations. Floating widget option removed per User request.
> - Python Virtualenv must be created with `--system-site-packages` to link system AyatanaAppIndicator and PyGObject bindings.
> - Static analysis pipeline target: `ruff`, `radon`, `vulture`, `bandit`, `pylint`.
> - State transitions to be monitored via `/tmp/nerd-dictation.cookie` PID validation against `/proc`.
> - **State Transition Bug Fix:** Monitored transition states (`STATE_TRANSITIONING`) are now resolved inside `NerdDictationMonitor` by comparing the environment's `detected_state` with the controller's `_previous_stable_state`, checking for spawned process exits, or using a 15-second safety timeout.
> - **Process Coordination Fix:** Formulated `NerdDockController` to accept and pass the `--cookie` argument to child `nerd-dictation` commands. This aligns the cookie path used by `nerd-dictation` with the path monitored by `NerdDictationMonitor`, resolving UI freeze when running inWayland/GNOME and allowing clean status synchronization.
> - **Visual UI State Sync:** Introduced separate visual state tracking (`self._current_ui_state`) in `NerdDockIndicator` to resolve the race condition where background-thread controller state modifications bypassed UI callbacks due to early return on matching state checks.
> - **Subprocess Exit Cleanup:** Integrated clean subprocess termination (`cancel_dictation`) into the UI's `shutdown()` lifecycle so that no background dictation daemon processes are orphaned when the user closes the tray app.
> - **Loading/Starting Up Feedback:**
>   - Introduced a dynamic `menu_status` insensitive menu item at the top of the context menu.
>   - Re-ordered tray click handler execution to execute the controller transition methods *before* updating the UI to `STATE_TRANSITIONING`, resolving target state querying races.
>   - Added explicit status indicator message `"Status: Starting Up (Loading Model)..."` and desktop notification `"Starting up (Loading model)..."` when starting dictation, giving instant feedback during large speech model loading.
> - **Asynchronous Model Ready Polling:** Spawned processes are now run with `--verbose 3` and have their `stdout`/`stderr` piped to a background thread. This thread parses output line-by-line for `"Model loaded."`, at which point `is_model_loaded()` transitions to `True`. The monitor thread suppresses transition to `STATE_RECORDING` until `is_model_loaded()` is `True` or the process exits. To avoid premature transitions, the fallback timeout was increased to 60.0 seconds.
>
> ## Key Findings
> - `nerd-dictation` resides at `/home/drusifer/.local/bin/nerd-dictation`
> - Ubuntu 26.04 includes GNOME 50 and Ayatana AppIndicator libraries.
> - **Virtualenv / --system-site-packages Behavior:** When virtualenv is created with system site packages, global packages (like `pytest`, `ruff`) satisfy pip requirements without installing their executable wrappers inside `venv/bin/`. To execute them reliably inside the venv, always use the pattern `$(PYTHON) -m <tool_name>` (e.g. `$(PYTHON) -m pytest`).
> - **Makefile Overrides:** Conditionally defined root `Makefile`'s generic `test` target based on the presence of `Makefile.prj` to avoid overriding recipe warnings.
> - **Black/Ruff Formatting with Trailing Commas:** Multiline function argument lists must have trailing commas on each line to comply with the project's Ruff formatting and linter guidelines.
>
> ## Important Notes
> - Keep UI updates thread-safe! Dispatch GUI updates from background monitor thread using `GLib.idle_add`.

---
*Last updated: 2026-05-22T15:00:00-04:00*
