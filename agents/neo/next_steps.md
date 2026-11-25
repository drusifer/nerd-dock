# Next Steps

## Immediate Next Action
- Wait for user validation of:
  1. The verbose background polling of `nerd-dictation`'s output, dynamically waiting for `"Model loaded."` before transitioning to the active Listening status.
  2. The extended 60.0-second fallback transition timeout preventing early state syncs when loading large models.
  3. Seamless backward compatibility when `nerd-dictation` is launched externally (instantly transitioning once the cookie is active).

## Waiting On
- User confirmation that the tray applet and dictation startup sequence behave correctly on Ubuntu 26.04.

## Planned Work
- [x] Implement Task 2.1: `NerdDockController` state machine and safe subprocess execution calls (`begin`, `end`, `suspend`, `resume`, `cancel`).
- [x] Implement Task 2.2: `NerdDictationMonitor` background thread watching `/tmp/nerd-dictation.cookie` and scanning running process PIDs.
- [x] Implement Task 2.3: Run and pass core logic unit tests with 80%+ coverage.
- [x] Task 3: Resolve transition grey-out bug, adding robust timeout, exit-reversion, and environment sync checking.
- [x] Task 4: Resolve cookie alignment between Nerd-Dock monitor and launched child subprocesses.
- [x] Task 5: Track visual UI state representation to avoid thread-safe callback race conditions.
- [x] Task 6: Kill active dictation daemon processes cleanly on application exit/quit.
- [x] Task 7: Build `tests/test_ui.py` to cover tray UI state management and integration headlessly.
- [x] Task 8: Implement dynamic Status menu item and instantaneous visual starting up feedback.

---
*Last updated: 2026-05-22T15:02:00-04:00*

