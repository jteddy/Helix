# Cearum Web

Recoil control system with a web UI. Runs as a FastAPI server on Xubuntu (or any Linux machine) connected to a MAKCU via USB. Open from any browser on your network — phone, tablet, or second monitor.

## Architecture

```
Gaming PC (Windows)
├── Game running
├── Mouse ──→ MAKCU (USB passthrough) ──→ Game PC
└── Stream Deck ──→ HTTP ──→ Cearum Server

Cearum Server (Xubuntu, any hardware)
├── MAKCU connected via USB COM
├── Python backend (systemd, auto-starts on boot)
├── http://<server-ip>:8000
└── Recoil + Flashlight loops running continuously

Any browser (phone, tablet, monitor)
└── http://<server-ip>:8000
    ├── Status panel  — MAKCU / Recoil / Flashlight / Script at a glance
    ├── Recoil tab    — enable, keybinds, sliders, scripts
    ├── Flashlight tab — timing controls
    ├── Settings tab  — game sensitivity scaling, browser hotkey, Stream Deck docs
    └── Vector Editor — full canvas-based pattern editor
```

---

## Quick Start

```bash
chmod +x install.sh start.sh setup-autostart.sh
./install.sh      # install Python dependencies once
./start.sh        # run manually (Ctrl+C to stop)
```

Open `http://<server-ip>:8000` from any browser. Find the IP:
```bash
hostname -I
```

---

## Auto-start on Boot (Xubuntu)

Run once — handles everything (installs deps, writes systemd service, enables, starts):

```bash
./setup-autostart.sh
```

Useful commands after setup:
```bash
sudo systemctl status  cearum-web
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

Status updates via WebSocket every 200ms — pressing M5 on your MAKCU reflects on your phone almost instantly.

---

## Stream Deck

See **`streamdeck/SETUP.md`** for full button-by-button instructions.

Short version: install the free *Web Requests by Adrián* plugin from the Stream Deck Store, then:
```
POST http://<server-ip>:8000/api/recoil/toggle
POST http://<server-ip>:8000/api/flashlight/toggle
GET  http://<server-ip>:8000/api/streamdeck
```

---

## Scripts & Game Organisation

Scripts are stored under `saved_scripts/` and can be organised into game subfolders:

```
saved_scripts/
├── ABI/                   ← Arena Breakout Infinite
│   ├── ak47.txt
│   └── mp5.txt
├── Tarkov/
│   └── m4.txt
└── legacy_script.txt      ← Flat root scripts still supported
```

When loading a game-scoped script via the API or Stream Deck, use the `game/weapon` form:
```
POST http://<server-ip>:8000/api/scripts/load/ABI/ak47
```

---

## Directory Structure

```
cearum-web/
├── main.py                       ← FastAPI backend + all API routes
├── state.py                      ← Shared app state (thread-safe)
├── config_manager.py             ← JSON save/load (atomic write)
├── setup-autostart.sh            ← One-shot systemd installer for Xubuntu
├── install.sh / start.sh
├── requirements.txt
├── mouse/makcu.py                ← MAKCU USB HID controller
├── menu/games.py                 ← Game sensitivity table
├── features/recoil/recoil.py     ← Recoil loop
├── features/flashlight/          ← Flashlight loop
├── static/index.html             ← Entire frontend (4 tabs, self-contained)
├── saved_scripts/                ← Recoil scripts + Vector Editor patterns
│   └── <game>/                   ← Optional game subfolders
│       └── <weapon>.txt
├── config.json                   ← Auto-saved every 30s (gitignored)
└── streamdeck/SETUP.md           ← Stream Deck configuration guide
```

> **Note:** The Vector Editor and the Recoil Scripts tab share the same `saved_scripts/` directory. There is no separate `patterns/` folder.

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

---

## Script File Format

Scripts are plain text files, one vector per line:

```
# x_offset, y_offset, delay_ms
0, 5, 85
-1, 6, 85
1, 7, 90
```

Lines starting with `#` are comments and are ignored.

---

## Troubleshooting

**MAKCU shows N/C (not connected):**
- Check the USB cable is seated firmly
- Confirm udev rules are applied: `sudo udevadm trigger`
- Check logs: `sudo journalctl -u cearum-web -n 50`

**Recoil has no effect:**
- Confirm Recoil is `ON` in the status panel
- Check the correct script is loaded
- Verify game sensitivity is set correctly in the Settings tab

**Server won't start:**
- Port 8000 already in use? `sudo lsof -i :8000`
- Python deps missing? Run `./install.sh` again
- Check logs: `sudo journalctl -u cearum-web -f`

**config.json / scripts_dir wrong path after reinstall:**
- Delete `config.json` and restart — the server will recreate it with the correct default path
