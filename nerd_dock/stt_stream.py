"""Streaming speech-to-text against a Kyutai moshi-server (``/api/asr-streaming``).

Each word arrives about half a second after it is spoken and is never revised, so words
are typed while you talk. Protocol (kyutai-labs/delayed-streams-modeling):

* client -> server: msgpack ``{"type": "Audio", "pcm": [float32, ...]}``, 24 kHz mono,
  1920 samples (80 ms) per message; ``{"type": "Marker", "id": n}`` to flush.
* server -> client: ``Word{text,start_time}``, ``EndWord``, ``Step`` (VAD), ``Ready``,
  and the ``Marker`` echoed once all audio sent before it has been transcribed.
* auth: header ``kyutai-api-key: <key>``.

No GTK imports: usable headless (``nerd-dock-stream``) and from the tray.
"""

import array
import logging
import os
import shutil
import subprocess  # nosec B404
import sys
import threading
import time
from collections.abc import Callable

import msgpack

logger = logging.getLogger("nerd_dock.stt")

STATE_STOPPED = "STOPPED"
STATE_RECORDING = "RECORDING"
STATE_SUSPENDED = "SUSPENDED"
STATE_STOPPING = "STOPPING"  # flushing the last words

SAMPLE_RATE = 24000
FRAME_SAMPLES = 1920  # 80 ms, the model's frame
FRAME_BYTES = FRAME_SAMPLES * 2  # PCM16 from the capture tool
FRAME_SECONDS = FRAME_SAMPLES / SAMPLE_RATE
SILENCE = [0.0] * FRAME_SAMPLES
FLUSH_TIMEOUT = 5.0  # stop: max wait for the marker echo
FLUSH_TAIL_S = 1.5  # stop: silence before the marker so the last word completes
MAX_BACKOFF = 15.0
ASR_PATH = "/api/asr-streaming"
DEFAULT_KEY_FILE = "~/.config/pi-patch/stt.env"
KEY_VARS = ("NERD_DOCK_STT_API_KEY", "STT_API_KEY")


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


def asr_url(base_url: str) -> str:
    """``http(s)://host:port`` or a ws(s) URL -> the streaming ASR endpoint."""
    url = base_url.rstrip("/")
    url = url.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
    return url if url.endswith(ASR_PATH) else url + ASR_PATH


def pcm16_to_floats(chunk: bytes) -> list[float]:
    """Little-endian PCM16 bytes -> floats in [-1, 1)."""
    samples = array.array("h")
    samples.frombytes(chunk[: len(chunk) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    return [s / 32768.0 for s in samples]


def audio_message(samples: list[float]) -> bytes:
    """One msgpack Audio message (float32 on the wire)."""
    return msgpack.packb(
        {"type": "Audio", "pcm": samples}, use_bin_type=True, use_single_float=True
    )


class StreamingSTT:
    """One dictation session streamed to the server.

    Pause keeps the connection open and clocked with silence, so the last words before
    the pause are still delivered; stop sends a Marker and keeps feeding silence until
    the server echoes it.
    """

    def __init__(
        self,
        url: str,
        api_key: str | None,
        type_text: Callable[[str], None],
        capture_cmd: list[str] | None = None,
    ) -> None:
        self.url = asr_url(url)
        self._api_key = api_key
        self._type_text = type_text
        self._capture_cmd = capture_cmd
        self.state: str = STATE_STOPPED
        self.last_error: str | None = None
        self.words = 0
        self._paused = False
        self._finish = False  # flush on exit (stop), not cancel
        self._stop = threading.Event()
        self._marker_seen = threading.Event()
        self._capture: subprocess.Popen | None = None
        self._ws = None

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
        threading.Thread(target=self._run, daemon=True).start()
        return True

    def suspend(self) -> bool:
        """Sends silence instead of the microphone; the connection stays open."""
        if self.state != STATE_RECORDING:
            return False
        self._paused = True
        self.state = STATE_SUSPENDED
        return True

    def resume(self) -> bool:
        """Sends the microphone again."""
        if self.state != STATE_SUSPENDED:
            return False
        self._paused = False
        self.state = STATE_RECORDING
        return True

    def stop(self) -> bool:
        """Ends the session after typing the words still on their way."""
        return self._shutdown(finish=True)

    def cancel(self) -> bool:
        """Ends the session immediately, discarding pending words."""
        return self._shutdown(finish=False)

    # Internals --------------------------------------------------------------

    def _shutdown(self, finish: bool) -> bool:
        if self.state == STATE_STOPPED:
            return False
        self._finish = finish
        self.state = STATE_STOPPING
        self._stop.set()
        self._kill_capture()
        # Non-blocking: the stream thread flushes, then reports STOPPED itself.
        return True

    def _kill_capture(self) -> None:
        proc, self._capture = self._capture, None
        if proc:
            proc.kill()
            proc.wait()

    def _send(self, data: bytes) -> None:
        ws = self._ws
        if ws is None:
            return
        try:
            ws.send(data)
        except Exception as e:
            logger.debug("STT send failed: %s", e)

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
        from websockets.exceptions import InvalidStatus
        from websockets.sync.client import connect

        headers = {"kyutai-api-key": self._api_key} if self._api_key else {}
        self._marker_seen.clear()
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
                self._stream_audio(receiver)
                if self._finish:
                    self._flush(receiver)
            finally:
                self._ws = None

    def _stream_audio(self, receiver: threading.Thread) -> None:
        while not self._stop.is_set() and receiver.is_alive():
            capture = self._capture
            chunk = capture.stdout.read(FRAME_BYTES) if capture else b""
            if not chunk:
                if self._stop.is_set():
                    return
                raise ConnectionError("microphone capture ended")
            samples = SILENCE if self._paused else pcm16_to_floats(chunk)
            self._send(audio_message(samples))
        if not self._stop.is_set():
            raise ConnectionError("server closed the connection")

    def _flush(self, receiver: threading.Thread) -> None:
        """Trailing silence (so the last word completes), a Marker, then silence until
        the server echoes it. Without the tail the last word is lost (verified live)."""
        silence = audio_message(SILENCE)
        for _ in range(int(FLUSH_TAIL_S / FRAME_SECONDS)):
            if not receiver.is_alive():
                return
            self._send(silence)
            time.sleep(FRAME_SECONDS)
        self._send(msgpack.packb({"type": "Marker", "id": 0}))
        end = time.monotonic() + FLUSH_TIMEOUT
        while receiver.is_alive() and time.monotonic() < end:
            if self._marker_seen.wait(FRAME_SECONDS):
                return
            self._send(silence)
        logger.debug("Flush: no marker echo within %.0fs", FLUSH_TIMEOUT)

    def _receive(self, ws) -> None:
        try:
            for raw in ws:
                if isinstance(raw, bytes):
                    self._handle_event(msgpack.unpackb(raw, raw=False))
        except Exception as e:
            logger.debug("STT receiver ended: %s", e)
        finally:
            self._marker_seen.set()

    def _handle_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "Word":
            text = (event.get("text") or "").strip()
            if text:
                self.words += 1
                self._type_text(text + " ")
        elif kind == "Marker":
            self._marker_seen.set()
        elif kind == "Error":
            logger.warning("STT server error: %s", event.get("message", event))
