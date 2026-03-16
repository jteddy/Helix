# Stream Deck Setup for Cearum Web

The Stream Deck runs on your **gaming PC (Windows)** and talks to the Cearum server over your LAN via HTTP.

---

## Plugin to Install

From the Stream Deck Store, install:

> **Web Requests** by Adrián — Free

Search "Web Requests" in the store. It will appear in the results.

---

## Your Server Address

Replace `CEARUM_IP` in all examples below with your server's actual IP address, e.g. `192.168.1.50`.

Find it in the **Settings tab** of the Cearum web UI, or run on the server:
```bash
hostname -I
```

> **Tip:** Assign a static IP to the Cearum server in your router settings so this address never changes.

---

## Button Setup (Web Requests plugin)

Each button uses the **Web Requests** action. The fields you fill in are:

| Field | Notes |
|-------|-------|
| **URL** | Full address including port 8000 |
| **Method** | GET or POST depending on the button |
| **Body** | Leave empty for all buttons below |

---

## Standard Buttons

### Button 1 — Toggle Recoil ON/OFF

```
Method : POST
URL    : http://CEARUM_IP:8000/api/recoil/toggle
Body   : (empty)
Title  : Recoil
```

---

### Button 2 — Toggle Flashlight ON/OFF

```
Method : POST
URL    : http://CEARUM_IP:8000/api/flashlight/toggle
Body   : (empty)
Title  : Flash
```

---

### Button 3 — Cycle to Next Script

Cycles through all scripts across all game folders in alphabetical order.

```
Method : POST
URL    : http://CEARUM_IP:8000/api/scripts/cycle
Body   : (empty)
Title  : Cycle Script
```

---

### Button 4 — Load a Specific Script

#### Flat script (root of `saved_scripts/`)
```
Method : POST
URL    : http://CEARUM_IP:8000/api/scripts/load/ak47
Body   : (empty)
Title  : AK-47
```

#### Game-scoped script (organised under a game subfolder)
```
Method : POST
URL    : http://CEARUM_IP:8000/api/scripts/load/ABI/ak47
Body   : (empty)
Title  : ABI AK-47
```

Replace `ABI` with your game folder name and `ak47` with the weapon name (no `.txt` extension, case-sensitive). The game folder names match what you see in the Recoil tab's script list.

> **Which format to use?** If your scripts are organised by game in the Vector Editor (e.g. `ABI/ak47`), use the `load/{game}/{weapon}` form. If you have flat legacy scripts in the root `saved_scripts/` folder, use `load/{name}`.

---

### Button 5 — Check Status

```
Method : GET
URL    : http://CEARUM_IP:8000/api/streamdeck
Body   : (empty)
Title  : Status
```

Returns JSON that Web Requests can display as the button title:
```json
{
  "recoil":     true,
  "flashlight": false,
  "makcu":      true,
  "script":     "ABI/ak47"
}
```

If Web Requests supports title templates, use `{recoil}` to show ON/OFF on the button face, or `{script}` to show the loaded script name.

---

## Recommended Layouts

### 5-button single row

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│  RECOIL  │  FLASH   │  CYCLE   │  AK-47   │  STATUS  │
│  TOGGLE  │  TOGGLE  │  SCRIPT  │  (load)  │  (poll)  │
└──────────┴──────────┴──────────┴──────────┴──────────┘
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
http://CEARUM_IP:8000/api/scripts/load/ABI/ak47
http://CEARUM_IP:8000/api/scripts/load/ABI/m4a1
```

---

## Advanced: Multi-Action Toggle with State Icon

Using BarRaider's **"Toggle"** action type:

1. **State 0** (Recoil OFF icon): `POST /api/recoil/toggle`
2. **State 1** (Recoil ON icon): `POST /api/recoil/toggle`

To keep the icon in sync even when toggled via the MAKCU button (M4/M5), add a polling `GET` to `/api/streamdeck` on a 500ms–1000ms interval and use the `recoil` field to update button state.

---

## Troubleshooting

**Button does nothing / times out:**
- Confirm the Cearum server is running — open `http://CEARUM_IP:8000` in a browser on the gaming PC
- Check Windows Firewall isn't blocking outbound connections on port 8000
- Make sure gaming PC and Cearum server are on the same LAN

**Script load returns 404:**
- The script name is case-sensitive and must match the filename exactly (without `.txt`)
- If using game-scoped scripts, confirm the game folder name matches: check the Recoil tab or browse `saved_scripts/` on the server
- Use `GET http://CEARUM_IP:8000/api/scripts` to list all available scripts and confirm the names

**Wrong IP:**
- The server IP can change on DHCP. Assign a static IP to the Cearum server in your router settings, or use its hostname if your router supports mDNS

**State out of sync:**
- Add a polling `GET` to `/api/streamdeck` on a 1-second interval
- Use JSONPath extraction to update button titles dynamically

**Server stopped:**
- On the Cearum server: `sudo systemctl restart cearum-web`
- Check logs: `sudo journalctl -u cearum-web -n 50`
