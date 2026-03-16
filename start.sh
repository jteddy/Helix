#!/bin/bash
IP=$(hostname -I | awk '{print $1}')
echo "========================================"
echo "  Cearum Web"
echo "  http://localhost:8000"
echo "  http://${IP}:8000  (network)"
echo "  Ctrl+C to stop"
echo "========================================"
echo ""
python3 main.py
