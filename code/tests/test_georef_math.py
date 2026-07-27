# -*- coding: utf-8 -*-
"""Tests for pure georeferencing math (homography / affine checks)."""

import sys
import types

import numpy as np
import pytest

from code.tests.support import (
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


def _stub_qgis_modules():
    """Minimal stubs so GeoReferencing can import without a QGIS runtime."""
    ensure_qgis_fmv_package()
    keys = qgis_stub_keys(
        "QGISFMV.utils.layers.QgsFmvLayers",
        "QGISFMV.utils.ui.QgsUtils",
    )
    saved = snapshot_modules(keys)

    def _mod(name):
        m = sys.modules.get(name)
        if m is None:
            m = types.ModuleType(name)
            sys.modules[name] = m
        return m

    qgis = _mod("qgis")
    pyqt = _mod("qgis.PyQt")
    qgis.PyQt = pyqt
    _mod("qgis.PyQt.QtCore")
    _mod("qgis.core")

    layers = _mod("QGISFMV.utils.layers.QgsFmvLayers")
    layers.UpdateFootPrintData = lambda *a, **k: None
    layers.UpdateBeamsData = lambda *a, **k: None

    ui = _mod("QGISFMV.utils.ui.QgsUtils")

    class QgsUtils:
        @staticmethod
        def showUserAndLogMessage(*a, **k):
            return None

    ui.QgsUtils = QgsUtils
    return saved


@pytest.fixture(scope="module")
def geo():
    saved = _stub_qgis_modules()
    try:
        mod = load_plugin_module(
            "utils/core/QgsFmvGeoReferencing.py",
            "QGISFMV.utils.core.QgsFmvGeoReferencing",
        )
    except Exception as exc:
        restore_modules(saved)
        pytest.skip(f"Cannot load GeoReferencing: {exc}")
    yield mod
    restore_modules(saved)
    sys.modules.pop("QGISFMV.utils.core.QgsFmvGeoReferencing", None)


class TestHomographyNumpy:
    def test_identity_mapping(self, geo):
        src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
        dst = src.copy()
        H = geo._find_homography_numpy(src, dst)
        assert H.shape == (3, 3)
        p = np.array([0.5, 0.5, 1.0], dtype=np.float32)
        q = H @ p
        q = q[:2] / q[2]
        assert q[0] == pytest.approx(0.5, abs=1e-3)
        assert q[1] == pytest.approx(0.5, abs=1e-3)

    def test_translation(self, geo):
        src = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
        dst = src + np.array([2.0, 3.0], dtype=np.float32)
        H = geo._find_homography_numpy(src, dst)
        p = np.array([0.0, 0.0, 1.0], dtype=np.float32)
        q = H @ p
        q = q[:2] / q[2]
        assert q[0] == pytest.approx(2.0, abs=1e-2)
        assert q[1] == pytest.approx(3.0, abs=1e-2)


class TestAffineUsable:
    def test_none(self, geo):
        assert geo._affineTransformIsUsable(None) is False

    def test_wrong_length(self, geo):
        assert geo._affineTransformIsUsable((1, 2, 3)) is False

    def test_nan(self, geo):
        assert geo._affineTransformIsUsable((1, 0, 0, 1, 0, float("nan"))) is False

    def test_valid(self, geo):
        assert geo._affineTransformIsUsable((0, 1, 0, 0, 0, -1)) is True
