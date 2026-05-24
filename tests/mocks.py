"""Headless mock classes and helpers for testing Nerd-Dock."""

import io
from typing import Any


class MockProcess:
    """Mock subprocess process handle."""

    def __init__(self, pid: int, args: list[str]):
        self.pid = pid
        self.args = args
        self.returncode = 0
        self.stdout = io.StringIO("Loading model...\nModel loaded.\n")

    def poll(self) -> int:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


class MockSubprocess:
    """Mock subprocess module namespace."""

    def __init__(self) -> None:
        self.spawned_processes: list[MockProcess] = []
        self.next_pid = 1234
        self.last_run_args: list[list[str]] = []
        self.should_fail = False

    def Popen(self, args: list[str], *extra_args: Any, **kwargs: Any) -> MockProcess:
        if self.should_fail:
            raise OSError("Subprocess spawn failed")
        proc = MockProcess(self.next_pid, args)
        self.next_pid += 1
        self.spawned_processes.append(proc)
        return proc

    def run(self, args: list[str], *extra_args: Any, **kwargs: Any) -> Any:
        self.last_run_args.append(args)

        class CompletedProcess:
            def __init__(self, run_args: list[str], exit_code: int = 0):
                self.args = run_args
                self.returncode = exit_code
                self.stdout = b""
                self.stderr = b""

        return CompletedProcess(args)


class MockFileSystem:
    """Mock OS and built-in file operations."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.existing_pids: list[int] = []

    def exists(self, path: str) -> bool:
        # Check if it's a PID check under /proc
        if path.startswith("/proc/"):
            try:
                pid = int(path.split("/")[2])
                return pid in self.existing_pids
            except (ValueError, IndexError):
                return False
        return path in self.files

    def remove(self, path: str) -> None:
        if path in self.files:
            del self.files[path]
        else:
            raise FileNotFoundError(f"[Errno 2] No such file: '{path}'")

    def mock_open(self, path: str, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        # Returns a stream mock reading/writing to self.files
        fs_self = self

        class MockFileStream:
            def __init__(self) -> None:
                self.mode = mode
                self.path = path
                self._lines = fs_self.files.get(self.path, "").splitlines(keepends=True)
                self._index = 0

            def __enter__(self) -> "MockFileStream":
                return self

            def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
                pass

            def read(self) -> str:
                if "r" not in self.mode:
                    raise OSError("File not open for reading")
                return fs_self.files.get(self.path, "")

            def write(self, content: str) -> None:
                if "w" not in self.mode:
                    raise OSError("File not open for writing")
                fs_self.files[self.path] = str(content)
                self._lines = str(content).splitlines(keepends=True)

            def __iter__(self) -> "MockFileStream":
                return self

            def __next__(self) -> str:
                if self._index >= len(self._lines):
                    raise StopIteration
                line = self._lines[self._index]
                self._index += 1
                return line

        if "w" not in mode and path not in self.files:
            raise FileNotFoundError(f"[Errno 2] No such file: '{path}'")
        return MockFileStream()
