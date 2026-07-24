#!/bin/bash

set -e

PLUGIN_NAME="QGISFMV"
PLUGIN_DISPLAY_NAME="QGIS FMV"

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_SOURCE="$REPO_ROOT/code"

# Detect QGIS profile path (macOS Application Support, then Linux XDG).
resolve_qgis_profile() {
    local candidates=(
        "$HOME/Library/Application Support/QGIS/QGIS4/profiles/default"
        "${XDG_DATA_HOME:-$HOME/.local/share}/QGIS/QGIS4/profiles/default"
        "$HOME/.local/share/QGIS/QGIS3/profiles/default"
    )
    local path
    for path in "${candidates[@]}"; do
        if [ -d "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

if ! QGIS_PROFILE="$(resolve_qgis_profile)"; then
    echo "Error: QGIS profile not found."
    echo "Looked for:"
    echo "  ~/Library/Application Support/QGIS/QGIS4/profiles/default  (macOS)"
    echo "  ~/.local/share/QGIS/QGIS4/profiles/default                 (Linux)"
    echo "Make sure QGIS 4 is installed and has been launched once."
    exit 1
fi

PLUGIN_DIR="$QGIS_PROFILE/python/plugins"

if [ ! -d "$PLUGIN_SOURCE" ]; then
    echo "Error: Plugin source not found at $PLUGIN_SOURCE"
    echo "Are you running this from the project root?"
    exit 1
fi

echo "======================================"
echo " $PLUGIN_DISPLAY_NAME DEV INSTALL"
echo "======================================"
echo "QGIS profile: $QGIS_PROFILE"

mkdir -p "$PLUGIN_DIR"

# Remove previous installation if it exists
if [ -L "$PLUGIN_DIR/$PLUGIN_NAME" ]; then
    rm "$PLUGIN_DIR/$PLUGIN_NAME"
elif [ -d "$PLUGIN_DIR/$PLUGIN_NAME" ]; then
    echo "Warning: Removing existing plugin directory"
    rm -rf "$PLUGIN_DIR/$PLUGIN_NAME"
fi

# Create symlink to /code
ln -s "$PLUGIN_SOURCE" "$PLUGIN_DIR/$PLUGIN_NAME"

# Remove legacy vendor / python_deps folders if present
if [ -L "$PLUGIN_SOURCE/vendor" ]; then
    rm "$PLUGIN_SOURCE/vendor"
fi
if [ -d "$PLUGIN_SOURCE/python_deps" ]; then
    echo "Removing legacy code/python_deps (deps now come from requirements.txt)..."
    rm -rf "$PLUGIN_SOURCE/python_deps"
fi

echo ""
echo "Installing Python dependencies from code/requirements.txt..."
bash "$REPO_ROOT/scripts/install_plugin_requirements.sh"

echo ""
echo "Plugin linked correctly:"
ls -l "$PLUGIN_DIR/$PLUGIN_NAME"

echo ""
echo "Dependencies: code/requirements.txt → ~/.qgis-fmv-packages (no sudo)"
echo "Dev tools:    pip install -r requirements-dev.txt  (outside QGIS)"
echo ""
echo "Now open QGIS and use Plugin Reloader"
echo ""
echo "Debug (same flow as LoadQSS):"
echo "  1. ./debug_qgis.sh"
echo "  2. Cursor → Run and Debug → 'Attach to QGIS (QGISFMV)'"
echo "  3. Reload plugin to hit breakpoints"
