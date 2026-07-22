#!/bin/bash
# Same debug flow as LoadQSS: FRAN_DEBUG=1 + debugpy in QGIS profile + attach in Cursor.
set -e

export FRAN_DEBUG=1

ROOT="$(cd "$(dirname "$0")" && pwd)"
QGIS_PROFILE="$HOME/Library/Application Support/QGIS/QGIS4/profiles/default"
QGIS_PYTHON_DIR="$QGIS_PROFILE/python"
QGIS_BIN="${QGIS_BIN:-/Applications/QGIS.app/Contents/MacOS/QGIS-final-4_0_0}"

# Ensure plugin symlink (same as LoadQSS install_dev.sh layout)
PLUGIN_DIR="$QGIS_PROFILE/python/plugins"
if [ ! -e "$PLUGIN_DIR/QGISFMV" ]; then
    echo "Plugin not linked — running install_dev.sh first..."
    bash "$ROOT/install_dev.sh"
fi

if [ ! -d "$QGIS_PYTHON_DIR/debugpy" ]; then
    echo "Installing debugpy into QGIS profile..."
    pip3 install --target="$QGIS_PYTHON_DIR" debugpy 2>/dev/null || {
        echo "Error: Could not install debugpy"
        echo "Run manually: pip3 install --target=\"$QGIS_PYTHON_DIR\" debugpy"
        exit 1
    }
fi

if [ ! -x "$QGIS_BIN" ]; then
    echo "Error: QGIS binary not found at $QGIS_BIN"
    echo "Set QGIS_BIN if your build uses another name."
    exit 1
fi

echo "======================================"
echo " QGISFMV DEBUG MODE"
echo "======================================"
echo ""
echo "Starting QGIS with debug mode..."
echo "Cursor: Run and Debug → 'Attach to QGIS (QGISFMV)'"
echo ""

exec "$QGIS_BIN"
