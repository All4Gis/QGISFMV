#!/usr/bin/env python3
"""Build script for QGIS FMV plugin.

Translations for PyQt6 (QGIS 4.0+).
Run from the repo root (outside QGIS):

    python3 build.py

Requires: pip install PyQt6 PySide6
 
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CODE_DIR = ROOT_DIR / "code"
I18N_DIR = CODE_DIR / "i18n"

def _script_search_dirs():
    """Directories where pip installs console scripts (often not on PATH)."""
    dirs = []
    exe = Path(sys.executable).resolve()
    dirs.append(exe.parent)
    dirs.append(exe.parent.parent / "bin")

    try:
        import site

        if sys.platform == "win32":
            dirs.append(Path(site.USER_BASE) / "Scripts")
        else:
            dirs.append(Path(site.getuserbase()) / "bin")
            dirs.append(Path.home() / ".local" / "bin")
            ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            dirs.append(Path.home() / "Library" / "Python" / ver / "bin")
    except Exception:
        pass

    seen = set()
    for d in dirs:
        key = str(d)
        if key not in seen:
            seen.add(key)
            yield d


def find_tool(*names):
    """Locate a Qt build tool by name across PATH and pip script folders."""
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    for name in names:
        for folder in _script_search_dirs():
            for candidate in (folder / name, folder / f"{name}.exe"):
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)
    return None


def run_cmd(cmd, description):
    """Run a command and handle errors."""
    print(f"  {description}...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        print(f"  Error: {err}")
        return False
    return True


def _pyuic_cmd():
    """Return argv prefix to compile .ui files (pyuic6 binary or python -m)."""
    pyuic = find_tool("pyuic6")
    if pyuic:
        return [pyuic]
    try:
        import PyQt6.uic  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "PyQt6 is required. Install with: pip install PyQt6"
        ) from exc
    return [sys.executable, "-m", "PyQt6.uic.pyuic"]

def _lrelease_cmd():
    """Return argv prefix for .ts -> .qm compilation, or None if unavailable."""
    return find_tool("lrelease", "pyside6-lrelease", "lrelease-qt6")


def compile_translations():
    """Compile .ts translation files to .qm using lrelease."""
    print("\n[3/3] Compiling translations...")

    lrelease = _lrelease_cmd()
    if lrelease is None:
        print("  Warning: lrelease not found, skipping translations.")
        print("  Install with: pip install PySide6")
        return True

    pro_path = I18N_DIR / "qgisfmv.pro"
    ts_files = []
    if pro_path.exists():
        in_translations = False
        for line in pro_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("TRANSLATIONS"):
                in_translations = True
                parts = stripped.split("=", 1)
                if len(parts) > 1:
                    for f in parts[1].split():
                        f = f.rstrip("\\").strip()
                        if f:
                            ts_files.append(I18N_DIR / f)
                continue
            if in_translations:
                if stripped.startswith("#") or "=" in stripped:
                    in_translations = False
                    continue
                for f in stripped.split():
                    f = f.rstrip("\\").strip()
                    if f:
                        ts_files.append(I18N_DIR / f)

    if not ts_files:
        ts_files = list(I18N_DIR.glob("*.ts"))

    if not ts_files:
        print("  No .ts translation files found, skipping.")
        return True

    success = True
    for ts_path in ts_files:
        if not ts_path.exists():
            print(f"  Warning: {ts_path.name} not found, skipping.")
            continue
        qm_path = ts_path.with_suffix(".qm")
        cmd = [
            lrelease,
            str(ts_path),
            "-qm",
            str(qm_path),
            "-compress",
            "-removeidentical",
        ]
        if not run_cmd(cmd, f"  {ts_path.name} -> {qm_path.name}"):
            success = False
    return success


def check_dependencies():
    """Check if required tools are installed."""
    print("Checking dependencies...")

    try:
        pyuic = _pyuic_cmd()
        label = pyuic[0] if len(pyuic) == 1 else " ".join(pyuic[1:3])
        print(f"  pyuic6: OK ({label})")
    except RuntimeError as exc:
        print(f"Missing: {exc}")
        return False

    lrelease = _lrelease_cmd()
    if lrelease:
        print(f"  lrelease: OK ({lrelease})")
    else:
        print("  lrelease: not found (translations will be skipped)")

    return True


def main():
    """Main build function."""
    print("=" * 50)
    print("QGIS FMV Build")
    print("=" * 50)

    if not check_dependencies():
        sys.exit(1)

    if not compile_translations():
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Build completed successfully!")
    print("=" * 50)


if __name__ == "__main__":
    main()
