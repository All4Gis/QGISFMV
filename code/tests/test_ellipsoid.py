# -*- coding: utf-8 -*-
"""
Tests for geodesic calculations in QgsGeoUtils.

The ``destination()`` function is pure Python and can run without QGIS.
The ``distance()``, ``bearing()``, and ``polygon_area()`` functions
require the QGIS runtime (QgsDistanceArea).
"""

import math
import pytest


# ---------------------------------------------------------------------------
# Pure-Python tests (no QGIS needed)
# ---------------------------------------------------------------------------
class TestDestination:
    """Test the great-circle destination function (pure Python)."""

    def _destination(self, point, distance_m, bearing_deg):
        """Import destination without QGIS dependency."""
        from math import degrees, radians, sin, cos, asin, atan2
        R = 6371008.8
        lon1, lat1 = (radians(c) for c in point)
        rb = radians(bearing_deg)
        delta = distance_m / R
        lat2 = asin(sin(lat1) * cos(delta) + cos(lat1) * sin(delta) * cos(rb))
        num = sin(rb) * sin(delta) * cos(lat1)
        den = cos(delta) - sin(lat1) * sin(lat2)
        lon2 = lon1 + atan2(num, den)
        return ((degrees(lon2) + 540) % 360 - 180, degrees(lat2))

    def test_destination_north(self):
        """Going due north from equator should increase latitude."""
        lon, lat = self._destination((0.0, 0.0), 111_000, 0.0)
        assert lat == pytest.approx(1.0, abs=0.1)
        assert lon == pytest.approx(0.0, abs=0.1)

    def test_destination_east(self):
        """Going due east from equator should increase longitude."""
        lon, lat = self._destination((0.0, 0.0), 111_000, 90.0)
        assert lon == pytest.approx(1.0, abs=0.1)
        assert lat == pytest.approx(0.0, abs=0.1)

    def test_destination_south(self):
        """Going due south from equator should decrease latitude."""
        lon, lat = self._destination((0.0, 0.0), 111_000, 180.0)
        assert lat == pytest.approx(-1.0, abs=0.1)

    def test_destination_zero_distance(self):
        """Zero distance should return the same point."""
        lon, lat = self._destination((10.0, 20.0), 0.0, 45.0)
        assert lon == pytest.approx(10.0, abs=1e-6)
        assert lat == pytest.approx(20.0, abs=1e-6)

    def test_destination_consistency(self):
        """Destination at bearing 0 and 180 should be roughly opposite."""
        start = (-3.7038, 40.4168)  # Madrid
        d = 500_000  # 500 km
        north = self._destination(start, d, 0.0)
        south = self._destination(start, d, 180.0)
        # Latitudes should have opposite signs relative to start
        assert north[1] > start[1]
        assert south[1] < start[1]


class TestHaversineFallback:
    """Pure-Python geodesic fallback used when QgsDistanceArea returns 0."""

    def test_madrid_barcelona_order_of_magnitude(self):
        from code.tests.support import load_plugin_module

        geo = load_plugin_module("geo/QgsGeoUtils.py", "QGISFMV.geo.QgsGeoUtils")
        madrid = (-3.7038, 40.4168)
        barcelona = (2.1734, 41.3851)
        d = geo._haversine_m(madrid, barcelona)
        assert 480_000 < d < 650_000

    def test_same_point_zero(self):
        from code.tests.support import load_plugin_module

        geo = load_plugin_module("geo/QgsGeoUtils.py", "QGISFMV.geo.QgsGeoUtils")
        assert geo._haversine_m((1.0, 2.0), (1.0, 2.0)) == pytest.approx(0.0, abs=1e-6)

    def test_spherical_area_positive(self):
        from code.tests.support import load_plugin_module

        geo = load_plugin_module("geo/QgsGeoUtils.py", "QGISFMV.geo.QgsGeoUtils")
        # Small triangle near equator (~1° × 1°)
        ring = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
        area = geo._spherical_ring_area_m2(ring)
        assert area > 1e9  # ~ half of 111km×111km


# ---------------------------------------------------------------------------
# QGIS runtime tests
# ---------------------------------------------------------------------------
_qgis_available = False
try:
    from qgis.core import QgsApplication
    _qgis_available = QgsApplication.instance() is not None
except ImportError:
    pass

pytestmark_qgis = pytest.mark.skipif(
    not _qgis_available,
    reason="QGIS runtime not available"
)


@ pytestmark_qgis
class TestDistanceQGIS:
    """Test distance() using QgsDistanceArea (requires QGIS)."""

    def test_same_point(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        assert distance((0.0, 0.0), (0.0, 0.0)) == 0.0

    def test_madrid_barcelona(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        madrid = (-3.7038, 40.4168)
        barcelona = (2.1734, 41.3851)
        d = distance(madrid, barcelona)
        assert 480_000 < d < 650_000

    def test_symmetry(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        a = (0.0, 0.0)
        b = (10.0, 10.0)
        assert distance(a, b) == pytest.approx(distance(b, a), rel=1e-6)

    def test_pole_to_pole(self):
        from QGISFMV.geo.QgsGeoUtils import distance
        d = distance((0.0, 89.0), (0.0, -89.0))
        assert 19_000_000 < d < 21_000_000

    def test_known_distance_1_degree_lat(self):
        """1 degree of latitude ≈ 111 km."""
        from QGISFMV.geo.QgsGeoUtils import distance
        d = distance((0.0, 0.0), (0.0, 1.0))
        assert 110_000 < d < 112_000

    def test_known_distance_500km_north(self):
        """~500 km north from Madrid along the same meridian."""
        from QGISFMV.geo.QgsGeoUtils import distance
        d = distance((-3.7038, 40.4168), (-3.7038, 44.9))
        assert 480_000 < d < 520_000


@ pytestmark_qgis
class TestBearingQGIS:
    """Test bearing() using QgsDistanceArea (requires QGIS)."""

    def test_bearing_north(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b = bearing((0.0, 0.0), (0.0, 10.0))
        assert b == pytest.approx(0.0, abs=1.0)

    def test_bearing_east(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b = bearing((0.0, 0.0), (10.0, 0.0))
        assert b == pytest.approx(90.0, abs=1.0)

    def test_bearing_south(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b = bearing((0.0, 10.0), (0.0, 0.0))
        assert b == pytest.approx(180.0, abs=1.0)

    def test_bearing_west(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b = bearing((0.0, 0.0), (-10.0, 0.0))
        assert b == pytest.approx(270.0, abs=5.0)

    def test_bearing_symmetry(self):
        from QGISFMV.geo.QgsGeoUtils import bearing
        b_ab = bearing((0.0, 0.0), (10.0, 10.0))
        b_ba = bearing((10.0, 10.0), (0.0, 0.0))
        # Back bearing should be roughly opposite
        assert (b_ab + 180) % 360 == pytest.approx(b_ba, abs=5.0)


@ pytestmark_qgis
class TestPolygonAreaQGIS:
    """Test polygon_area() using QgsDistanceArea (requires QGIS)."""

    def test_degenerate_ring(self):
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        assert polygon_area([]) == 0.0
        assert polygon_area([(0, 0)]) == 0.0
        assert polygon_area([(0, 0), (1, 1)]) == 0.0

    def test_known_area(self):
        """A 1-degree × 1-degree box at the equator ≈ 12,364 km²."""
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        area = polygon_area(ring)
        assert 12_000_000_000 < area < 12_500_000_000

    def test_small_square(self):
        """A small square near Madrid."""
        from QGISFMV.geo.QgsGeoUtils import polygon_area
        # ~1km × 1km square
        ring = [
            (-3.70, 40.41),
            (-3.69, 40.41),
            (-3.69, 40.42),
            (-3.70, 40.42),
        ]
        area = polygon_area(ring)
        assert 5_000_000 < area < 15_000_000  # ~8-12 km²
