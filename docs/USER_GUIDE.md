# Nerd-Dock user guide

## Start

```bash
nerd-dock --stt-url http://host:8001
```

| Option | Default | Meaning |
|---|---|---|
| `--stt-url` | `$NERD_DOCK_STT_URL` | Server address (required) |
| `--stt-key-file` | `~/.config/pi-patch/stt.env` | File with `STT_API_KEY=...`; `NERD_DOCK_STT_API_KEY` also works |
| `--input-tool` | `YDOTOOL` | `YDOTOOL`, `WTYPE`, `XDOTOOL`, `DOTOOL`, `DOTOOLC` or `STDOUT` |
| `--verbose` | off | Debug logging |

## Tray menu

| State | Icon | What it means |
|---|---|---|
| Stopped | gray | No connection, microphone off |
| Listening | red | Words are typed as you speak |
| Paused | amber | Connection open, silence is sent instead of the microphone |
| Stopping | gray | Typing the last words, then disconnecting |

**Stop** types the words still on their way. **Cancel** discards them.

## Keyboard shortcut

The running app exposes a `toggle` action on the session bus: stopped starts, listening pauses, paused resumes. It never stops; use the menu for that.

In GNOME: *Settings, Keyboard, View and Customise Shortcuts, Custom Shortcuts, +*, with this command and the shortcut Super+Z:

```bash
gapplication action io.github.drusifer.NerdDock toggle
```

Hold-to-talk is not offered: while a modifier key is held, typed words would act as shortcuts.

## Without the tray

```bash
nerd-dock-stream --url http://host:8001
```

Prints words in the terminal (`--input-tool` types them instead). Ctrl-C stops. `pkill -USR1 -f nerd-dock-stream` pauses and resumes.

## Troubleshooting

- "rejected the API key": the key does not match the server's.
- Listening but no words: check the server is reachable, and run with `--verbose`. A lost connection is retried with a growing delay.
- Words recognised but not typed: check `ydotoold` can run, or choose another `--input-tool`.
