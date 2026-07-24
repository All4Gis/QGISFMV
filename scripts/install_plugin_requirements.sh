#!/bin/bash
# Install runtime plugin dependencies from code/requirements.txt.
#
# Never requires sudo / write access to QGIS.app.
# Packages go to ~/.qgis-fmv-packages (added to sys.path by the plugin bootstrap).
#
# Includes: pymisb, matplotlib, opencv-contrib-python
# On signed macOS QGIS, OpenCV native wheels may still fail to load (code signing);
# the plugin then falls back to numpy tracking.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REQ_FILE="$REPO_ROOT/code/requirements.txt"
FMV_PKGS="${QGIS_FMV_PACKAGES:-$HOME/.qgis-fmv-packages}"

if [ ! -f "$REQ_FILE" ]; then
    echo "Error: requirements file not found at $REQ_FILE"
    exit 1
fi

resolve_python() {
    if [ -n "${QGIS_PY:-}" ] && [ -x "$QGIS_PY" ]; then
        echo "$QGIS_PY"
        return 0
    fi
    local candidate
    if [ "$(uname -s)" = "Darwin" ]; then
        local app="${QGIS_APP:-/Applications/QGIS.app}"
        for candidate in \
            "$app/Contents/MacOS/python" \
            "$app/Contents/MacOS/bin/python3" \
            "$app/Contents/Resources/python/bin/python3" \
            "$app/Contents/MacOS/python3.12" \
            "$app/Contents/MacOS/bin/python3.12" \
            "$app/Contents/MacOS/python3"; do
            if [ -x "$candidate" ]; then
                echo "$candidate"
                return 0
            fi
        done
    fi
    # Linux: prefer QGIS-adjacent interpreters, then system python3.
    for candidate in \
        /usr/bin/python3.12 \
        /usr/bin/python3.11 \
        /usr/bin/python3.10 \
        /usr/bin/python3 \
        /usr/local/bin/python3 \
        /usr/lib/qgis/python3 \
        /usr/libexec/qgis/python3; do
        if [ -x "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi
    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi
    return 1
}

ensure_pip() {
    local py="$1"
    export PYTHONNOUSERSITE=1
    export PYTHONPATH="$FMV_PKGS${PYTHONPATH:+:$PYTHONPATH}"

    if "$py" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    echo "pip not found — bootstrapping into $FMV_PKGS (no sudo)..."
    mkdir -p "$FMV_PKGS"

    # Prefer ensurepip only if it can write somewhere useful; usually fails on
    # read-only QGIS.app — then use get-pip --target.
    "$py" -m ensurepip --upgrade >/dev/null 2>&1 || true
    if "$py" -m pip --version >/dev/null 2>&1; then
        return 0
    fi

    local get_pip
    get_pip="$(mktemp -t qgis_fmv_get_pip.XXXXXX.py)"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$get_pip"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$get_pip" https://bootstrap.pypa.io/get-pip.py
    else
        echo "ERROR: need curl or wget to bootstrap pip"
        rm -f "$get_pip"
        return 1
    fi

    if ! "$py" "$get_pip" --target="$FMV_PKGS" --no-warn-script-location; then
        rm -f "$get_pip"
        return 1
    fi
    rm -f "$get_pip"
    "$py" -m pip --version >/dev/null 2>&1
}

pip_install_target() {
    local py="$1"
    shift
    local extra=()
    if "$py" -m pip install --help 2>/dev/null | grep -q break-system-packages; then
        extra+=(--break-system-packages)
    fi
    PYTHONNOUSERSITE=1 PYTHONPATH="$FMV_PKGS${PYTHONPATH:+:$PYTHONPATH}" \
        "$py" -m pip install --target="$FMV_PKGS" "$@" "${extra[@]}"
}

if ! PY="$(resolve_python)"; then
    echo "Error: could not find a Python interpreter (set QGIS_PY)."
    exit 1
fi

echo "======================================"
echo " QGIS FMV — install requirements"
echo "======================================"
echo "Requirements: $REQ_FILE"
echo "Python:       $PY"
echo "Target:       $FMV_PKGS  (no sudo / no write to QGIS.app)"
echo ""

mkdir -p "$FMV_PKGS"
export PYTHONNOUSERSITE=1
export PYTHONPATH="$FMV_PKGS${PYTHONPATH:+:$PYTHONPATH}"

if ! ensure_pip "$PY"; then
    echo ""
    echo "ERROR: could not bootstrap pip without admin rights."
    echo "Install pip for your user Python, or set QGIS_PY to an interpreter that has pip."
    exit 1
fi

echo "Upgrading pip tooling into $FMV_PKGS..."
pip_install_target "$PY" --upgrade pip setuptools wheel 2>/dev/null || true

echo ""
echo "Installing pymisb, matplotlib, OpenCV into $FMV_PKGS..."
if ! pip_install_target "$PY" -r "$REQ_FILE"; then
    echo ""
    echo "ERROR: pip install failed."
    echo "Manual (no sudo):"
    echo "  mkdir -p \"$FMV_PKGS\""
    echo "  PYTHONNOUSERSITE=1 \"$PY\" -m pip install --target=\"$FMV_PKGS\" -r \"$REQ_FILE\""
    exit 1
fi

echo ""
echo "Verifying imports..."
Pymisb_OK=0
CV2_OK=0
if PYTHONNOUSERSITE=1 PYTHONPATH="$FMV_PKGS" "$PY" -c "import pymisb" 2>/dev/null; then
    echo "  pymisb: OK"
    Pymisb_OK=1
else
    echo "  pymisb: FAILED"
fi

if ver="$(PYTHONNOUSERSITE=1 PYTHONPATH="$FMV_PKGS" "$PY" -c "import cv2; print(cv2.__version__)" 2>/dev/null)"; then
    echo "  OpenCV: OK ($ver)"
    CV2_OK=1
else
    echo "  OpenCV: not importable here (optional)"
    echo "  The plugin will use numpy tracking fallback when OpenCV cannot load."
fi

if [ "$Pymisb_OK" -ne 1 ]; then
    echo ""
    echo "ERROR: pymisb is required and failed to import."
    exit 1
fi

echo ""
echo "Done. Packages are in: $FMV_PKGS"
echo "Reload the QGIS FMV plugin (or restart QGIS)."
if [ "$CV2_OK" -ne 1 ]; then
    exit 0
fi
exit 0
