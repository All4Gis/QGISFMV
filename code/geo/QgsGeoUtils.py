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
        if _measure.sourceCrs().isGeographic():
            _measure.setEllipsoid(_measure.sourceCrs().ellipsoidAcronym())
    except Exception as _exc:
        log.debug('QgsDistanceArea CRS setup failed, using planar fallback: %s', _exc)

    return _measure


# ---------------------------------------------------------------------------
# distance(point1, point2) -> float  (meters)
#   point = (lon, lat) or [lon, lat] — WGS84 degrees
# ---------------------------------------------------------------------------
def distance(point1: Sequence[float], point2: Sequence[float]) -> float:
    """
    Geodesic distance in meters between two WGS84 points.

    Uses PyQGIS ``QgsDistanceArea.measureLine()`` for ellipsoidal
    accuracy (Vincenty-level).  Falls back to planar if QGIS
    runtime is not available.

    Args:
        point1: (lon, lat) or [lon, lat] in WGS84 degrees.
        point2: (lon, lat) or [lon, lat] in WGS84 degrees.

    Returns:
        Distance in meters (float).
    """
    from qgis.core import QgsPointXY

    p1 = QgsPointXY(float(point1[0]), float(point1[1]))
    p2 = QgsPointXY(float(point2[0]), float(point2[1]))
    return _get_measure().measureLine(p1, p2)


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
_EARTH_MEAN_RADIUS = 6371008.8


def destination(point: Sequence[float], distance_m: float, bearing_deg: float) -> tuple[float, float]:
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
    accuracy.

    Args:
        coordinates: List of (lon, lat) tuples forming the exterior ring.
                     Must have at least 3 points.

    Returns:
        Area in square meters (float).  Returns 0.0 for degenerate rings.
    """
    if len(coordinates) < 3:
        return 0.0

    from qgis.core import QgsPointXY, QgsGeometry

    points = [QgsPointXY(float(c[0]), float(c[1])) for c in coordinates]
    geom = QgsGeometry.fromPolygonXY([points])
    return abs(_get_measure().measureArea(geom))
