# Stream Deck Setup for Helix

The Stream Deck runs on your **gaming PC (Windows)** and talks to the Helix server over your LAN via HTTP.

---

## Plugin to Install

From the Stream Deck Store, install:

> **Web Requests** by Adrián — Free

Search "Web Requests" in the store. It will appear in the results.

---

## Your Server Address

Replace `HELIX_IP` in all examples below with your server's actual IP address, e.g. `192.168.1.50`.

Find it in the **Settings tab** of the Helix web UI under Connection → Server, or run on the server:
```bash
hostname -I
```

> **Tip:** Assign a static IP to the Helix server in your router settings so this address never changes.

---

## Button Setup (Web Requests plugin)

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

---

## Standard Buttons

### Button 1 — Toggle Recoil ON/OFF

```
Title  : Recoil
URL    : http://HELIX_IP:8000/api/recoil/toggle
Method : POST
```

---

### Button 2 — Toggle Flashlight ON/OFF

```
Title  : Flash
URL    : http://HELIX_IP:8000/api/flashlight/toggle
Method : POST
```

---

### Button 3 — Cycle to Next Script

Cycles through all scripts across all game folders in alphabetical order.

```
Title  : Cycle Script
URL    : http://HELIX_IP:8000/api/scripts/cycle
Method : POST
```

---

### Button 4 — Load a Specific Script

#### Game-scoped script (organised under a game subfolder)
```
Title  : CS2 AK-47
URL    : http://HELIX_IP:8000/api/scripts/load/CS2/ak47
Method : POST
```

#### Script name with spaces

Spaces in filenames must be URL-encoded as `%20`. Do not use a literal space in the URL.

```
Title  : CS2 AK47 Meta
URL    : http://HELIX_IP:8000/api/scripts/load/CS2/AK47%20Meta
Method : POST
```

The file on disk is `saved_scripts/CS2/AK47 Meta.txt` — the server decodes `%20` back to a space automatically.

Replace `CS2` with your game folder name and the script name with the filename (no `.txt` extension, case-sensitive, spaces as `%20`). The game folder names match what you see in the Recoil tab's script list.

---

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

## Advanced: Polling for State Sync

The Web Requests plugin fires only on button press — it does not poll automatically. If you toggle recoil via the MAKCU side button (M4/M5) rather than Stream Deck, the button icon will fall out of sync.

To keep state in sync you need a plugin that supports **periodic HTTP polling**, such as:

- **DataDog** by BarRaider — can poll a URL on a timer and update button text/icon based on the response
- **KNX** or other automation plugins that support scheduled GET requests

Poll `GET http://HELIX_IP:8000/api/streamdeck` on a 1-second interval and read the `recoil` field (`true`/`false`) to update button state.

For most users this is unnecessary — just use the standard POST toggle button.

---

## Troubleshooting

**Button does nothing / times out:**
- Confirm the Helix server is running — open `http://HELIX_IP:8000` in a browser on the gaming PC
- Check Windows Firewall isn't blocking outbound connections on port 8000
- Make sure gaming PC and Helix server are on the same LAN

**Script load returns 404:**
- The script name is case-sensitive and must match the filename exactly (without `.txt`)
- If using game-scoped scripts, confirm the game folder name matches: check the Recoil tab or browse `saved_scripts/` on the server
- Use `GET http://HELIX_IP:8000/api/scripts` to list all available scripts and confirm the names

**Wrong IP:**
- The server IP can change on DHCP. Assign a static IP to the Helix server in your router settings, or use its hostname if your router supports mDNS

**State out of sync:**
- Add a polling `GET` to `/api/streamdeck` on a 1-second interval
- Use JSONPath extraction to update button titles dynamically

**Server stopped:**
- On the Helix server: `sudo systemctl restart cearum-web`
- Check logs: `sudo journalctl -u cearum-web -n 50`
