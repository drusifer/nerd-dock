"""Main Entry Point for the Nerd-Dock Tray Application."""

import argparse
import logging
import signal
import sys

# Safe check for GTK and AyatanaAppIndicator
try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import GLib, Gtk

    HAS_GRAPHICS = True
except (ImportError, ValueError) as e:
    HAS_GRAPHICS = False
    GRAPHICS_ERROR = e

from nerd_dock.controller import NerdDockController
from nerd_dock.monitor import NerdDictationMonitor

# Configure Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("nerd_dock.main")


def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="Nerd-Dock: A system tray controller for nerd-dictation.",
    )
    parser.add_argument(
        "--executable",
        type=str,
        default="/home/drusifer/.local/bin/nerd-dictation",
        help="Path to nerd-dictation (default: %(default)s)",
    )
    parser.add_argument(
        "--cookie",
        type=str,
        default="/tmp/nerd-dictation.cookie",  # nosec B108
        help="Path to cookie file (default: %(default)s)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.25,
        help="Background process polling interval in seconds (default: %(default)s)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debugging logs",
    )
    return parser.parse_args()


def main() -> int:
    """Main execution block."""
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled.")

    # 1. Validate GTK and AyatanaAppIndicator availability
    if not HAS_GRAPHICS:
        logger.error(
            "System UI Libraries (Gtk 3.0 or AyatanaAppIndicator3 0.1) "
            "are not available.\n"
            "Ensure you have installed system dependencies "
            "(e.g., gir1.2-ayatanaappindicator3-0.1) "
            "and that you are running in a graphical X11/Wayland "
            "desktop environment.\n"
            "Error: %s",
            GRAPHICS_ERROR,
        )
        return 1

    logger.info("Initializing Nerd-Dock tray application...")

    try:
        # 2. Instantiate core components
        controller = NerdDockController(
            executable_path=args.executable,
            cookie_path=args.cookie,
        )
        monitor = NerdDictationMonitor(
            controller=controller,
            cookie_path=args.cookie,
            poll_interval=args.poll_interval,
        )

        # Import UI indicator here to ensure it's loaded after GTK verification
        from nerd_dock.ui_indicator import NerdDockIndicator

        indicator = NerdDockIndicator(controller=controller, monitor=monitor)

        # 3. Start the background process monitor
        monitor.start()

        # 4. Handle clean termination signals (SIGINT, SIGTERM)
        def signal_handler(signum: int, _frame) -> None:
            logger.info(
                "Termination signal %d received. Initiating teardown...",
                signum,
            )
            indicator.shutdown()
            Gtk.main_quit()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # 5. Schedule a short timer tick to process Python signals
        # This keeps the Python interpreter active and makes Ctrl+C responsive
        # during the GTK main loop execution.
        def sigint_timeout() -> bool:
            return True

        GLib.timeout_add(250, sigint_timeout)

        # 6. Start the GTK main loop
        logger.info("Nerd-Dock is successfully loaded. Running GTK Main Loop.")
        Gtk.main()

    except Exception as e:
        logger.exception(
            "An unhandled exception occurred during application lifetime: %s",
            e,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
