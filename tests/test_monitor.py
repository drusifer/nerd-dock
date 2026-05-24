import unittest
from unittest.mock import MagicMock, patch

from nerd_dock.controller import (
    STATE_RECORDING,
    STATE_STOPPED,
    STATE_SUSPENDED,
    STATE_TRANSITIONING,
    NerdDockController,
)
from nerd_dock.monitor import NerdDictationMonitor
from tests.mocks import MockFileSystem


class TestNerdDictationMonitor(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = NerdDockController(executable_path="/mock/bin/nerd-dictation")
        self.mock_fs = MockFileSystem()
        self.monitor = NerdDictationMonitor(
            controller=self.controller,
            cookie_path="/tmp/nerd-dictation.cookie",
            poll_interval=0.01,
        )

    @patch("os.path.exists")
    def test_determine_state_no_cookie(self, mock_exists: patch) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        state = self.monitor._determine_state()
        self.assertEqual(state, STATE_STOPPED)

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_determine_state_invalid_cookie(
        self,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        self.mock_fs.files["/tmp/nerd-dictation.cookie"] = ""
        state = self.monitor._determine_state()
        self.assertEqual(state, STATE_STOPPED)

    @patch("os.path.exists")
    @patch("builtins.open")
    @patch("os.remove")
    def test_determine_state_stale_cookie(
        self,
        mock_remove: patch,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open
        mock_remove.side_effect = self.mock_fs.remove

        self.mock_fs.files["/tmp/nerd-dictation.cookie"] = "9999"

        state = self.monitor._determine_state()
        self.assertEqual(state, STATE_STOPPED)
        self.assertNotIn("/tmp/nerd-dictation.cookie", self.mock_fs.files)
        mock_remove.assert_called_once_with("/tmp/nerd-dictation.cookie")

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_determine_state_recording(
        self,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        self.mock_fs.files["/tmp/nerd-dictation.cookie"] = "1234"
        self.mock_fs.existing_pids.append(1234)
        self.mock_fs.files["/proc/1234/status"] = "Name: python\nState: S (sleeping)\n"

        state = self.monitor._determine_state()
        self.assertEqual(state, STATE_RECORDING)

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_determine_state_suspended(
        self,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        self.mock_fs.files["/tmp/nerd-dictation.cookie"] = "1234"
        self.mock_fs.existing_pids.append(1234)
        self.mock_fs.files["/proc/1234/status"] = "Name: python\nState: T (stopped)\n"

        state = self.monitor._determine_state()
        self.assertEqual(state, STATE_SUSPENDED)

    @patch("os.path.exists")
    @patch("builtins.open")
    @patch("time.sleep")
    def test_monitor_sync_loop_and_callback(
        self,
        mock_sleep: patch,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        callback_mock = MagicMock()
        self.monitor._callback = callback_mock

        self.assertEqual(self.controller.get_state(), STATE_STOPPED)

        self.mock_fs.files["/tmp/nerd-dictation.cookie"] = "5555"
        self.mock_fs.existing_pids.append(5555)
        self.mock_fs.files["/proc/5555/status"] = "Name: python\nState: S (sleeping)\n"

        self.monitor._active = True

        def break_loop(*args: patch, **kwargs: patch) -> None:
            self.monitor._active = False

        mock_sleep.side_effect = break_loop

        with patch("nerd_dock.monitor.HAS_GLIB", False):
            self.monitor._run()

        self.assertEqual(self.controller.get_state(), STATE_RECORDING)
        callback_mock.assert_called_once_with(STATE_RECORDING)

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_monitor_resolves_transitioning_on_change(
        self,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        # Set starting state to STOPPED, then transition to TRANSITIONING
        self.controller.set_state(STATE_STOPPED)
        self.controller.set_state(STATE_TRANSITIONING)

        # Set environment to RECORDING (different from pre-transition state STOPPED)
        self.mock_fs.files["/tmp/nerd-dictation.cookie"] = "5555"
        self.mock_fs.existing_pids.append(5555)
        self.mock_fs.files["/proc/5555/status"] = "Name: python\nState: S (sleeping)\n"

        callback_mock = MagicMock()
        self.monitor._callback = callback_mock

        with (
            patch("time.sleep") as mock_sleep,
            patch("nerd_dock.monitor.HAS_GLIB", False),
        ):
            self.monitor._active = True

            def break_loop(*args: patch, **kwargs: patch) -> None:
                self.monitor._active = False

            mock_sleep.side_effect = break_loop

            self.monitor._run()

            # Controller state should transition to RECORDING
            self.assertEqual(self.controller.get_state(), STATE_RECORDING)
            callback_mock.assert_called_once_with(STATE_RECORDING)

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_monitor_ignores_transitioning_when_no_change(
        self,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        # Set starting state to STOPPED, then transition to TRANSITIONING
        self.controller.set_state(STATE_STOPPED)
        self.controller.set_state(STATE_TRANSITIONING)

        # Set environment to STOPPED (same as pre-transition state STOPPED)
        # (Meaning no cookie exists)

        callback_mock = MagicMock()
        self.monitor._callback = callback_mock

        with (
            patch("time.sleep") as mock_sleep,
            patch("nerd_dock.monitor.HAS_GLIB", False),
        ):
            self.monitor._active = True

            def break_loop(*args: patch, **kwargs: patch) -> None:
                self.monitor._active = False

            mock_sleep.side_effect = break_loop

            self.monitor._run()

            # Controller state should remain TRANSITIONING
            self.assertEqual(self.controller.get_state(), STATE_TRANSITIONING)
            callback_mock.assert_not_called()

    @patch("os.path.exists")
    @patch("builtins.open")
    def test_monitor_reverts_transitioning_on_process_exit(
        self,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        # Set starting state to STOPPED, then transition to TRANSITIONING
        self.controller.set_state(STATE_STOPPED)
        self.controller.set_state(STATE_TRANSITIONING)

        # Mock a terminated process on the controller
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 1  # exited with code 1
        self.controller._process = mock_proc

        callback_mock = MagicMock()
        self.monitor._callback = callback_mock

        with (
            patch("time.sleep") as mock_sleep,
            patch("nerd_dock.monitor.HAS_GLIB", False),
        ):
            self.monitor._active = True

            def break_loop(*args: patch, **kwargs: patch) -> None:
                self.monitor._active = False

            mock_sleep.side_effect = break_loop

            self.monitor._run()

            # Controller state should revert to STOPPED due to process exit
            self.assertEqual(self.controller.get_state(), STATE_STOPPED)
            callback_mock.assert_called_once_with(STATE_STOPPED)

    @patch("os.path.exists")
    @patch("builtins.open")
    @patch("time.time")
    def test_monitor_reverts_transitioning_on_timeout(
        self,
        mock_time: patch,
        mock_open_builtin: patch,
        mock_exists: patch,
    ) -> None:
        mock_exists.side_effect = self.mock_fs.exists
        mock_open_builtin.side_effect = self.mock_fs.mock_open

        # Mock time so we can trigger the 60-second timeout
        mock_time.return_value = 100.0

        # Set starting state to STOPPED, then transition to TRANSITIONING
        self.controller.set_state(STATE_STOPPED)
        self.controller.set_state(STATE_TRANSITIONING)

        # Change mocked current time to exceed the timeout (> 60 seconds after 100.0)
        mock_time.return_value = 170.0

        callback_mock = MagicMock()
        self.monitor._callback = callback_mock

        with (
            patch("time.sleep") as mock_sleep,
            patch("nerd_dock.monitor.HAS_GLIB", False),
        ):
            self.monitor._active = True

            def break_loop(*args: patch, **kwargs: patch) -> None:
                self.monitor._active = False

            mock_sleep.side_effect = break_loop

            self.monitor._run()

            # Controller state should sync with detected state (STOPPED)
            self.assertEqual(self.controller.get_state(), STATE_STOPPED)
            callback_mock.assert_called_once_with(STATE_STOPPED)

    @patch("os.path.exists")
    def test_monitor_start_stop(self, mock_exists: patch) -> None:
        self.assertFalse(self.monitor._active)
        self.monitor.start()
        self.assertTrue(self.monitor._active)
        # Calling start again should not spawn multiple threads
        self.monitor.start()
        self.assertTrue(self.monitor._active)
        self.monitor.stop()
        self.assertFalse(self.monitor._active)
