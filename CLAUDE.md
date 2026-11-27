# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Nerd-Dock is a GNOME tray indicator (GTK 3 + Ayatana AppIndicator) for live dictation: it streams the microphone to a Kyutai `moshi-server` and types the words. Streaming is the only mode. Target platform is Fedora (Silverblue/toolbox); system deps are installed with `dnf`, not apt.

## Commands

Always use `make` (see `make help`):

- `make install-system-deps` — `sudo dnf install` of the OS packages
- `make setup` — creates `venv/` with `--system-site-packages` (required so the venv sees the system `gi` bindings) and installs `.[dev]`
- `make run ARGS="--stt-url http://host:8001"` — run the tray app; `make install` — pipx install
- `make test` — pytest with coverage. Single test: `PYTHONPATH=. venv/bin/python3 -m pytest tests/test_stt_stream.py::TestStream`
- `make lint` — ruff check + format check, radon, vulture, bandit, pylint duplicate-code (all must pass); `make format` auto-fixes

## Architecture

See `docs/ARCH.md`. `StreamingSTT.state` is the single source of truth; the tray polls it on the GTK thread. Tests use a fake server and microphone (`tests/fakes.py`) and mock GTK objects; they need `gi` installed but no display.

## Multi-agent workflow

`AGENTS.md` defines the "Bob Protocol" personas (state files under `agents/<persona>.docs/`, coordination via `make chat MSG=... PERSONA=...` into `agents/CHAT.md`). Follow it when invoked as a persona.
