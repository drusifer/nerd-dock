"""Typing commands and the ydotool daemon."""

import os
import socket
import tempfile
import unittest
from unittest.mock import patch

from nerd_dock.typing_tools import InputDaemon, make_typer


class TestTyper(unittest.TestCase):
    def test_ydotool_command(self) -> None:
        with patch("subprocess.run") as run:
            make_typer("YDOTOOL")("hi ")
        run.assert_called_once_with(["ydotool", "type", "--", "hi "], check=False)

    def test_dotool_reads_stdin(self) -> None:
        with patch("subprocess.run") as run:
            make_typer("DOTOOL")("hi")
        run.assert_called_once_with(
            ["dotool"], input="type hi\n", text=True, check=False
        )

    def test_stdout_prints_words_on_one_line(self) -> None:
        with patch("builtins.print") as out:
            make_typer("STDOUT")("hi ")
        out.assert_called_once_with("hi ", end="", flush=True)


class TestInputDaemon(unittest.TestCase):
    def test_stale_socket_is_replaced_and_daemon_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".ydotool_socket")
            with socket.socket(socket.AF_UNIX) as s:  # bind, then die: stale file
                s.bind(path)
            daemon = InputDaemon("YDOTOOL")
            with (
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": tmp}),
                patch("shutil.which", return_value="/usr/bin/ydotoold"),
                patch("subprocess.Popen") as popen,
            ):
                daemon.start()
                daemon.stop()
            self.assertFalse(os.path.exists(path))
            popen.assert_called_once_with(
                ["/usr/bin/ydotoold", f"--socket-path={path}"]
            )
            popen.return_value.terminate.assert_called_once()

    def test_not_started_for_other_tools(self) -> None:
        with patch("subprocess.Popen") as popen:
            InputDaemon("XDOTOOL").start()
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
