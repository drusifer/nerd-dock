"""Nerd-Dock Subprocess Controller and State Machine."""

import logging
import subprocess  # nosec B404
import threading
import time

# State Definitions
STATE_STOPPED = "STOPPED"
STATE_RECORDING = "RECORDING"
STATE_SUSPENDED = "SUSPENDED"
STATE_TRANSITIONING = "TRANSITIONING"

logger = logging.getLogger("nerd_dock.controller")


class NerdDockController:
    """Manages nerd-dictation subprocesses and tracks application states."""

    def __init__(
        self,
        executable_path: str = "/home/drusifer/.local/bin/nerd-dictation",
        cookie_path: str | None = None,
    ) -> None:
        self._state: str = STATE_STOPPED
        self.executable_path: str = executable_path
        self.cookie_path: str | None = cookie_path
        self._process: subprocess.Popen | None = None  # vulture: ignore
        self._previous_stable_state: str = STATE_STOPPED
        self._transition_start_time: float = 0.0
        self._target_state: str | None = None
        self._model_loaded: bool = False

    def get_state(self) -> str:
        """Returns the current state."""
        return self._state

    def set_state(self, state: str) -> None:
        """Sets the current state and logs the transition."""
        if state not in (
            STATE_STOPPED,
            STATE_RECORDING,
            STATE_SUSPENDED,
            STATE_TRANSITIONING,
        ):
            raise ValueError(f"Invalid state: {state}")
        if self._state != state:
            logger.info("State transition: %s -> %s", self._state, state)
            if state == STATE_TRANSITIONING:
                self._previous_stable_state = self._state
                self._transition_start_time = time.time()
            else:
                self._target_state = None
            self._state = state

    def get_target_state(self) -> str | None:
        """Returns the target state of the current transition, if any."""
        return self._target_state

    def is_model_loaded(self) -> bool:
        """Checks if the model has finished loading.

        If the process was not spawned by us (meaning self._process is None),
        we immediately return True for backward compatibility.
        """
        if self._process is None:
            return True
        return self._model_loaded

    def _read_output(self, proc: subprocess.Popen) -> None:
        """Reads subprocess output to detect when the model is loaded."""
        if not proc.stdout:
            return
        try:
            for line in proc.stdout:
                logger.debug("nerd-dictation output: %s", line.strip())
                if "Model loaded." in line:
                    logger.info("Detected 'Model loaded.' in output.")
                    self._model_loaded = True
                    break
        except Exception as e:
            logger.error("Error reading nerd-dictation output: %s", e)

    def begin_dictation(self, options: list[str] | None = None) -> bool:
        """Launches the dictation process asynchronously."""
        if self._state != STATE_STOPPED:
            logger.warning("Cannot begin dictation: current state is %s", self._state)
            return False

        previous_state = self._state
        self._target_state = STATE_RECORDING
        self.set_state(STATE_TRANSITIONING)
        self._model_loaded = False

        cmd = [self.executable_path, "begin"]
        if self.cookie_path:
            cmd.extend(["--cookie", self.cookie_path])

        # Check if --verbose is already in options to avoid duplicates
        has_verbose = False
        if options:
            for opt in options:
                if "--verbose" in opt:
                    has_verbose = True
                    break
        if not has_verbose:
            cmd.extend(["--verbose", "3"])

        if options:
            cmd.extend(options)

        try:
            logger.info("Executing: %s", " ".join(cmd))
            # Spawn asynchronously so it doesn't block the main UI thread.
            self._process = subprocess.Popen(  # nosec B603  # vulture: ignore
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            # Read output in background to detect when model is loaded.
            threading.Thread(
                target=self._read_output,
                args=(self._process,),
                daemon=True,
            ).start()
            return True
        except (OSError, ValueError) as e:
            logger.error("Failed to execute begin: %s", e)
            self.set_state(previous_state)
            return False

    def _execute_subcommand(self, subcommand: str, _target_state: str) -> bool:
        """Executes a short-lived sync subcommand to control the daemon."""
        if self._state == STATE_STOPPED and subcommand in (
            "end",
            "suspend",
            "resume",
            "cancel",
        ):
            logger.warning("Cannot %s dictation: dictation is not running", subcommand)
            return False

        previous_state = self._state
        self._target_state = _target_state
        self.set_state(STATE_TRANSITIONING)

        cmd = [self.executable_path, subcommand]
        if self.cookie_path:
            cmd.extend(["--cookie", self.cookie_path])

        try:
            logger.info("Executing: %s", " ".join(cmd))
            # Run synchronously since control commands return immediately.
            result = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                check=True,
            )
            logger.debug("Subcommand %s result: %s", subcommand, result.returncode)
            return True
        except (subprocess.CalledProcessError, OSError) as e:
            logger.error("Failed to execute %s: %s", subcommand, e)
            self.set_state(previous_state)
            return False

    def end_dictation(self) -> bool:
        """Stops the dictation process."""
        if self._process:
            self._process = None
        return self._execute_subcommand("end", STATE_STOPPED)

    def suspend_dictation(self) -> bool:
        """Suspends/pauses the active dictation process."""
        return self._execute_subcommand("suspend", STATE_SUSPENDED)

    def resume_dictation(self) -> bool:
        """Resumes the suspended dictation process."""
        return self._execute_subcommand("resume", STATE_RECORDING)

    def cancel_dictation(self) -> bool:
        """Cancels the active dictation process, ignoring buffer."""
        if self._process:
            self._process = None
        return self._execute_subcommand("cancel", STATE_STOPPED)
