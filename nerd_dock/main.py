"""Main entry point for the Nerd-Dock tray application."""

import argparse
import logging
import os
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

from nerd_dock.options import add_common_options
from nerd_dock.stt_stream import StreamingSTT, load_api_key
from nerd_dock.typing_tools import InputDaemon, make_typer

logger = logging.getLogger("nerd_dock.main")


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Nerd-Dock: tray control for streaming dictation.",
    )
    parser.add_argument(
        "--stt-url",
        default=os.environ.get("NERD_DOCK_STT_URL"),
        help="Server, e.g. http://host:8001 (env NERD_DOCK_STT_URL)",
    )
    add_common_options(parser, "--stt-key-file", default_tool="YDOTOOL")
    args = parser.parse_args(argv)
    if not args.stt_url:
        parser.error("pass --stt-url or set NERD_DOCK_STT_URL")
    return args


def _run_tray(args: argparse.Namespace) -> None:
    # Imported here so it only loads after the GTK check.
    from nerd_dock.ui_indicator import NerdDockIndicator

    stream = StreamingSTT(
        url=args.stt_url,
        api_key=load_api_key(args.stt_key_file),
        type_text=make_typer(args.input_tool),
    )
    daemon = InputDaemon(args.input_tool)
    daemon.start()
    indicator = NerdDockIndicator(stream)
    indicator.enable_remote_toggle()

    def quit_on_signal(signum: int, _frame) -> None:
        logger.info("Signal %d received, quitting.", signum)
        indicator.shutdown()
        Gtk.main_quit()

    signal.signal(signal.SIGINT, quit_on_signal)
    signal.signal(signal.SIGTERM, quit_on_signal)
    # Python only runs signal handlers when the interpreter gets a turn.
    GLib.timeout_add(250, lambda: True)

    logger.info("Streaming dictation via %s", stream.url)
    try:
        Gtk.main()
    finally:
        daemon.stop()


def main() -> int:
    args = parse_arguments()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    if not HAS_GRAPHICS:
        logger.error(
            "GTK 3 / AyatanaAppIndicator3 are not available. Run "
            "'make install-system-deps' and use a desktop session. Error: %s",
            GRAPHICS_ERROR,
        )
        return 1
    try:
        _run_tray(args)
    except Exception:
        logger.exception("Nerd-Dock failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
