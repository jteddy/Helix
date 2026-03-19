# Stream Deck Setup for Helix

The Stream Deck runs on your **gaming PC (Windows)** and talks to the Helix server over your LAN via HTTP.

Two options are available. **Option A** gives you live state-aware icons that update automatically. **Option B** is a simpler setup using a third-party plugin.

---

## Your Server Address

Replace `HELIX_IP` in all examples below with your server's actual IP address, e.g. `192.168.1.50`.

Find it in the **Settings tab** of the Helix web UI under Connection → Server, or run on the server:
```bash
hostname -I
```

> **Tip:** Assign a static IP to the Helix server in your router settings so this address never changes.

---

## Option A — Helix Plugin (recommended)

A custom Stream Deck plugin that polls the Helix API every second and renders live icons on each button. When you toggle recoil from the web UI, the MAKCU side button, or another device, the Stream Deck icon updates within one second.

### Available Actions

| Action | Key Press | Icon Shows |
|--------|-----------|------------|
| **Toggle Recoil** | Toggles recoil on/off | Green crosshair (ON) or dim red crosshair (OFF) |
| **Toggle Flashlight** | Toggles flashlight on/off | Yellow bolt (ON) or dim red bolt (OFF) |
| **Cycle Script** | Cycles to next script | Blue arrows + current script name |
| **MAKCU Status** | *(display only)* | Green chip (connected) or red chip (error) |

### Install

1. Close the Stream Deck software.
2. Copy `streamdeck/com.helix.sdPlugin` into your plugins folder:
   ```
   %APPDATA%\Elgato\StreamDeck\Plugins\
   ```
3. Restart the Stream Deck software.
4. Look for the **Helix** category in the action list.

### Configure

1. Drag any Helix action onto a button.
2. In the **Property Inspector** (right panel), enter your Helix server URL:
   ```
   http://HELIX_IP:8000
   ```
3. Click **Test Connection** to verify. You should see "Connected!" in green.
4. This setting is shared across all Helix buttons — set it once.

### How State Sync Works

The plugin polls `GET /api/streamdeck` once per second. The response contains the current state of recoil, flashlight, MAKCU, and the loaded script name. The plugin renders an SVG icon for each button based on that state and pushes it to the Stream Deck hardware via `setImage`.

When you press a button, the plugin sends the matching POST request (`/api/recoil/toggle`, etc.) and immediately re-polls, so the icon updates without waiting for the next 1-second tick.

State changes from **any source** — web UI, MAKCU side button, another Stream Deck, or the API — are reflected within one second.

### Icon Reference Files

Static SVG previews of each button state are included inside the plugin folder at `com.helix.sdPlugin/icons/`. The plugin itself renders icons dynamically in JavaScript — these files are reference copies for previewing designs or converting to PNG for other tools.

```
com.helix.sdPlugin/icons/
├── recoil-on.svg       (green crosshair)
├── recoil-off.svg      (red crosshair)
├── flashlight-on.svg   (yellow lightning bolt)
├── flashlight-off.svg  (red lightning bolt)
├── cycle.svg           (blue circular arrows + script name)
├── makcu-ok.svg        (green USB chip)
└── makcu-err.svg       (red USB chip)
```

All icons are 144×144 SVG.

---

## Option B — Simple Setup (Web Requests plugin)

If you prefer a quick setup without state sync, use the free **Web Requests** plugin.

### Plugin to Install

From the Stream Deck Store, install:

> **Web Requests** by Adrián — Free

Search "Web Requests" in the store. It will appear in the results.

### Button Setup

Drag the **Web Requests** action onto a button. When prompted to choose an action type, select:

> **HTTP Request** — not WebSocket Message

WebSocket Message is for persistent socket connections and will not work with Helix. HTTP Request sends a standard one-off HTTP call, which is what all the endpoints below expect.

Each button uses the following fields:

| Field | Value |
|-------|-------|
| **Title** | Label shown on the button face |
| **URL** | Full address including port 8000 |
| **Method** | GET or POST depending on the button |

> **Content Type, Headers, and Body are not needed** for any of the standard buttons below — leave them empty or at their defaults.

### Standard Buttons

#### Button 1 — Toggle Recoil ON/OFF

```
Title  : Recoil
URL    : http://HELIX_IP:8000/api/recoil/toggle
Method : POST
```

#### Button 2 — Toggle Flashlight ON/OFF

```
Title  : Flash
URL    : http://HELIX_IP:8000/api/flashlight/toggle
Method : POST
```

#### Button 3 — Cycle to Next Script

Cycles through all scripts across all game folders in alphabetical order.

```
Title  : Cycle Script
URL    : http://HELIX_IP:8000/api/scripts/cycle
Method : POST
```

#### Button 4 — Load a Specific Script

**Game-scoped script (organised under a game subfolder)**
```
Title  : CS2 AK-47
URL    : http://HELIX_IP:8000/api/scripts/load/CS2/ak47
Method : POST
```

**Script name with spaces**

Spaces in filenames must be URL-encoded as `%20`. Do not use a literal space in the URL.

```
Title  : CS2 AK47 Meta
URL    : http://HELIX_IP:8000/api/scripts/load/CS2/AK47%20Meta
Method : POST
```

The file on disk is `saved_scripts/CS2/AK47 Meta.txt` — the server decodes `%20` back to a space automatically.

Replace `CS2` with your game folder name and the script name with the filename (no `.txt` extension, case-sensitive, spaces as `%20`). The game folder names match what you see in the Recoil tab's script list.

---

## Recommended Layouts

### 4-button single row

For most users, four buttons cover everything:

```
┌──────────┬──────────┬──────────┬──────────┐
│  RECOIL  │  FLASH   │  CYCLE   │  AK-47   │
│  TOGGLE  │  TOGGLE  │  SCRIPT  │  (load)  │
└──────────┴──────────┴──────────┴──────────┘
```

### Full 5×3 deck (per-weapon buttons)

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│  RECOIL  │  FLASH   │  MAKCU   │  CYCLE   │ SCRIPT 1 │
│  ON/OFF  │  ON/OFF  │  STATUS  │  SCRIPT  │  (ak47)  │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│ SCRIPT 2 │ SCRIPT 3 │ SCRIPT 4 │ SCRIPT 5 │          │
│  (m4a1)  │  (mp5)   │  (scar)  │  (m416)  │          │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

For game-scoped scripts, each weapon button URL becomes:
```
http://HELIX_IP:8000/api/scripts/load/ABI/ak47
http://HELIX_IP:8000/api/scripts/load/ABI/m4a1
```

---

## API Reference

These are the endpoints used by both options above.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/recoil/toggle` | Toggle recoil on/off |
| POST | `/api/flashlight/toggle` | Toggle flashlight on/off |
| POST | `/api/scripts/cycle` | Cycle to next script |
| POST | `/api/scripts/load/{name}` | Load a flat script |
| POST | `/api/scripts/load/{game}/{name}` | Load a game-scoped script |
| GET | `/api/streamdeck` | Lightweight state for polling |
| GET | `/api/health` | Liveness check + MAKCU status |

`GET /api/streamdeck` returns:
```json
{
    "recoil": true,
    "flashlight": false,
    "makcu": true,
    "script": "CS2/ak47"
}
```

---

## Troubleshooting

**Plugin not showing in action list:**
- Make sure the `com.helix.sdPlugin` folder is directly inside `%APPDATA%\Elgato\StreamDeck\Plugins\` (not nested in an extra subfolder)
- Restart the Stream Deck software completely (right-click tray icon → Quit, then relaunch)

**Button does nothing / times out:**
- Confirm the Helix server is running — open `http://HELIX_IP:8000` in a browser on the gaming PC
- Check Windows Firewall isn't blocking outbound connections on port 8000
- Make sure gaming PC and Helix server are on the same LAN

**Icons stay in error state (red):**
- The plugin can't reach the server — use the Property Inspector's **Test Connection** button to diagnose
- Check that the URL includes the protocol (`http://`) and port (`:8000`)

**Script load returns 404:**
- The script name is case-sensitive and must match the filename exactly (without `.txt`)
- If using game-scoped scripts, confirm the game folder name matches: check the Recoil tab or browse `saved_scripts/` on the server
- Use `GET http://HELIX_IP:8000/api/scripts` to list all available scripts and confirm the names

**Wrong IP:**
- The server IP can change on DHCP. Assign a static IP to the Helix server in your router settings, or use its hostname if your router supports mDNS

**Server stopped:**
- On the Helix server: `sudo systemctl restart helix`
- Check logs: `sudo journalctl -u helix -n 50`
