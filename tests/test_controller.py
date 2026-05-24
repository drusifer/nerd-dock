import subprocess
import unittest
from unittest.mock import patch

from nerd_dock.controller import (
    STATE_RECORDING,
    STATE_STOPPED,
    STATE_SUSPENDED,
    STATE_TRANSITIONING,
    NerdDockController,
)
from tests.mocks import MockSubprocess


class TestNerdDockController(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_sub = MockSubprocess()
        self.controller = NerdDockController(executable_path="/mock/bin/nerd-dictation")

    @patch("subprocess.Popen")
    def test_begin_dictation_success(self, mock_popen: patch) -> None:
        mock_popen.side_effect = self.mock_sub.Popen

        self.assertEqual(self.controller.get_state(), STATE_STOPPED)

        success = self.controller.begin_dictation(["--osd"])
        self.assertTrue(success)

        # State transitions to TRANSITIONING during spawn
        self.assertEqual(self.controller.get_state(), STATE_TRANSITIONING)

        mock_popen.assert_called_once_with(
            ["/mock/bin/nerd-dictation", "begin", "--verbose", "3", "--osd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    @patch("subprocess.Popen")
    def test_begin_dictation_with_cookie_path(self, mock_popen: patch) -> None:
        mock_popen.side_effect = self.mock_sub.Popen
        self.controller.cookie_path = "/tmp/custom.cookie"

        success = self.controller.begin_dictation(["--osd"])
        self.assertTrue(success)

        mock_popen.assert_called_once_with(
            [
                "/mock/bin/nerd-dictation",
                "begin",
                "--cookie",
                "/tmp/custom.cookie",
                "--verbose",
                "3",
                "--osd",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    @patch("subprocess.Popen")
    def test_begin_dictation_failure(self, mock_popen: patch) -> None:
        mock_popen.side_effect = OSError("Spawn failed")

        success = self.controller.begin_dictation()
        self.assertFalse(success)
        self.assertEqual(self.controller.get_state(), STATE_STOPPED)

    @patch("subprocess.Popen")
    def test_double_begin_prevention(self, mock_popen: patch) -> None:
        mock_popen.side_effect = self.mock_sub.Popen

        self.controller.set_state(STATE_RECORDING)
        success = self.controller.begin_dictation()
        self.assertFalse(success)
        self.assertEqual(self.controller.get_state(), STATE_RECORDING)
        mock_popen.assert_not_called()

    @patch("subprocess.run")
    def test_subcommands_success(self, mock_run: patch) -> None:
        mock_run.side_effect = self.mock_sub.run

        self.controller.set_state(STATE_RECORDING)

        # End
        success = self.controller.end_dictation()
        self.assertTrue(success)
        self.assertEqual(self.controller.get_state(), STATE_TRANSITIONING)
        mock_run.assert_any_call(
            ["/mock/bin/nerd-dictation", "end"],
            capture_output=True,
            check=True,
        )

        # Suspend
        self.controller.set_state(STATE_RECORDING)
        success = self.controller.suspend_dictation()
        self.assertTrue(success)

        # Resume
        self.controller.set_state(STATE_SUSPENDED)
        success = self.controller.resume_dictation()
        self.assertTrue(success)

        # Cancel
        self.controller.set_state(STATE_RECORDING)
        success = self.controller.cancel_dictation()
        self.assertTrue(success)

    @patch("subprocess.run")
    def test_subcommand_failure_recovers_state(self, mock_run: patch) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")

        self.controller.set_state(STATE_RECORDING)
        success = self.controller.suspend_dictation()

        self.assertFalse(success)
        self.assertEqual(self.controller.get_state(), STATE_RECORDING)

    def test_invalid_state_transition(self) -> None:
        with self.assertRaises(ValueError):
            self.controller.set_state("INVALID_STATE")

    @patch("subprocess.run")
    def test_prevent_control_commands_when_stopped(self, mock_run: patch) -> None:
        self.controller.set_state(STATE_STOPPED)
        success = self.controller.end_dictation()
        self.assertFalse(success)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_subcommands_with_cookie_path(self, mock_run: patch) -> None:
        mock_run.side_effect = self.mock_sub.run
        self.controller.cookie_path = "/tmp/custom.cookie"
        self.controller.set_state(STATE_RECORDING)

        success = self.controller.end_dictation()
        self.assertTrue(success)
        mock_run.assert_any_call(
            ["/mock/bin/nerd-dictation", "end", "--cookie", "/tmp/custom.cookie"],
            capture_output=True,
            check=True,
        )

    @patch("subprocess.Popen")
    def test_is_model_loaded_external_vs_internal(self, mock_popen: patch) -> None:
        mock_popen.side_effect = self.mock_sub.Popen

        # External process: self._process is None
        self.assertTrue(self.controller.is_model_loaded())

        # Spawned process: is_model_loaded becomes True when thread parses stdout
        success = self.controller.begin_dictation()
        self.assertTrue(success)

        import time

        for _ in range(50):
            if self.controller.is_model_loaded():
                break
            time.sleep(0.01)

        self.assertTrue(self.controller.is_model_loaded())
