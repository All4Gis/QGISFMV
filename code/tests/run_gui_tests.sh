#!/bin/bash
# Run GUI / visual tests inside QGIS.
# Usage: ./run_gui_tests.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"

# Find QGIS binary
QGIS_BIN="/Applications/QGIS.app/Contents/MacOS/QGIS-final-4_0_0"
if [ ! -f "$QGIS_BIN" ]; then
    QGIS_BIN="$(which qgis 2>/dev/null || echo '')"
fi

if [ -z "$QGIS_BIN" ] || [ ! -f "$QGIS_BIN" ]; then
    echo "ERROR: QGIS not found. Install QGIS or set QGIS_BIN."
    exit 1
fi

echo "Using QGIS: $QGIS_BIN"
echo "Plugin dir: $PLUGIN_DIR"

# Run the GUI test runner inside QGIS's Python
"$QGIS_BIN" --code "
import sys
sys.path.insert(0, '$PLUGIN_DIR')
from QGISFMV.tests.run_gui_tests import run_all
success = run_all()
import sys
sys.exit(0 if success else 1)
"
