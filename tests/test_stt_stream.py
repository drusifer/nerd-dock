"""Streaming client and headless CLI against a fake server (no gi)."""

import os
import tempfile
import threading
import unittest
from unittest.mock import patch

import msgpack
from websockets.sync.server import serve

from nerd_dock import stream_cli
from nerd_dock.stt_stream import (
    FRAME_SAMPLES,
    STATE_STOPPED,
    STATE_STOPPING,
    STATE_SUSPENDED,
    StreamingSTT,
    asr_url,
    audio_message,
    load_api_key,
    pcm16_to_floats,
)
from tests.fakes import FAKE_MIC, FakeKyutai, wait_for


class TestHelpers(unittest.TestCase):
    def test_url(self) -> None:
        self.assertEqual(asr_url("http://h:8001"), "ws://h:8001/api/asr-streaming")
        self.assertEqual(
            asr_url("wss://h/api/asr-streaming/"), "wss://h/api/asr-streaming"
        )

    def test_pcm16_to_floats(self) -> None:
        self.assertEqual(
            pcm16_to_floats(b"\x00\x00\x00\x40\x00\x80\x01"), [0.0, 0.5, -1.0]
        )

    def test_audio_message_is_float32_msgpack(self) -> None:
        packed = audio_message([0.25] * FRAME_SAMPLES)
        self.assertEqual(packed.count(b"\xca"), FRAME_SAMPLES)
        self.assertEqual(msgpack.unpackb(packed)["pcm"][0], 0.25)

    def test_api_key_from_file(self) -> None:
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write("export STT_API_KEY='abc'\n")
        self.addCleanup(os.remove, f.name)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(load_api_key(f.name), "abc")
            self.assertIsNone(load_api_key("/nonexistent"))


class TestStream(unittest.TestCase):
    def setUp(self) -> None:
        self.server = FakeKyutai()
        self.typed: list[str] = []
        self.stt = StreamingSTT(
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
        self.assertEqual(self.stt.state, STATE_STOPPING)
        self.assertFalse(self.stt.start())  # not until the flush is done
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
        stt = StreamingSTT(
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
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(stream_cli.main(["--key-file", "/nonexistent"]), 2)

    def test_run_prints_words_and_stops_cleanly(self) -> None:
        server = FakeKyutai()
        typed: list[str] = []
        stt = StreamingSTT(
            f"http://127.0.0.1:{server.port}", "k", typed.append, capture_cmd=FAKE_MIC
        )
        threading.Timer(1.0, stt.stop).start()
        self.assertEqual(stream_cli.run(stt, poll=0.02), 0)
        self.assertEqual(typed, ["Hello, ", "world. "])
        server.close()

    def test_run_fails_when_capture_missing(self) -> None:
        stt = StreamingSTT("http://x", None, print, capture_cmd=["/nonexistent/mic"])
        self.assertEqual(stream_cli.run(stt), 1)


if __name__ == "__main__":
    unittest.main()
