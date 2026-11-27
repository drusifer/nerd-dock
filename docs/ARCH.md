# Architecture

| Module | Role |
|---|---|
| `main.py` | Tray entry point: options and wiring |
| `stream_cli.py` | Headless entry point (`nerd-dock-stream`) |
| `options.py` | Options both entry points share |
| `stt_stream.py` | Microphone capture, WebSocket protocol, session state |
| `typing_tools.py` | Typing words; runs `ydotoold` |
| `ui_indicator.py` | AppIndicator menu, notifications, D-Bus toggle |

## State

`StreamingSTT.state` is the only state: `STOPPED`, `RECORDING`, `SUSPENDED`, `STOPPING`. The tray polls it every 250 ms on the GTK thread, so changes the stream makes itself (flush finished, key rejected) show up without cross-thread calls.

## Threads

One thread runs the connect/stream loop and reconnects with backoff; one per connection receives words. Pause sends silence so the model stays clocked. Stop sends trailing silence and a `Marker`, then waits for the server to echo it.
