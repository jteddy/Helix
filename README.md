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

Short version: install the free *HTTP Request by BarRaider* plugin, then:
```
POST http://<server-ip>:8000/api/recoil/toggle
POST http://<server-ip>:8000/api/flashlight/toggle
GET  http://<server-ip>:8000/api/streamdeck
```

---

## Directory Structure

```
cearum-web/
├── main.py                       ← FastAPI backend + all API routes
├── state.py                      ← Shared app state
├── config_manager.py             ← JSON save/load on the server
├── setup-autostart.sh            ← One-shot systemd installer for Xubuntu
├── install.sh / start.sh
├── requirements.txt
├── mouse/makcu.py                ← MAKCU USB HID controller (unchanged)
├── menu/games.py                 ← Game sensitivity table
├── features/recoil/recoil.py     ← Recoil loop
├── features/flashlight/          ← Flashlight loop
├── static/index.html             ← Entire frontend (4 tabs, self-contained)
├── patterns/                     ← Vector Editor patterns
├── saved_scripts/                ← Recoil scripts
├── config.json                   ← Auto-saved every 30s
└── streamdeck/SETUP.md           ← Stream Deck configuration guide
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/state` | Full state snapshot |
| POST | `/api/recoil` | Update recoil settings |
| POST | `/api/recoil/toggle` | Toggle recoil on/off |
| GET | `/api/scripts` | List scripts |
| POST | `/api/scripts/load/{name}` | Load a script |
| POST | `/api/scripts/save` | Save a script |
| POST | `/api/scripts/cycle` | Cycle to next script |
| DELETE | `/api/scripts/{name}` | Delete a script |
| POST | `/api/flashlight` | Update flashlight settings |
| POST | `/api/flashlight/toggle` | Toggle flashlight on/off |
| POST | `/api/settings` | Update game/sensitivity settings |
| GET | `/api/patterns` | List vector editor patterns |
| GET/POST/DELETE | `/api/patterns/{game}/{weapon}` | CRUD for patterns |
| GET | `/api/streamdeck` | Lightweight status for Stream Deck polling |
| WS | `/ws` | Live status stream (200ms push) |
