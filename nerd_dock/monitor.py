"""Nerd-Dictation Environment Monitor Thread."""

import logging
import os
import threading
import time
from collections.abc import Callable

# Import GLib safely for thread-safe UI callbacks
try:
    from gi.repository import GLib

    HAS_GLIB = True
except ImportError:
    HAS_GLIB = False

from nerd_dock.controller import (
    STATE_RECORDING,
    STATE_STOPPED,
    STATE_SUSPENDED,
    STATE_TRANSITIONING,
    NerdDockController,
)

logger = logging.getLogger("nerd_dock.monitor")


class NerdDictationMonitor:
    """Monitors the state of nerd-dictation in a background thread."""

    def __init__(
        self,
        controller: NerdDockController,
        cookie_path: str = "/tmp/nerd-dictation.cookie",  # nosec B108
        callback: Callable[[str], None] | None = None,
        poll_interval: float = 0.25,
    ) -> None:
        self._controller: NerdDockController = controller
        self.cookie_path: str = cookie_path
        self._callback: Callable[[str], None] | None = callback
        self.poll_interval: float = poll_interval
        self._active: bool = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Starts the background monitor thread."""
        if self._active:
            return
        self._active = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Monitor thread started.")

    def stop(self) -> None:
        """Stops the background monitor thread."""
        if not self._active:
            return
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)
        logger.info("Monitor thread stopped.")

    def _get_process_state(self, pid: int) -> str | None:
        """Reads process status from Linux /proc/PID/status."""
        status_path = f"/proc/{pid}/status"
        if not os.path.exists(status_path):
            return None
        try:
            with open(status_path, encoding="utf-8") as f:
                for line in f:
                    if line.startswith("State:"):
                        # Extract the state character, e.g., 'T' (stopped) or
                        # 'S' (sleeping)
                        parts = line.split()
                        if len(parts) >= 2:
                            return parts[1]
        except (OSError, PermissionError) as e:
            logger.debug("Failed to read status for PID %d: %s", pid, e)
            return None
        return None

    def _determine_state(self) -> str:
        """Evaluates cookie and OS processes to determine active dictation state."""
        # 1. Check if cookie file exists
        if not os.path.exists(self.cookie_path):
            return STATE_STOPPED

        # 2. Try to read PID from cookie
        try:
            with open(self.cookie_path, encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return STATE_STOPPED
                pid = int(content)
        except (ValueError, OSError) as e:
            logger.warning("Cookie file exists but is unreadable or invalid: %s", e)
            return STATE_STOPPED

        # 3. Check /proc for the process state
        proc_state = self._get_process_state(pid)
        if proc_state is None:
            # PID is dead or process does not exist
            logger.info("Stale cookie detected. PID %d is not active.", pid)
            try:
                os.remove(self.cookie_path)
            except OSError as e:
                logger.error("Failed to remove stale cookie file: %s", e)
            return STATE_STOPPED

        # T = Stopped (via SIGSTOP, which is what nerd-dictation suspend does)
        if proc_state == "T":
            return STATE_SUSPENDED

        # Any other state (R, S, D, etc.) means it is active and running
        return STATE_RECORDING

    def _run(self) -> None:
        """Main loop for the monitor thread."""
        while self._active:
            try:
                # Calculate current environment state
                detected_state = self._determine_state()

                # Get controller's internal tracked state
                current_state = self._controller.get_state()

                # If the controller is transitioning, let it complete its operation
                if current_state == STATE_TRANSITIONING:
                    prev_stable = getattr(
                        self._controller, "_previous_stable_state", STATE_STOPPED
                    )
                    trans_time = getattr(
                        self._controller, "_transition_start_time", 0.0
                    )

                    # 1. If environment state changed from pre-transition, complete
                    if detected_state != prev_stable:
                        # Wait if transitioning to RECORDING but model is not loaded yet
                        is_active = (
                            self._controller._process is None
                            or self._controller._process.poll() is None
                        )
                        if (
                            detected_state == STATE_RECORDING
                            and not self._controller.is_model_loaded()
                            and is_active
                        ):
                            time.sleep(self.poll_interval)
                            continue

                        logger.info(
                            "Monitor detected transition complete "
                            "from %s to %s (detected %s)",
                            prev_stable,
                            detected_state,
                            detected_state,
                        )
                        self._controller.set_state(detected_state)
                        if self._callback:
                            self._trigger_callback(detected_state)
                        time.sleep(self.poll_interval)
                        continue
                    # 2. If spawned process terminated unexpectedly, revert to STOPPED
                    elif (
                        prev_stable == STATE_STOPPED
                        and getattr(self._controller, "_process", None) is not None
                        and self._controller._process.poll() is not None
                    ):
                        logger.warning(
                            "Spawned nerd-dictation process exited "
                            "unexpectedly with code %s.",
                            self._controller._process.poll(),
                        )
                        self._controller.set_state(STATE_STOPPED)
                        if self._callback:
                            self._trigger_callback(STATE_STOPPED)
                        time.sleep(self.poll_interval)
                        continue
                    # 3. Fallback timeout: if transitioning takes > 60s, sync state
                    elif time.time() - trans_time > 60.0:
                        logger.warning(
                            "Transition from %s timed out. "
                            "Syncing to detected state: %s",
                            prev_stable,
                            detected_state,
                        )
                        self._controller.set_state(detected_state)
                        if self._callback:
                            self._trigger_callback(detected_state)
                        time.sleep(self.poll_interval)
                        continue
                    else:
                        time.sleep(self.poll_interval)
                        continue

                # Sync state if mismatch is found
                if detected_state != current_state:
                    logger.info(
                        "Monitor detected state change: %s -> %s",
                        current_state,
                        detected_state,
                    )
                    self._controller.set_state(detected_state)
                    if self._callback:
                        self._trigger_callback(detected_state)

            except Exception as e:
                logger.error("Error in monitor thread: %s", e, exc_info=True)

            time.sleep(self.poll_interval)

    def _trigger_callback(self, state: str) -> None:
        """Dispatches callback thread-safely via GLib if active."""
        if HAS_GLIB:
            GLib.idle_add(self._callback, state)
        else:
            self._callback(state)
