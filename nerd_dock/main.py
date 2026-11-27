"""Main Entry Point for the Nerd-Dock Tray Application."""

import argparse
import logging
import os
import shutil
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
from nerd_dock.kyutai_stream import KyutaiSTT
from nerd_dock.monitor import NerdDictationMonitor
from nerd_dock.stt_stream import (
    DEFAULT_KEY_FILE,
    DEFAULT_MODEL,
    StreamingSTT,
    load_api_key,
    make_typer,
)

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
        default=shutil.which("nerd-dictation")
        or os.path.expanduser("~/.local/bin/nerd-dictation"),
        help="Path to nerd-dictation (default: found on PATH, else %(default)s)",
    )
    parser.add_argument(
        "--cookie",
        type=str,
        default="/tmp/nerd-dictation.cookie",  # nosec B108
        help="Path to cookie file (default: %(default)s)",
    )
    parser.add_argument(
        "--input-tool",
        type=str,
        default="YDOTOOL",
        choices=("XDOTOOL", "DOTOOL", "DOTOOLC", "YDOTOOL", "WTYPE", "STDOUT"),
        help="nerd-dictation --simulate-input-tool (default: %(default)s)",
    )
    parser.add_argument(
        "--stt-url",
        type=str,
        default=os.environ.get("NERD_DOCK_STT_URL"),
        help="Stream to an OpenAI-Realtime STT server (e.g. http://host:8000) "
        "instead of nerd-dictation. Env: NERD_DOCK_STT_URL",
    )
    parser.add_argument(
        "--stt-backend",
        choices=("realtime", "kyutai"),
        default=os.environ.get("NERD_DOCK_STT_BACKEND", "realtime"),
        help="realtime = OpenAI-Realtime/Speaches (text after a pause); "
        "kyutai = Kyutai moshi-server (words while you talk, e.g. "
        "http://host:8001). Env: NERD_DOCK_STT_BACKEND (default: %(default)s)",
    )
    parser.add_argument(
        "--stt-model",
        type=str,
        default=DEFAULT_MODEL,
        help="STT model id (default: %(default)s)",
    )
    parser.add_argument(
        "--stt-key-file",
        type=str,
        default=DEFAULT_KEY_FILE,
        help="File with STT_API_KEY=... (or set NERD_DOCK_STT_API_KEY); "
        "default: %(default)s",
    )
    parser.add_argument(
        "--stt-silence-ms",
        type=int,
        default=None,
        help="Server VAD silence before an utterance is finalized (ms)",
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
        stream = None
        if args.stt_url and args.stt_backend == "kyutai":
            stream = KyutaiSTT(
                url=args.stt_url,
                api_key=load_api_key(args.stt_key_file),
                type_text=make_typer(args.input_tool),
            )
            logger.info("Streaming dictation via %s", stream.url)
        elif args.stt_url:
            stream = StreamingSTT(
                url=args.stt_url,
                api_key=load_api_key(args.stt_key_file),
                type_text=make_typer(args.input_tool),
                model=args.stt_model,
                silence_ms=args.stt_silence_ms,
            )
            logger.info("Streaming dictation via %s", stream.url)
        controller = NerdDockController(
            executable_path=args.executable,
            cookie_path=args.cookie,
            input_tool=args.input_tool,
            stream=stream,
        )
        controller.start_input_daemon()
        monitor = NerdDictationMonitor(
            controller=controller,
            cookie_path=args.cookie,
            poll_interval=args.poll_interval,
        )

        # Import UI indicator here to ensure it's loaded after GTK verification
        from nerd_dock.ui_indicator import NerdDockIndicator

        indicator = NerdDockIndicator(controller=controller, monitor=monitor)

        indicator.enable_remote_toggle()

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
