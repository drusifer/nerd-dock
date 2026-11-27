"""Typing recognised words into the focused window."""

import logging
import os
import shutil
import socket
import subprocess  # nosec B404
from collections.abc import Callable

logger = logging.getLogger("nerd_dock.typing")

INPUT_TOOLS = ("YDOTOOL", "WTYPE", "XDOTOOL", "DOTOOL", "DOTOOLC", "STDOUT")
_COMMANDS = {
    "YDOTOOL": ["ydotool", "type", "--"],
    "WTYPE": ["wtype", "--"],
    "XDOTOOL": ["xdotool", "type", "--clearmodifiers", "--"],
}


def make_typer(input_tool: str) -> Callable[[str], None]:
    """Returns a function that types text with the given input tool."""

    def type_text(text: str) -> None:
        if input_tool in _COMMANDS:
            subprocess.run([*_COMMANDS[input_tool], text], check=False)  # nosec B603
        elif input_tool in ("DOTOOL", "DOTOOLC"):
            subprocess.run(  # nosec B603
                [input_tool.lower()], input=f"type {text}\n", text=True, check=False
            )
        else:
            print(text, end="", flush=True)

    return type_text


def _socket_alive(path: str) -> bool:
    """True if something is accepting connections on the unix socket."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        try:
            sock.connect(path)
        except OSError:
            return False
    return True


class InputDaemon:
    """Runs ydotoold (needed to type on Wayland) when YDOTOOL is selected."""

    def __init__(self, input_tool: str) -> None:
        self.input_tool = input_tool
        self._process: subprocess.Popen | None = None

    def start(self) -> None:
        """Starts ydotoold unless one is already serving the socket.

        Sets YDOTOOL_SOCKET so the daemon and the ydotool client agree on it.
        """
        if self.input_tool != "YDOTOOL":
            return
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")  # nosec B108
        socket_path = os.path.join(runtime_dir, ".ydotool_socket")
        os.environ["YDOTOOL_SOCKET"] = socket_path
        daemon = shutil.which("ydotoold")
        if not daemon:
            logger.warning("ydotoold not found; typing will not work.")
            return
        if os.path.exists(socket_path):
            if _socket_alive(socket_path):
                logger.info("ydotoold already running on %s", socket_path)
                return
            logger.info("Removing stale ydotool socket %s", socket_path)
            os.remove(socket_path)
        try:
            self._process = subprocess.Popen(  # nosec B603
                [daemon, f"--socket-path={socket_path}"],
            )
            logger.info("Started ydotoold on %s", socket_path)
        except OSError as e:
            logger.error("Failed to start ydotoold: %s", e)

    def stop(self) -> None:
        """Terminates ydotoold if it was started here."""
        if not self._process:
            return
        self._process.terminate()
        self._process.wait(timeout=2)
        self._process = None
        socket_path = os.environ.get("YDOTOOL_SOCKET")
        if socket_path and os.path.exists(socket_path):
            os.remove(socket_path)
