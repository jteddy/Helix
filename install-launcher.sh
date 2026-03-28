#!/bin/bash
# ============================================================
#  install-launcher.sh
#  Installs the Helix Launcher into your applications menu
#  and creates a desktop shortcut.
#
#  Run once:
#    chmod +x install-launcher.sh
#    ./install-launcher.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$(which python3)"
ICON_SRC="$SCRIPT_DIR/icons/helix.svg"
ICON_DEST="$HOME/.local/share/icons/hicolor/scalable/apps/helix.svg"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/helix-launcher.desktop"

echo "============================================"
echo "  Helix Launcher — Desktop Install"
echo "============================================"
echo ""

# ── PyQt6 ─────────────────────────────────────────────────────────────────────
echo "[ 1/3 ] Installing PyQt6..."
pip3 install --break-system-packages PyQt6
echo "        Done."
echo ""

# ── Icon ──────────────────────────────────────────────────────────────────────
echo "[ 2/3 ] Installing icon..."
mkdir -p "$(dirname "$ICON_DEST")"
cp "$ICON_SRC" "$ICON_DEST"
# Refresh icon cache if gtk-update-icon-cache is available
if command -v gtk-update-icon-cache &> /dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi
echo "        Installed to $ICON_DEST"
echo ""

# ── .desktop file ─────────────────────────────────────────────────────────────
echo "[ 3/3 ] Creating application menu entry..."
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Helix Launcher
Comment=Helix recoil server control panel
Exec=${PYTHON_BIN} ${SCRIPT_DIR}/launcher.py
Icon=helix
Terminal=false
Categories=Utility;
Keywords=helix;recoil;launcher;server;
StartupWMClass=helix-launcher
EOF
chmod +x "$DESKTOP_FILE"

# Also place a copy on the Desktop if it exists
if [ -d "$HOME/Desktop" ]; then
    cp "$DESKTOP_FILE" "$HOME/Desktop/helix-launcher.desktop"
    chmod +x "$HOME/Desktop/helix-launcher.desktop"
    echo "        Shortcut placed on Desktop."
fi

echo "        Entry: $DESKTOP_FILE"
echo ""

echo "============================================"
echo "  Done — search for 'Helix Launcher' in"
echo "  your applications menu, or run:"
echo ""
echo "    python3 $SCRIPT_DIR/launcher.py"
echo "============================================"
echo ""
