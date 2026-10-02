# HELIX

**Fork of [dev-boog/Cearum-Recoil](https://github.com/dev-boog/Cearum-Recoil/)** — reworked with a web UI front-end so the controls are accessible from any browser on your network.

Recoil control system with a web UI. Runs as a FastAPI server on **Linux or Windows** connected to a MAKCU via USB.

---

## Android App

A native Android companion app is available — full functionality except the vector editor.

- Download / auto-update via [Obtainium](https://github.com/ImranR98/Obtainium) from the [releases page](https://github.com/jteddy/Helix/releases)
- Requires Android 8.0+ and the Helix server on the same Wi-Fi network
- Maintains a persistent WebSocket connection for live status updates; all changes sent instantly via REST
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

The server is a Python [FastAPI](https://fastapi.tiangolo.com/) application that runs on Linux or Windows. It exposes an HTTP API and a WebSocket endpoint that the browser UI connects to. The server checks state every 200 ms and pushes it to all connected clients over WebSocket whenever it has changed, so every open browser tab stays in sync automatically.

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
    ├── Header + status cards — MAKCU dot, Recoil / Flashlight / Script at a glance
    ├── Recoil tab     — enable, mouse-button binds, sliders, scripts
    ├── Flashlight tab — timing controls
    ├── Tools tab      — burst history, RPM calculator, Pattern Recorder, Pattern Visualiser
    └── Settings tab   — theme, game sensitivity scaling, connection, Stream Deck endpoints
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

`install.py` will ask which MAKCU firmware version you are running and install the correct makcu library automatically. Helix is tested on firmware **v3.7** — see [Troubleshooting → Firmware](#firmware).

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

Run once — installs `requirements.txt`, adds your user to the `plugdev` / `dialout` groups, writes the udev rule and a systemd service, then enables and starts it. Log out and back in (or reboot) afterwards so the group change applies:

```bash
./setup-autostart.sh
```

`requirements.txt` pulls the stock `makcu` library from PyPI. If you are on firmware v3.7, run `python install.py` first and pick the matching build (see [Firmware](#firmware)).

Useful commands after setup:
```bash
sudo systemctl status helix
sudo systemctl restart helix
sudo journalctl -u helix -f    # live logs
```

You can also restart from any browser: **Settings → Server → Restart**. The server exits and systemd relaunches it (about 5–10 s), with no sudo or password. This relies on the unit's `Restart=always` line, which `setup-autostart.sh` writes; if you edit the unit, keep `Restart=always` (or `on-failure`).

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

The header shows the app version and a **MAKCU** dot — green = connected, red = not connected (or the WebSocket to the server is down). Below it are three live cards — readable at a glance on a phone:

| Card | Meaning |
|------|---------|
| **Recoil** | `ON` green / `OFF` — tap to toggle from the browser |
| **Flashlight** | `ON` only when both flashlight and recoil are enabled — tap to toggle the flashlight master switch (shown as `Master: ON/OFF` on the card) |
| **Script** | Name of the currently loaded recoil script (`CS2: <weapon>` while a CS2 built-in pattern is selected) |

Status is pushed over WebSocket (checked every 200 ms, sent when it changes), with a 7 s REST poll of `/api/streamdeck` as a fallback for the MAKCU dot and cards.

---

## UI — Feature Reference

### Recoil Tab

**Control**

| Setting | What it does |
|---------|-------------|
| Enable Recoil | Master switch for recoil compensation (same as tapping the Recoil status card). |
| Toggle Mouse Button | Which mouse button (M4, M5, MMB) physically toggles recoil on/off via the MAKCU hardware. |
| Cycle Script Mouse Button | Which mouse button (M4, M5, MMB) cycles to the next saved script — useful for swapping weapons without touching the UI. Cycling stays inside the loaded script's game folder (or the root folder if the script has no game). |
| Require Aim (RMB) | Recoil compensation only fires while right mouse button is held (i.e. while aiming down sights). |
| Loop Recoil | When the script reaches the last shot vector, it loops back to the beginning instead of stopping. Useful for sustained automatic fire. |
| Randomisation | Adds small random offsets to each movement (and ±10% jitter to each shot's delay) so the pattern is less deterministic. The offset size is controlled by **Random Strength** in the Scaling card. |
| Return Crosshair | When you release the fire button, the MAKCU moves the mouse back by the vertical (Y) movement it applied during that burst. Horizontal movement is not undone. |

**Scaling**

All sliders run 0–100 in the UI; the API takes the underlying value (UI ÷ 20 for Recoil Scalar and Random Strength, ÷ 100 for X/Y Control, ÷ 50 for Return Speed).

| Setting | What it does |
|---------|-------------|
| Recoil Scalar | Global multiplier applied to every vector in the script. 1.0 (slider 20) = unchanged; increase to compensate for lower in-game sensitivity; decrease to dial it back. Ignored while a game preset is selected in Settings (the preset's scalar is used instead). |
| X Control | Scales only the horizontal (X) component of each vector — 0 disables all horizontal correction. |
| Y Control | Scales only the vertical (Y) component — 0 disables all vertical correction. |
| Random Strength | How large the random offsets can be when Randomisation is enabled. Higher values feel more human; too high and accuracy degrades. |
| Return Speed | Duration of the crosshair return move (slider 50 = 1 s), so higher values return more slowly. Only relevant when Return Crosshair is on. |

**CS2 Built-in Patterns**

Shown on the Recoil tab only while **Game** is set to **CS2** in Settings. Selecting a weapon (AK-47, M4A1-S) overrides the loaded script with a built-in pattern; choose *None* to go back to the loaded script.

**Scripts**

The scripts panel lets you manage your recoil scripts directly in the browser without needing a file manager or SSH. You can organise scripts into game folders (e.g. `ABI/`, `PubG/`) with **+ Game**, load a script to make it active, edit the raw vector text in the editor (steps are numbered in the gutter), and save or delete scripts — all stored on the web server. The `sens` field stores the in-game sensitivity the script was recorded at; it is saved with the script and shown here, but is not used when scaling (scaling comes from Settings).

---

### Flashlight Tab

The Flashlight feature automates your in-game torch/flashlight key to fire automatically when you fire your weapon.

| Setting | What it does |
|---------|-------------|
| Enable Flashlight | Master switch for the flashlight feature (same as tapping the Flashlight status card). |
| Flashlight Mouse Button | Which mouse button (LMB, RMB, MMB, M4, M5) the MAKCU clicks to trigger your in-game flashlight key. |
| Hold Threshold (ms) | How long you must hold the fire button before the flashlight triggers. Short tap shots (burst fire) won't activate it — only sustained fire will. |
| Cooldown (ms) | Minimum time between flashlight activations to avoid rapid re-triggering. |
| Pre-Fire Delay (ms) | A randomised delay (min → max) added after the hold threshold is met before the flashlight actually turns on. |

> Flashlight only fires when **Recoil is ON** and a mouse button is selected — prevents it from triggering in menus.

---

### Tools Tab

**Burst History**

The duration (ms) of your last five fire bursts, newest first. Click an entry to copy it into the RPM Calculator's *Measured* field. Not persisted across server restarts.

**RPM Calculator**

| Section | What it does |
|---------|-------------|
| Theoretical | Enter a weapon's RPM and magazine size to get ms per shot and total magazine duration. |
| Measured | Enter a measured burst time (ms) and shot count to get the effective RPM and ms per shot. |

**Pattern Recorder**

Records your own hand compensation while you spray and turns it into recoil steps. Turn **Recoil OFF**, press **Arm**, then hold left-click and spray (compensating by hand) — recording starts when you press and ends when you release (or choose *Start now* and press **Stop**). Set the shot interval (ms/shot — prefilled from the RPM Calculator), then **Load into editor** puts the steps into the script editor and the Pattern Visualiser; name and save them on the Recoil tab as usual.

| Field | What it does |
|-------|-------------|
| Shot interval | Milliseconds per shot. Each recoil step is the mouse movement you made during one shot interval. |
| Shots | Number of steps. Blank = recording length ÷ interval. |
| Reaction lead | Shifts the recorded movement earlier by this many ms, to offset your reaction delay (you pull down *after* the recoil kick). 0 replays your movement exactly as recorded. |

The recorder reads the firmware's tracked pointer position (`km.getpos`) 100 times a second (polling much faster makes the firmware drop its button-event stream, after which left-click is never seen), so it works on V3.x and V4.026+ firmware but needs Recoil OFF: the position includes everything sent to the PC, including Helix's own compensation. The live `position` readout lets you check that your movement is detected before you spray. A warning appears if the path reached the edge of the firmware's virtual screen (the data is then invalid). The default virtual screen allows about ±540 counts of vertical travel; tick **wide range** before arming for very long pulls (it enlarges the virtual screen for the recording and restores it afterwards).

**Button Monitor**

Shows what Helix receives from the MAKCU, so you can check each mouse button against your firmware: five lit pills (LMB, RMB, MMB, M4, M5) with event counts, the stream format Helix detected (`0x53 frames` or text), non-text byte and overflow counters, and the latest raw frames in hex. **Start monitor** also asks the firmware directly for the stream switch and each button's state (`km.buttons()`, `km.left()` …) so you can compare what the firmware says with what Helix received. Other buttons: re-enable the stream by text command or by the vendor's binary command, reset counters, and two **Test move** buttons that nudge the mouse 100 counts right or down to prove movement injection works independently of buttons and recoil. **Generate report** collects settings, the loaded script, button state and device information into one block of text to send when reporting a problem (it leaves out your folder paths). The monitor polls only while it is switched on and the Tools tab is open.

**Pattern Visualiser**

A canvas preview of the cumulative mouse path the loaded recoil script produces, with step count, total X / total Y and duration. It reads from and writes to the script editor on the Recoil tab — changes made here appear in that editor but are only stored when you press **Save** there. The **Advanced** button switches from the plain preview to the full editor:

| Feature | What it does |
|---------|-------------|
| Canvas | Drag points to adjust them; double-click to add a step; right-click for add / insert / inspect / delete. |
| Step list + inspector | Numeric x, y and delay (ms) editing per step; arrow keys nudge a selected point (Shift = ×5), Delete removes it. |
| Undo / Redo | Ctrl+Z / Ctrl+Y. |
| Play | Animates the path using each step's delay. |
| Bulk menu | Reverse, Mirror X / Y, Smooth, Scale X / Y / delays, Set all delays. |
| Snap, grid, numbers | Snap dragged points to a coordinate step (1, 5, 10 or 25), show the grid, show step numbers. |

---

### Settings Tab

**Appearance**

Theme selector (Default, Midnight, Ember, Cearum). The theme is stored on the server, so every connected client uses it.

**Sensitivity Scaling**

| Setting | What it does |
|---------|-------------|
| Game | Select your game from a built-in preset list. This sets a base scalar for that game so scripts written for a reference sensitivity are automatically scaled correctly. Select **Manual** to control the Recoil Scalar yourself. |
| In-Game Sensitivity | Enter your actual in-game sensitivity. Combined with the game preset, the server calculates the correct scalar: `base / your_sens`. |

**Connection**

Shows live status of the MAKCU device, its firmware, the serial baud rate, the web server, and the WebSocket connection so you can diagnose connectivity issues at a glance. After every connect Helix confirms the device really runs at 4,000,000 baud by asking it (`km.version()`, plus `km.baud()` on V4.073+); *confirmed by device* means the device answered at that rate. If the device does not answer, the baud row says so rather than showing a healthy connection.

**Server**

Shows how long the server has been up and has a **Restart** button (it asks for confirmation, then the page reconnects and reloads by itself). Under the systemd service the server exits and systemd relaunches it; started by hand (`python main.py` / `./start.sh`) it restarts itself in place. Settings are saved first, and the MAKCU reconnects on startup. Restart is not available on Windows (use the launcher) or when the server was started some other way, such as `uvicorn main:app`; the button is then disabled. Requests from other websites are rejected, but like the rest of the API there is no password, so anyone on your network can restart the server.

**Stream Deck**

Displays the API endpoints needed to configure the Web Requests plugin. See the [Stream Deck setup guide](https://github.com/jteddy/Helix/blob/main/streamdeck/SETUP.md) for full button-by-button instructions.

---

## Saved Scripts

Scripts are files stored in the `saved_scripts/` directory on the web server. They can be organised into game subfolders:

```
saved_scripts/
├── ABI/
│   ├── General.json
│   └── MP5.json
├── PubG/
│   └── M416.txt         ← legacy .txt scripts are still read
└── legacy_script.txt    ← flat root scripts still supported
```

### Script File Format

Scripts saved from the web UI or the API are written as `.json`:

```json
{
  "version": 1,
  "game": "ABI",
  "author": "",
  "sensitivity": 1.0,
  "steps": [
    [0.0, 5.0, 85.0],
    [-1.0, 6.0, 85.0]
  ]
}
```

Each step is `[x_offset, y_offset, delay_ms]`. `sensitivity` is the in-game sensitivity the script was recorded at (informational — see Scripts above), and `author` is currently always written empty.

Plain `.txt` scripts are still supported for loading — one vector per line, `x_offset, y_offset, delay_ms`; lines starting with `#` are comments and are ignored:

```
# x_offset, y_offset, delay_ms
0, 5, 85
-1, 6, 85
1, 7, 90
```

If a `.json` and a `.txt` share a name, the `.json` is used. Saving a script always writes `.json` (comment lines are not carried over), and deleting a script removes both formats. `.txt` files are treated as recorded at sensitivity 1.0.

---

## Stream Deck

A custom Stream Deck plugin is included with live state-aware icons — buttons update automatically when state changes from any source (web UI, MAKCU side button, API). It provides four actions: **Toggle Recoil**, **Toggle Flashlight**, **Cycle Script** and a display-only **MAKCU Status**, and polls `GET /api/streamdeck` once per second.

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
├── shared.py                     ← Shared singletons (state, makcu_controller, save_async)
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
│   ├── device.py                 ← GET /api/device
│   ├── server.py                 ← GET /api/server, POST /api/server/restart
│   ├── diagnostics.py            ← /api/buttons*, /api/device/test-move, /api/diagnostics
│   ├── recorder.py               ← /api/recorder/*
│   └── streamdeck.py             ← /api/streamdeck, /streamdeck/setup
├── mouse/makcu.py                ← MAKCU USB HID controller
├── menu/games.py                 ← Game sensitivity table
├── features/
│   ├── recoil/recoil.py          ← Recoil loop
│   ├── flashlight/               ← Flashlight loop
│   ├── recorder/recorder.py      ← Pattern recorder (getpos sampling, steps conversion)
│   └── cs2/weapon_data.py        ← Built-in CS2 recoil patterns (AK-47, M4A1-S)
├── static/index.html             ← Entire frontend (Recoil, Flashlight, Tools, Settings tabs; self-contained)
├── launcher.py                   ← PyQt6 desktop launcher (optional, desktop Linux only)
├── install-launcher.sh           ← Installs launcher to app menu + desktop shortcut
├── icons/helix.svg               ← App icon (used by launcher + .desktop file)
├── saved_scripts/                ← Recoil scripts (.json, legacy .txt)
│   └── <game>/
│       └── <weapon>.json
├── config.json                   ← Saved on every change and every 30s (gitignored)
├── config.json.bak               ← Copy of config.json made at startup (gitignored)
├── streamdeck/SETUP.md           ← Stream Deck configuration guide
└── streamdeck/com.helix.sdPlugin ← Stream Deck plugin (copy to Plugins folder)
```

---

## API Reference

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/state` | Full state snapshot (recoil, flashlight, settings, scripts, games, `makcu_connected`) |
| GET | `/api/health` | Server + MAKCU health check |
| GET | `/api/device` | `{connected, firmware, baud, baud_ok}` — display strings from the post-connect link check; `baud_ok` is `true` (device answered at 4,000,000), `false` (device reported another rate) or `null` (not confirmed) |
| GET | `/api/server` | `{restart_supported, mode, started_at, pid}` — `mode` is `systemd` (supervisor relaunches), `exec` (re-executes itself) or `null` (restart unavailable) |
| POST | `/api/server/restart` | Save settings, then exit and relaunch. Returns `{ok, mode}` just before the server goes down. 403 if the request has a cross-site `Origin`, 501 if restart is unavailable |
| WS | `/ws` | Live status stream (state checked every 200 ms, pushed when it changes) |

### Recoil

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/recoil` | Update recoil settings (partial update supported). Fields: `enabled`, `toggle_keybind`, `cycle_keybind`, `require_aim`, `loop_recoil`, `randomisation`, `return_crosshair`, `randomisation_strength`, `recoil_scalar`, `x_control`, `y_control`, `return_speed` |
| POST | `/api/recoil/toggle` | Toggle recoil on/off |

Slider-type fields take the underlying value, not the 0–100 UI value (see [Scaling](#recoil-tab)).

### Scripts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scripts` | List scripts (root, or a game folder via `?game=`) + loaded script + all games |
| GET | `/api/scripts/games` | List game subfolders |
| GET | `/api/scripts/content/{name}` | Get script content — looks in the root folder first, then each game folder |
| GET | `/api/scripts/content/{game}/{name}` | Get game-scoped script content |
| POST | `/api/scripts/load/{name}` | Load a flat script |
| POST | `/api/scripts/load/{game}/{name}` | Load a game-scoped script |
| POST | `/api/scripts/save` | Save a script as `.json` (`name`, `content`, optional `game`, optional `sensitivity`, default 1.0) |
| POST | `/api/scripts/cycle` | Cycle to the next script within the loaded script's game folder (root folder if it has no game) |
| DELETE | `/api/scripts/{name}` | Delete a flat script |
| DELETE | `/api/scripts/{game}/{name}` | Delete a game-scoped script |

Content endpoints return `{"content": "x,y,delay_ms\n...", "sensitivity": 1.0, "game": "", "author": ""}` regardless of whether the file on disk is `.json` or `.txt`.

### Patterns

Same storage as scripts (`saved_scripts/<game>/<weapon>.json`). The bundled web UI no longer calls these endpoints (it uses `/api/scripts/*`); they remain for external clients.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patterns` | List all game/weapon groups (games with at least one script) |
| GET | `/api/patterns/{game}/{weapon}` | Get pattern content (same response as the script content endpoints) |
| POST | `/api/patterns/{game}/{weapon}` | Save pattern content — body is raw vector text, or JSON `{"content": ..., "sensitivity": ...}` |
| DELETE | `/api/patterns/{game}/{weapon}` | Delete a pattern |

### Flashlight

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/flashlight` | Update flashlight settings (partial update). Fields: `enabled`, `keybind`, `hold_threshold_ms`, `cooldown_ms`, `pre_fire_min_ms`, `pre_fire_max_ms` |
| POST | `/api/flashlight/toggle` | Toggle flashlight on/off |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/settings` | Update `game_scalar` (game preset name or `Manual`), `game_sensitivity` and `theme` |

### Pattern Recorder

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/recorder` | Status: `state` (`idle`, `armed`, `recording`, `done`, `error`), `message` (while armed it shows the live getpos rate and whether left-click is being seen), `samples`, `duration_ms`, live `pos`, `rate_hz`, `clamped`, `lmb` |
| POST | `/api/recorder/arm` | Start (`{"trigger": "lmb" \| "now", "max_s": 20}`). `lmb` waits for left-click, records while held. 409 if Recoil is ON or a recording is running, 503 if MAKCU is not connected |
| POST | `/api/recorder/stop` | Finish now and keep the data |
| POST | `/api/recorder/cancel` | Discard |
| GET | `/api/recorder/result` | Convert the last recording: `?interval_ms=85&shots=30&lead_ms=0` (`shots`, `lead_ms` optional) → `{steps: [[x, y, delay_ms], …], total, path, duration_ms, clamped}` |

### Diagnostics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/buttons` | Button states, event counts, stream format, overflow counters and recent raw frames. `?probe=1` also queries the firmware (`stream_enabled`, `probe`) |
| POST | `/api/buttons/enable` | `{"mode": "text" \| "binary"}` — re-enable the button stream; returns what was sent and the firmware's reply |
| POST | `/api/buttons/reset` | Zero the event and overflow counters |
| POST | `/api/device/test-move` | `{"dx", "dy"}` (each within ±300) — one mouse move, to test injection |
| GET | `/api/diagnostics` | Settings, loaded-script summary, button and device state in one JSON object (no folder paths) |

### CS2 Built-in Patterns

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cs2/weapons` | List available built-in CS2 weapon patterns |
| POST | `/api/cs2/weapon` | Select a weapon (`{"weapon": "ak47"}`) or clear (`{"weapon": "none"}`) |

When a CS2 weapon is selected it overrides the loaded script for the recoil loop. Scaling still follows the Settings tab: with **Game** set to CS2 it is `1.25 / your_sens`; with **Manual** it is the Recoil Scalar.

### Stream Deck

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/streamdeck` | Lightweight JSON status for polling |
| GET | `/streamdeck/setup` | `streamdeck/SETUP.md` rendered as an HTML page (loads `marked` and `DOMPurify` from cdn.jsdelivr.net) |

**Response:**
```json
{
  "recoil":     true,
  "flashlight": false,
  "makcu":      true,
  "script":     "ABI/ak47"
}
```


---

## Troubleshooting

### Firmware

Helix is tested on MAKCU firmware **v3.7**, flashed on **both** the left (device) and right (host) sides.

`install.py` asks which firmware you are running and installs the matching `makcu` library build:

| Choice | Library build | Difference |
|--------|---------------|------------|
| 3.4 (stable) | `makcu==2.3.1` from PyPI | Side buttons are addressed as `ms1` / `ms2` |
| 3.7 | [`jteddy/makcu-py-lib`](https://github.com/jteddy/makcu-py-lib) branch `firmware-v3.7` | Identical, except the side buttons are addressed as `side1` / `side2` (renamed in firmware 3.7) |

The library build has to match the firmware. With a mismatched build, programmatic M4/M5 clicks fail — this affects the Flashlight when its mouse button is set to M4 or M5. Everything else Helix does goes through the same library calls on both builds.

**Firmware V4.x is not yet confirmed on hardware.** Everything Helix sends through the library (`km.move`, `km.left/right/middle/side1/side2`, `km.buttons`, and the binary baud-change frame at connect) is listed as available on the [MAKCU V4 API page](https://makcu.com/en/api/). Per that page, use **V4.039 or later** with the 3.7 library build: earlier V4 builds reject the baud-change frame. From V4.041 the firmware's default mouse interpolation is AUTO (it adapts 1–64 ms to the interval between injected moves) instead of V3-style immediate sends, which can change recoil timing; it is only adjustable through the binary MAK_API (opcode `0x1F`), not a text command. Test on your hardware after any firmware change.

### Updating Firmware

- MAKCU requires the CH343 USB-to-serial driver on the computer you use for flashing. See the setup page under Documentation below for the download link.
- **Correct COM port:** the COM port for USB 2 should be numbered below 10. A port number of 10 or higher can cause connection issues.
- **Baud rate:** the baud rate is matched to the software you use — see the baud rate section on the MAKCU information page.
- **Both sides flashed:** make sure both the left (device) and right (host) sides are set up and flashed.

#### Documentation
- https://www.makcu.com/en/setup
- https://makcu.com/en/api/ — serial command reference, including the V4 differences
- https://makcu.com/mcp/documentation — MAKCU's MCP server: a read-only, hosted docs lookup (command reference, search, LED troubleshooting; no key needed). The repo's `.mcp.json` registers it as `makcu-docs` for Claude Code; approve it once when prompted.

#### Tools
- https://terminal.spacehuhn.com/
- https://makxd.com/

### Left-click not detected

If the Pattern Recorder stays on *armed* (or recoil never fires), Helix is not receiving button events from the MAKCU. While armed, the card reports the live `getpos` rate, whether the firmware says its button stream is on, and how many non-text bytes (button-stream frames) the device has sent since you armed, with the latest one in hex. Press and release left-click and watch those: a non-zero count means the device is sending something; `button stream OFF` means the firmware refused to enable it. The recorder also asks the firmware for the physical button state (`km.left()`, shown in the card) and uses it as a fallback trigger when the button stream is silent.

The **Button Monitor** card (Tools tab) shows what Helix receives live: each button's state and event count, the stream format, overflows and the latest raw frames in hex. **Generate report** collects everything needed to diagnose a problem into one block of text to send along with your firmware version.

### Script does not play to the end / left-click or right-click misread

Newer MAKCU firmware reports mouse buttons as binary frames (`de ad 03 00 53 …`), which the `makcu` library misreads: a right-click can appear as a left-click and any button press while you hold left-click makes it flicker, restarting the recoil script from step 1. Helix decodes these frames itself (the Button Monitor and the Pattern Recorder card name the format they see). It also re-enables the stream by itself if the firmware reports an overflow.

Every recoil burst logs how far the script got, for example `[Recoil] BURST: 2400ms, 30/30 steps (LMB released)` (`sudo journalctl -u helix -f` under systemd). If the last step never seems to apply, check that line first, then that **X Control** is not 0 (it zeroes all horizontal movement) and that the Game / Recoil Scalar is not tiny.

### MAKCU Setup on Arch Linux (CachyOS)

The MAKCU uses an ESP32-S3 with native CDC ACM, so no CH343 driver is needed.

1. Put the MAKCU in flash/normal mode per the docs.
2. Plug it into USB.
3. Check the port:
   ```bash
   ls /dev/ttyACM*
   ```
4. Connect over serial (the baud rate defaults to 115200 unless changed):
   ```bash
   screen /dev/ttyACM0 115200
   ```
   Exit `screen` with `Ctrl+A` then `\`.

Notes:
- The device appears as `ttyACM0` via the built-in `cdc-acm` kernel driver.
- No additional drivers are required on modern Linux kernels.
