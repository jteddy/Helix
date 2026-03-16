# Stream Deck Setup for Cearum Web

The Stream Deck runs on your **gaming PC (Windows)** and talks to the Cearum server over your LAN via HTTP.

---

## Plugin to Install

From the Stream Deck Store, install:

> **Web Requests** by Adrián — Free

Search "http request" in the store and it will appear in the results.

---

## Your Server Address

Replace `CEARUM_IP` in all examples below with your server's actual IP address, e.g. `192.168.1.50`.

Find it on the **Settings tab** of the Cearum web UI, or run on the server:
```bash
hostname -I
```

---

## Button Setup (Web Requests plugin)

Each button uses the **Web Requests** action. The fields you fill in are:

| Field | Notes |
|-------|-------|
| **URL** | Full address including port 8000 |
| **Method** | GET or POST depending on the button |
| **Body** | Leave empty for toggle/cycle actions |

---

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

```
Method : POST
URL    : http://CEARUM_IP:8000/api/scripts/cycle
Body   : (empty)
Title  : Cycle Script
```

---

### Button 4 — Load a Specific Script

```
Method : POST
URL    : http://CEARUM_IP:8000/api/scripts/load/ak47
Body   : (empty)
Title  : AK-47
```

Replace `ak47` with the exact script name (no `.txt` extension, case-sensitive).

---

### Button 5 — Check Status (MAKCU / Recoil state)

```
Method : GET
URL    : http://CEARUM_IP:8000/api/streamdeck
Body   : (empty)
Title  : Status
```

The response is JSON — Web Requests can display it as the button title:
```json
{
  "recoil":     true,
  "flashlight": false,
  "makcu":      true,
  "script":     "ak47"
}
```

If Web Requests supports a title template, use `{recoil}` to show ON/OFF on the button face.

---

## Recommended Layout (5-button row)

```
┌──────────┬──────────┬──────────┬──────────┬──────────┐
│  RECOIL  │  FLASH   │  CYCLE   │  AK-47   │  STATUS  │
│  TOGGLE  │  TOGGLE  │  SCRIPT  │  (load)  │  (poll)  │
└──────────┴──────────┴──────────┴──────────┴──────────┘
```

---

## Troubleshooting

**Button does nothing / times out:**
- Confirm the Cearum server is running — open `http://CEARUM_IP:8000` in a browser on the gaming PC
- Check Windows Firewall isn't blocking outbound connections on port 8000
- Make sure gaming PC and Cearum server are on the same LAN

**Wrong IP:**
- The server IP can change on DHCP. Consider assigning a static IP to the Cearum server in your router settings, or use its hostname if your router supports it.

**Server stopped:**
- On the Cearum server: `sudo systemctl restart cearum-web`
- Check logs: `sudo journalctl -u cearum-web -n 50`
