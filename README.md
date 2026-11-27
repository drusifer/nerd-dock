# Nerd-Dock

A GNOME tray indicator for live dictation. It streams your microphone to a Kyutai speech-to-text server (`moshi-server`) and types each word into the focused window while you talk.

It needs a server: see `cluster/docs/stt-superman-setup.md` in the pi-patch repo.

## Install (Fedora)

```bash
make install-system-deps   # OS packages (sudo, once)
make install               # pipx install, with git hooks
```

## Run

Put the key in `~/.config/pi-patch/stt.env` as `STT_API_KEY=...`, then:

```bash
nerd-dock --stt-url http://host:8001          # tray app
nerd-dock-stream --url http://host:8001       # terminal only; prints the words
```

`NERD_DOCK_STT_URL` sets the server for both. See `docs/USER_GUIDE.md` for the options and the keyboard shortcut.

## Develop

`make test`, `make lint`, `make format`. The tests need the system `gi` bindings but no display.

MIT License.
