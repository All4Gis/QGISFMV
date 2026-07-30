# -*- coding: utf-8 -*-
"""Unit tests for mosaic helpers (pure numpy / optional GDAL; no QGIS GUI)."""

import time
import types
from code.tests.support import ensure_qgis_fmv_package, load_plugin_module
from unittest.mock import MagicMock

import numpy as np
import pytest


@pytest.fixture
def mosaic():
    ensure_qgis_fmv_package()
    # Clear feather cache between tests.
    mod = load_plugin_module(
        "utils/core/QgsFmvMosaic.py", "QGISFMV.utils.core.QgsFmvMosaic"
    )
    mod._feather_weights_cache.clear()
    mod._mosaic_capture_state = {
        "time": 0.0,
        "lat": None,
        "lon": None,
        "footprint_span": None,
    }
    return mod


@pytest.fixture
def mock_gv(monkeypatch, mosaic):
    """Install a lightweight session stand-in on QgsFmvUtils.gv."""
    ensure_qgis_fmv_package()
    utils_name = "QGISFMV.utils.core.QgsFmvUtils"
    if utils_name not in __import__("sys").modules:
        stub = types.ModuleType(utils_name)
        __import__("sys").modules[utils_name] = stub
    utils = __import__("sys").modules[utils_name]

    gv = MagicMock()
    gv.getSensorLatitude.return_value = 40.0
    gv.getSensorLongitude.return_value = -3.0
    gv.getFrameCenterLat.return_value = 40.0
    gv.getFrameCenterLon.return_value = -3.0
    gv.getCornerUL.return_value = (40.1, -3.1)
    gv.getCornerUR.return_value = (40.1, -2.9)
    gv.getCornerLR.return_value = (39.9, -2.9)
    gv.getCornerLL.return_value = (39.9, -3.1)
    utils.gv = gv
    return gv


class TestMosaicFeatherWeights:
    def test_peak_at_center(self, mosaic):
        w = mosaic._mosaic_feather_weights(32, 32, feather_px=8)
        assert w.shape == (32, 32)
        assert float(w[16, 16]) >= float(w[0, 16])
        assert float(w[0, 0]) < 0.2

    def test_cache_reuse(self, mosaic):
        a = mosaic._mosaic_feather_weights(16, 16, feather_px=8)
        b = mosaic._mosaic_feather_weights(16, 16, feather_px=8)
        assert a is b

    def test_min_feather_clamped(self, mosaic):
        w = mosaic._mosaic_feather_weights(20, 20, feather_px=2)
        assert w.shape == (20, 20)
        assert float(w.max()) == 1.0


class TestFootprintWeights:
    def test_zero_outside_mask(self, mosaic):
        mask = np.zeros((40, 40), dtype=bool)
        mask[10:30, 10:30] = True
        weights = mosaic._footprint_weights_from_mask(mask, feather_px=8)
        assert weights.shape == mask.shape
        assert float(weights[~mask].max()) == 0.0
        assert float(weights[20, 20]) > float(weights[10, 20])

    def test_empty_mask(self, mosaic):
        mask = np.zeros((8, 8), dtype=bool)
        weights = mosaic._footprint_weights_from_mask(mask, feather_px=8)
        assert weights.shape == mask.shape
        assert float(weights.max()) == 0.0


class TestMosaicOutputResolution:
    def test_landscape_bounds(self, mosaic):
        xres, yres, width, height = mosaic._mosaic_output_resolution(
            (0.0, 0.0, 2.0, 1.0), max_output_size=100
        )
        assert width == 100
        assert height == 50
        assert xres > 0 and yres > 0

    def test_portrait_bounds(self, mosaic):
        xres, yres, width, height = mosaic._mosaic_output_resolution(
            (0.0, 0.0, 1.0, 2.0), max_output_size=100
        )
        assert height == 100
        assert width == 50


class TestScaleAffine:
    def test_scales_pixel_size(self, mosaic):
        affine = (10.0, 1.0, 0.0, 20.0, 0.0, -1.0)
        scaled = mosaic._scale_affine_for_resize(affine, 100, 100, 50, 50)
        assert scaled[0] == 10.0
        assert scaled[3] == 20.0
        assert scaled[1] == pytest.approx(2.0)
        assert scaled[5] == pytest.approx(-2.0)

    def test_identity_when_same_size(self, mosaic):
        affine = (10.0, 1.0, 0.0, 20.0, 0.0, -1.0)
        assert mosaic._scale_affine_for_resize(affine, 64, 64, 64, 64) is affine

    def test_guards_zero_new_size(self, mosaic):
        affine = (10.0, 1.0, 0.0, 20.0, 0.0, -1.0)
        assert mosaic._scale_affine_for_resize(affine, 64, 64, 0, 32) is affine
        assert mosaic._scale_affine_for_resize(None, 64, 64, 32, 32) is None

    def test_union_extent_empty(self, mosaic):
        assert mosaic._union_extent([]) is None


class TestAcceptMosaicFrame:
    def test_accept_first_sample(self, mosaic, mock_gv):
        assert mosaic._should_accept_mosaic_frame() is True

    def test_reject_rapid_duplicate(self, mosaic, mock_gv):
        mosaic._should_accept_mosaic_frame()
        assert mosaic._should_accept_mosaic_frame() is False

    def test_accept_when_moved_far(self, mosaic, mock_gv, monkeypatch):
        mosaic._should_accept_mosaic_frame()
        mock_gv.getSensorLatitude.return_value = 41.0
        mock_gv.getSensorLongitude.return_value = -3.0
        # Force interval not to dominate; movement alone should accept.
        import QGISFMV.utils.constants as cfg

        monkeypatch.setattr(cfg, "MOSAIC_MIN_INTERVAL_SEC", 9999.0)
        monkeypatch.setattr(cfg, "MOSAIC_MIN_MOVE_METERS", 10.0)
        assert mosaic._should_accept_mosaic_frame() is True

    def test_accept_none_gv(self, mosaic, monkeypatch):
        import sys

        utils = sys.modules.get("QGISFMV.utils.core.QgsFmvUtils")
        if utils is None:
            utils = types.ModuleType("QGISFMV.utils.core.QgsFmvUtils")
            sys.modules["QGISFMV.utils.core.QgsFmvUtils"] = utils
        utils.gv = None
        assert mosaic._should_accept_mosaic_frame() is True


class TestDatasetExtent:
    def test_dataset_extent_uses_all_corners(self, tmp_path, mosaic):
        try:
            from osgeo import gdal, osr
        except ImportError:
            pytest.skip("GDAL not available")

        path = tmp_path / "rotated.tif"
        driver = gdal.GetDriverByName("GTiff")
        dataset = driver.Create(str(path), 10, 10, 1)
        dataset.SetGeoTransform([0.0, 1.0, 0.5, 10.0, 0.5, -1.0])
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        dataset.SetProjection(srs.ExportToWkt())
        dataset.GetRasterBand(1).WriteArray(np.zeros((10, 10), dtype="uint8"))
        dataset.FlushCache()
        dataset = None

        extent = mosaic._dataset_extent_wgs84(str(path))
        assert extent is not None
        minx, miny, maxx, maxy = extent
        assert minx < maxx
        assert miny < maxy
        assert minx <= 0.0
        assert maxx >= 9.0


class TestFootprintInputsChanged:
    def test_detects_corner_delta(self):
        ensure_qgis_fmv_package()
        # GeoReferencing pulls QGIS layers; skip if unavailable.
        try:
            geo = load_plugin_module(
                "utils/core/QgsFmvGeoReferencing.py",
                "QGISFMV.utils.core.QgsFmvGeoReferencing",
            )
        except Exception as exc:
            pytest.skip(f"GeoReferencing unavailable: {exc}")

        import sys

        utils_name = "QGISFMV.utils.core.QgsFmvUtils"
        utils = sys.modules.get(utils_name)
        if utils is None:
            utils = types.ModuleType(utils_name)
            sys.modules[utils_name] = utils

        gv = MagicMock()
        gv.getCornerUL.return_value = (40.1, -3.1)
        gv.getCornerUR.return_value = (40.1, -2.9)
        gv.getCornerLR.return_value = (39.9, -2.9)
        gv.getCornerLL.return_value = (39.9, -3.1)
        utils.gv = gv

        packet = types.SimpleNamespace(
            CornerLatitudePoint1Full=40.1,
            CornerLongitudePoint1Full=-3.1,
            CornerLatitudePoint2Full=40.1,
            CornerLongitudePoint2Full=-2.9,
            CornerLatitudePoint3Full=39.9,
            CornerLongitudePoint3Full=-2.9,
            CornerLatitudePoint4Full=39.9,
            CornerLongitudePoint4Full=-3.1,
        )
        assert geo._footprint_inputs_changed(packet) is False
        packet.CornerLatitudePoint1Full = 40.2
        assert geo._footprint_inputs_changed(packet) is True


class TestResetMosaicState:
    def test_reset_clears_counter(self, mosaic):
        mosaic._mosaic_frame_counter = 5
        mosaic.resetMosaicFrameCounter()
        assert mosaic._mosaic_frame_counter == 0
        assert mosaic._mosaic_capture_state["lat"] is None
