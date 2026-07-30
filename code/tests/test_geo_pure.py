# -*- coding: utf-8 -*-
"""Pure geodesic helpers that work without a QGIS runtime (Haversine fallback)."""

from code.tests.support import ensure_qgis_fmv_package, load_plugin_module

import pytest

ensure_qgis_fmv_package()
geo = load_plugin_module("geo/QgsGeoUtils.py", "QGISFMV.geo.QgsGeoUtils")


class TestHaversine:
    def test_same_point(self):
        assert geo._haversine_m((-3.7, 40.4), (-3.7, 40.4)) == pytest.approx(0.0)

    def test_one_degree_latitude(self):
        # ~111 km per degree of latitude
        d = geo._haversine_m((0.0, 0.0), (0.0, 1.0))
        assert 110_000 < d < 112_000

    def test_distance_uses_haversine_without_qgis(self):
        d = geo.distance((-3.7, 40.4), (-3.7, 40.5))
        assert d > 10_000


class TestDestination:
    def test_north_one_km(self):
        lon, lat = geo.destination((-3.7, 40.4), 1000.0, 0.0)
        assert lon == pytest.approx(-3.7, abs=1e-4)
        assert lat > 40.4

    def test_east_moves_longitude(self):
        lon, lat = geo.destination((-3.7, 40.4), 1000.0, 90.0)
        assert lon > -3.7
        assert lat == pytest.approx(40.4, abs=1e-3)


class TestSphericalArea:
    def test_empty(self):
        assert geo._spherical_ring_area_m2([]) == 0.0

    def test_two_points(self):
        assert geo._spherical_ring_area_m2([(0, 0), (1, 1)]) == 0.0

    def test_unit_box_positive(self):
        ring = [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]
        area = geo._spherical_ring_area_m2(ring)
        assert area > 1e9  # roughly 12_000 km²
