# 🎙️ Nerd-Dock

> A premium, system-wide GNOME top-bar tray indicator and process controller for `nerd-dictation`. Built with Python, PyGObject, and Ayatana AppIndicator, delivering native GTK tray menus, interactive desktop notifications, and real-time state synchronization.

---

## 🌟 Product Highlights

*   **Zero-Overhead Top Bar Control:** Start, stop, pause, and resume your local offline speech-to-text dictation directly from your desktop panel.
*   **Vibrant Icon & Tooltip States:** High-visibility dynamic microphone icons change color (gray/red/amber) and display clear interactive tooltips to instantly reflect current dictation status.
*   **Real-Time State Synchronization:** A background environment thread continuously monitors the OS process table and system cookies, instantly synchronizing the tray interface even if dictation is triggered outside the applet (e.g., via CLI or standard hotkeys).
*   **Native Desktop Integration:** Integrates seamlessly into the GNOME top bar using Ayatana AppIndicator3 and standard GLib main loops—no external shell extensions required.
*   **Desktop Notifications:** Dispatches clean, native Linux notifications using `libnotify` for state transition alerts (e.g., when the microphone goes active or is suspended).
*   **Resilient Process Management:** Safe subprocess controllers prevent duplicate execution, handle transitions gracefully, and completely avoid orphaned background daemons on application shutdown.

---

## 📊 Dictation State Machine & Visuals

Nerd-Dock is built on a precise 4-state machine that guarantees the UI represents the exact state of the system at all times:

| State | Tray Icon Representation | Context Menu Actions | Hover Tooltip | Desktop Notification | System Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`STOPPED`** | 🔘 Gray Microphone (`nerd-dock-stopped`) | **Start Dictation** (Enabled)<br>*All others disabled* | `"Dictation: Stopped"` | `"Dictation Stopped."` | No active dictation processes, no audio capture, zero CPU overhead. |
| **`RECORDING`** | 🔴 Vibrant Red Microphone (`nerd-dock-recording`) | **Pause Dictation**, **Stop Dictation**, **Cancel Dictation** (Enabled)<br>*Start/Resume disabled* | `"Dictation: Listening"` | `"Microphone Active — Listening..."` | Dictation model loaded in memory, capturing audio, typing live keystrokes. |
| **`SUSPENDED`** | 🟡 Amber Pause Circle (`nerd-dock-paused`) | **Resume Dictation**, **Stop Dictation**, **Cancel Dictation** (Enabled)<br>*Start/Pause disabled* | `"Dictation: Paused"` | `"Dictation Suspended / Muted."` | Model kept in RAM, microphone muted, process paused (`SIGSTOP`), no CPU consumption. |
| **`TRANSITIONING`** | 🔘 Gray Microphone (`nerd-dock-stopped`) | *All actions temporarily disabled* | `"Dictation: Starting Up..."` or `"Resuming..."` | `"Starting up (Loading model)..."` | Spawning background model process or sending signal subcommands. Prevents click race conditions. |

---

## 🛠️ Architecture & Data Flow

GTK and system tray applets operate strictly on the main thread. To prevent blocking the GUI and avoid thread conflicts, Nerd-Dock implements a thread-safe, decoupled model using **GObject / GLib** event triggers:

```mermaid
graph TD
    %% Styling
    classDef main fill:#1e1e2f,stroke:#7289da,stroke-width:2px,color:#fff;
    classDef thread fill:#2f1e2f,stroke:#f04747,stroke-width:2px,color:#fff;
    classDef external fill:#1e2f1e,stroke:#43b581,stroke-width:2px,color:#fff;
    
    subgraph MainThread ["GNOME GUI Main Loop (GTK 3)"]
        A[NerdDockApp]:::main --> B[NerdDockIndicator]:::main
        B -->|Controls Dropdowns| C[GTK Context Menu]:::main
        B -->|Updates Icon & Tooltip| D[Ayatana AppIndicator]:::main
        B -->|Dispatches Alerts| E[libnotify / Notify]:::main
    end

    subgraph Controller ["Subprocess Management"]
        F[NerdDockController]:::main
    end

    subgraph BackgroundThread ["Monitoring Thread"]
        G[NerdDictationMonitor]:::thread
    end

    subgraph OS ["Operating System & Environment"]
        H[nerd-dictation Subprocess]:::external
        I[/tmp/nerd-dictation.cookie]:::external
        J[/proc/PID/status]:::external
    end

    %% Interactions
    C -->|User Click: Start/Pause/Stop| F
    F -->|Spawn / Signal| H
    G -->|Reads PID| I
    G -->|Checks Process State| J
    G -->|Thread-Safe Callback via GLib.idle_add| B
    H -.->|Writes PID| I
```

---

## 🚀 Getting Started

### 📋 Prerequisites

Nerd-Dock is optimized for **Ubuntu 26.04** (GNOME 50). It relies on native system libraries for GObject Introspection, GTK+ 3.0, Ayatana AppIndicator, and Desktop Notifications:

```bash
# Install required system dependencies
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    gir1.2-gtk-3.0 \
    gir1.2-ayatanaappindicator3-0.1 \
    gir1.2-notify-0.7
```

### 📦 Installation

To preserve system packages and link native system GObject bindings, Nerd-Dock must be installed in a Python virtual environment (`venv`) using the `--system-site-packages` flag.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/drusifer/nerd-dock.git
    cd nerd-dock
    ```

2.  **Set Up the Environment:**
    The project features an automated setup script via the `Makefile` to set up the virtual environment and install all packages in editable mode:
    ```bash
    make setup
    ```

---

## 💻 Usage

Start the tray application using the simple development wrapper:

```bash
make run
```

### ⚙️ Command-Line Arguments

For advanced configurations, you can execute the Python entry point directly and supply options:

```bash
python3 nerd_dock/main.py [OPTIONS]
```

| Flag | Argument Type | Default Value | Description |
| :--- | :--- | :--- | :--- |
| `--executable` | `str` | `"/home/drusifer/.local/bin/nerd-dictation"` | The absolute filepath to the `nerd-dictation` CLI program. |
| `--cookie` | `str` | `"/tmp/nerd-dictation.cookie"` | Path to the runtime lock/cookie file containing the active PID. |
| `--poll-interval` | `float` | `0.25` | Background monitor polling loop delay (in seconds). Lower values increase responsiveness. |
| `--verbose` | *Flag (No arg)* | `False` | Enables comprehensive debug-level log dumps to standard output. |

---

## 🧪 Developer Automation & Quality Gates

The project contains a comprehensive verification suite configured through [Makefile.prj](file:///home/drusifer/Projects/nerd-dock/Makefile.prj) to ensure extreme code quality, reliability, and security:

```bash
# Run unit test harness with full statement coverage report
make test

# Run the complete static analysis lint pipeline
make lint

# Automatically format code and apply auto-fixes
make format

# Clean build caches, coverage databases, and pycaches
make clean
```

### 🛡️ Quality Standards Checked:
*   **Style Conformity:** `ruff check` and `ruff format` to guarantee strict PEP 8 formatting.
*   **Complexity Guard:** `radon cc` ensures all code remains simple, readable, and highly maintainable (complexity scores <= A/B).
*   **Unused Code Scanning:** `vulture` scans the codebase for dead variables or dead functions.
*   **Security Vulnerabilities:** `bandit` audits files for potential shell-injection or other security risks.
*   **Code Duplication Prevention:** `pylint --enable=duplicate-code` strictly guards against copy-paste programming.

---

## 📂 Repository Navigation

*   [nerd_dock/main.py](file:///home/drusifer/Projects/nerd-dock/nerd_dock/main.py) — Main entry point containing initialization logic and arg parsing.
*   [nerd_dock/controller.py](file:///home/drusifer/Projects/nerd-dock/nerd_dock/controller.py) — Core subprocess execution wrapper and state machine.
*   [nerd_dock/monitor.py](file:///home/drusifer/Projects/nerd-dock/nerd_dock/monitor.py) — Background cookie scanning thread.
*   [nerd_dock/ui_indicator.py](file:///home/drusifer/Projects/nerd-dock/nerd_dock/ui_indicator.py) — Ayatana AppIndicator tray applet and menu events.
*   [docs/PRD.md](file:///home/drusifer/Projects/nerd-dock/docs/PRD.md) — Product Requirements Document outlining full specifications.
*   [docs/ARCH.md](file:///home/drusifer/Projects/nerd-dock/docs/ARCH.md) — Technical Architecture Design Document.
*   [docs/USER_GUIDE.md](file:///home/drusifer/Projects/nerd-dock/docs/USER_GUIDE.md) — The ultimate user guide for setup and advanced desktop binding.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](file:///home/drusifer/Projects/nerd-dock/LICENSE) for details.
