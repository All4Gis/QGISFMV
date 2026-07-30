# -*- coding: utf-8 -*-
"""Timeline bookmark helpers (no full QWidget paint required)."""

import sys
import types
from code.tests.support import (
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


def _timeline_mod():
    ensure_qgis_fmv_package()
    keys = qgis_stub_keys("qgis.PyQt.QtGui", "qgis.PyQt.QtWidgets")
    saved = snapshot_modules(keys)

    for name in keys:
        sys.modules.setdefault(name, types.ModuleType(name))

    qgis = sys.modules["qgis"]
    pyqt = sys.modules["qgis.PyQt"]
    qgis.PyQt = pyqt

    qtcore = sys.modules["qgis.PyQt.QtCore"]

    class _Signal:
        def __init__(self, *a):
            pass

        def connect(self, *a, **k):
            return None

        def emit(self, *a, **k):
            return None

    qtcore.Qt = types.SimpleNamespace(
        MouseButton=types.SimpleNamespace(LeftButton=1),
        PenStyle=types.SimpleNamespace(NoPen=0),
        AlignmentFlag=types.SimpleNamespace(AlignCenter=4),
    )
    qtcore.QRectF = lambda *a: None
    qtcore.pyqtSignal = lambda *a: _Signal()

    qtgui = sys.modules["qgis.PyQt.QtGui"]

    class QColor:
        def __init__(self, *a):
            self.args = a

        def darker(self, *a):
            return self

    qtgui.QColor = QColor
    qtgui.QPainter = object
    qtgui.QPen = object
    qtgui.QBrush = object
    qtgui.QFont = object

    qtw = sys.modules["qgis.PyQt.QtWidgets"]

    class QWidget:
        def __init__(self, parent=None):
            self._parent = parent

        def setMinimumHeight(self, *a):
            return None

        def setMaximumHeight(self, *a):
            return None

        def setMouseTracking(self, *a):
            return None

        def update(self):
            return None

        def width(self):
            return 200

        def height(self):
            return 32

    qtw.QWidget = QWidget
    qtw.QToolTip = types.SimpleNamespace(
        showText=lambda *a: None, hideText=lambda: None
    )

    mod = load_plugin_module(
        "player/features/QgsFmvTimeline.py",
        "QGISFMV.player.features.QgsFmvTimeline",
    )
    return mod, saved


class TestTimelineEvents:
    def test_add_and_clear(self):
        mod, saved = _timeline_mod()
        try:
            tw = mod.TimelineWidget()
            assert tw.eventCount() == 0
            tw.addEvent(12.5, label="Bookmark 1")
            tw.addEvent(3.0, label="Bookmark 2")
            assert tw.eventCount() == 2
            assert tw._events[0].time_sec == 3.0
            assert tw._events[1].label == "Bookmark 1"
            tw.clearEvents()
            assert tw.eventCount() == 0
        finally:
            restore_modules(saved)
            sys.modules.pop("QGISFMV.player.features.QgsFmvTimeline", None)
