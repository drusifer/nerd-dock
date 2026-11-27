# Nerd-Dock — SDLC

How this project is built, tested, changed and released — the source of truth for change
management across the whole project. **Owned by Tank**; to change anything here,
ask `@Tank *devops sdlc <what and why>` — the mechanism and this document change together.

## 1. Toolchain

| | Python |
|---|---|
| Runtime version | OS interpreter (`python3`, `requires-python >=3.10` in `pyproject.toml`); not pinned in mise (see section 9) |
| Manifest | `pyproject.toml` |
| Lockfile | None — dev tools and `websockets` use lower bounds; the app is installed via pipx on user machines |
| Package manager | `pip` in a venv created with `--system-site-packages` |
| Local environment | `venv/` (gitignored) |

Other required tools: `task` 3 and `gitleaks` 8 — pinned in `mise.toml`, installed by `mise install`.
OS packages (not installable by mise): `python3-gobject gtk3 libayatana-appindicator-gtk3 libnotify
pulseaudio-utils ydotool git curl unzip` — installed by `make install-system-deps`.

## 2. Setup

From a clean checkout:

```sh
mise install              # task + gitleaks (no sudo)
make install-system-deps  # OS packages (sudo, once; pre-Task target)
make setup
make test
```

Prerequisites not installed by `make setup`: the OS packages above and `mise` itself
(<https://mise.jdx.dev>). Tests run without a display; running the tray app needs a desktop session.

## 3. Make targets

The Makefile is a forwarding shim to `Taskfile.yml`; agents run `bobp make <target>`.
`ARGS="..."` is passed through (`make run ARGS="--stt-url http://host:8001"`).

| Target | Runs | Notes |
|---|---|---|
| `install-system-deps` | `sudo dnf install ...` | In the Makefile, not Task: must work before `task` exists. Only target using sudo |
| `setup` | venv + `pip install -e .[dev]` | checksum-cached on `pyproject.toml` |
| `install` | `pipx install . --system-site-packages --force`, plus hooks | fails fast if `gi` / AppIndicator are missing |
| `install-hooks` | sets `core.hooksPath` to `.githooks` | gitleaks pre-commit |
| `run` | `install` + `setup`, then `nerd_dock/main.py $ARGS` | |
| `test` | pytest with coverage | `ARGS` passes through |
| `lint` | ruff, radon, vulture, bandit, pylint duplicate-code | all must pass |
| `format` | ruff format + fix | |
| `security-scan` | gitleaks git-aware scan | |
| `clean` / `distclean` | remove caches and builds / also `venv/` | |
| `help` | lists tasks | |

Standard targets deliberately absent: `build` — the package is installed with pipx from source and
no artifact is published.

## 4. Dependencies

- **Add:** edit `[project].dependencies` (runtime) or `[project.optional-dependencies].dev` in `pyproject.toml`, then `make setup`.
- **Upgrade / remove:** edit the bound, run `make setup`; the venv is rebuilt by `make distclean && make setup` when in doubt.
- **Dev-only tools:** `[project.optional-dependencies].dev`.
- **Commit afterwards:** `pyproject.toml`.
- **Who:** Neo adds and bumps dependencies. A new package manager, language, runtime pin or OS package is a mechanism change — Tank's.

## 5. Quality gates

| Gate | Target | Required before |
|---|---|---|
| Tests | `make test` | every handoff to Trin; sprint close |
| Static analysis | `make lint` | every handoff to Trin; sprint close |
| Secret scan | `make security-scan` | sprint close; staged changes on every commit (hook) |

## 6. Change management

Where another document, skill or habit disagrees with this one, this one wins — report it to Tank.

### Change classes

| Class | Examples | Proposed by | Approved by | Must pass | Recorded in |
|---|---|---|---|---|---|
| Routine | feature, fix, refactor, docs, dependency per section 4 | anyone / Cypher story | Morpheus review | section 5 gates | `agents/CHAT.md`, commit |
| Mechanism | toolchain, `Taskfile.yml`, `Makefile`, gates, this document | anyone, via `@Tank *devops sdlc` | Tank + user | from-clean rebuild + section 5 | this file, `agents/CHAT.md` |
| Release / deploy | version bump in `pyproject.toml`, new pipx install | user | user | section 5 | commit |
| Emergency | hotfix outside a sprint | user | user, may be after the fact | `make test` at minimum | `agents/CHAT.md`, reviewed at next sprint close |

### Flow

1. **Request** — user message or Cypher story in `agents/CHAT.md`.
2. **Branch** — work happens on `main` unless the user asks for a branch.
3. **Implement** — through `make` targets only; tests accompany behavior changes.
4. **Gate** — section 5 gates pass locally before handoff.
5. **Review** — Trin tests, Morpheus reviews; Switch reviews anything touching subprocess, sockets or secrets.
6. **Integrate** — agents commit and push only when the user asks.
7. **Record** — `agents/CHAT.md`, and `docs/` when behavior changes.

### Rules

- Never commit secrets, `venv/`, `.task/` or the STT API key (`~/.config/pi-patch/stt.env` stays outside the repo).
- **Rollback:** `git revert` the change; for the installed app, `make install` from the reverted tree.
- **Changing this document:** only Tank edits it; every edit updates the Last verified line.

## 7. Versioning and release

- **Version lives in:** `pyproject.toml` (`[project].version`).
- **Bumped:** by the user when releasing.
- **Artifact:** None — installed from source with `pipx`; nothing is published.

## 8. CI / deploy

None — everything runs locally. A future pipeline must call the same `make` targets as section 5.

## 9. Known deviations

- **No pinned Python in mise and no uv:** the venv must see the OS `gi` bindings (`python3-gobject` is not on PyPI-buildable terms without GTK dev headers), so it uses the OS interpreter with `--system-site-packages`, and pip rather than uv.
- **`sudo` in `install-system-deps`:** OS packages cannot come from mise. It is a user-run, pre-Task Makefile target.
- **Unverified:** a clean `mise install` flow; `install` and `run` end-to-end on a machine with the OS packages present; the gitleaks hook. `task` was verified via `go-task-bin` in the venv, and `make test` / `make lint` through the shim.
- **13 `tests/test_ui.py` tests fail** while `python3-gobject` is not installed (the real, empty `gi` shadows the test stub). They are expected to pass after `make install-system-deps`; not yet confirmed.

## 10. Conformance check

Run by Tank at sprint close (`*devops sdlc-check`):

1. `make distclean && make setup && make test && make lint` passes.
2. Every third-party import is declared in `pyproject.toml`; nothing was installed by hand.
3. Every target in section 3 exists in `Taskfile.yml` (or the Makefile for `install-system-deps`) and does what the table says.
4. No doc or script tells people to bypass `make` or install outside `venv/`.
5. `mise.toml` pins `task` and `gitleaks`; `.task/` and `venv/` are gitignored.
6. This sprint's changes followed section 6.
7. `make run ARGS="--stt-url ..."` starts and the tray icon appears (needs a desktop session).

---
*Last verified: 2026-11-25 against the working tree on `main` (uncommitted) by Tank — partially: see section 9.*
