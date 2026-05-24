# Current Task

**Status:** Completed
**Assigned to:** Neo (SWE)
**Started:** 2026-05-22T14:19:00-04:00

## Task Description
Resolve the state transition bug where the tray UI got permanently greyed out (stuck in `STATE_TRANSITIONING`) after launching dictation. We need to implement a mechanism in the background process monitor `NerdDictationMonitor` to intelligently resolve transition states, revert back to safe states upon background child process failures, and handle timeouts. Additionally, align the cookie path parameter between `NerdDictationMonitor` and the launched `nerd-dictation` subprocess by passing the `--cookie` CLI parameter, ensuring correct status detection. In the follow-up, track the visual state separately to resolve UI update race conditions, clean up orphaned dictation processes on quit, and verify using a new automated mock view test suite.
Furthermore, implement instant feedback when starting dictation ("Dictation: Starting Up..." and "Status: Starting Up (Loading Model)...") to keep the user informed during large speech recognition model loading delays.

## Progress
- [x] Task 1: Identify root cause of the permanent `STATE_TRANSITIONING` UI grey-out
- [x] Task 2: Implement `_previous_stable_state` and `_transition_start_time` in `NerdDockController`
- [x] Task 3: Implement smart transition resolution in `NerdDictationMonitor` (state comparison, subprocess poll checks, and 15s fallback timeout)
- [x] Task 4: Align cookie paths by accepting and passing `--cookie <path>` to child `nerd-dictation` subprocess calls
- [x] Task 5: Add comprehensive unit tests in `tests/test_monitor.py` and `tests/test_controller.py` verifying all behaviors and command formulations
- [x] Task 6: Pass the test and static analysis pipelines (10/10 Pylint score)
- [x] Task 7: Implement visual state tracking (`_current_ui_state`) in `NerdDockIndicator` to resolve the callback sync race condition
- [x] Task 8: Add subprocess cleanup (`cancel_dictation`) on UI shutdown to prevent orphaned background processes on exit
- [x] Task 9: Create new GObject/Gtk tray UI test suite `tests/test_ui.py` running headlessly with full assertion coverage
- [x] Task 10: Run full quality assurance suite, verifying 100% ruff, pylint, and unit test compliance
- [x] Task 11: Add dynamic status menu item at the top of the context menu showing dynamic status (e.g. `Status: Starting Up (Loading Model)...`)
- [x] Task 12: Fix target state race in click handlers by updating controller state *before* calling `update_ui`
- [x] Task 13: Add desktop notification `"Starting up (Loading model)..."` when starting dictation
- [x] Task 14: Extend test suite in `test_ui.py` to cover all of these new transitions and status menu item labels, maintaining 100% test pass rate
- [x] Task 15: Capture `stdout`/`stderr` from `nerd-dictation begin` asynchronously by redirecting to a pipe
- [x] Task 16: Spawn a background thread that reads the pipe line-by-line looking for the `"Model loaded."` string
- [x] Task 17: Maintain visual status at `STATE_TRANSITIONING` while the model is loading and transition to `STATE_RECORDING` only after `"Model loaded."` is detected
- [x] Task 18: Implement fallback/external safety immediately assuming model is loaded if spawned externally (`self._process` is `None`)
- [x] Task 19: Increase fallback timeout in the monitor thread from 15.0 seconds to 60.0 seconds to allow the large speech model to load
- [x] Task 20: Extend and run full headless test suite including a new unit test for `is_model_loaded()`, verifying 100% test pass rate and clean static analysis (10/10 pylint score)

## Blockers
None

## Oracle Consultations
None yet

---
*Last updated: 2026-05-22T15:01:00-04:00*

