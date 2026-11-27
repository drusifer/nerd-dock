"""Streaming speech-to-text backend (OpenAI Realtime WebSocket, e.g. Speaches).

Captures the microphone as raw PCM16 mono 24 kHz, streams it over a WebSocket and
types every finished utterance through the configured input tool. See
``stt-streaming-client.md`` for the protocol notes this follows.
"""

import base64
import json
import logging
import os
import shutil
import subprocess  # nosec B404
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from urllib.parse import quote

logger = logging.getLogger("nerd_dock.stt")

STATE_STOPPED = "STOPPED"
STATE_RECORDING = "RECORDING"
STATE_SUSPENDED = "SUSPENDED"

SAMPLE_RATE = 24000
CHUNK_BYTES = SAMPLE_RATE * 2 // 10  # 100 ms of PCM16 mono
DEFAULT_MODEL = "Systran/faster-distil-whisper-large-v3"
DEFAULT_KEY_FILE = "~/.config/pi-patch/stt.env"
KEY_VARS = ("NERD_DOCK_STT_API_KEY", "STT_API_KEY")
# Whisper likes to invent these on near-silence.
JUNK_TRANSCRIPTS = frozenset({"", ".", "you", "thanks.", "thank you."})
DRAIN_TIMEOUT = 3.0
MAX_BACKOFF = 15.0


def load_api_key(key_file: str | None = DEFAULT_KEY_FILE) -> str | None:
    """Returns the API key from the environment, else from the key file."""
    for var in KEY_VARS:
        if os.environ.get(var):
            return os.environ[var]
    if not key_file:
        return None
    try:
        with open(os.path.expanduser(key_file), encoding="utf-8") as f:
            for line in f:
                name, _, value = line.strip().removeprefix("export ").partition("=")
                if name in KEY_VARS and value:
                    return value.strip("'\"")
    except OSError as e:
        logger.debug("No STT key file: %s", e)
    return None


def realtime_url(base_url: str, model: str) -> str:
    """Builds the realtime endpoint from ``http(s)://host:port`` or a ws(s) URL."""
    url = base_url.rstrip("/")
    url = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    if "/v1/realtime" not in url:
        url = url.removesuffix("/v1") + "/v1/realtime"
    return f"{url}?intent=transcription&model={quote(model, safe='')}"


def session_update(model: str, silence_ms: int | None = None) -> dict:
    """The GA-dialect session.update message."""
    vad: dict = {"type": "server_vad"}
    if silence_ms:
        vad["silence_duration_ms"] = silence_ms
    return {
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {"type": "audio/pcm", "rate": SAMPLE_RATE},
                    "transcription": {"model": model},
                    "turn_detection": vad,
                }
            },
        },
    }


def keep_transcript(text: str) -> bool:
    """False for empty or known-junk transcripts."""
    return text.strip().lower() not in JUNK_TRANSCRIPTS


def capture_command() -> list[str] | None:
    """First available raw PCM16 24 kHz mono microphone capture command."""
    if shutil.which("parec"):
        return [
            "parec",
            "--format=s16le",
            f"--rate={SAMPLE_RATE}",
            "--channels=1",
            "--latency-msec=100",
        ]
    if shutil.which("arecord"):
        return ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", "24000", "-c", "1"]
    return None


def make_typer(input_tool: str | None) -> Callable[[str], None]:
    """Returns a function that types text with the given nerd-dictation input tool."""
    tool = (input_tool or "STDOUT").upper()
    commands = {
        "YDOTOOL": ["ydotool", "type", "--"],
        "WTYPE": ["wtype", "--"],
        "XDOTOOL": ["xdotool", "type", "--clearmodifiers", "--"],
    }

    def type_text(text: str) -> None:
        if tool in commands:
            subprocess.run([*commands[tool], text], check=False)  # nosec B603
        elif tool in ("DOTOOL", "DOTOOLC"):
            exe = "dotoolc" if tool == "DOTOOLC" else "dotool"
            subprocess.run(  # nosec B603
                [exe], input=f"type {text}\n", text=True, check=False
            )
        else:
            print(text, flush=True)

    return type_text


class StreamingSTT:
    """One dictation session streamed to a realtime STT server."""

    def __init__(
        self,
        url: str,
        api_key: str | None,
        type_text: Callable[[str], None],
        model: str = DEFAULT_MODEL,
        silence_ms: int | None = None,
        capture_cmd: list[str] | None = None,
    ) -> None:
        self.url = realtime_url(url, model)
        self._api_key = api_key
        self._type_text = type_text
        self._model = model
        self._silence_ms = silence_ms
        self._capture_cmd = capture_cmd
        self.state: str = STATE_STOPPED
        self.last_error: str | None = None
        self._paused = False
        self._finish = False  # commit and drain on exit (stop), not cancel
        self._stop = threading.Event()
        self._drained = threading.Event()
        self._capture: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._ws = None
        self._send_lock = threading.Lock()
        self._speech_stopped_at: float | None = None

    # Public control surface -------------------------------------------------

    def start(self) -> bool:
        """Opens the microphone and begins streaming. False if it cannot start."""
        if self.state != STATE_STOPPED:
            return False
        cmd = self._capture_cmd or capture_command()
        if not cmd:
            self.last_error = "No capture tool found (install pulseaudio-utils)."
            logger.error(self.last_error)
            return False
        try:
            self._capture = subprocess.Popen(  # nosec B603
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
        except OSError as e:
            self.last_error = f"Cannot start microphone capture: {e}"
            logger.error(self.last_error)
            return False
        self.last_error = None
        self._paused = False
        self._finish = False
        self._stop.clear()
        self.state = STATE_RECORDING
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    def suspend(self) -> bool:
        """Stops sending audio; flushes what was said so far."""
        if self.state != STATE_RECORDING:
            return False
        self._paused = True
        self.state = STATE_SUSPENDED
        self._send({"type": "input_audio_buffer.commit"})
        return True

    def resume(self) -> bool:
        """Resumes sending audio."""
        if self.state != STATE_SUSPENDED:
            return False
        self._paused = False
        self.state = STATE_RECORDING
        return True

    def stop(self) -> bool:
        """Ends the session, typing any pending utterance first."""
        return self._shutdown(finish=True)

    def cancel(self) -> bool:
        """Ends the session immediately, discarding pending audio."""
        return self._shutdown(finish=False)

    # Internals --------------------------------------------------------------

    def _shutdown(self, finish: bool) -> bool:
        if self.state == STATE_STOPPED:
            return False
        self._finish = finish
        self._stop.set()
        self._kill_capture()
        # Non-blocking: the stream thread drains, then reports STOPPED itself.
        return True

    def _kill_capture(self) -> None:
        proc, self._capture = self._capture, None
        if proc:
            proc.kill()
            proc.wait()

    def _send(self, message: dict) -> None:
        self._send_data(json.dumps(message))

    def _send_data(self, data: str | bytes) -> None:
        ws = self._ws
        if ws is None:
            return
        try:
            with self._send_lock:
                ws.send(data)
        except Exception as e:
            logger.debug("STT send failed: %s", e)

    @contextmanager
    def _connected(self, headers: dict[str, str]) -> Iterator[threading.Thread]:
        """Opens the WebSocket and starts the receiver thread, which is yielded.

        A rejected API key becomes PermissionError, so it is not retried.
        """
        from websockets.exceptions import InvalidStatus
        from websockets.sync.client import connect

        try:
            ws = connect(
                self.url, additional_headers=headers, open_timeout=10, max_size=None
            )
        except InvalidStatus as e:
            code = e.response.status_code
            if code in (401, 403):
                raise PermissionError(
                    f"STT server rejected the API key (HTTP {code})."
                ) from e
            raise
        with ws:
            self._ws = ws
            receiver = threading.Thread(target=self._receive, args=(ws,), daemon=True)
            receiver.start()
            try:
                yield receiver
            finally:
                self._ws = None

    def _run(self) -> None:
        """Connect/stream loop; reconnects with backoff until stopped."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                self._session()
                backoff = 1.0
            except PermissionError as e:
                self.last_error = str(e)
                logger.error("STT: %s", e)
                break
            except Exception as e:
                self.last_error = f"STT connection failed: {e}"
                logger.warning("%s; retrying in %.0fs", self.last_error, backoff)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF)
        self._kill_capture()
        self.state = STATE_STOPPED

    def _session(self) -> None:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        self._drained.clear()
        with self._connected(headers) as receiver:
            self._send(session_update(self._model, self._silence_ms))
            self._stream_audio(receiver)
            if self._finish:
                self._send({"type": "input_audio_buffer.commit"})
                self._drained.wait(DRAIN_TIMEOUT)

    def _stream_audio(self, receiver: threading.Thread) -> None:
        while not self._stop.is_set() and receiver.is_alive():
            capture = self._capture
            chunk = capture.stdout.read(CHUNK_BYTES) if capture else b""
            if not chunk:
                if self._stop.is_set():
                    return
                raise ConnectionError("microphone capture ended")
            if self._paused:
                continue
            audio = base64.b64encode(chunk).decode("ascii")
            self._send({"type": "input_audio_buffer.append", "audio": audio})
        if not self._stop.is_set():
            raise ConnectionError("server closed the connection")

    def _receive(self, ws) -> None:
        try:
            for raw in ws:
                self._handle_event(json.loads(raw))
        except Exception as e:
            logger.debug("STT receiver ended: %s", e)
        finally:
            self._drained.set()

    def _handle_event(self, event: dict) -> None:
        kind = event.get("type", "")
        if kind == "input_audio_buffer.speech_stopped":
            self._speech_stopped_at = time.monotonic()
        elif kind == "conversation.item.input_audio_transcription.completed":
            text = (event.get("transcript") or "").strip()
            heard = self._speech_stopped_at
            if heard is not None:
                logger.debug(
                    "STT latency: %.2fs from end of speech to text.",
                    time.monotonic() - heard,
                )
            if keep_transcript(text):
                started = time.monotonic()
                self._type_text(text + " ")
                logger.debug(
                    "STT typed %d chars in %.2fs.",
                    len(text),
                    time.monotonic() - started,
                )
            self._drained.set()
        elif kind == "error":
            logger.debug("STT server error: %s", event.get("error"))
            self._drained.set()
