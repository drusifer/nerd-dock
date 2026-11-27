"""Tray indicator tests (GTK objects are mocked; gi itself must be installed)."""

import unittest
from unittest.mock import MagicMock, patch

from nerd_dock.stt_stream import (
    STATE_RECORDING,
    STATE_STOPPED,
    STATE_STOPPING,
    STATE_SUSPENDED,
)


class TestIndicator(unittest.TestCase):
    def setUp(self) -> None:
        gtk = MagicMock()
        gtk.MenuItem.side_effect = lambda **_kwargs: MagicMock()
        self.notify = MagicMock()
        patchers = [
            patch("nerd_dock.ui_indicator.GLib"),
            patch("nerd_dock.ui_indicator.Gtk", gtk),
            patch("nerd_dock.ui_indicator.Gio"),
            patch("nerd_dock.ui_indicator.AyatanaAppIndicator3"),
            patch("nerd_dock.ui_indicator.Notify", self.notify),
            patch("nerd_dock.ui_indicator.HAS_NOTIFY", True),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)

        from nerd_dock.ui_indicator import NerdDockIndicator

        self.stream = MagicMock(state=STATE_STOPPED, last_error=None)
        self.indicator = NerdDockIndicator(self.stream)

    def _show(self, state: str) -> None:
        self.stream.state = state
        self.assertTrue(self.indicator.refresh())

    def test_menu_follows_state(self) -> None:
        self._show(STATE_RECORDING)
        self.indicator.menu_pause.set_sensitive.assert_called_with(True)
        self.indicator.menu_start.set_sensitive.assert_called_with(False)
        self.indicator.menu_status.set_label.assert_called_with("Status: Listening")
        self._show(STATE_STOPPING)
        self.indicator.menu_stop.set_sensitive.assert_called_with(False)

    def test_stop_with_error_notifies_it(self) -> None:
        self._show(STATE_RECORDING)
        self.stream.last_error = "key rejected"
        self._show(STATE_STOPPED)
        self.assertEqual(self.notify.Notification.new.call_args[0][1], "key rejected")

    def test_toggle_starts_pauses_and_resumes_but_never_stops(self) -> None:
        states = (STATE_STOPPED, STATE_RECORDING, STATE_SUSPENDED, STATE_STOPPING)
        for state in states:
            self.stream.state = state
            self.indicator.toggle_dictation()
        self.stream.start.assert_called_once()
        self.stream.suspend.assert_called_once()
        self.stream.resume.assert_called_once()
        self.stream.stop.assert_not_called()

    def test_failed_start_shows_the_reason(self) -> None:
        self.stream.start.return_value = False
        self.stream.last_error = "no microphone"
        self.indicator.toggle_dictation()
        self.assertEqual(self.notify.Notification.new.call_args[0][1], "no microphone")

    def test_shutdown_releases_the_microphone(self) -> None:
        self.indicator.shutdown()
        self.stream.cancel.assert_called_once()

    def test_remote_toggle_registers_action(self) -> None:
        self.indicator.enable_remote_toggle()
        self.indicator._gio_app.add_action.assert_called_once()
        self.indicator._gio_app.register.assert_called_once()


if __name__ == "__main__":
    unittest.main()
