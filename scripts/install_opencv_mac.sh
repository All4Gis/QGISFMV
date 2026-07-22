#!/bin/bash
# Deprecated: use scripts/install_plugin_requirements.sh (installs full requirements.txt).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Note: install_opencv_mac.sh is deprecated."
echo "Running scripts/install_plugin_requirements.sh instead..."
exec bash "$SCRIPT_DIR/install_plugin_requirements.sh"
