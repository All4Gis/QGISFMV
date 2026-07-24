#!/bin/bash

set -e

PLUGIN_NAME="QGISFMV"

resolve_plugin_dir() {
    local candidates=(
        "$HOME/Library/Application Support/QGIS/QGIS4/profiles/default/python/plugins/$PLUGIN_NAME"
        "${XDG_DATA_HOME:-$HOME/.local/share}/QGIS/QGIS4/profiles/default/python/plugins/$PLUGIN_NAME"
        "$HOME/.local/share/QGIS/QGIS3/profiles/default/python/plugins/$PLUGIN_NAME"
    )
    local path
    for path in "${candidates[@]}"; do
        if [ -e "$path" ] || [ -L "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

if ! PLUGIN_DIR="$(resolve_plugin_dir)"; then
    echo "Plugin not installed. Nothing to remove."
    exit 0
fi

if [ -L "$PLUGIN_DIR" ]; then
    rm "$PLUGIN_DIR"
    echo "Symlink removed: $PLUGIN_DIR"
elif [ -d "$PLUGIN_DIR" ]; then
    rm -rf "$PLUGIN_DIR"
    echo "Plugin directory removed: $PLUGIN_DIR"
fi

echo "Plugin uninstalled successfully."
