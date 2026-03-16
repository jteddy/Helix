# Stream Deck Setup for Cearum Web

The Stream Deck runs on your **gaming PC (Windows)** and talks to the Cearum server over your LAN.

---

## Prerequisites

Install the free **HTTP Request by BarRaider** plugin from the Stream Deck Store:

1. Open Stream Deck software → click the Store icon (bottom right)
2. Search: `HTTP Request`
3. Install **"HTTP Request" by BarRaider**

---

## Server Address

Replace `CEARUM_IP` in all examples below with your server's IP address, e.g. `192.168.1.50`.

You can find the IP on the **Settings tab** of the Cearum web UI.

---

## Button Configurations

### Button 1 — Toggle Recoil ON/OFF

| Field | Value |
|-------|-------|
| Action | HTTP Request |
| URL | `http://CEARUM_IP:8000/api/recoil/toggle` |
| Method | POST |
| Body | *(empty)* |
| Title | Recoil |

**Dynamic title (shows current state):**
- Set a second HTTP Request button with GET `http://CEARUM_IP:8000/api/streamdeck`
- Use the `recoil` field from the JSON response to update the title

---

### Button 2 — Toggle Flashlight ON/OFF

| Field | Value |
|-------|-------|
| Action | HTTP Request |
| URL | `http://CEARUM_IP:8000/api/flashlight/toggle` |
| Method | POST |
| Body | *(empty)* |
| Title | Flash |

---

### Button 3 — MAKCU Status (read-only poll)

| Field | Value |
|-------|-------|
| Action | HTTP Request (polling mode) |
| URL | `http://CEARUM_IP:8000/api/streamdeck` |
| Method | GET |
| Poll Interval | 1 second |

The response JSON:
```json
{
  "recoil":     true,
  "flashlight": false,
  "makcu":      true,
  "script":     "ak47"
}
```

Use BarRaider's **JSONPath** feature to extract fields:
- `$.recoil` → show on Recoil button title
- `$.makcu` → show on MAKCU button
- `$.script` → show currently loaded script name

---

### Button 4 — Cycle Script

| Field | Value |
|-------|-------|
| Action | HTTP Request |
| URL | `http://CEARUM_IP:8000/api/scripts/cycle` |
| Method | POST |
| Body | *(empty)* |
| Title | Cycle Script |

---

### Button 5 — Load a specific script

| Field | Value |
|-------|-------|
| Action | HTTP Request |
| URL | `http://CEARUM_IP:8000/api/scripts/load/ak47` |
| Method | POST |
| Body | *(empty)* |
| Title | AK-47 |

Replace `ak47` with the exact script name (no `.txt` extension).

---

## Advanced: Multi-Action Toggle with State Icon

Using BarRaider's **"Toggle"** action type:

1. **State 0** (Recoil OFF icon): POST `/api/recoil/toggle`
2. **State 1** (Recoil ON icon): POST `/api/recoil/toggle`

Combine with a polling GET to `/api/streamdeck` every 500ms to keep the icon in sync even when toggled via MAKCU button (M4/M5).

---

## Recommended Profile Layout (5×3 deck)

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│  RECOIL  │  FLASH   │  MAKCU   │  CYCLE   │ SCRIPT 1 │
│  ON/OFF  │  ON/OFF  │  STATUS  │  SCRIPT  │  (ak47)  │
├──────────┼──────────┼──────────┼──────────┼──────────┤
│ SCRIPT 2 │ SCRIPT 3 │          │          │          │
│ (m4a1)   │ (mp5)    │          │          │          │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## Troubleshooting

**Button does nothing:**
- Check that `CEARUM_IP` is correct
- Confirm the Cearum server is running: open `http://CEARUM_IP:8000` in a browser
- Check Windows Firewall isn't blocking outbound HTTP on port 8000

**State out of sync:**
- Add a polling GET to `/api/streamdeck` on a 1-second interval
- Use JSONPath extraction to update button titles dynamically

**Connection refused:**
- The Cearum service may have stopped: `sudo systemctl status cearum-web`
- Check logs: `sudo journalctl -u cearum-web -n 50`
