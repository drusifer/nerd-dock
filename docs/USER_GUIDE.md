# 📖 Nerd-Dock User Guide

> Welcome to the comprehensive guide for **Nerd-Dock**, the ultimate desktop control applet for the lightweight, offline speech-to-text dictation engine, `nerd-dictation`. This guide will walk you through native system setup, UI controls, advanced configurations, custom desktop integration, global hotkey bindings, and troubleshooting tips.

---

## 🚀 1. Native System Installation

Nerd-Dock is built in Python utilizing **GObject Introspection (PyGObject)** to directly bind GNOME system frameworks. This ensures a lightweight execution footprint without needing bloated web wrappers or memory-heavy desktop containers.

### Step 1: Install Ubuntu System Libraries
Before setting up python modules, you need to install the GObject wrapper libraries for GTK 3, Ayatana AppIndicator, and the Libnotify desktop notification framework. Run the following command:

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-gi \
    gir1.2-gtk-3.0 \
    gir1.2-ayatanaappindicator3-0.1 \
    gir1.2-notify-0.7
```

### Step 2: Set Up Python Virtual Environment
PyGObject bindings rely on binary C libraries installed on your host OS. To allow Python to access these host libraries while maintaining an isolated dev environment, you **must** initialize the Python virtual environment with the `--system-site-packages` flag.

Our standard setup automation handles this completely:
```bash
# Deletes old environments and builds a fresh, correct virtual environment
make setup
```

Under the hood, this target executes:
```bash
python3 -m venv --system-site-packages venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -e .[dev]
```

### Step 3: Run the Application
Once the setup is successfully completed, launch the application:
```bash
make run
```
You will immediately see a gray microphone icon appear in your desktop's top-panel system status tray!

---

## 🎙️ 2. Core Concepts: Nerd-Dictation Explained

If you are new to speech-to-text on Linux, here is a quick overview of how the systems function:

1.  **`nerd-dictation`**: An offline, open-source dictation software package that uses the **Vosk API** speech recognition toolkit. It captures audio input from your microphone, processes it locally using offline acoustic models, and injects the transcribed text directly as simulated keystrokes wherever your cursor is focused.
2.  **CLI Operation**: Standard control is done by executing shell commands (e.g. `nerd-dictation begin` to start dictating, `nerd-dictation end` to stop).
3.  **The Problem**: Operating a CLI during dictation is cumbersome—you must keep a terminal window open or guess whether your microphone is currently active.
4.  **The Solution**: **Nerd-Dock** wraps the CLI engine in a native top panel applet, giving you a persistent glowing microphone to visually verify your recording state and a mouse-clickable dropdown menu.

---

## 🎛️ 3. System Tray Menu & Visual Controls

The system tray menu is dynamic, automatically disabling invalid actions based on your current state to avoid command errors:

```
+------------------------------------------+
|  🎙️ Status: Stopped                      | <-- Informative Header (Disabled)
|------------------------------------------|
|  ▶️ Start Dictation                       | <-- Enabled only when Stopped
|  ⏸️ Pause Dictation                       | <-- Enabled only when Recording
|  🔁 Resume Dictation                      | <-- Enabled only when Paused
|  ⏹️ Stop Dictation                        | <-- Enabled when Recording or Paused
|  ❌ Cancel Dictation                      | <-- Enabled when Recording or Paused (discards buffer)
|------------------------------------------|
|  🚪 Quit                                 | <-- Exits Nerd-Dock completely
+------------------------------------------+
```

### Under the Hood Actions:
*   **Start Dictation:** Spawns `nerd-dictation begin` asynchronously. The microphone icon remains gray, and the header reads `"Status: Starting Up (Loading Model)..."`. Vosk is loading the large acoustic language model into RAM.
*   **Model Loaded / Recording:** Once the model is loaded (detected automatically by reading standard output), the icon flashes to **glowing red**, a system notification pops up reading `"Microphone Active — Listening..."`, and the model begins typing text.
*   **Pause Dictation:** Executes `nerd-dictation suspend`. Under the hood, this sends a Unix `SIGSTOP` signal to pause the background process. The icon switches to **amber pause**, silencing audio capture and reducing CPU utilization to zero while keeping the massive model in RAM for instant resumption.
*   **Resume Dictation:** Executes `nerd-dictation resume`, sending a Unix `SIGCONT` signal to instantly wake the process. The icon turns **glowing red** immediately.
*   **Stop Dictation:** Executes `nerd-dictation end`. This flushes any remaining speech recognition buffers, type-injects the final words, and shuts down the background daemon cleanly. The icon returns to **gray microphone**.
*   **Cancel Dictation:** Executes `nerd-dictation cancel`. This instantly kills the active daemon and discards any remaining audio buffer without typing it out.
*   **Quit:** Safely terminates any running `nerd-dictation` subprocesses to prevent orphaned daemons, cleans up temporary files, shuts down the notifications framework, and exits.

---

## 🎹 4. Integrating with GNOME Keyboard Shortcuts (Hotkeys)

While mouse clicks are convenient, the true power of hands-free dictation is unlocked by binding keyboard hotkeys to control states. 

Thanks to Nerd-Dock's **Real-Time State Monitor Thread**, if you trigger dictation using command-line commands or keyboard hotkeys, the tray applet instantly intercepts the state change and updates the visual icons and notification banners.

### Recommended Global Hotkey Bindings
You can bind global hotkeys using GNOME's native keyboard settings panel:

1.  Open GNOME **Settings** -> **Keyboard** -> **Keyboard Shortcuts** -> **View and Customise Shortcuts**.
2.  Scroll to the bottom and select **Custom Shortcuts**.
3.  Click **Add Shortcut** (`+`) and input the following configurations:

#### 🎙️ Toggle Start / Stop Dictation
*   **Name:** `Nerd-Dictation: Start / Stop`
*   **Command:** `/home/drusifer/.local/bin/nerd-dictation toggle`
*   **Shortcut Recommendation:** `Super + D` (or `Super + Space`)

#### ⏸️ Toggle Pause / Resume (Mute)
*   **Name:** `Nerd-Dictation: Pause / Resume`
*   **Command:** `/home/drusifer/.local/bin/nerd-dictation suspend-toggle`
*   **Shortcut Recommendation:** `Super + Shift + D`

> [!TIP]
> When you press `Super + D`, the system will execute the command line tool. Nerd-Dock's background thread (running at 250ms intervals) reads the PID cookie file `/tmp/nerd-dictation.cookie` and queries `/proc/<pid>/status`. Within milliseconds, your tray microphone changes from gray to glowing red, accompanied by a desktop notification, giving you immediate visual confirmation of your microphone status.

---

## ⚙️ 5. Advanced Customization & Performance Tuning

For advanced users, Nerd-Dock can be customized via command-line arguments to tailor it to your environment:

```bash
python3 nerd_dock/main.py --executable /usr/bin/nerd-dictation --poll-interval 0.1 --verbose
```

### 1. Custom Executable Paths (`--executable`)
If you installed `nerd-dictation` to a custom location, inside a different virtual environment, or globally under `/usr/bin/`, pass the absolute path:
```bash
python3 nerd_dock/main.py --executable /usr/local/bin/nerd-dictation
```

### 2. Tuning Polling Intervals (`--poll-interval`)
The monitor thread polls the active cookie file and `/proc` status table. The default is `0.25` seconds (250ms), which provides a near-instant UI response with virtually zero CPU overhead (less than 0.1% CPU).
*   **Tuning for High Responsiveness:** Set to `0.1` (100ms) for instantaneous tray visual updates on keyboard hotkeys.
*   **Tuning for Minimal Systems:** Set to `0.5` or `1.0` seconds to reduce CPU cycles even further on low-powered battery devices.

### 3. Desktop Heads-Up Display Notifications
Desktop notification popups are driven by PyGObject's native `Notify` module, which links directly to standard Ubuntu desktop environments. Notifications will appear when:
1.  Dictation is started (notifies you that the Vosk model is loading).
2.  The microphone goes active (listening).
3.  The dictation is paused/muted.
4.  Dictation stops.

---

## 🔍 6. Troubleshooting & FAQs

### Q: The AppIndicator tray icon is missing or not visible!
> [!WARNING]
> Standard vanilla GNOME Shells on some distributions (like Arch or Debian) do not display classic legacy system AppIndicators by default.
> *   **On Ubuntu:** Ayatana AppIndicator is installed and enabled by default.
> *   **On other GNOME distributions:** You must install and enable the GNOME Shell extension: **[AppIndicator and KStatusNotifierItem Support](https://extensions.gnome.org/extension/615/appindicator-support/)**. Run `sudo apt install gnome-shell-extension-appindicator` on Debian-based distributions.

### Q: Why does the system tray say "Starting Up..." for a few seconds when I click Start?
This is completely normal. `nerd-dictation` uses machine learning Vosk models that can range from 50MB (lightweight) to over 1GB (highly accurate model). When starting dictation, the engine must load this model file from your hard drive into your system RAM before it can begin processing speech. During this period, Nerd-Dock locks its actions and shows a transition status to prevent clicks from clashing.

### Q: Why do I get a `gi.require_version` error on startup?
This happens if you run the program inside a standard Python virtual environment that does not have access to host system libraries.
*   **The Cause:** Virtual environments created using `python3 -m venv venv` are completely isolated and cannot read GObject C-bindings.
*   **The Fix:** Recreate your environment with host package access:
    ```bash
    python3 -m venv --system-site-packages venv
    venv/bin/pip install -e .[dev]
    ```

### Q: Can I run Nerd-Dock headlessly or run tests?
Yes! The test suite is fully headless. Our tests mock out system GTK elements, the filesystem, and subprocess behaviors so they can be run in a remote CI pipeline or terminal shell without an X11/Wayland display server active:
```bash
make test
```
