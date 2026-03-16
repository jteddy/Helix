#!/bin/bash
echo "========================================"
echo "  Cearum Web — Setup"
echo "========================================"
echo ""

CURRENT_USER="$(whoami)"

# ── Python dependencies ───────────────────────────────────────────
echo "[ 1/3 ] Installing Python dependencies..."
python3 -m ensurepip --upgrade 2>/dev/null || true
pip3 install --break-system-packages -r requirements.txt
echo "        Done."
echo ""

# ── USB permissions ───────────────────────────────────────────────
echo "[ 2/3 ] Adding $CURRENT_USER to USB device groups..."
sudo usermod -aG plugdev "$CURRENT_USER"
sudo usermod -aG dialout "$CURRENT_USER"
echo "        Done."
echo ""

# ── udev rule for MAKCU HID access ───────────────────────────────
echo "[ 3/3 ] Writing udev rule for HID devices..."
sudo tee /etc/udev/rules.d/99-makcu.rules > /dev/null <<'EOF'
# MAKCU — allow all users to access HID devices without root
SUBSYSTEM=="hidraw", MODE="0666"
SUBSYSTEM=="usb", ATTRS{bInterfaceClass}=="03", MODE="0666"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
echo "        Done."
echo ""

echo "========================================"
echo "  Setup complete."
echo ""
echo "  IMPORTANT: Log out and back in (or"
echo "  reboot) for group changes to take effect."
echo ""
echo "  Then run:  ./start.sh"
echo "========================================"
