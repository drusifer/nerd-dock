"""A fake Kyutai server and microphone for tests."""

import sys
import threading
import time

import msgpack
from websockets.sync.server import serve

# Endless 80 ms frames of a constant non-zero sample, paced like a microphone.
FAKE_MIC = [
    sys.executable,
    "-c",
    "import sys,time\n"
    "while True:\n"
    " sys.stdout.buffer.write(b'\\x00\\x10' * 1920); sys.stdout.buffer.flush(); "
    "time.sleep(0.08)",
]


class FakeKyutai:
    """Sends a Word every 3 audio frames; echoes a Marker 2 frames after it arrives."""

    def __init__(self, words=("Hello,", "world.")) -> None:
        self.key: str | None = None
        self.audio: list[list[float]] = []
        self.markers = 0
        self._words = list(words)
        self._server = serve(self._handle, "127.0.0.1", 0)
        self.port = self._server.socket.getsockname()[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def _handle(self, ws) -> None:
        self.key = ws.request.headers.get("kyutai-api-key")
        marker_at = None
        for raw in ws:
            msg = msgpack.unpackb(raw, raw=False)
            if msg["type"] == "Marker":
                self.markers += 1
                marker_at = len(self.audio) + 2
                continue
            self.audio.append(msg["pcm"])
            if len(self.audio) % 3 == 0 and self._words:
                word = {"type": "Word", "text": self._words.pop(0), "start_time": 0.1}
                ws.send(msgpack.packb(word))
            if marker_at is not None and len(self.audio) >= marker_at:
                ws.send(msgpack.packb({"type": "Marker", "id": 0}))
                marker_at = None

    def close(self) -> None:
        self._server.shutdown()


def wait_for(cond, timeout=5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False
