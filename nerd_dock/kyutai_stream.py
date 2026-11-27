"""Kyutai streaming speech-to-text backend (moshi-server ``/api/asr-streaming``).

Unlike the OpenAI-Realtime backend (Whisper, text only after a pause), Kyutai STT emits
each word about half a second after it is spoken and never revises it, so words are
typed while you talk. Protocol (kyutai-labs/delayed-streams-modeling):

* client -> server: msgpack ``{"type": "Audio", "pcm": [float32, ...]}``, 24 kHz mono,
  1920 samples (80 ms) per message; ``{"type": "Marker", "id": n}`` to flush.
* server -> client: ``Word{text,start_time}``, ``EndWord``, ``Step`` (VAD), ``Ready``,
  and the ``Marker`` echoed once all audio sent before it has been transcribed.
* auth: header ``kyutai-api-key: <key>``.

No GTK imports: usable headless (``nerd-dock-stream``) and from the tray.
"""

import array
import logging
import sys
import threading
import time
from collections.abc import Callable

import msgpack

from nerd_dock.stt_stream import (
    STATE_RECORDING,
    STATE_SUSPENDED,
    StreamingSTT,
)

logger = logging.getLogger("nerd_dock.kyutai")

FRAME_SAMPLES = 1920  # 80 ms at 24 kHz, the model's frame
FRAME_BYTES = FRAME_SAMPLES * 2  # PCM16 from the capture tool
SILENCE = [0.0] * FRAME_SAMPLES
FLUSH_TIMEOUT = 5.0  # stop: max wait for the marker echo
FLUSH_TAIL_S = 1.5  # stop: silence before the marker so the last word completes
ASR_PATH = "/api/asr-streaming"


def kyutai_url(base_url: str) -> str:
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


class KyutaiSTT(StreamingSTT):
    """One dictation session streamed to a Kyutai moshi-server.

    Same control surface and states as :class:`StreamingSTT`. Pause keeps the stream
    clocked with silence (so the last words before the pause are still delivered);
    stop sends a Marker and keeps feeding silence until the server echoes it.
    """

    def __init__(
        self,
        url: str,
        api_key: str | None,
        type_text: Callable[[str], None],
        capture_cmd: list[str] | None = None,
    ) -> None:
        super().__init__(url, api_key, type_text, capture_cmd=capture_cmd)
        self.url = kyutai_url(url)
        self._marker_seen = threading.Event()
        self.words = 0

    # Control surface: pause must not send the Realtime commit message.

    def suspend(self) -> bool:
        if self.state != STATE_RECORDING:
            return False
        self._paused = True
        self.state = STATE_SUSPENDED
        return True

    # Wire format ------------------------------------------------------------

    def _session(self) -> None:
        headers = {"kyutai-api-key": self._api_key} if self._api_key else {}
        self._marker_seen.clear()
        with self._connected(headers) as receiver:
            self._stream_audio(receiver)
            if self._finish:
                self._flush(receiver)

    def _stream_audio(self, receiver: threading.Thread) -> None:
        while not self._stop.is_set() and receiver.is_alive():
            capture = self._capture
            chunk = capture.stdout.read(FRAME_BYTES) if capture else b""
            if not chunk:
                if self._stop.is_set():
                    return
                raise ConnectionError("microphone capture ended")
            samples = SILENCE if self._paused else pcm16_to_floats(chunk)
            self._send_data(audio_message(samples))
        if not self._stop.is_set():
            raise ConnectionError("server closed the connection")

    def _flush(self, receiver: threading.Thread) -> None:
        """Trailing silence (so the last word completes), a Marker, then silence until
        the server echoes it. Without the tail the last word is lost (verified live)."""
        silence = audio_message(SILENCE)
        frame_s = FRAME_SAMPLES / 24000
        for _ in range(int(FLUSH_TAIL_S / frame_s)):
            if not receiver.is_alive():
                return
            self._send_data(silence)
            time.sleep(frame_s)
        self._send_data(msgpack.packb({"type": "Marker", "id": 0}))
        end = time.monotonic() + FLUSH_TIMEOUT
        while receiver.is_alive() and time.monotonic() < end:
            if self._marker_seen.wait(frame_s):
                return
            self._send_data(silence)
        logger.debug("Kyutai flush: no marker echo within %.0fs", FLUSH_TIMEOUT)

    def _receive(self, ws) -> None:
        try:
            for raw in ws:
                if isinstance(raw, bytes):
                    self._handle_event(msgpack.unpackb(raw, raw=False))
        except Exception as e:
            logger.debug("Kyutai receiver ended: %s", e)
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
            logger.warning("Kyutai server error: %s", event.get("message", event))
