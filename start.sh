#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Cearum Web..."
IP=$(hostname -I | awk '{print $1}')
echo "Open http://${IP}:8888 in your browser"
echo ""
python3 main.py
