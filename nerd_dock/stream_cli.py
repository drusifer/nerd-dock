"""Headless streaming dictation: ``nerd-dock-stream``.

Captures the microphone, streams it to a Kyutai STT server and types (or prints) each
word as it is recognised. No GTK or display needed. Signals: SIGINT/SIGTERM stop
(flushing the last words), SIGUSR1 toggles pause.
"""

import argparse
import logging
import os
import shlex
import signal
import sys
import time

from nerd_dock.options import add_common_options
from nerd_dock.stt_stream import (
    STATE_RECORDING,
    STATE_STOPPED,
    StreamingSTT,
    load_api_key,
)
from nerd_dock.typing_tools import InputDaemon, make_typer

logger = logging.getLogger("nerd_dock.stream_cli")


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nerd-dock-stream",
        description="Stream the microphone to a Kyutai STT server and type words "
        "as they are spoken.",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get("NERD_DOCK_STT_URL"),
        help="Server, e.g. http://192.168.86.68:8001 (env NERD_DOCK_STT_URL)",
    )
    add_common_options(parser, "--key-file", default_tool="STDOUT")
    parser.add_argument(
        "--capture-cmd",
        help="Override the microphone command (raw PCM16 24 kHz mono on stdout), "
        "e.g. for tests: 'ffmpeg -i clip.wav -f s16le -ar 24000 -ac 1 -'",
    )
    return parser.parse_args(argv)


def run(stream: StreamingSTT, poll: float = 0.1) -> int:
    """Starts the stream and blocks until it stops. Returns an exit code."""

    def stop(_signum, _frame) -> None:
        stream.stop()

    def toggle(_signum, _frame) -> None:
        if stream.state == STATE_RECORDING:
            stream.suspend()
        else:
            stream.resume()

    handlers = {signal.SIGINT: stop, signal.SIGTERM: stop, signal.SIGUSR1: toggle}
    previous = {sig: signal.signal(sig, fn) for sig, fn in handlers.items()}
    try:
        if not stream.start():
            logger.error("Cannot start: %s", stream.last_error)
            return 1
        logger.info("Streaming to %s (Ctrl-C stops, SIGUSR1 pauses)", stream.url)
        while stream.state != STATE_STOPPED:
            time.sleep(poll)
        if stream.last_error and stream.words == 0:
            logger.error("%s", stream.last_error)
            return 1
        return 0
    finally:
        for sig, fn in previous.items():
            signal.signal(sig, fn)


def main(argv: list[str] | None = None) -> int:
    args = parse_arguments(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if not args.url:
        logger.error("No server: pass --url or set NERD_DOCK_STT_URL.")
        return 2

    stream = StreamingSTT(
        url=args.url,
        api_key=load_api_key(args.key_file),
        type_text=make_typer(args.input_tool),
        capture_cmd=shlex.split(args.capture_cmd) if args.capture_cmd else None,
    )
    daemon = InputDaemon(args.input_tool)
    daemon.start()
    try:
        return run(stream)
    finally:
        if args.input_tool == "STDOUT":
            print(flush=True)
        daemon.stop()


if __name__ == "__main__":
    sys.exit(main())
