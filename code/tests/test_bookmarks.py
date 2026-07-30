# -*- coding: utf-8 -*-
"""Bookmark export helpers + controller behaviour (no QGIS GUI)."""

import sys
import types
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock

import pytest

from code.tests.support import (
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


def _load_bookmark_mod():
    ensure_qgis_fmv_package()
    keys = qgis_stub_keys(
        "qgis.PyQt.QtGui",
        "qgis.PyQt.QtWidgets",
        "qgis.core",
        "QGISFMV.utils.ui.QgsUtils",
        "QGISFMV.utils.core.QgsFmvUtils",
    )
    saved = snapshot_modules(keys)
    for name in keys:
        sys.modules.setdefault(name, types.ModuleType(name))

    qgis = sys.modules["qgis"]
    pyqt = sys.modules["qgis.PyQt"]
    qgis.PyQt = pyqt

    qtcore = sys.modules["qgis.PyQt.QtCore"]
    qtcore.QCoreApplication = types.SimpleNamespace(
        translate=lambda *a, **k: a[-1] if a else ""
    )

    class QObject:
        def __init__(self, parent=None, *a, **k):
            self._parent = parent

    qtcore.QObject = QObject

    qtgui = sys.modules["qgis.PyQt.QtGui"]

    class QColor:
        def __init__(self, *a):
            self.args = a

    qtgui.QColor = QColor

    core = sys.modules["qgis.core"]
    core.Qgis = types.SimpleNamespace(
        MessageLevel=types.SimpleNamespace(Warning=1, Info=0)
    )

    ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]

    class QgsUtils:
        @staticmethod
        def showUserAndLogMessage(*a, **k):
            return None

    ui.QgsUtils = QgsUtils

    utils = sys.modules["QGISFMV.utils.core.QgsFmvUtils"]
    utils.askForFiles = lambda *a, **k: None

    mod = load_plugin_module(
        "player/features/QgsFmvBookmarkController.py",
        "QGISFMV.player.features.QgsFmvBookmarkController",
    )
    return mod, saved


class _FakeEvent:
    def __init__(self, time_sec, label=""):
        self.time_sec = time_sec
        self.label = label
        self.color = None


class _FakeTimeline:
    def __init__(self):
        self._events = []

    def addEvent(self, time_sec, label="", color=None, lat=None, lon=None, alt=None):
        ev = _FakeEvent(time_sec, label)
        ev.color = color
        ev.lat = lat
        ev.lon = lon
        ev.alt = alt
        self._events.append(ev)
        self._events.sort(key=lambda e: e.time_sec)
        return ev

    def clearEvents(self):
        self._events.clear()

    def eventCount(self):
        return len(self._events)

    def events(self):
        return list(self._events)


@pytest.fixture
def bookmark_mod():
    mod, saved = _load_bookmark_mod()
    try:
        yield mod
    finally:
        restore_modules(saved)
        sys.modules.pop("QGISFMV.player.features.QgsFmvBookmarkController", None)


class TestBookmarkExportHelpers:
    def test_csv_and_kml(self, bookmark_mod, tmp_path):
        events = [_FakeEvent(1.5, "A"), _FakeEvent(3.0, "B")]
        csv_path = tmp_path / "marks.csv"
        kml_path = tmp_path / "marks.kml"
        assert bookmark_mod.write_bookmarks_csv(str(csv_path), events) == 2
        assert bookmark_mod.write_bookmarks_kml(str(kml_path), events, "demo.ts") == 2
        text = csv_path.read_text(encoding="utf-8")
        assert "time_sec" in text and "1.5" in text
        root = ET.parse(str(kml_path)).getroot()
        assert "kml" in root.tag


class TestBookmarkController:
    def test_add_clear_and_alert(self, bookmark_mod, tmp_path):
        player = MagicMock()
        player.currentInfo = 12.0
        player.timeline = _FakeTimeline()
        player.fileName = "/tmp/clip.ts"
        ctrl = bookmark_mod.BookmarkController(player)

        ctrl.addBookmark()
        assert player.timeline.eventCount() == 1

        ctrl.onAlertTriggered("ALERT: altitude > 100")
        assert player.timeline.eventCount() == 2
        assert player.timeline.events()[-1].label.startswith("ALERT")

        out = ctrl.exportBookmarks(path=str(tmp_path / "out.csv"))
        assert out == str(tmp_path / "out.csv")
        assert (tmp_path / "out.csv").is_file()

        ctrl.clearBookmarks()
        assert player.timeline.eventCount() == 0
        assert ctrl.exportBookmarks(path=str(tmp_path / "empty.csv")) is None
