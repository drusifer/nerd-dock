"""Unit tests for Nerd-Dock Ayatana AppIndicator Tray UI."""

import unittest
from unittest.mock import MagicMock, patch

from nerd_dock.controller import (
    STATE_RECORDING,
    STATE_TRANSITIONING,
    NerdDockController,
)
from nerd_dock.monitor import NerdDictationMonitor


class TestNerdDockIndicator(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = NerdDockController(executable_path="/mock/bin/nerd-dictation")
        self.monitor = MagicMock(spec=NerdDictationMonitor)

        # Set up mocks for GLib, Gtk, AyatanaAppIndicator3, Notify
        self.mock_glib = MagicMock()
        self.mock_gtk = MagicMock()
        self.mock_appindicator = MagicMock()
        self.mock_notify = MagicMock()

        # We want GLib.idle_add to execute the callback synchronously for testing
        def mock_idle_add(func, *args, **kwargs):
            return func(*args, **kwargs)

        self.mock_glib.idle_add = mock_idle_add

        # Mock the indicator instance returned by new_with_path
        self.mock_indicator_instance = MagicMock()
        self.mock_appindicator.Indicator.new_with_path.return_value = (
            self.mock_indicator_instance
        )

        # Start the patchers for nerd_dock.ui_indicator dependencies
        self.patchers = [
            patch("nerd_dock.ui_indicator.GLib", self.mock_glib),
            patch("nerd_dock.ui_indicator.Gtk", self.mock_gtk),
            patch(
                "nerd_dock.ui_indicator.AyatanaAppIndicator3",
                self.mock_appindicator,
            ),
            patch("nerd_dock.ui_indicator.Notify", self.mock_notify),
            patch("nerd_dock.ui_indicator.HAS_NOTIFY", True),
        ]
        for p in self.patchers:
            p.start()

        # Import the class under test
        from nerd_dock.ui_indicator import NerdDockIndicator

        self.indicator = NerdDockIndicator(
            controller=self.controller,
            monitor=self.monitor,
        )

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()

    def test_init(self) -> None:
        # Verify that the elements are correctly initialized
        self.mock_appindicator.Indicator.new_with_path.assert_called_once()
        self.assertEqual(self.indicator._current_ui_state, "STOPPED")

    def test_state_change_callback_updates_ui(self) -> None:
        # Trigger state changed callback
        self.indicator._on_state_changed(STATE_RECORDING)

        # Verify that the UI state tracks it
        self.assertEqual(self.indicator._current_ui_state, STATE_RECORDING)
        self.assertEqual(self.controller.get_state(), STATE_RECORDING)

    def test_ui_sensitivity_during_transition(self) -> None:
        self.indicator.update_ui(STATE_TRANSITIONING)

        # Verify all options disabled
        self.indicator.menu_start.set_sensitive.assert_called_with(False)
        self.indicator.menu_pause.set_sensitive.assert_called_with(False)

    def test_ui_transition_labels(self) -> None:
        # 1. Starting Up (STOPPED -> RECORDING)
        self.controller._previous_stable_state = "STOPPED"
        self.controller._target_state = "RECORDING"
        self.indicator.update_ui(STATE_TRANSITIONING)
        self.mock_indicator_instance.set_icon_full.assert_called_with(
            "nerd-dock-stopped", "Dictation: Starting Up..."
        )
        self.indicator.menu_status.set_label.assert_called_with(
            "Status: Starting Up (Loading Model)..."
        )

        # 2. Stopping (RECORDING -> STOPPED)
        self.controller._previous_stable_state = "RECORDING"
        self.controller._target_state = "STOPPED"
        self.indicator.update_ui(STATE_TRANSITIONING)
        self.mock_indicator_instance.set_icon_full.assert_called_with(
            "nerd-dock-stopped", "Dictation: Stopping..."
        )
        self.indicator.menu_status.set_label.assert_called_with("Status: Stopping...")

    def test_shutdown_cancels_active_dictation(self) -> None:
        # Set state to recording
        self.controller.set_state(STATE_RECORDING)
        self.indicator._current_ui_state = STATE_RECORDING

        # Call shutdown
        with patch.object(self.controller, "cancel_dictation") as mock_cancel:
            self.indicator.shutdown()
            mock_cancel.assert_called_once()

    def test_on_start_clicked_success(self) -> None:
        with patch.object(
            self.controller,
            "begin_dictation",
            return_value=True,
        ) as mock_begin:
            self.controller._target_state = "RECORDING"
            self.indicator._on_start_clicked(None)
            mock_begin.assert_called_once()
            self.assertEqual(self.indicator._current_ui_state, STATE_TRANSITIONING)
            self.indicator.menu_status.set_label.assert_called_with(
                "Status: Starting Up (Loading Model)..."
            )

    def test_on_start_clicked_failure(self) -> None:
        with patch.object(
            self.controller,
            "begin_dictation",
            return_value=False,
        ) as mock_begin:
            self.indicator._on_start_clicked(None)
            mock_begin.assert_called_once()
            self.assertEqual(self.indicator._current_ui_state, "STOPPED")

    def test_on_pause_clicked(self) -> None:
        self.controller.set_state("RECORDING")
        self.indicator._current_ui_state = "RECORDING"
        with patch.object(
            self.controller,
            "suspend_dictation",
            return_value=True,
        ) as mock_suspend:
            self.controller._target_state = "SUSPENDED"
            self.indicator._on_pause_clicked(None)
            mock_suspend.assert_called_once()
            self.assertEqual(self.indicator._current_ui_state, STATE_TRANSITIONING)
            self.indicator.menu_status.set_label.assert_called_with(
                "Status: Pausing..."
            )

    def test_on_resume_clicked(self) -> None:
        self.controller.set_state("SUSPENDED")
        self.indicator._current_ui_state = "SUSPENDED"
        with patch.object(
            self.controller,
            "resume_dictation",
            return_value=True,
        ) as mock_resume:
            self.controller._target_state = "RECORDING"
            self.controller._previous_stable_state = "SUSPENDED"
            self.indicator._on_resume_clicked(None)
            mock_resume.assert_called_once()
            self.assertEqual(self.indicator._current_ui_state, STATE_TRANSITIONING)
            self.indicator.menu_status.set_label.assert_called_with(
                "Status: Resuming..."
            )

    def test_on_stop_clicked(self) -> None:
        self.controller.set_state("RECORDING")
        self.indicator._current_ui_state = "RECORDING"
        with patch.object(
            self.controller,
            "end_dictation",
            return_value=True,
        ) as mock_end:
            self.controller._target_state = "STOPPED"
            self.indicator._on_stop_clicked(None)
            mock_end.assert_called_once()
            self.assertEqual(self.indicator._current_ui_state, STATE_TRANSITIONING)
            self.indicator.menu_status.set_label.assert_called_with(
                "Status: Stopping..."
            )

    def test_on_cancel_clicked(self) -> None:
        self.controller.set_state("RECORDING")
        self.indicator._current_ui_state = "RECORDING"
        with patch.object(
            self.controller,
            "cancel_dictation",
            return_value=True,
        ) as mock_cancel:
            self.controller._target_state = "STOPPED"
            self.indicator._on_cancel_clicked(None)
            mock_cancel.assert_called_once()
            self.assertEqual(self.indicator._current_ui_state, STATE_TRANSITIONING)
            self.indicator.menu_status.set_label.assert_called_with(
                "Status: Stopping..."
            )
