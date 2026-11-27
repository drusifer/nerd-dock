"""Command-line options shared by the tray app and the headless client."""

import argparse

from nerd_dock.stt_stream import DEFAULT_KEY_FILE
from nerd_dock.typing_tools import INPUT_TOOLS


def add_common_options(
    parser: argparse.ArgumentParser, key_flag: str, default_tool: str
) -> None:
    """Adds the key file, input tool and verbosity options."""
    parser.add_argument(
        key_flag,
        default=DEFAULT_KEY_FILE,
        help="File with STT_API_KEY=... (or set NERD_DOCK_STT_API_KEY); "
        "default: %(default)s",
    )
    parser.add_argument(
        "--input-tool",
        default=default_tool,
        choices=INPUT_TOOLS,
        help="How words are typed; STDOUT prints them (default: %(default)s)",
    )
    parser.add_argument("--verbose", action="store_true", help="Debug logging")
