# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Nerd-Dock is a GNOME top-bar tray indicator (GTK 3 + Ayatana AppIndicator) that controls the external `nerd-dictation` CLI. Target platform is Fedora (Silverblue/toolbox); system deps are installed with `dnf`, not apt.

## Commands

Always use `make` (see `make help`):

- `make install-system-deps` — `sudo dnf install` of `python3-gobject gtk3 libayatana-appindicator-gtk3 libnotify`
- `make setup` — creates `venv/` with `--system-site-packages` (required so the venv sees the system `gi` bindings) and installs `.[dev]`
- `make run` — run the tray app; `make install` — `pipx install . --system-site-packages`
- `make test` — pytest with coverage. Single test: `PYTHONPATH=. venv/bin/python3 -m pytest tests/test_controller.py::test_name`
- `make lint` — ruff check + format check, radon, vulture, bandit, pylint duplicate-code (all must pass); `make format` auto-fixes

## Architecture

Four modules in `nerd_dock/`: `main.py` (arg parsing, wiring), `controller.py` (spawns/signals `nerd-dictation` subprocesses), `monitor.py` (background thread polling the cookie file `/tmp/nerd-dictation.cookie` and `/proc/PID/status`), `ui_indicator.py` (AppIndicator, GTK menu, libnotify).

- A 4-state machine (`STOPPED`, `RECORDING`, `SUSPENDED`, `TRANSITIONING`) drives icon, tooltip, menu sensitivity and notifications. Pause is `SIGSTOP` via `nerd-dictation suspend`.
- GTK must stay on the main thread: the monitor thread reports state changes back via `GLib.idle_add`. State can change externally (CLI/hotkeys), so the monitor, not the controller, is the source of truth.
- Tests run without a display: `tests/mocks.py` stubs the `gi` modules. Docs live in `docs/` (PRD, ARCH, USER_GUIDE).

## Multi-agent workflow

`AGENTS.md` defines the "Bob Protocol" personas (state files under `agents/<persona>.docs/`, coordination via `make chat MSG=... PERSONA=...` into `agents/CHAT.md`). Follow it when invoked as a persona.
