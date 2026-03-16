# Cearum Web

> **Fork of [dev-boog/Cearum-Recoil](https://github.com/dev-boog/Cearum-Recoil/)** — reworked with a web UI front-end so the controls are accessible from any browser on your network.

Recoil control system with a web UI. Runs as a FastAPI server on Linux connected to a MAKCU via USB. Open from any browser on your network — phone, tablet, or second monitor.

---

## Architecture

### Server

```
Any browser (phone, tablet, monitor)
└── http://<server-ip>:8000
        │
        ▼
Cearum Server  (Linux, any hardware)
├── Python / FastAPI  ← HTTP + WebSocket API
├── MAKCU connected via USB HID
└── Recoil + Flashlight loops running continuously
```

The server is a Python [FastAPI](https://fastapi.tiangolo.com/) application that runs on any Linux machine. It exposes an HTTP API and a WebSocket endpoint that the browser UI connects to. State is pushed to all connected clients every 200 ms over WebSocket, so every open browser tab stays in sync automatically.

### How It Fits Into Your Setup

```
Gaming PC (Windows)
├── Game running
├── Mouse ──→ MAKCU (USB passthrough) ──→ Game input
└── Stream Deck ──→ HTTP ──→ Cearum Server

Cearum Server (Linux, any hardware)
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

```bash
git clone https://github.com/jteddy/Cearum-Web/
cd Cearum-Web
chmod +x install.sh start.sh setup-autostart.sh
./install.sh      # install Python dependencies once
./start.sh        # run manually (Ctrl+C to stop)
```

Open `http://<server-ip>:8000` from any browser. Find your server's IP with:
```bash
hostname -I
```

---

## Auto-start on Boot

Run once — installs dependencies, writes a systemd service, enables it, and starts it:

```bash
./setup-autostart.sh
```

Useful commands after setup:
```bash
sudo systemctl status cearum-web
sudo systemctl restart cearum-web
sudo journalctl -u cearum-web -f    # live logs
```

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
| Hold Threshold (ms) | How long the keybind must be held before it counts as a "hold" rather than a tap — prevents accidental triggers. |
| Cooldown (ms) | Minimum time between flashlight activations to avoid rapid re-triggering. |
| Pre-Fire Delay (ms) | A randomised delay (min → max) inserted before each flashlight pulse for a more natural timing. |

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

Displays the API endpoints needed to configure the Web Requests plugin. See the [Stream Deck setup guide](https://github.com/jteddy/Cearum-Web/blob/main/streamdeck/SETUP.md) for full button-by-button instructions.

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

See the [Stream Deck setup guide](https://github.com/jteddy/Cearum-Web/blob/main/streamdeck/SETUP.md) for full button-by-button instructions.

Short version: install the free *Web Requests by Adrián* plugin from the Stream Deck Store, then configure buttons with:
```
POST http://<server-ip>:8000/api/recoil/toggle
POST http://<server-ip>:8000/api/flashlight/toggle
POST http://<server-ip>:8000/api/scripts/cycle
GET  http://<server-ip>:8000/api/streamdeck
```

---

## Directory Structure

```
cearum-web/
├── main.py                       ← FastAPI backend + all API routes
├── state.py                      ← Shared app state (thread-safe)
├── config_manager.py             ← JSON save/load (atomic write)
├── setup-autostart.sh            ← One-shot systemd installer
├── install.sh / start.sh
├── requirements.txt
├── mouse/makcu.py                ← MAKCU USB HID controller
├── menu/games.py                 ← Game sensitivity table
├── features/recoil/recoil.py     ← Recoil loop
├── features/flashlight/          ← Flashlight loop
├── static/index.html             ← Entire frontend (4 tabs, self-contained)
├── saved_scripts/                ← Recoil scripts + Vector Editor patterns
│   └── <game>/
│       └── <weapon>.txt
├── config.json                   ← Auto-saved every 30s (gitignored)
└── streamdeck/SETUP.md           ← Stream Deck configuration guide
```

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
