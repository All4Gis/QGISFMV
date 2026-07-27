# -*- coding: utf-8 -*-
"""Tests for export XML builders that do not need a QGIS map canvas."""

import sys
import types
import xml.etree.ElementTree as ET

import pytest

from code.tests.support import (
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


def _load_export():
    ensure_qgis_fmv_package()
    keys = qgis_stub_keys("QGISFMV.utils.ui.QgsUtils")
    saved = snapshot_modules(keys)

    for name in keys:
        sys.modules.setdefault(name, types.ModuleType(name))

    qgis = sys.modules["qgis"]
    qgis.core = sys.modules["qgis.core"]
    qgis.PyQt = sys.modules["qgis.PyQt"]
    core = sys.modules["qgis.core"]
    core.Qgis = types.SimpleNamespace(
        MessageLevel=types.SimpleNamespace(Warning=1, Info=0, Success=0)
    )
    core.QgsProject = types.SimpleNamespace(instance=lambda: None)
    core.QgsCoordinateReferenceSystem = object
    core.QgsCoordinateTransform = object
    core.QgsWkbTypes = types.SimpleNamespace(
        GeometryType=types.SimpleNamespace(Point=0, Line=1, Polygon=2),
        LineString=2,
        LineStringZ=1002,
        MultiLineString=5,
        MultiLineStringZ=1005,
        Point=1,
        PointZ=1001,
        MultiPoint=4,
        MultiPointZ=1004,
    )

    qtcore = sys.modules["qgis.PyQt.QtCore"]
    qtcore.QCoreApplication = types.SimpleNamespace(
        translate=lambda *a, **k: a[-1] if a else ""
    )

    qtw = sys.modules["qgis.PyQt.QtWidgets"]
    qtw.QFileDialog = object

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
        "utils/layers/QgsFmvExport.py", "QGISFMV.utils.layers.QgsFmvExport"
    )
    return mod, saved


@pytest.fixture
def export_mod():
    try:
        mod, saved = _load_export()
    except Exception as exc:
        pytest.skip(f"Cannot load export module: {exc}")
    try:
        yield mod
    finally:
        restore_modules(saved)
        sys.modules.pop("QGISFMV.utils.layers.QgsFmvExport", None)


class TestBuildGpxDocument:
    def test_track_points(self, export_mod, tmp_path):
        gpx = export_mod._build_gpx_document(
            "demo", [(-3.7, 40.4), (-3.71, 40.41)]
        )
        assert gpx.tag == "gpx"
        pts = list(gpx.iter("trkpt"))
        assert len(pts) == 2
        assert pts[0].attrib["lat"] == "40.400000"
        assert pts[0].attrib["lon"] == "-3.700000"

        out = tmp_path / "track.gpx"
        export_mod._write_gpx_file(gpx, str(out))
        assert out.is_file()
        tree = ET.parse(str(out))
        assert tree.getroot().tag.endswith("gpx") or tree.getroot().tag == "gpx"
