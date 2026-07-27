# -*- coding: utf-8 -*-
"""Tests for TaskResultsClassifier (pure, no Qt)."""

import sys
import types

import pytest

from code.tests.support import (
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


def _load_classifier():
    ensure_qgis_fmv_package()
    keys = qgis_stub_keys(
        "QGISFMV.utils.ui.QgsPlot",
        "QGISFMV.utils.ui.QgsUtils",
    )
    saved = snapshot_modules(keys)

    for name in keys:
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    qgis = sys.modules["qgis"]
    pyqt = sys.modules["qgis.PyQt"]
    qgis.PyQt = pyqt

    qtcore = sys.modules["qgis.PyQt.QtCore"]
    qtcore.QCoreApplication = types.SimpleNamespace(
        translate=lambda *a, **k: a[-1] if a else ""
    )

    qtw = sys.modules["qgis.PyQt.QtWidgets"]
    qtw.QMessageBox = types.SimpleNamespace(
        StandardButton=types.SimpleNamespace(Yes=1, No=0)
    )

    core = sys.modules["qgis.core"]
    core.Qgis = types.SimpleNamespace(
        MessageLevel=types.SimpleNamespace(Warning=1, Info=0)
    )
    core.QgsProject = types.SimpleNamespace(instance=lambda: None)
    core.QgsRasterLayer = object

    plot = sys.modules["QGISFMV.utils.ui.QgsPlot"]
    plot.ShowPlot = lambda *a, **k: None

    ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]

    class QgsUtils:
        @staticmethod
        def showUserAndLogMessage(*a, **k):
            return None

        @staticmethod
        def CustomMessage(*a, **k):
            return 0

    ui.QgsUtils = QgsUtils

    mod = load_plugin_module(
        "player/features/QgsFmvTaskResults.py",
        "QGISFMV.player.features.QgsFmvTaskResults",
    )
    return mod, saved


@pytest.fixture
def mod():
    module, saved = _load_classifier()
    try:
        yield module
    finally:
        restore_modules(saved)
        sys.modules.pop("QGISFMV.player.features.QgsFmvTaskResults", None)


class TestClassifyTaskResult:
    def test_empty(self, mod):
        assert mod.classify_task_result(None)["kind"] == "empty"
        assert mod.classify_task_result("x")["kind"] == "empty"

    def test_error(self, mod):
        info = mod.classify_task_result({"error": "boom", "stop_record_animation": True})
        assert info["kind"] == "error"
        assert info["error"] == "boom"
        assert info["stop_record_animation"] is True

    def test_georeferencing(self, mod):
        info = mod.classify_task_result({"task": "Georeferencing mosaic"})
        assert info["kind"] == "georeferencing"

    def test_bitrate(self, mod):
        info = mod.classify_task_result({"task": "Bitrate Analysis"})
        assert info["kind"] == "bitrate"

    def test_video_info(self, mod):
        info = mod.classify_task_result(
            {"task": "Show Video Info Task", "json": {"a": 1}}
        )
        assert info["kind"] == "video_info"
        assert info["has_json"] is True

    def test_save_georef_frame(self, mod):
        info = mod.classify_task_result(
            {"task": "Save Current Georeferenced Frame Task", "file": "/tmp/x.tif"}
        )
        assert info["kind"] == "save_georef_frame"
        assert info["file"] == "/tmp/x.tif"

    def test_empty_dict(self, mod):
        assert mod.classify_task_result({})["kind"] == "empty"

    def test_generic_success(self, mod):
        info = mod.classify_task_result({"task": "Export KML"})
        assert info["kind"] == "success"
