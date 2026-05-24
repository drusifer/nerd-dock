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

from gi.repository import AyatanaAppIndicator3, GLib, Gtk

from nerd_dock.controller import (
    STATE_RECORDING,
    STATE_STOPPED,
    STATE_SUSPENDED,
    STATE_TRANSITIONING,
    NerdDockController,
)
from nerd_dock.monitor import NerdDictationMonitor

logger = logging.getLogger("nerd_dock.ui_indicator")

# Locate resources directory
RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
ICONS_DIR = os.path.join(RESOURCES_DIR, "icons")


class NerdDockIndicator:
    """System tray indicator (Ayatana AppIndicator) for nerd-dictation."""

    def __init__(
        self,
        controller: NerdDockController,
        monitor: NerdDictationMonitor,
    ) -> None:
        self.controller: NerdDockController = controller
        self.monitor: NerdDictationMonitor = monitor

        logger.info("Initializing Ayatana AppIndicator with icon path: %s", ICONS_DIR)

        # 1. Initialize Desktop Notifications
        self._init_notifications()

        # 2. Create the Ayatana AppIndicator
        self.indicator = AyatanaAppIndicator3.Indicator.new_with_path(
            "nerd-dock",
            "nerd-dock-stopped",
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
            ICONS_DIR,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Nerd-Dictation Controller")

        # 3. Create the GTK context menu
        self.menu = Gtk.Menu()
        self._build_menu()
        self.indicator.set_menu(self.menu)

        # 4. Bind monitor state callback
        self.monitor._callback = self._on_state_changed

        # 5. Apply the initial state to the UI
        self._current_ui_state = self.controller.get_state()
        self.update_ui(self._current_ui_state)

    def _init_notifications(self) -> None:
        """Initializes libnotify for system desktop notifications."""
        global HAS_NOTIFY
        if HAS_NOTIFY:
            try:
                Notify.init("Nerd-Dock")
                logger.info("Desktop notifications initialized.")
            except Exception as e:
                HAS_NOTIFY = False
                logger.warning("Failed to initialize desktop notifications: %s", e)

    def _send_notification(self, title: str, message: str) -> None:
        """Sends a desktop notification to the user."""
        if HAS_NOTIFY:
            try:
                n = Notify.Notification.new(title, message, "audio-input-microphone")
                n.show()
            except Exception as e:
                logger.warning("Failed to show desktop notification: %s", e)

    def _build_menu(self) -> None:
        """Builds all menu items for the tray context menu."""
        # Status indicator item (grayed out header)
        self.menu_status = Gtk.MenuItem(label="Status: Stopped")
        self.menu_status.set_sensitive(False)
        self.menu.append(self.menu_status)

        # Separator
        self.menu.append(Gtk.SeparatorMenuItem())

        # Menu option: Start
        self.menu_start = Gtk.MenuItem(label="Start Dictation")
        self.menu_start.connect("activate", self._on_start_clicked)
        self.menu.append(self.menu_start)

        # Menu option: Pause
        self.menu_pause = Gtk.MenuItem(label="Pause Dictation")
        self.menu_pause.connect("activate", self._on_pause_clicked)
        self.menu.append(self.menu_pause)

        # Menu option: Resume
        self.menu_resume = Gtk.MenuItem(label="Resume Dictation")
        self.menu_resume.connect("activate", self._on_resume_clicked)
        self.menu.append(self.menu_resume)

        # Menu option: Stop
        self.menu_stop = Gtk.MenuItem(label="Stop Dictation")
        self.menu_stop.connect("activate", self._on_stop_clicked)
        self.menu.append(self.menu_stop)

        # Menu option: Cancel
        self.menu_cancel = Gtk.MenuItem(label="Cancel Dictation")
        self.menu_cancel.connect("activate", self._on_cancel_clicked)
        self.menu.append(self.menu_cancel)

        # Separator
        separator = Gtk.SeparatorMenuItem()
        self.menu.append(separator)

        # Menu option: Quit
        menu_quit = Gtk.MenuItem(label="Quit")
        menu_quit.connect("activate", self._on_quit_clicked)
        self.menu.append(menu_quit)

        # Show all menu items
        self.menu.show_all()

    def update_ui(self, state: str) -> None:
        """Updates the tray icon, tooltip, and menu item sensitivity based on state."""
        logger.debug("Updating UI state representation to: %s", state)
        self._current_ui_state = state

        # Map state to specific custom icon
        if state == STATE_RECORDING:
            icon_name = "nerd-dock-recording"
            label = "Dictation: Listening"
        elif state == STATE_SUSPENDED:
            icon_name = "nerd-dock-paused"
            label = "Dictation: Paused"
        elif state == STATE_TRANSITIONING:
            icon_name = "nerd-dock-stopped"  # fallback for brief transitional state
            target = self.controller.get_target_state()
            prev = getattr(self.controller, "_previous_stable_state", STATE_STOPPED)
            if target == STATE_RECORDING and prev == STATE_STOPPED:
                label = "Dictation: Starting Up..."
            elif target == STATE_RECORDING and prev == STATE_SUSPENDED:
                label = "Dictation: Resuming..."
            elif target == STATE_SUSPENDED:
                label = "Dictation: Pausing..."
            elif target == STATE_STOPPED:
                label = "Dictation: Stopping..."
            else:
                label = "Dictation: Working..."
        else:
            icon_name = "nerd-dock-stopped"
            label = "Dictation: Stopped"

        # Update AppIndicator icon and label
        self.indicator.set_icon_full(icon_name, label)
        # Note: AppIndicator doesn't have a direct set_tooltip method,
        # but set_title is used by tray implementations as accessibility/tooltip.
        self.indicator.set_title(label)

        # Update Menu Status label
        if hasattr(self, "menu_status"):
            status_text = label.replace("Dictation: ", "Status: ")
            if "Starting Up" in status_text:
                status_text = "Status: Starting Up (Loading Model)..."
            self.menu_status.set_label(status_text)

        # Update Menu sensitivities
        is_stopped = state == STATE_STOPPED
        is_recording = state == STATE_RECORDING
        is_suspended = state == STATE_SUSPENDED
        is_transitioning = state == STATE_TRANSITIONING

        if is_transitioning:
            # Disable actions during transition
            self.menu_start.set_sensitive(False)
            self.menu_pause.set_sensitive(False)
            self.menu_resume.set_sensitive(False)
            self.menu_stop.set_sensitive(False)
            self.menu_cancel.set_sensitive(False)
        else:
            self.menu_start.set_sensitive(is_stopped)
            self.menu_pause.set_sensitive(is_recording)
            self.menu_resume.set_sensitive(is_suspended)
            self.menu_stop.set_sensitive(is_recording or is_suspended)
            self.menu_cancel.set_sensitive(is_recording or is_suspended)

    def _on_state_changed(self, state: str) -> None:
        """Callback triggered by process monitor when state changes.

        Run on main thread.
        """
        GLib.idle_add(self._handle_state_changed_on_main, state)

    def _handle_state_changed_on_main(self, state: str) -> None:
        """Performs UI update and system notification safely on the GLib main thread."""
        old_ui_state = getattr(self, "_current_ui_state", None)
        if old_ui_state == state:
            return

        self.controller.set_state(state)
        self.update_ui(state)

        # Notify user on meaningful state changes
        if state == STATE_RECORDING:
            self._send_notification(
                "Nerd Dictation",
                "Microphone Active — Listening...",
            )
        elif state == STATE_SUSPENDED:
            self._send_notification("Nerd Dictation", "Dictation Suspended / Muted.")
        elif state == STATE_STOPPED and old_ui_state != STATE_TRANSITIONING:
            self._send_notification("Nerd Dictation", "Dictation Stopped.")

    # Menu Action Handlers

    def _on_start_clicked(self, _widget: Gtk.MenuItem) -> None:
        logger.info("User clicked: Start Dictation")
        # Attempt to launch the subprocess asynchronously
        if self.controller.begin_dictation():
            self.update_ui(STATE_TRANSITIONING)
            self._send_notification(
                "Nerd Dictation",
                "Starting up (Loading model)...",
            )
        else:
            self.update_ui(self.controller.get_state())

    def _on_pause_clicked(self, _widget: Gtk.MenuItem) -> None:
        logger.info("User clicked: Pause Dictation")
        if self.controller.suspend_dictation():
            self.update_ui(STATE_TRANSITIONING)
        else:
            self.update_ui(self.controller.get_state())

    def _on_resume_clicked(self, _widget: Gtk.MenuItem) -> None:
        logger.info("User clicked: Resume Dictation")
        if self.controller.resume_dictation():
            self.update_ui(STATE_TRANSITIONING)
        else:
            self.update_ui(self.controller.get_state())

    def _on_stop_clicked(self, _widget: Gtk.MenuItem) -> None:
        logger.info("User clicked: Stop Dictation")
        if self.controller.end_dictation():
            self.update_ui(STATE_TRANSITIONING)
        else:
            self.update_ui(self.controller.get_state())

    def _on_cancel_clicked(self, _widget: Gtk.MenuItem) -> None:
        logger.info("User clicked: Cancel Dictation")
        if self.controller.cancel_dictation():
            self.update_ui(STATE_TRANSITIONING)
        else:
            self.update_ui(self.controller.get_state())

    def _on_quit_clicked(self, _widget: Gtk.MenuItem) -> None:
        logger.info("User clicked: Quit Application")
        self.shutdown()
        Gtk.main_quit()

    def shutdown(self) -> None:
        """Cleans up the background monitors, notifications, and stops venv loops."""
        logger.info("Shutting down Nerd-Dock Indicator...")
        # 1. Stop background monitor thread safely
        self.monitor.stop()

        # 2. Terminate the active dictation daemon process so it is not orphaned
        state = self.controller.get_state()
        if state in (STATE_RECORDING, STATE_SUSPENDED, STATE_TRANSITIONING):
            logger.info("Stopping active nerd-dictation daemon process on exit...")
            self.controller.cancel_dictation()

        # 3. Shutdown notification system cleanly
        if HAS_NOTIFY:
            try:
                Notify.uninit()
            except Exception as e:
                logger.warning("Error during notification shutdown: %s", e)
