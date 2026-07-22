#!/usr/bin/env python3
# coding: utf-8
"""Build script for QGIS FMV plugin.

Compiles UI files, resources, and translations for PyQt6 (QGIS 4.0+).
Run from the repo root (outside QGIS):

    python3 build.py

Requires: pip install PyQt6 PySide6

After ``pyuic6``, generated files are patched for QGIS / PyQt6:
- imports → ``qgis.PyQt``
- ``Qt.DockWidgetClosable`` → ``QDockWidget.DockWidgetFeature.*``
- ``QToolButton.addSeparator()`` → explicit ``QMenu`` (ToolButtons have no separators)
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
CODE_DIR = ROOT_DIR / "code"
UI_DIR = CODE_DIR / "ui"
GUI_DIR = CODE_DIR / "gui"
I18N_DIR = CODE_DIR / "i18n"

UI_FILES = [
    "ui_FmvAlertRule.ui",
    "ui_FmvBrightnessContrast.ui",
    "ui_FmvVideoInfo.ui",
    "ui_FmvTableProgress.ui",
    "ui_FmvAbout.ui",
    "ui_FmvSettings.ui",
    "ui_FmvManager.ui",
    "ui_FmvMetadata.ui",
    "ui_FmvMilitarySymbols.ui",
    "ui_FmvMultiplexer.ui",
    "ui_FmvOpenStream.ui",
    "ui_FmvPlayer.ui",
]


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


def _rcc_cmd():
    """Return argv prefix for resources.qrc compilation, or None if unavailable."""
    rcc = find_tool("rcc", "pyrcc6", "pyside6-rcc")
    if rcc:
        return [rcc]
    try:
        import PySide6  # noqa: F401

        rcc_path = Path(PySide6.__file__).resolve().parent / "rcc.exe"
        if rcc_path.is_file():
            return [str(rcc_path)]
    except ImportError:
        pass
    return None


def _lrelease_cmd():
    """Return argv prefix for .ts -> .qm compilation, or None if unavailable."""
    return find_tool("lrelease", "pyside6-lrelease", "lrelease-qt6")


def _patch_qgis_pyqt_imports(content):
    """Rewrite generated PyQt6/PySide6 imports to ``qgis.PyQt`` for QGIS runtime."""
    for old, new in (
        (
            "from PyQt6 import QtCore, QtGui, QtWidgets",
            "from qgis.PyQt import QtCore, QtGui, QtWidgets",
        ),
        (
            "from PySide6 import QtCore, QtGui, QtWidgets",
            "from qgis.PyQt import QtCore, QtGui, QtWidgets",
        ),
        ("from PyQt6 import QtCore", "from qgis.PyQt import QtCore"),
        ("from PySide6 import QtCore", "from qgis.PyQt import QtCore"),
        ("import PySide6.QtCore as QtCore", "from qgis.PyQt import QtCore"),
        ("from qgscolorbutton import QgsColorButton", "from qgis.gui import QgsColorButton"),
    ):
        content = content.replace(old, new)
    return content


def _patch_dockwidget_features(content):
    """Fix pyuic6 emitting ``Qt.DockWidgetClosable`` (invalid in PyQt6)."""

    def _repl(match):
        target = match.group(1)
        inner = match.group(2)
        parts = []
        for part in inner.split("|"):
            token = part.strip()
            name = token.replace("QtCore.Qt.", "").replace("Qt.", "")
            if name.startswith("DockWidget") and not name.startswith(
                "QtWidgets.QDockWidget"
            ):
                parts.append(f"QtWidgets.QDockWidget.DockWidgetFeature.{name}")
            else:
                parts.append(token)
        joined = "\n            | ".join(parts)
        return f"{target}.setFeatures(\n            {joined}\n        )"

    return re.sub(
        r"(\w+)\.setFeatures\(((?:[^)]*Qt(?:Core)?\.Qt\.DockWidget\w+[^)]*))\)",
        _repl,
        content,
    )


def _patch_toolbutton_separators(content):
    """Rewrite ``QToolButton.addSeparator()`` blocks into an explicit ``QMenu``.

    ``pyuic6`` emits ``toolBtn.addSeparator()`` for ``<addaction name="separator"/>``
    on QToolButtons, but only QMenu / QToolBar support separators.
    """
    buttons = sorted(set(re.findall(r"self\.(toolBtn_\w+)\.addSeparator\(\)", content)))
    for btn in buttons:
        menu_attr = f"self._{btn}_menu"
        pattern = re.compile(
            rf"((?:        self\.{re.escape(btn)}\."
            rf"(?:addAction\([^)]+\)|addSeparator\(\))\n)+)"
        )

        def _repl_block(match, _btn=btn, _menu=menu_attr):
            block = match.group(1)
            lines = [f"        {_menu} = QtWidgets.QMenu(parent=self.{_btn})\n"]
            for line in block.splitlines(True):
                lines.append(line.replace(f"self.{_btn}.", f"{_menu}.", 1))
            lines.append(f"        self.{_btn}.setMenu({_menu})\n")
            return "".join(lines)

        content, n = pattern.subn(_repl_block, content)
        if n:
            print(f"    patched {btn}.addSeparator() → QMenu ({n} block(s))")
    return content


def _patch_player_draw_toolbar(content):
    """pyuic6 omits QToolBar.addWidget for child QToolButtons — inject explicitly."""
    if "class Ui_PlayerWindow" not in content:
        return content
    if "DrawToolBar.addWidget(self.toolBtn_DPolygon)" in content:
        return content

    replacements = (
        (
            "        self.toolBtn_DLine.addAction(self.actionRemove_All_Line)\n"
            "        self.DrawToolBar.addAction(self.actionMilitary_Symbols)\n",
            "        self.toolBtn_DLine.addAction(self.actionRemove_All_Line)\n"
            "        self.DrawToolBar.addWidget(self.toolBtn_DPolygon)\n"
            "        self.DrawToolBar.addWidget(self.toolBtn_DPoint)\n"
            "        self.DrawToolBar.addWidget(self.toolBtn_DLine)\n"
            "        self.DrawToolBar.addAction(self.actionMilitary_Symbols)\n",
        ),
        (
            "        self.toolBtn_Measure.setMenu(self._toolBtn_Measure_menu)\n"
            "        self.DrawToolBar.addSeparator()\n",
            "        self.toolBtn_Measure.setMenu(self._toolBtn_Measure_menu)\n"
            "        self.DrawToolBar.addWidget(self.toolBtn_Measure)\n"
            "        self.DrawToolBar.addSeparator()\n",
        ),
        (
            "        self.toolBtn_Cesure.addAction(self.actionRemove_All_censured)\n"
            "        self.DrawToolBar.addSeparator()\n",
            "        self.toolBtn_Cesure.addAction(self.actionRemove_All_censured)\n"
            "        self.DrawToolBar.addWidget(self.toolBtn_Cesure)\n"
            "        self.DrawToolBar.addSeparator()\n",
        ),
    )
    updated = content
    for old, new in replacements:
        if old not in updated:
            return content
        updated = updated.replace(old, new, 1)
    if updated != content:
        print("    patched DrawToolBar.addWidget for QToolButtons")
    return updated


def _patch_generated_ui(py_path):
    """Apply all post-pyuic fixes required for QGIS 4 / PyQt6."""
    original = py_path.read_text(encoding="utf-8")
    content = original
    content = _patch_qgis_pyqt_imports(content)
    content = _patch_dockwidget_features(content)
    content = _patch_toolbutton_separators(content)
    content = _patch_player_draw_toolbar(content)
    if content != original:
        py_path.write_text(content, encoding="utf-8")
        print(f"    patched {py_path.name} for QGIS/PyQt6")


def _ensure_gui_package():
    """Make sure ``code/gui`` exists as an importable package after a clean wipe."""
    GUI_DIR.mkdir(parents=True, exist_ok=True)
    init_py = GUI_DIR / "__init__.py"
    if not init_py.exists():
        init_py.write_text(
            '# -*- coding: utf-8 -*-\n'
            '"""Generated UI modules and Qt resources '
            '(produced by ``python3 build.py``)."""\n',
            encoding="utf-8",
        )
        print(f"  created {init_py.relative_to(ROOT_DIR)}")


def compile_ui_files():
    """Compile .ui files to .py using pyuic6."""
    print("\n[1/3] Compiling UI files...")
    try:
        pyuic = _pyuic_cmd()
    except RuntimeError as exc:
        print(f"  Error: {exc}")
        return False

    _ensure_gui_package()

    for ui_file in UI_FILES:
        ui_path = UI_DIR / ui_file
        py_name = ui_file.replace(".ui", ".py")
        py_path = GUI_DIR / py_name
        cmd = [*pyuic, str(ui_path), "-o", str(py_path)]
        if not run_cmd(cmd, f"  {ui_file} -> {py_name}"):
            return False
        _patch_generated_ui(py_path)
    return True


def compile_resources():
    """Compile .qrc resources to .py using rcc/pyrcc6/pyside6-rcc."""
    print("\n[2/3] Compiling resources...")

    rcc = _rcc_cmd()
    if rcc is None:
        print("  Warning: rcc not found, skipping resource compilation.")
        print("  Install with: pip install PySide6")
        return True

    qrc_path = UI_DIR / "resources.qrc"
    py_path = GUI_DIR / "resources_rc.py"
    print(f"  resources.qrc -> resources_rc.py ({rcc[0]})")

    cmd = [*rcc, "-g", "python", str(qrc_path), "-o", str(py_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "").strip()
        print(f"  Error: {err}")
        return False

    # pyside6-rcc emits PySide6 imports; QGIS runtime needs qgis.PyQt.
    content = py_path.read_text(encoding="utf-8")
    patched = _patch_qgis_pyqt_imports(content)
    if patched != content:
        py_path.write_text(patched, encoding="utf-8")
    print("  Patched resources_rc.py imports → qgis.PyQt (not PySide6)")
    return True


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

    if not (UI_DIR / "resources.qrc").exists():
        print(f"Missing: {UI_DIR / 'resources.qrc'}")
        return False

    try:
        pyuic = _pyuic_cmd()
        label = pyuic[0] if len(pyuic) == 1 else " ".join(pyuic[1:3])
        print(f"  pyuic6: OK ({label})")
    except RuntimeError as exc:
        print(f"Missing: {exc}")
        return False

    rcc = _rcc_cmd()
    if rcc:
        print(f"  rcc: OK ({rcc[0]})")
    else:
        print("  rcc: not found (resources will not be compiled)")

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

    if not compile_ui_files():
        sys.exit(1)

    if not compile_resources():
        sys.exit(1)

    if not compile_translations():
        sys.exit(1)

    print("\n" + "=" * 50)
    print("Build completed successfully!")
    print("=" * 50)


if __name__ == "__main__":
    main()
