# -*- coding: utf-8 -*-
"""
Tests for geodesic calculations (migrated from sphere.py to QgsGeoUtils).

Pure-Python tests run without QGIS.  Tests marked with ``qgis`` require
the QGIS runtime for QgsDistanceArea.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# Pure-Python tests (no QGIS needed)
# ---------------------------------------------------------------------------
class TestDestinationPure:
    """Great-circle destination — pure Python, no QGIS."""

    def _dest(self, point, dist, brg):
        from math import degrees, radians, sin, cos, asin, atan2
        R = 6371008.8
        lon1, lat1 = (radians(c) for c in point)
        rb = radians(brg)
        d = dist / R
        lat2 = asin(sin(lat1) * cos(d) + cos(lat1) * sin(d) * cos(rb))
        num = sin(rb) * sin(d) * cos(lat1)
        den = cos(d) - sin(lat1) * sin(lat2)
        lon2 = lon1 + atan2(num, den)
        return ((degrees(lon2) + 540) % 360 - 180, degrees(lat2))

    def test_north_from_equator(self):
        lon, lat = self._dest((0.0, 0.0), 111_000, 0.0)
        assert lat == pytest.approx(1.0, abs=0.1)
        assert lon == pytest.approx(0.0, abs=0.1)

    def test_east_from_equator(self):
        lon, lat = self._dest((0.0, 0.0), 111_000, 90.0)
        assert lon == pytest.approx(1.0, abs=0.1)
        assert lat == pytest.approx(0.0, abs=0.1)

    def test_zero_distance(self):
        lon, lat = self._dest((10.0, 20.0), 0.0, 45.0)
        assert lon == pytest.approx(10.0, abs=1e-6)
        assert lat == pytest.approx(20.0, abs=1e-6)

    def test_consistency(self):
        """Bearing 0 vs 180 should give opposite latitude shifts."""
        start = (-3.7038, 40.4168)
        n = self._dest(start, 500_000, 0.0)
        s = self._dest(start, 500_000, 180.0)
        assert n[1] > start[1] > s[1]


# ---------------------------------------------------------------------------
# QGIS runtime tests
# ---------------------------------------------------------------------------
_qgis_available = False
try:
    from qgis.core import QgsApplication
    _qgis_available = QgsApplication.instance() is not None
except ImportError:
    pass

pytestmark = pytest.mark.skipif(
    not _qgis_available,
    reason="QGIS runtime not available"
)


@ pytestmark
class TestDistanceQGIS:
    """distance() via QgsDistanceArea."""

    def test_same_point(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        assert distance((0.0, 0.0), (0.0, 0.0)) == 0.0

    def test_madrid_barcelona(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        d = distance((-3.7038, 40.4168), (2.1734, 41.3851))
        assert 480_000 < d < 650_000

    def test_symmetry(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        a, b = (0.0, 0.0), (10.0, 10.0)
        assert distance(a, b) == pytest.approx(distance(b, a), rel=1e-6)

    def test_one_degree_lat(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        d = distance((0.0, 0.0), (0.0, 1.0))
        assert 110_000 < d < 112_000

    def test_known_500km(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        d = distance((-3.7038, 40.4168), (-3.7038, 44.9))
        assert 480_000 < d < 520_000


@ pytestmark
class TestBearingQGIS:
    """bearing() via QgsDistanceArea."""

    def test_north(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        assert bearing((0.0, 0.0), (0.0, 10.0)) == pytest.approx(0.0, abs=1.0)

    def test_east(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        assert bearing((0.0, 0.0), (10.0, 0.0)) == pytest.approx(90.0, abs=1.0)

    def test_south(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b = bearing((0.0, 10.0), (0.0, 0.0))
        assert b == pytest.approx(180.0, abs=1.0)

    def test_west(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b = bearing((0.0, 0.0), (-10.0, 0.0))
        assert b == pytest.approx(270.0, abs=5.0)

    def test_back_bearing(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b_ab = bearing((0.0, 0.0), (10.0, 10.0))
        b_ba = bearing((10.0, 10.0), (0.0, 0.0))
        assert (b_ab + 180) % 360 == pytest.approx(b_ba, abs=5.0)


@ pytestmark
class TestPolygonAreaQGIS:
    """polygon_area() via QgsDistanceArea."""

    def test_empty_ring(self):
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        assert polygon_area([]) == 0.0

    def test_two_points(self):
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        assert polygon_area([(0, 0), (1, 1)]) == 0.0

    def test_one_degree_box(self):
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        area = polygon_area(ring)
        assert 12_000_000_000 < area < 12_500_000_000

    def test_small_square_madrid(self):
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        ring = [
            (-3.70, 40.41), (-3.69, 40.41),
            (-3.69, 40.42), (-3.70, 40.42),
        ]
        area = polygon_area(ring)
        assert 5_000_000 < area < 15_000_000

    def test_unit_square_at_origin(self):
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        area = polygon_area(ring)
        assert area > 0
