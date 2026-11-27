"""Kyutai streaming backend and headless CLI, against a fake msgpack server (no gi)."""

import sys
import threading
import unittest

import msgpack
from websockets.sync.server import serve

from nerd_dock import stream_cli
from nerd_dock.kyutai_stream import (
    FRAME_SAMPLES,
    KyutaiSTT,
    audio_message,
    kyutai_url,
    pcm16_to_floats,
)
from nerd_dock.stt_stream import STATE_STOPPED, STATE_SUSPENDED
from tests.test_stt_stream import wait_for

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


class TestHelpers(unittest.TestCase):
    def test_url(self) -> None:
        self.assertEqual(kyutai_url("http://h:8001"), "ws://h:8001/api/asr-streaming")
        self.assertEqual(
            kyutai_url("wss://h/api/asr-streaming/"), "wss://h/api/asr-streaming"
        )

    def test_pcm16_to_floats(self) -> None:
        self.assertEqual(
            pcm16_to_floats(b"\x00\x00\x00\x40\x00\x80\x01"), [0.0, 0.5, -1.0]
        )

    def test_audio_message_is_float32_msgpack(self) -> None:
        packed = audio_message([0.25] * FRAME_SAMPLES)
        self.assertEqual(packed.count(b"\xca"), FRAME_SAMPLES)
        self.assertEqual(msgpack.unpackb(packed)["pcm"][0], 0.25)


class TestKyutaiStream(unittest.TestCase):
    def setUp(self) -> None:
        self.server = FakeKyutai()
        self.typed: list[str] = []
        self.stt = KyutaiSTT(
            f"http://127.0.0.1:{self.server.port}",
            "key123",
            self.typed.append,
            capture_cmd=FAKE_MIC,
        )

    def tearDown(self) -> None:
        self.stt.cancel()
        wait_for(lambda: self.stt.state == STATE_STOPPED)
        self.server.close()

    def test_words_typed_as_they_arrive(self) -> None:
        self.assertTrue(self.stt.start())
        self.assertTrue(wait_for(lambda: len(self.typed) == 2))
        self.assertEqual(self.typed, ["Hello, ", "world. "])
        self.assertEqual(self.server.key, "key123")
        self.assertEqual(len(self.server.audio[0]), FRAME_SAMPLES)
        self.assertAlmostEqual(self.server.audio[0][0], 4096 / 32768)

    def test_pause_sends_silence_and_resume_sends_mic(self) -> None:
        self.stt.start()
        wait_for(lambda: len(self.server.audio) > 2)
        self.assertTrue(self.stt.suspend())
        self.assertEqual(self.stt.state, STATE_SUSPENDED)
        n = len(self.server.audio)
        self.assertTrue(wait_for(lambda: len(self.server.audio) > n + 3))
        self.assertFalse(any(self.server.audio[-1]))  # silence keeps the model clocked
        self.assertTrue(self.stt.resume())
        n = len(self.server.audio)
        self.assertTrue(wait_for(lambda: len(self.server.audio) > n + 2))
        self.assertTrue(any(self.server.audio[-1]))

    def test_stop_flushes_with_marker(self) -> None:
        self.stt.start()
        wait_for(lambda: len(self.server.audio) > 2)
        self.assertTrue(self.stt.stop())
        self.assertTrue(wait_for(lambda: self.stt.state == STATE_STOPPED, timeout=3))
        self.assertEqual(self.server.markers, 1)

    def test_cancel_skips_flush(self) -> None:
        self.stt.start()
        wait_for(lambda: len(self.server.audio) > 2)
        self.assertTrue(self.stt.cancel())
        self.assertTrue(wait_for(lambda: self.stt.state == STATE_STOPPED))
        self.assertEqual(self.server.markers, 0)

    def test_wrong_key_stops_without_retry(self) -> None:
        def reject(connection, _request):
            return connection.respond(403, "Unauthorized\n")

        srv = serve(lambda ws: None, "127.0.0.1", 0, process_request=reject)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        stt = KyutaiSTT(
            f"http://127.0.0.1:{srv.socket.getsockname()[1]}",
            "bad",
            self.typed.append,
            capture_cmd=FAKE_MIC,
        )
        self.assertTrue(stt.start())
        self.assertTrue(wait_for(lambda: stt.state == STATE_STOPPED))
        self.assertIn("rejected the API key", stt.last_error)
        srv.shutdown()


class TestCli(unittest.TestCase):
    def test_missing_url_is_usage_error(self) -> None:
        self.assertEqual(stream_cli.main(["--key-file", "/nonexistent"]), 2)

    def test_run_prints_words_and_stops_cleanly(self) -> None:
        server = FakeKyutai()
        typed: list[str] = []
        stt = KyutaiSTT(
            f"http://127.0.0.1:{server.port}", "k", typed.append, capture_cmd=FAKE_MIC
        )
        threading.Timer(1.0, stt.stop).start()
        self.assertEqual(stream_cli.run(stt, poll=0.02), 0)
        self.assertEqual(typed, ["Hello, ", "world. "])
        server.close()

    def test_run_fails_when_capture_missing(self) -> None:
        stt = KyutaiSTT("http://x", None, print, capture_cmd=["/nonexistent/mic"])
        self.assertEqual(stream_cli.run(stt), 1)


if __name__ == "__main__":
    unittest.main()
