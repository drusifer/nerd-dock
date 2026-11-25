import json
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock

from websockets.sync.server import serve

from nerd_dock.controller import (
    STATE_RECORDING,
    STATE_STOPPED,
    STATE_TRANSITIONING,
    NerdDockController,
)
from nerd_dock.stt_stream import (
    STATE_SUSPENDED,
    StreamingSTT,
    keep_transcript,
    load_api_key,
    realtime_url,
    session_update,
)

TRANSCRIBED = "conversation.item.input_audio_transcription.completed"

# Endless 100 ms chunks of silence, paced like a microphone.
FAKE_MIC = [
    sys.executable,
    "-c",
    "import sys,time\n"
    "while True:\n"
    " sys.stdout.buffer.write(bytes(4800)); sys.stdout.buffer.flush(); "
    "time.sleep(0.1)",
]


class FakeServer:
    """Minimal Realtime server: answers 3 audio chunks with a transcript."""

    def __init__(self, transcripts=("hello world", "Thanks.")) -> None:
        self.messages: list[dict] = []
        self.auth: str | None = None
        self._transcripts = list(transcripts)
        self._server = serve(self._handle, "127.0.0.1", 0)
        self.port = self._server.socket.getsockname()[1]
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def _handle(self, ws) -> None:
        self.auth = ws.request.headers.get("Authorization")
        appends = 0
        for raw in ws:
            msg = json.loads(raw)
            self.messages.append(msg)
            if msg["type"] == "input_audio_buffer.append":
                appends += 1
                if appends % 3 == 0 and self._transcripts:
                    ws.send(
                        json.dumps(
                            {
                                "type": TRANSCRIBED,
                                "transcript": self._transcripts.pop(0),
                            }
                        )
                    )

    def close(self) -> None:
        self._server.shutdown()


def wait_for(cond, timeout=5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


class TestHelpers(unittest.TestCase):
    def test_realtime_url(self) -> None:
        self.assertEqual(
            realtime_url("http://h:8000", "a/b"),
            "ws://h:8000/v1/realtime?intent=transcription&model=a%2Fb",
        )
        self.assertEqual(
            realtime_url("https://h/v1", "m"),
            "wss://h/v1/realtime?intent=transcription&model=m",
        )

    def test_session_update(self) -> None:
        vad = session_update("m", 400)["session"]["audio"]["input"]["turn_detection"]
        self.assertEqual(vad, {"type": "server_vad", "silence_duration_ms": 400})

    def test_junk_filter(self) -> None:
        self.assertFalse(keep_transcript("  Thanks. "))
        self.assertTrue(keep_transcript("Thanks for the update."))

    def test_load_api_key(self) -> None:
        import os
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
            f.write("OTHER=1\nSTT_API_KEY='secret'\n")
        old = {k: os.environ.pop(k, None) for k in ("STT_API_KEY",)}
        try:
            self.assertEqual(load_api_key(f.name), "secret")
        finally:
            os.unlink(f.name)
            for k, v in old.items():
                if v is not None:
                    os.environ[k] = v


class TestStreaming(unittest.TestCase):
    def setUp(self) -> None:
        self.server = FakeServer()
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

    def test_stream_types_transcript_and_filters_junk(self) -> None:
        self.assertTrue(self.stt.start())
        self.assertTrue(wait_for(lambda: self.typed))
        self.assertEqual(self.typed, ["hello world "])
        self.assertEqual(self.server.auth, "Bearer key123")
        self.assertEqual(self.server.messages[0]["type"], "session.update")
        wait_for(lambda: len(self.server.messages) > 6)
        self.assertEqual(self.typed, ["hello world "])  # "Thanks." dropped

    def test_suspend_stops_audio_and_resume_restarts(self) -> None:
        self.stt.start()
        wait_for(lambda: len(self.server.messages) > 3)
        self.assertTrue(self.stt.suspend())
        self.assertEqual(self.stt.state, STATE_SUSPENDED)
        time.sleep(0.4)
        count = len(self.server.messages)
        time.sleep(0.5)
        self.assertEqual(len(self.server.messages), count)
        self.assertTrue(self.stt.resume())
        self.assertTrue(wait_for(lambda: len(self.server.messages) > count + 2))

    def test_stop_commits_and_reports_stopped(self) -> None:
        self.stt.start()
        wait_for(lambda: len(self.server.messages) > 3)
        self.assertTrue(self.stt.stop())
        self.assertTrue(wait_for(lambda: self.stt.state == STATE_STOPPED))
        types = [m["type"] for m in self.server.messages]
        self.assertIn("input_audio_buffer.commit", types)

    def test_wrong_key_stops_without_retry(self) -> None:
        from websockets.sync.server import serve as s

        def reject(connection, _request):
            return connection.respond(403, "Not authenticated\n")

        srv = s(lambda ws: None, "127.0.0.1", 0, process_request=reject)
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

    def test_start_fails_without_capture_tool(self) -> None:
        stt = StreamingSTT(
            "http://x", None, self.typed.append, capture_cmd=["/nonexistent/mic"]
        )
        self.assertFalse(stt.start())
        self.assertIn("Cannot start microphone", stt.last_error)


class TestControllerStreaming(unittest.TestCase):
    def test_controller_delegates_to_stream(self) -> None:
        stream = MagicMock()
        stream.start.return_value = True
        stream.stop.return_value = True
        c = NerdDockController(stream=stream)
        self.assertTrue(c.begin_dictation())
        self.assertEqual(c.get_state(), STATE_TRANSITIONING)
        c.set_state(STATE_RECORDING)
        self.assertTrue(c.end_dictation())
        stream.stop.assert_called_once()

    def test_failed_start_restores_state(self) -> None:
        stream = MagicMock()
        stream.start.return_value = False
        c = NerdDockController(stream=stream)
        self.assertFalse(c.begin_dictation())
        self.assertEqual(c.get_state(), STATE_STOPPED)


if __name__ == "__main__":
    unittest.main()


class TestInputDaemon(unittest.TestCase):
    def test_stale_socket_is_replaced_and_daemon_started(self) -> None:
        import os
        import socket
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".ydotool_socket")
            with socket.socket(socket.AF_UNIX) as s:  # bind, then die: stale file
                s.bind(path)
            self.assertTrue(os.path.exists(path))
            c = NerdDockController(input_tool="YDOTOOL")
            with (
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": tmp}),
                patch("shutil.which", return_value="/usr/bin/ydotoold"),
                patch("subprocess.Popen") as popen,
            ):
                c.start_input_daemon()
            self.assertFalse(os.path.exists(path))
            popen.assert_called_once_with(
                ["/usr/bin/ydotoold", f"--socket-path={path}"]
            )
