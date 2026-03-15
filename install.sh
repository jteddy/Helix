#!/bin/bash
echo "================================"
echo " Cearum Web - Setup"
echo "================================"
echo ""

pip3 install -r requirements.txt

echo ""
echo "NOTE: On Linux, ensure your user can access the serial port:"
echo "  sudo usermod -a -G dialout \$USER"
echo "  Then log out and back in."
echo ""
echo "================================"
echo " Done. Run ./start.sh to launch."
echo "================================"
