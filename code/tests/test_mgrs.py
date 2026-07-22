# -*- coding: utf-8 -*-
"""Tests for MGRS coordinate conversion (uses mgrs PyPI package)."""

import pytest

mgrs = pytest.importorskip("mgrs")

_instance = mgrs.MGRS()


class TestMgrsConversion:
    def test_to_mgrs_returns_string(self):
        result = _instance.toMGRS(40.0, -3.0)
        assert isinstance(result, str)

    def test_to_mgrs_madrid(self):
        result = _instance.toMGRS(40.4168, -3.7038)
        assert len(result) > 0
        assert result[0].isdigit()

    def test_to_mgrs_equator(self):
        result = _instance.toMGRS(0.0, 0.0)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_to_mgrs_north_pole(self):
        result = _instance.toMGRS(89.0, 0.0)
        assert isinstance(result, str)

    def test_to_mgrs_south_pole(self):
        result = _instance.toMGRS(-89.0, 0.0)
        assert isinstance(result, str)


class TestMgrsRoundtrip:
    def test_to_mgrs_to_wgs_roundtrip(self):
        lat, lon = 40.4168, -3.7038
        mgrs_str = _instance.toMGRS(lat, lon)
        latlon = _instance.toLatLon(mgrs_str)
        assert latlon[0] == pytest.approx(lat, abs=0.001)
        assert latlon[1] == pytest.approx(lon, abs=0.001)

    def test_to_mgrs_to_wgs_roundtrip_equator(self):
        lat, lon = 0.0, 0.0
        mgrs_str = _instance.toMGRS(lat, lon)
        latlon = _instance.toLatLon(mgrs_str)
        assert latlon[0] == pytest.approx(lat, abs=0.001)
        assert latlon[1] == pytest.approx(lon, abs=0.001)
