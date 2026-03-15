# cearum-web

Web-based frontend for Cearum recoil compensation. Runs as a local server on Windows or Linux/Raspberry Pi — control from any browser on your network.

## Architecture

```
Browser (any device on network)
        ↕  HTTP REST + WebSocket
FastAPI Backend  (this server)
        ↕  USB/Serial
    MAKCU device
```

The recoil loop runs as a background thread with zero web latency — the browser only handles configuration. The loop timing is identical to the desktop Cearum app.

## Quick Start (Windows)

```
install.bat
start.bat
```
Open `http://localhost:8000`

## Quick Start (Linux / Raspberry Pi)

```bash
# One-time: add user to serial port group
sudo usermod -a -G dialout $USER
# Log out and back in

chmod +x install.sh start.sh
./install.sh
./start.sh
```
Open `http://<device-ip>:8000` from any device on your network.

## Project Structure

```
cearum-web/
├── main.py               ← FastAPI app, startup sequence
├── core/
│   ├── state.py          ← shared state (recoil settings + MAKCU status)
│   ├── makcu_device.py   ← MAKCU connection and movement
│   └── recoil_loop.py    ← compensation loop (runs in background thread)
├── api/
│   ├── config.py         ← REST: read/write recoil settings
│   ├── patterns.py       ← REST: vector (pattern) CRUD
│   └── status.py         ← WebSocket: live MAKCU + recoil status
├── frontend/
│   └── static/
│       └── index.html    ← control panel + vector editor
├── patterns/             ← vector .txt files
│   └── cs2/
│       └── ak47.txt
└── requirements.txt
```

## API Reference

### Config
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get all settings |
| PATCH | `/api/config` | Update settings |
| POST | `/api/config/enable` | Enable recoil |
| POST | `/api/config/disable` | Disable recoil |
| POST | `/api/config/toggle` | Toggle recoil |

### Patterns (Vectors)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patterns` | List all patterns |
| GET | `/api/patterns/{game}/{weapon}` | Get pattern text |
| POST | `/api/patterns/{game}/{weapon}` | Save pattern |
| POST | `/api/patterns/{game}/{weapon}/activate` | Load into recoil loop |
| DELETE | `/api/patterns/{game}/{weapon}` | Delete pattern |

### Status
| Type | Endpoint | Description |
|------|----------|-------------|
| WebSocket | `/ws/status` | Live status updates every 250ms |

## Linux systemd (auto-start on boot)

Create `/etc/systemd/system/cearum-web.service`:
```ini
[Unit]
Description=Cearum Web
After=network.target

[Service]
WorkingDirectory=/home/pi/cearum-web
ExecStart=/usr/bin/python3 main.py
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable cearum-web
sudo systemctl start cearum-web
sudo systemctl status cearum-web
```
