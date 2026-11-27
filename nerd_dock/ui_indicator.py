"""Nerd-Dock Ayatana AppIndicator System Tray Interface."""

import logging
import os

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify

    HAS_NOTIFY = True
except (ValueError, ImportError):
    HAS_NOTIFY = False

from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk

from nerd_dock.stt_stream import (
    STATE_RECORDING,
    STATE_STOPPED,
    STATE_STOPPING,
    STATE_SUSPENDED,
    StreamingSTT,
)

logger = logging.getLogger("nerd_dock.ui_indicator")

# D-Bus application id; the GNOME shortcut command targets this name.
APP_ID = "io.github.drusifer.NerdDock"
ICONS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "resources", "icons"
)
POLL_MS = 250

# state -> (icon, label, notification)
STATES = {
    STATE_STOPPED: ("nerd-dock-stopped", "Stopped", "Dictation stopped."),
    STATE_RECORDING: ("nerd-dock-recording", "Listening", "Listening..."),
    STATE_SUSPENDED: ("nerd-dock-paused", "Paused", "Dictation paused."),
    STATE_STOPPING: ("nerd-dock-stopped", "Stopping...", None),
}


class NerdDockIndicator:
    """Tray icon and menu for one streaming dictation session."""

    def __init__(self, stream: StreamingSTT) -> None:
        self.stream = stream
        self._shown: str | None = None

        if HAS_NOTIFY:
            Notify.init("Nerd-Dock")

        self.indicator = AyatanaAppIndicator3.Indicator.new_with_path(
            "nerd-dock",
            "nerd-dock-stopped",
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
            ICONS_DIR,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        self.menu = Gtk.Menu()
        self._build_menu()
        self.indicator.set_menu(self.menu)
        self.refresh()
        # Follow changes the stream makes itself (stop finished, key rejected).
        GLib.timeout_add(POLL_MS, self.refresh)

    def _item(self, label: str, action=None) -> "Gtk.MenuItem":
        item = Gtk.MenuItem(label=label)
        if action:
            item.connect("activate", lambda _widget: self._act(action))
        self.menu.append(item)
        return item

    def _build_menu(self) -> None:
        self.menu_status = self._item("Status: Stopped")
        self.menu_status.set_sensitive(False)
        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu_start = self._item("Start Dictation", self.stream.start)
        self.menu_pause = self._item("Pause Dictation", self.stream.suspend)
        self.menu_resume = self._item("Resume Dictation", self.stream.resume)
        self.menu_stop = self._item("Stop Dictation", self.stream.stop)
        self.menu_cancel = self._item("Cancel Dictation", self.stream.cancel)
        self.menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit_clicked)
        self.menu.append(quit_item)
        self.menu.show_all()

    def _notify(self, message: str) -> None:
        if not HAS_NOTIFY:
            return
        try:
            Notify.Notification.new(
                "Nerd-Dock", message, "audio-input-microphone"
            ).show()
        except Exception as e:
            logger.warning("Failed to show desktop notification: %s", e)

    def _act(self, action) -> None:
        """Runs a stream operation and shows the result."""
        if not action() and self.stream.last_error:
            self._notify(self.stream.last_error)
        self.refresh()

    def refresh(self) -> bool:
        """Brings the icon and menu in line with the stream. True keeps the timer."""
        state = self.stream.state
        if state == self._shown:
            return True
        previous, self._shown = self._shown, state
        icon, label, message = STATES[state]
        self.indicator.set_icon_full(icon, f"Dictation: {label}")
        self.indicator.set_title(f"Dictation: {label}")
        self.menu_status.set_label(f"Status: {label}")
        self.menu_start.set_sensitive(state == STATE_STOPPED)
        self.menu_pause.set_sensitive(state == STATE_RECORDING)
        self.menu_resume.set_sensitive(state == STATE_SUSPENDED)
        live = state in (STATE_RECORDING, STATE_SUSPENDED)
        self.menu_stop.set_sensitive(live)
        self.menu_cancel.set_sensitive(live)
        if previous is not None and message:
            if state == STATE_STOPPED and self.stream.last_error:
                message = self.stream.last_error
            self._notify(message)
        return True

    def enable_remote_toggle(self) -> None:
        """Exposes a `toggle` action on the session bus for a GNOME shortcut.

        Bind a custom shortcut to:
        gapplication action io.github.drusifer.NerdDock toggle
        """
        # Not NON_UNIQUE: only a unique application owns APP_ID on the bus, and
        # without the name `gapplication action` cannot reach it.
        self._gio_app = Gio.Application.new(APP_ID, Gio.ApplicationFlags.FLAGS_NONE)
        action = Gio.SimpleAction.new("toggle", None)
        action.connect("activate", lambda _a, _p: self.toggle_dictation())
        self._gio_app.add_action(action)
        self._gio_app.register(None)
        if self._gio_app.get_is_remote():
            raise RuntimeError("Nerd-Dock is already running.")
        logger.info("Toggle action available on D-Bus as %s", APP_ID)

    def toggle_dictation(self) -> None:
        """Starts when stopped, then flips between recording and paused."""
        action = {
            STATE_STOPPED: self.stream.start,
            STATE_RECORDING: self.stream.suspend,
            STATE_SUSPENDED: self.stream.resume,
        }.get(self.stream.state)
        if action:
            self._act(action)
        else:
            logger.info("Ignoring toggle while %s", self.stream.state)

    def _on_quit_clicked(self, _widget) -> None:
        self.shutdown()
        Gtk.main_quit()

    def shutdown(self) -> None:
        """Ends any session so the microphone is released."""
        self.stream.cancel()
        if HAS_NOTIFY:
            Notify.uninit()
