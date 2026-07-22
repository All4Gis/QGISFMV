# -*- coding: utf-8 -*-
"""Unit tests for mosaic helpers in QgsFmvUtils."""

import time

import pytest

from code.tests.support import load_plugin_module as _load_plugin_module


@pytest.fixture
def fmv_utils():
    # QgsFmvUtilsState requires QGIS runtime (qgis.utils.iface)
    try:
        from qgis.utils import iface  # noqa: F401
    except ImportError:
        pytest.skip("QGIS runtime not available")

    module = _load_plugin_module("utils/core/QgsFmvUtils.py", "QGISFMV.utils.core.QgsFmvUtils")
    from QGISFMV.utils.core.QgsFmvUtilsState import globalVariablesState

    module.gv = globalVariablesState()
    module._mosaic_capture_state = {
        "time": 0.0,
        "lat": None,
        "lon": None,
        "footprint_span": None,
    }
    return module


def test_should_accept_mosaic_frame_on_first_sample(fmv_utils):
    fmv_utils.gv.setSensorLatitude(40.0)
    fmv_utils.gv.setSensorLongitude(-3.0)
    assert fmv_utils._should_accept_mosaic_frame() is True


def test_should_reject_rapid_duplicate_position(fmv_utils):
    fmv_utils.gv.setSensorLatitude(40.0)
    fmv_utils.gv.setSensorLongitude(-3.0)
    fmv_utils._should_accept_mosaic_frame()
    assert fmv_utils._should_accept_mosaic_frame() is False


def test_should_accept_when_footprint_span_grows(fmv_utils):
    fmv_utils.gv.setSensorLatitude(40.0)
    fmv_utils.gv.setSensorLongitude(-3.0)
    fmv_utils.gv.setCornerUL((40.1, -3.1))
    fmv_utils.gv.setCornerUR((40.1, -2.9))
    fmv_utils.gv.setCornerLR((39.9, -2.9))
    fmv_utils.gv.setCornerLL((39.9, -3.1))
    fmv_utils._should_accept_mosaic_frame()

    fmv_utils.gv.setCornerUL((40.2, -3.2))
    fmv_utils.gv.setCornerUR((40.2, -2.8))
    fmv_utils.gv.setCornerLR((39.8, -2.8))
    fmv_utils.gv.setCornerLL((39.8, -3.2))
    assert fmv_utils._should_accept_mosaic_frame() is True


def test_footprint_inputs_changed_detects_corner_delta(fmv_utils):
    packet = type(
        "Packet",
        (),
        {
            "CornerLatitudePoint1Full": 40.1,
            "CornerLongitudePoint1Full": -3.1,
            "CornerLatitudePoint2Full": 40.1,
            "CornerLongitudePoint2Full": -2.9,
            "CornerLatitudePoint3Full": 39.9,
            "CornerLongitudePoint3Full": -2.9,
            "CornerLatitudePoint4Full": 39.9,
            "CornerLongitudePoint4Full": -3.1,
        },
    )()
    fmv_utils.gv.setCornerUL((40.1, -3.1))
    fmv_utils.gv.setCornerUR((40.1, -2.9))
    fmv_utils.gv.setCornerLR((39.9, -2.9))
    fmv_utils.gv.setCornerLL((39.9, -3.1))
    assert fmv_utils._footprint_inputs_changed(packet) is False

    packet.CornerLatitudePoint1Full = 40.2
    assert fmv_utils._footprint_inputs_changed(packet) is True


def test_footprint_weights_zero_outside_mask(fmv_utils):
    import numpy as np

    mask = np.zeros((40, 40), dtype=bool)
    mask[10:30, 10:30] = True
    weights = fmv_utils._footprint_weights_from_mask(mask, feather_px=8)
    assert weights.shape == mask.shape
    assert float(weights[~mask].max()) == 0.0
    assert float(weights[20, 20]) > float(weights[10, 20])


def test_mosaic_feather_weights_peak_at_center(fmv_utils):
    import numpy as np

    w = fmv_utils._mosaic_feather_weights(32, 32, feather_px=8)
    assert w.shape == (32, 32)
    assert float(w[16, 16]) >= float(w[0, 16])
    assert float(w[0, 0]) < 0.2


def test_dataset_extent_uses_all_corners(tmp_path, fmv_utils):
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
    dataset.GetRasterBand(1).WriteArray(
        __import__("numpy").zeros((10, 10), dtype="uint8")
    )
    dataset.FlushCache()
    dataset = None

    extent = fmv_utils._dataset_extent_wgs84(str(path))
    assert extent is not None
    minx, miny, maxx, maxy = extent
    assert minx < maxx
    assert miny < maxy
    assert minx <= 0.0
    assert maxx >= 9.0
