# -*- coding: utf-8 -*-
"""
GUI / Visual testing harness for QGIS FMV.

Starts a headless QGIS instance, boots the plugin, and exposes helpers
for clicking buttons, opening dialogs, capturing screenshots, and comparing
them against baseline images.

Usage (from the QGIS Python console or via ``qgis --code``)::

    from QGISFMV.tests.gui_test_harness import GUITestHarness
    harness = GUITestHarness()
    harness.start()
    harness.click("actionPlay")
    harness.screenshot("after_play")
    harness.assert_screenshot_matches("after_play")
    harness.stop()

Or run via pytest with the QGIS runner::

    QGISFMV/tests/run_tests.sh test_gui_player.py
"""

import time
from pathlib import Path

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QImage, QColor
from qgis.PyQt.QtWidgets import QApplication, QWidget, QAction
from qgis.core import QgsApplication

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).parent
_BASELINES_DIR = _TESTS_DIR / "baselines"
_SCREENSHOTS_DIR = _TESTS_DIR / "screenshots"


def _ensure_dirs():
    _BASELINES_DIR.mkdir(exist_ok=True)
    _SCREENSHOTS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Helper: wait for a condition with timeout
# ---------------------------------------------------------------------------
def wait_for(condition_fn, timeout_sec=5.0, poll_ms=50):
    """Block until *condition_fn()* returns truthy or *timeout_sec* elapses."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        result = condition_fn()
        if result:
            return result
        QApplication.processEvents()
        time.sleep(poll_ms / 1000.0)
    return None


# ---------------------------------------------------------------------------
# Helper: capture a widget as QImage
# ---------------------------------------------------------------------------
def capture_widget(widget):
    """Return a QImage screenshot of *widget*."""
    geom = widget.geometry()
    img = QImage(geom.width(), geom.height(), QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    widget.render(img)
    return img


def save_screenshot(img, name):
    """Save a QImage to the screenshots directory, return the path."""
    _ensure_dirs()
    path = _SCREENSHOTS_DIR / f"{name}.png"
    img.save(str(path), "PNG")
    return path


def image_hash(img):
    """Return a perceptual hash (average hash) of a QImage for comparison."""
    # Scale down to 16×16 grayscale
    small = img.scaled(
        16,
        16,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation,
    )
    pixels = []
    for y in range(16):
        for x in range(16):
            pixels.append(qGray(small.pixel(x, y)))
    avg = sum(pixels) / len(pixels)
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    return bits


def qGray(rgb):
    """Extract gray value (0-255) from a 32-bit ARGB pixel."""
    r = (rgb >> 16) & 0xFF
    g = (rgb >> 8) & 0xFF
    b = rgb & 0xFF
    return int(0.299 * r + 0.587 * g + 0.114 * b)


def images_match(img1, img2, threshold=0.95):
    """Compare two QImages using average hash. Returns (match, similarity)."""
    h1, h2 = image_hash(img1), image_hash(img2)
    matches = sum(a == b for a, b in zip(h1, h2))
    similarity = matches / len(h1)
    return similarity >= threshold, similarity


# ---------------------------------------------------------------------------
# GUITestHarness — the main testing class
# ---------------------------------------------------------------------------
class GUITestHarness:
    """
    Automated GUI tester for QGIS FMV.

    Starts QGIS, loads the plugin, and provides methods to:
    - Find and click widgets by name or type
    - Open/close dialogs
    - Capture and compare screenshots
    - Simulate keyboard and mouse input
    """

    def __init__(self):
        self._iface = None
        self._plugin = None
        self._player = None
        self._manager = None
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        """Start QGIS application and load the FMV plugin."""
        if self._started:
            return

        # Ensure QGIS app is running
        if QgsApplication.instance() is None:
            import sys

            QgsApplication.setPrefixPath("/Applications/QGIS.app/Contents/MacOS", True)
            self._qgs_app = QgsApplication([], False)
            self._qgs_app.initQgis()
        else:
            self._qgs_app = QgsApplication.instance()

        # Create a mock iface if needed
        from qgis.utils import iface as _iface

        self._iface = _iface

        # Load the plugin
        from QGISFMV.QgsFmv import Fmv

        self._plugin = Fmv(self._iface)
        self._started = True
        _ensure_dirs()

    def stop(self):
        """Tear down the plugin and QGIS."""
        if self._plugin is not None:
            try:
                self._plugin.unload()
            except Exception:
                pass
            self._plugin = None
        self._started = False

    # ------------------------------------------------------------------
    # Widget lookup
    # ------------------------------------------------------------------
    def find_widget(self, name, parent=None):
        """Find a child widget by objectName. Returns None if not found."""
        root = parent or self._get_main_window()
        if root is None:
            return None
        return root.findChild(QWidget, name)

    def find_action(self, name, parent=None):
        """Find a QAction by objectName."""
        root = parent or self._get_main_window()
        if root is None:
            return None
        return root.findChild(QAction, name)

    def find_all(self, widget_type, parent=None):
        """Find all children of a given type."""
        root = parent or self._get_main_window()
        if root is None:
            return []
        return root.findChildren(widget_type)

    def _get_main_window(self):
        """Return the QGIS main window."""
        from qgis.utils import iface

        if iface is not None:
            return iface.mainWindow()
        return QApplication.activeWindow()

    # ------------------------------------------------------------------
    # Actions: click, toggle, type
    # ------------------------------------------------------------------
    def click(self, action_name):
        """Click a QAction by its objectName."""
        action = self.find_action(action_name)
        if action is None:
            raise ValueError(f"Action '{action_name}' not found")
        action.trigger()
        QApplication.processEvents()

    def toggle(self, action_name, checked=True):
        """Set a checkable QAction's checked state."""
        action = self.find_action(action_name)
        if action is None:
            raise ValueError(f"Action '{action_name}' not found")
        action.setChecked(checked)
        QApplication.processEvents()

    def click_widget(self, widget_name):
        """Click a QPushButton or similar widget by objectName."""
        w = self.find_widget(widget_name)
        if w is None:
            raise ValueError(f"Widget '{widget_name}' not found")
        w.click()
        QApplication.processEvents()

    def type_text(self, widget_name, text):
        """Type text into a QLineEdit or QTextEdit."""
        w = self.find_widget(widget_name)
        if w is None:
            raise ValueError(f"Widget '{widget_name}' not found")
        if hasattr(w, "setText"):
            w.setText(text)
        elif hasattr(w, "setPlainText"):
            w.setPlainText(text)
        QApplication.processEvents()

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------
    def open_dialog(self, action_name, dialog_attr="dialog"):
        """Trigger an action that opens a dialog, wait for it to appear."""
        self.click(action_name)
        # Wait up to 3s for a new top-level window
        dialog = wait_for(
            lambda: QApplication.activeWindow(),
            timeout_sec=3.0,
        )
        return dialog

    def close_dialog(self, dialog):
        """Close a dialog gracefully."""
        if dialog is not None:
            dialog.close()
            QApplication.processEvents()

    # ------------------------------------------------------------------
    # Screenshots / Visual regression
    # ------------------------------------------------------------------
    def screenshot(self, name, widget=None):
        """Capture a screenshot. Returns the saved file path."""
        target = widget or self._get_main_window()
        if target is None:
            raise RuntimeError("No widget to screenshot")
        img = capture_widget(target)
        return save_screenshot(img, name)

    def assert_screenshot_matches(self, name, threshold=0.95):
        """
        Compare the current screenshot against a baseline.

        If no baseline exists, save the current image as the new baseline.
        Raises AssertionError if similarity is below threshold.
        """
        _ensure_dirs()
        current_path = _SCREENSHOTS_DIR / f"{name}.png"
        baseline_path = _BASELINES_DIR / f"{name}.png"

        if not current_path.exists():
            raise FileNotFoundError(f"Screenshot '{name}' not captured yet")

        current_img = QImage(str(current_path))

        if not baseline_path.exists():
            # First run — save as baseline
            import shutil

            shutil.copy2(str(current_path), str(baseline_path))
            return True, 1.0

        baseline_img = QImage(str(baseline_path))
        match, similarity = images_match(current_img, baseline_img, threshold)

        if not match:
            # Save diff image for debugging
            diff_path = _SCREENSHOTS_DIR / f"{name}_diff.png"
            diff = QImage(current_img.size(), QImage.Format.Format_ARGB32)
            diff.fill(QColor(255, 255, 255))
            for y in range(min(current_img.height(), baseline_img.height())):
                for x in range(min(current_img.width(), baseline_img.width())):
                    if qGray(current_img.pixel(x, y)) != qGray(
                        baseline_img.pixel(x, y)
                    ):
                        diff.setPixel(x, y, QColor(255, 0, 0).rgba())
            diff.save(str(diff_path), "PNG")

            raise AssertionError(
                f"Screenshot '{name}' differs: similarity={similarity:.2%} "
                f"(threshold={threshold:.0%}). Diff saved to {diff_path}"
            )

        return True, similarity

    def update_baseline(self, name):
        """Overwrite the baseline with the current screenshot."""
        _ensure_dirs()
        src = _SCREENSHOTS_DIR / f"{name}.png"
        dst = _BASELINES_DIR / f"{name}.png"
        if src.exists():
            import shutil

            shutil.copy2(str(src), str(dst))

    # ------------------------------------------------------------------
    # Plugin access
    # ------------------------------------------------------------------
    def get_player(self):
        """Return the current QgsFmvPlayer instance, or None."""
        if self._plugin is None:
            return None
        mgr = getattr(self._plugin, "_FMVManager", None)
        if mgr is not None:
            return getattr(mgr, "_PlayerDlg", None)
        return None

    def get_manager(self):
        """Return the current FmvManager instance, or None."""
        if self._plugin is None:
            return None
        return getattr(self._plugin, "_FMVManager", None)

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def process_events_for(duration_sec):
        """Process Qt events for *duration_sec* seconds."""
        deadline = time.monotonic() + duration_sec
        while time.monotonic() < deadline:
            QApplication.processEvents()
            time.sleep(0.01)
