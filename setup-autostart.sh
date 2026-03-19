#!/bin/bash
# ============================================================
#  setup-autostart.sh
#  Installs Helix as a systemd service on Xubuntu/Ubuntu
#  Also fixes USB/HID permissions for the MAKCU device.
#  Run once:
#    chmod +x setup-autostart.sh
#    ./setup-autostart.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"
PYTHON_BIN="$(which python3)"

echo "============================================"
echo "  Helix — Autostart Setup"
echo "============================================"
echo "  Install path : $SCRIPT_DIR"
echo "  Running as   : $CURRENT_USER"
echo "  Python       : $PYTHON_BIN"
echo "============================================"
echo ""

# ── 1. Python dependencies ────────────────────────────────────
echo "[ 1/5 ] Installing Python dependencies..."
pip3 install --break-system-packages -r "$SCRIPT_DIR/requirements.txt"
echo "        Done."
echo ""

# ── 2. USB group membership ───────────────────────────────────
echo "[ 2/5 ] Adding $CURRENT_USER to USB device groups (plugdev, dialout)..."
sudo usermod -aG plugdev "$CURRENT_USER"
sudo usermod -aG dialout "$CURRENT_USER"
echo "        Done."
echo ""

# ── 3. udev rule — MAKCU HID access without root ─────────────
echo "[ 3/5 ] Writing udev rule for HID/USB access..."
sudo tee /etc/udev/rules.d/99-makcu.rules > /dev/null <<'EOF'
# MAKCU — allow all users to access HID devices without root
SUBSYSTEM=="hidraw", MODE="0666"
SUBSYSTEM=="usb", ATTRS{bInterfaceClass}=="03", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "        Done."
echo ""

# ── 4. systemd service ────────────────────────────────────────
SERVICE_NAME="helix"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "[ 4/5 ] Writing systemd service to $SERVICE_FILE ..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Helix — Recoil Control Server
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_BIN} ${SCRIPT_DIR}/main.py
Restart=always
RestartSec=5
SupplementaryGroups=dialout plugdev

[Install]
WantedBy=multi-user.target
EOF
echo "        Done."
echo ""

# ── 5. Enable and start ───────────────────────────────────────
echo "[ 5/5 ] Enabling and starting service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"
sleep 2
echo "        Done."
echo ""

# ── Status ────────────────────────────────────────────────────
echo "============================================"
STATUS=$(sudo systemctl is-active "$SERVICE_NAME" 2>/dev/null)
if [ "$STATUS" = "active" ]; then
    IP=$(hostname -I | awk '{print $1}')
    echo "  Service is RUNNING"
    echo ""
    echo "  Open in browser:"
    echo "    http://localhost:8000"
    echo "    http://${IP}:8000  (network / phone)"
else
    echo "  Service status: $STATUS"
    echo "  Check logs: sudo journalctl -u $SERVICE_NAME -n 50"
fi
echo ""
echo "  *** IMPORTANT: Log out and back in (or reboot)"
echo "  *** for group membership changes to take effect."
echo "============================================"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status  $SERVICE_NAME"
echo "  sudo systemctl restart $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo ""
