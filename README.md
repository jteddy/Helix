# HELIX

**Fork of [dev-boog/Cearum-Recoil](https://github.com/dev-boog/Cearum-Recoil/)** — reworked with a web UI front-end so the controls are accessible from any browser on your network.

Recoil control system with a web UI. Runs as a FastAPI server on **Linux or Windows** connected to a MAKCU via USB.

---

## Android App

A native Android companion app is available — full functionality except the vector editor.

- Download / auto-update via [Obtainium](https://github.com/ImranR98/Obtainium) from the [releases page](https://github.com/jteddy/Helix/releases)
- Requires Android 8.0+ and the Helix server on the same Wi-Fi network
- Maintains a persistent WebSocket connection for live 200ms status updates; all changes sent instantly via REST
- Status bar shows two indicator dots: **MAKCU** (device connected) and **WS** (WebSocket live)

---

## Architecture

### Server

```
Any browser (phone, tablet, monitor)
└── http://<server-ip>:8000
        │
        ▼
Helix Server  (Linux or Windows, any hardware)
├── Python / FastAPI  ← HTTP + WebSocket API
├── MAKCU connected via USB HID
└── Recoil + Flashlight loops running continuously
```

The server is a Python [FastAPI](https://fastapi.tiangolo.com/) application that runs on Linux or Windows. It exposes an HTTP API and a WebSocket endpoint that the browser UI connects to. State is pushed to all connected clients every 200 ms over WebSocket, so every open browser tab stays in sync automatically.

### How It Fits Into Your Setup

```
Gaming PC (Windows)
├── Game running
├── Mouse ──→ MAKCU (USB passthrough) ──→ Game input
└── Stream Deck ──→ HTTP ──→ Helix server

Helix Server (Linux, any hardware)
└── http://<server-ip>:8000

Any browser (phone, tablet, monitor)
└── http://<server-ip>:8000
    ├── Status panel  — MAKCU / Recoil / Flashlight / Script at a glance
    ├── Recoil tab    — enable, keybinds, sliders, scripts
    ├── Flashlight tab — timing controls
    ├── Settings tab  — game sensitivity scaling, browser hotkey, Stream Deck docs
    └── Vector Editor — canvas-based recoil pattern editor
```

---

## Quick Start

### Linux

```bash
git clone https://github.com/jteddy/Helix.git
cd Helix
python install.py   # first-time setup — installs deps, USB groups, udev rule
./start.sh          # run manually (Ctrl+C to stop)
```

`install.py` will ask which MAKCU firmware version you are running and install the correct makcu library automatically.

Open `http://<server-ip>:8000` from any browser. Find your server's IP with:
```bash
hostname -I
```

### Windows

1. Install [Python 3.10+](https://www.python.org/downloads/) — check **"Add python.exe to PATH"** during setup
2. Open **Command Prompt** or **PowerShell** in the Helix folder:
```cmd
git clone https://github.com/jteddy/Helix.git
cd Helix
python install.py
```
3. Select your MAKCU firmware version when prompted. No USB group or udev steps are needed on Windows — the installer skips them automatically.
4. Start the server:
```cmd
python main.py
```
5. Open `http://localhost:8000` in any browser.

> **Note:** `start.sh` and the systemd autostart are Linux-only. On Windows just run `python main.py` directly. To find your machine's IP for accessing from another device (phone etc.), run `ipconfig` and look for your LAN address.

---

## Auto-start on Boot

Run once — installs dependencies, writes a systemd service, enables it, and starts it:

```bash
./setup-autostart.sh
```

Useful commands after setup:
```bash
sudo systemctl status helix
sudo systemctl restart helix
sudo journalctl -u helix -f    # live logs
```

---

## Desktop Launcher

If you run Helix on the same machine you game on, the launcher gives you a GUI popup to Start / Stop / Restart the server with a live log terminal and a system tray icon.

### Linux

**Install once:**
```bash
./install-launcher.sh
```

This installs PyQt6, copies the Helix icon into your icon theme, and adds a **Helix Launcher** entry to your applications menu with a desktop shortcut.

**Or run directly any time:**
```bash
python3 launcher.py
```

### Windows

Install PyQt6, then run the launcher directly — no shell script needed:
```cmd
pip install PyQt6
python launcher.py
```

On Windows the launcher runs in **manual mode** automatically (systemd is not available). Start / Stop / Restart control `main.py` as a subprocess and the log terminal streams its output live. The system tray icon works natively.

### Launcher features

| Feature | Detail |
|---------|--------|
| **Status indicator** | Green dot = running, grey = stopped, red = failed. Refreshes every 10 s. |
| **Start / Stop / Restart** | Calls `systemctl --user` (no sudo) or `pkexec systemctl` for system-level services. Manual mode spawns `python main.py` directly. |
| **Live log terminal** | Streams `journalctl -f` output continuously — no polling. Errors highlighted red, warnings yellow, key events green. |
| **Open in Browser** | One click to open `http://localhost:8000`. |
| **System tray** | Closing the window hides to tray. Left-click to show/hide; right-click for quick actions. |

### Systemd mode notes

`setup-autostart.sh` installs a **system-level** service (`/etc/systemd/system/helix.service`). Start/Stop/Restart from the launcher will trigger a polkit password dialog (like any other graphical privilege escalation on Xubuntu).

To avoid the password prompt entirely, convert to a **user-level** service (runs as your user, no sudo ever needed):

```bash
# One-time migration — run in a terminal:
sudo systemctl stop helix
sudo systemctl disable helix
mkdir -p ~/.config/systemd/user
sudo cp /etc/systemd/system/helix.service ~/.config/systemd/user/helix.service
# Remove the User= line (service is already running as you)
sed -i '/^User=/d' ~/.config/systemd/user/helix.service
systemctl --user daemon-reload
systemctl --user enable helix
systemctl --user start helix
```

After this the launcher will detect `systemd-user` mode and all controls work without any password prompt.

---

## Status Panel

The top of the UI shows four live cards — readable at a glance on a phone:

| Card | Meaning |
|------|---------|
| **MAKCU** | `OK` green = connected · `N/C` red = not connected |
| **Recoil** | `ON` green / `OFF` — tap to toggle from the browser |
| **Flashlight** | `ON` only when both flashlight and recoil are enabled |
| **Script** | Name of the currently loaded recoil script |

Status updates via WebSocket every 200 ms.

---

## UI — Feature Reference

### Recoil Tab

**Control**

| Setting | What it does |
|---------|-------------|
| Toggle Keybind (MAKCU) | Which mouse button (M4, M5, MMB) physically toggles recoil on/off via the MAKCU hardware. |
| Cycle Script Keybind | Which mouse button cycles to the next saved script — useful for swapping weapons without touching the UI. |
| Require Aim (RMB) | Recoil compensation only fires while right mouse button is held (i.e. while aiming down sights). |
| Loop Recoil | When the script reaches the last shot vector, it loops back to the beginning instead of stopping. Useful for sustained automatic fire. |
| Randomisation | Adds small random offsets to each movement so the pattern is less deterministic. The amount is controlled by **Randomisation Strength** in the Scaling card. |
| Return Crosshair | After the script finishes, the MAKCU moves the mouse back to approximately where it started. |

**Scaling**

| Setting | What it does |
|---------|-------------|
| Recoil Scalar | Global multiplier applied to every vector in the script. 1.0 = unchanged; increase to compensate for lower in-game sensitivity; decrease to dial it back. Overridden automatically when a game preset is selected in Settings. |
| X Control | Scales only the horizontal (X) component of each vector — 0 disables all horizontal correction. |
| Y Control | Scales only the vertical (Y) component — 0 disables all vertical correction. |
| Randomisation Strength | How large the random offsets can be when Randomisation is enabled. Higher values feel more human; too high and accuracy degrades. |
| Return Speed | Controls how quickly the crosshair returns to its original position after the script finishes (only relevant when Return Crosshair is on). |

**Scripts**

The scripts panel lets you manage your recoil scripts directly in the browser without needing a file manager or SSH. You can organise scripts into game folders (e.g. `ABI/`, `Tarkov/`), load a script to make it active, edit the raw vector text, and save or delete scripts — all stored on the web server.

---

### Flashlight Tab

The Flashlight feature automates your in-game torch/flashlight key to fire automatically when you fire your weapon.

| Setting | What it does |
|---------|-------------|
| Flashlight Keybind | Which mouse button maps to your in-game flashlight key. |
| Hold Threshold (ms) | How long you must hold the fire button before the flashlight triggers. Short tap shots (burst fire) won't activate it — only sustained fire will. |
| Cooldown (ms) | Minimum time between flashlight activations to avoid rapid re-triggering. |
| Pre-Fire Delay (ms) | A randomised delay (min → max) added after the hold threshold is met before the flashlight actually turns on. |

> Flashlight only fires when **Recoil is ON** — prevents it from triggering in menus.

---

### Settings Tab

**Game Sensitivity Scaling**

| Setting | What it does |
|---------|-------------|
| Game | Select your game from a built-in preset list. This sets a base scalar for that game so scripts written for a reference sensitivity are automatically scaled correctly. Select **Manual** to control the Recoil Scalar yourself. |
| In-Game Sensitivity | Enter your actual in-game sensitivity. Combined with the game preset, the server calculates the correct scalar: `base / your_sens`. |

**Browser Hotkey**

Lets you bind a keyboard key on the current device to toggle recoil without needing a Stream Deck or MAKCU button. The binding is stored in the browser's local storage — it only applies when the tab is focused and is per-device.

**Connection**

Shows live status of the MAKCU device, the web server, and the WebSocket connection so you can diagnose connectivity issues at a glance.

**Stream Deck**

Displays the API endpoints needed to configure the Web Requests plugin. See the [Stream Deck setup guide](https://github.com/jteddy/Helix/blob/main/streamdeck/SETUP.md) for full button-by-button instructions.

---

### Vector Editor Tab

A canvas-based graphical editor for creating and editing recoil patterns visually rather than editing raw text.

| Feature | What it does |
|---------|-------------|
| Canvas | Click to place shot vectors; drag existing points to adjust. The path shows the cumulative mouse travel the MAKCU will produce. |
| Table view | Switch between the visual canvas and a tabular list of all vectors (x, y, delay) for precise numeric editing. |
| Game / Weapon fields | Organise patterns by game and weapon name — mirrors the folder structure used by the Recoil Scripts panel. |
| Save Pattern | Writes the pattern to the web server as a script file (`saved_scripts/<game>/<weapon>.txt`). |
| Copy to Scripts | Saves the pattern and immediately loads it as the active recoil script, switching to the Recoil tab. |
| Load / Delete | Browse and manage previously saved patterns from the sidebar. |

> The Vector Editor and the Recoil Scripts panel share the same `saved_scripts/` directory — a pattern saved here appears in the Recoil Scripts list and vice versa.

---

## Saved Scripts

Scripts are plain text files stored in the `saved_scripts/` directory on the web server. They can be organised into game subfolders:

```
saved_scripts/
├── ABI/
│   ├── ak47.txt
│   └── mp5.txt
├── Tarkov/
│   └── m4.txt
└── legacy_script.txt    ← flat root scripts still supported
```

### Script File Format

One vector per line — `x_offset, y_offset, delay_ms`:

```
# x_offset, y_offset, delay_ms
0, 5, 85
-1, 6, 85
1, 7, 90
```

Lines starting with `#` are comments and are ignored.

---

## Stream Deck

A custom Stream Deck plugin is included with live state-aware icons — buttons update automatically when state changes from any source (web UI, MAKCU side button, API).

**Quick install:** copy `streamdeck/com.helix.sdPlugin` into your Stream Deck plugins folder, restart the software, and set your server URL:

```
%APPDATA%\Elgato\StreamDeck\Plugins\
```

See the [full setup guide](https://github.com/jteddy/Helix/blob/main/streamdeck/SETUP.md) for details and alternative setup options.

---

## Directory Structure

```
helix/
├── main.py                       ← FastAPI app, WebSocket, lifespan, health
├── shared.py                     ← Shared singletons (state, save_async)
├── state.py                      ← Shared app state (thread-safe)
├── config_manager.py             ← JSON save/load (atomic write)
├── install.py                    ← First-time setup (deps, USB groups, udev)
├── start.sh                      ← Run the server manually
├── setup-autostart.sh            ← One-shot systemd installer
├── requirements.txt
├── routers/
│   ├── recoil.py                 ← POST /api/recoil, /api/recoil/toggle
│   ├── scripts.py                ← /api/scripts/*, /api/patterns/*
│   ├── flashlight.py             ← /api/flashlight, /api/flashlight/toggle
│   ├── settings.py               ← POST /api/settings
│   ├── cs2.py                    ← GET /api/cs2/weapons, POST /api/cs2/weapon
│   └── streamdeck.py             ← /api/streamdeck, /streamdeck/setup
├── mouse/makcu.py                ← MAKCU USB HID controller
├── menu/games.py                 ← Game sensitivity table
├── features/
│   ├── recoil/recoil.py          ← Recoil loop
│   ├── flashlight/               ← Flashlight loop
│   └── cs2/weapon_data.py        ← Built-in CS2 recoil patterns (AK-47, M4A1-S)
├── static/index.html             ← Entire frontend (4 tabs, self-contained)
├── launcher.py                   ← PyQt6 desktop launcher (optional, desktop Linux only)
├── install-launcher.sh           ← Installs launcher to app menu + desktop shortcut
├── icons/helix.svg               ← App icon (used by launcher + .desktop file)
├── saved_scripts/                ← Recoil scripts + Vector Editor patterns
│   └── <game>/
│       └── <weapon>.txt
├── config.json                   ← Auto-saved every 30s (gitignored)
├── streamdeck/SETUP.md           ← Stream Deck configuration guide
└── streamdeck/com.helix.sdPlugin ← Stream Deck plugin (copy to Plugins folder)
```

---

## Future Enhancements

### JSON-Wrapped Script Metadata

Scripts are currently stored as plain `.txt` files. A future enhancement could wrap them in a thin JSON envelope to attach metadata — name, description, creation date, tags, weapon type — without breaking the existing `x,y,delay_ms` line format stored inside. This would make the script library searchable and self-describing without relying on folder/file naming alone.

---

## API Reference

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/state` | Full state snapshot (recoil, flashlight, settings, scripts, games) |
| GET | `/api/health` | Server + MAKCU health check |
| WS | `/ws` | Live status stream (200ms push) |

### Recoil

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/recoil` | Update recoil settings (partial update supported) |
| POST | `/api/recoil/toggle` | Toggle recoil on/off |

### Scripts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scripts` | List flat scripts + loaded script + all games |
| GET | `/api/scripts/games` | List game subfolders |
| GET | `/api/scripts/content/{name}` | Get flat script content |
| GET | `/api/scripts/content/{game}/{name}` | Get game-scoped script content |
| POST | `/api/scripts/load/{name}` | Load a flat script |
| POST | `/api/scripts/load/{game}/{name}` | Load a game-scoped script |
| POST | `/api/scripts/save` | Save a script (`name`, `content`, optional `game`) |
| POST | `/api/scripts/cycle` | Cycle to next script (across all games) |
| DELETE | `/api/scripts/{name}` | Delete a flat script |
| DELETE | `/api/scripts/{game}/{name}` | Delete a game-scoped script |

### Vector Editor Patterns

Patterns share the same backend as scripts (`saved_scripts/<game>/<weapon>.txt`).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patterns` | List all game/weapon groups |
| GET | `/api/patterns/{game}/{weapon}` | Get pattern content |
| POST | `/api/patterns/{game}/{weapon}` | Save pattern content |
| DELETE | `/api/patterns/{game}/{weapon}` | Delete a pattern |

### Flashlight

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/flashlight` | Update flashlight settings |
| POST | `/api/flashlight/toggle` | Toggle flashlight on/off |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/settings` | Update game scalar and sensitivity |

### CS2 Built-in Patterns

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cs2/weapons` | List available built-in CS2 weapon patterns |
| POST | `/api/cs2/weapon` | Select a weapon (`{"weapon": "ak47"}`) or clear (`{"weapon": "none"}`) |

When a CS2 weapon is selected it overrides the loaded script for the recoil loop. The scaling still uses your in-game sensitivity from Settings (`base 1.25 / your_sens`).

### Stream Deck

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/streamdeck` | Lightweight JSON status for polling |

**Response:**
```json
{
  "recoil":     true,
  "flashlight": false,
  "makcu":      true,
  "script":     "ABI/ak47"
}
```
