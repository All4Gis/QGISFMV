# -*- coding: utf-8 -*-
"""
Consolidated geodesic utilities for QGISFMV.

Uses PyQGIS ``QgsDistanceArea`` for ellipsoidal WGS84 distance, bearing,
and area calculations.  Pure-Python ``destination()`` is provided because
QGIS has no direct equivalent for great-circle destination.

All QGIS objects are created lazily on first use, so this module can be
safely imported before ``QgsApplication`` is fully initialized.
"""

from __future__ import annotations

from math import degrees, radians, sin, cos, asin, atan2
from typing import Sequence

from QGISFMV.utils.logging import log

_EARTH_MEAN_RADIUS = 6371008.8

# ---------------------------------------------------------------------------
# Lazy singleton — created on first call, not at import time.
# ---------------------------------------------------------------------------
_measure = None


def _get_measure():
    """Return (and lazily initialize) the QgsDistanceArea singleton."""
    global _measure
    if _measure is not None:
        return _measure

    from qgis.core import (
        QgsDistanceArea,
        QgsCoordinateReferenceSystem,
        QgsProject,
    )

    _measure = QgsDistanceArea()
    try:
        crs = QgsCoordinateReferenceSystem("EPSG:4326")
        ctx = QgsProject.instance().transformContext()
        _measure.setSourceCrs(crs, ctx)
        # Geographic CRS without an explicit ellipsoid returns 0 from
        # measureLine/measureArea. ``ellipsoidAcronym()`` is often empty for
        # EPSG:4326, so force WGS84.
        if not _measure.setEllipsoid("WGS84"):
            _measure.setEllipsoid("EPSG:7030")
    except Exception as _exc:
        log.debug("QgsDistanceArea CRS setup failed, using planar fallback: %s", _exc)

    return _measure


def _haversine_m(point1: Sequence[float], point2: Sequence[float]) -> float:
    """Great-circle distance in meters (fallback when QGIS measure fails)."""
    lon1, lat1 = radians(float(point1[0])), radians(float(point1[1]))
    lon2, lat2 = radians(float(point2[0])), radians(float(point2[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2.0) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2.0) ** 2
    return 2.0 * _EARTH_MEAN_RADIUS * asin(min(1.0, a**0.5))


def _spherical_ring_area_m2(coordinates: Sequence[Sequence[float]]) -> float:
    """Spherical polygon area (m²) via spherical excess; fallback only."""
    if len(coordinates) < 3:
        return 0.0
    rad = [(radians(float(c[0])), radians(float(c[1]))) for c in coordinates]
    if rad[0] != rad[-1]:
        rad.append(rad[0])
    total = 0.0
    for i in range(len(rad) - 1):
        lon1, lat1 = rad[i]
        lon2, lat2 = rad[i + 1]
        total += (lon2 - lon1) * (2.0 + sin(lat1) + sin(lat2))
    return abs(total) * _EARTH_MEAN_RADIUS * _EARTH_MEAN_RADIUS / 2.0


# ---------------------------------------------------------------------------
# distance(point1, point2) -> float  (meters)
#   point = (lon, lat) or [lon, lat] — WGS84 degrees
# ---------------------------------------------------------------------------
def distance(point1: Sequence[float], point2: Sequence[float]) -> float:
    """
    Geodesic distance in meters between two WGS84 points.

    Uses PyQGIS ``QgsDistanceArea.measureLine()`` for ellipsoidal
    accuracy (Vincenty-level).  Falls back to Haversine if QGIS
    returns 0 for distinct points (missing ellipsoid) or is unavailable.

    Args:
        point1: (lon, lat) or [lon, lat] in WGS84 degrees.
        point2: (lon, lat) or [lon, lat] in WGS84 degrees.

    Returns:
        Distance in meters (float).
    """
    try:
        from qgis.core import QgsPointXY

        p1 = QgsPointXY(float(point1[0]), float(point1[1]))
        p2 = QgsPointXY(float(point2[0]), float(point2[1]))
        meters = float(_get_measure().measureLine(p1, p2))
        if meters > 0.0 or p1 == p2:
            return meters
    except Exception as exc:
        log.debug("QgsDistanceArea.measureLine failed, using Haversine: %s", exc)
    return _haversine_m(point1, point2)


# ---------------------------------------------------------------------------
# bearing(point1, point2) -> float  (degrees, 0-360)
# ---------------------------------------------------------------------------
def bearing(point1: Sequence[float], point2: Sequence[float]) -> float:
    """
    Initial bearing (azimuth) in degrees from point1 to point2.

    Args:
        point1: (lon, lat) or [lon, lat] in WGS84 degrees.
        point2: (lon, lat) or [lon, lat] in WGS84 degrees.

    Returns:
        Bearing in degrees, normalized to [0, 360).
    """
    from qgis.core import QgsPointXY

    p1 = QgsPointXY(float(point1[0]), float(point1[1]))
    p2 = QgsPointXY(float(point2[0]), float(point2[1]))
    b = _get_measure().bearing(p1, p2)
    return (degrees(b) + 360) % 360


# ---------------------------------------------------------------------------
# destination(point, distance, bearing) -> (lon, lat)
#   Pure-Python great-circle — no QGIS equivalent.
# ---------------------------------------------------------------------------
def destination(
    point: Sequence[float], distance_m: float, bearing_deg: float
) -> tuple[float, float]:
    """
    Destination point given a start point, distance, and bearing.

    Uses the great-circle (Haversine) formula.  There is no direct
    QGIS equivalent for this calculation.

    Args:
        point: (lon, lat) or [lon, lat] in WGS84 degrees.
        distance_m: Distance to travel in meters.
        bearing_deg: Initial bearing in degrees (0=North, 90=East).

    Returns:
        (lon, lat) tuple of the destination point in WGS84 degrees.
    """
    lon1, lat1 = (radians(c) for c in point)
    rb = radians(bearing_deg)
    delta = distance_m / _EARTH_MEAN_RADIUS

    lat2 = asin(sin(lat1) * cos(delta) + cos(lat1) * sin(delta) * cos(rb))
    num = sin(rb) * sin(delta) * cos(lat1)
    den = cos(delta) - sin(lat1) * sin(lat2)
    lon2 = lon1 + atan2(num, den)

    return ((degrees(lon2) + 540) % 360 - 180, degrees(lat2))


# ---------------------------------------------------------------------------
# polygon_area(ring) -> float  (square meters)
# ---------------------------------------------------------------------------
def polygon_area(coordinates: Sequence[Sequence[float]]) -> float:
    """
    Geodesic area of a polygon ring in square meters (WGS84).

    Uses PyQGIS ``QgsDistanceArea.measureArea()`` for ellipsoidal
    accuracy. Falls back to spherical excess if QGIS returns 0.

    Args:
        coordinates: List of (lon, lat) tuples forming the exterior ring.
                     Must have at least 3 points.

    Returns:
        Area in square meters (float).  Returns 0.0 for degenerate rings.
    """
    ring = [c for c in coordinates if c is not None and c[0] is not None]
    if len(ring) < 3:
        return 0.0

    try:
        from qgis.core import QgsPointXY, QgsGeometry

        points = [QgsPointXY(float(c[0]), float(c[1])) for c in ring]
        if points[0] != points[-1]:
            points.append(QgsPointXY(points[0]))
        geom = QgsGeometry.fromPolygonXY([points])
        area_m2 = abs(float(_get_measure().measureArea(geom)))
        if area_m2 > 0.0:
            return area_m2
    except Exception as exc:
        log.debug("QgsDistanceArea.measureArea failed, using spherical: %s", exc)

    return _spherical_ring_area_m2(ring)
