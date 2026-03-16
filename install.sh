#!/bin/bash
echo "========================================"
echo "  Cearum Web — Setup"
echo "========================================"
echo ""

# Ensure pip is available
python3 -m ensurepip --upgrade 2>/dev/null || true

echo "Installing dependencies..."
pip3 install --break-system-packages -r requirements.txt

echo ""
echo "========================================"
echo "  Setup complete."
echo "  Run:  ./start.sh"
echo "========================================"
