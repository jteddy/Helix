#!/bin/bash
# ============================================================
#  setup-autostart.sh
#  Installs Cearum Web as a systemd service on Xubuntu/Ubuntu
#  Run once as the user who will own the service:
#    chmod +x setup-autostart.sh
#    ./setup-autostart.sh
# ============================================================

set -e

# ── Detect install path ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"
PYTHON_BIN="$(which python3)"

echo "============================================"
echo "  Cearum Web — Autostart Setup"
echo "============================================"
echo "  Install path : $SCRIPT_DIR"
echo "  Running as   : $CURRENT_USER"
echo "  Python       : $PYTHON_BIN"
echo "============================================"
echo ""

# ── Install Python dependencies ──────────────────────────────
echo "[ 1/4 ] Installing Python dependencies..."
pip3 install --break-system-packages -r "$SCRIPT_DIR/requirements.txt"
echo "        Done."
echo ""

# ── Write systemd service file ────────────────────────────────
SERVICE_NAME="cearum-web"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "[ 2/4 ] Writing systemd service to $SERVICE_FILE ..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Cearum Web — Recoil Control Server
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_BIN} ${SCRIPT_DIR}/main.py
Restart=always
RestartSec=5

# Ensure USB devices are accessible
SupplementaryGroups=dialout plugdev

[Install]
WantedBy=multi-user.target
EOF
echo "        Done."
echo ""

# ── Enable and start ──────────────────────────────────────────
echo "[ 3/4 ] Enabling service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "        Done."
echo ""

echo "[ 4/4 ] Starting service now..."
sudo systemctl start "$SERVICE_NAME"
sleep 2

# ── Status check ──────────────────────────────────────────────
echo ""
echo "============================================"
STATUS=$(sudo systemctl is-active "$SERVICE_NAME" 2>/dev/null)
if [ "$STATUS" = "active" ]; then
    IP=$(hostname -I | awk '{print $1}')
    echo "  ✓  Service is RUNNING"
    echo ""
    echo "  Open in browser:"
    echo "    http://localhost:8000"
    echo "    http://${IP}:8000  (network / phone)"
else
    echo "  ✗  Service status: $STATUS"
    echo ""
    echo "  Check logs with:"
    echo "    sudo journalctl -u $SERVICE_NAME -n 50"
fi
echo "============================================"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status  $SERVICE_NAME"
echo "  sudo systemctl stop    $SERVICE_NAME"
echo "  sudo systemctl start   $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f   (live logs)"
echo ""
