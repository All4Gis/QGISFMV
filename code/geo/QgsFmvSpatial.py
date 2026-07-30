# -*- coding: utf-8 -*-
"""Pure spatial helpers (no QGIS dependency) for geofence, seek, and detections."""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple

Point2 = Tuple[float, float]
Sample3 = Tuple[float, float, float]  # lon, lat, time_sec


def point_in_ring(lon: float, lat: float, ring: Sequence[Point2]) -> bool:
    """Ray-casting point-in-polygon. *ring* is ``[(lon, lat), ...]`` (open or closed)."""
    if ring is None or len(ring) < 3:
        return False
    pts = list(ring)
    if pts[0] != pts[-1]:
        pts = pts + [pts[0]]
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = float(pts[i][0]), float(pts[i][1])
        xj, yj = float(pts[j][0]), float(pts[j][1])
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-15) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def haversine_m(a: Point2, b: Point2) -> float:
    """Great-circle distance in meters between two WGS84 points."""
    lon1, lat1 = math.radians(float(a[0])), math.radians(float(a[1]))
    lon2, lat2 = math.radians(float(b[0])), math.radians(float(b[1]))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    return 2.0 * 6371008.8 * math.asin(min(1.0, math.sqrt(h)))


def initial_bearing_deg(a: Point2, b: Point2) -> float:
    """Forward azimuth in degrees from *a* → *b* (0 = North, 90 = East)."""
    lon1, lat1 = math.radians(float(a[0])), math.radians(float(a[1]))
    lon2, lat2 = math.radians(float(b[0])), math.radians(float(b[1]))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(
        dlon
    )
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360.0) % 360.0


def format_distance_m(meters: float) -> str:
    """Human-readable distance (``123 m`` / ``1.2 km``)."""
    try:
        m = float(meters)
    except (TypeError, ValueError):
        return "?"
    if not math.isfinite(m):
        return "?"
    if abs(m) < 1000.0:
        return f"{m:.0f} m"
    return f"{m / 1000.0:.1f} km"


def next_lookback_after(
    lon: float,
    lat: float,
    samples: Sequence,
    after_sec: float,
    cluster_dt: float = 2.0,
) -> Optional[tuple]:
    """First lookback/FOV hit at or after *after_sec*, or ``None``."""
    hits = lookback_samples(lon, lat, samples, cluster_dt=cluster_dt, max_hits=80)
    after = float(after_sec or 0.0)
    for sample in hits:
        if float(sample[2]) + 1e-6 >= after:
            return sample
    return None


def target_cue_state(
    pin_lon: float,
    pin_lat: float,
    from_lon: float,
    from_lat: float,
    time_sec: float,
    samples: Sequence = (),
    footprint_ring=None,
) -> dict:
    """Compute HUD cue fields for a pinned target.

    Returns keys: ``distance_m``, ``bearing_deg``, ``in_fov``, ``next_time_sec``,
    ``eta_sec``, ``label``.
    """
    dist = haversine_m((from_lon, from_lat), (pin_lon, pin_lat))
    brng = initial_bearing_deg((from_lon, from_lat), (pin_lon, pin_lat))
    in_fov = bool(
        footprint_ring
        and len(footprint_ring) >= 3
        and point_in_ring(pin_lon, pin_lat, footprint_ring)
    )
    next_t = None
    eta = None
    if not in_fov and samples:
        nxt = next_lookback_after(pin_lon, pin_lat, samples, time_sec)
        if nxt is not None:
            next_t = float(nxt[2])
            eta = max(0.0, next_t - float(time_sec or 0.0))
    if in_fov:
        label = f"TGT {format_distance_m(dist)} / {brng:03.0f}° / IN FOV"
    elif next_t is not None:
        label = (
            f"TGT {format_distance_m(dist)} / {brng:03.0f}° / "
            f"FOV@{next_t:.1f}s (+{eta:.1f}s)"
        )
    else:
        label = f"TGT {format_distance_m(dist)} / {brng:03.0f}°"
    return {
        "distance_m": dist,
        "bearing_deg": brng,
        "in_fov": in_fov,
        "next_time_sec": next_t,
        "eta_sec": eta,
        "label": label,
    }


def nearest_sample(
    lon: float, lat: float, samples: Sequence[Sample3]
) -> Optional[Sample3]:
    """Return the nearest ``(lon, lat, time_sec)`` sample, or None if empty."""
    if not samples:
        return None
    best = None
    best_d = float("inf")
    for sample in samples:
        d = haversine_m((lon, lat), (sample[0], sample[1]))
        if d < best_d:
            best_d = d
            best = sample
    return best


def box_center(box) -> Point2:
    """Return pixel center ``(x, y)`` of an ``(x0, y0, x1, y1)`` box."""
    x0, y0, x1, y1 = box[:4]
    return (0.5 * (float(x0) + float(x1)), 0.5 * (float(y0) + float(y1)))


def image_xy_to_latlon(gt, x: float, y: float) -> Optional[Point2]:
    """Project image pixel through a 3×3 GCP transform → ``(lat, lon)``.

    Matches ``VideoUtils.GetTransf`` / ``GetPointCommonCoords`` conventions.
    """
    if gt is None:
        return None
    try:
        import numpy as np

        world = np.asarray(np.dot(gt, [float(x), float(y), 1.0]), dtype=float)
        scalar = float(world[2])
        if abs(scalar) < 1e-12:
            return None
        lat = float(world[0] / scalar)
        lon = float(world[1] / scalar)
        if not (math.isfinite(lat) and math.isfinite(lon)):
            return None
        return lat, lon
    except Exception:
        return None


def metadata_lat_lon(
    metadata_dict, prefer_frame_center: bool = True
) -> Optional[Point2]:
    """Extract ``(lat, lon)`` from a MetadataList-style dict."""
    if not metadata_dict:
        return None
    lat = lon = None
    lat_keys = (
        ("frame center latitude", "sensor latitude")
        if prefer_frame_center
        else ("sensor latitude", "frame center latitude")
    )
    lon_keys = (
        ("frame center longitude", "sensor longitude")
        if prefer_frame_center
        else ("sensor longitude", "frame center longitude")
    )
    for _key, val in metadata_dict.items():
        try:
            name = str(val[0]).lower()
            num = float(val[1])
        except (TypeError, ValueError, IndexError):
            continue
        for token in lat_keys:
            if token in name and lat is None:
                lat = num
        for token in lon_keys:
            if token in name and lon is None:
                lon = num
    if lat is None or lon is None:
        return None
    return lat, lon


def close_ring(ring: Iterable[Point2]) -> list:
    """Return a closed ring copy."""
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) >= 3 and pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def detections_inside_ring(detections_by_class, ring) -> list:
    """Return ``[(class_name, point_dict), ...]`` for detections inside *ring*.

    *detections_by_class* maps class name → list of dicts with ``lon``/``lat``.
    """
    if not detections_by_class or not ring:
        return []
    hits = []
    for cls, points in detections_by_class.items():
        for p in points or []:
            try:
                lon = float(p["lon"])
                lat = float(p["lat"])
            except (KeyError, TypeError, ValueError):
                continue
            if point_in_ring(lon, lat, ring):
                hits.append((str(cls), p))
    return hits


def lookback_samples(
    lon: float,
    lat: float,
    samples: Sequence,
    cluster_dt: float = 2.0,
    max_hits: int = 40,
    proximity_m: float = 80.0,
) -> list:
    """Return samples when the sensor FOV covered ``(lon, lat)``.

    Prefer footprint containment. If no footprints exist in the index, fall
    back to samples whose platform/frame-center is within *proximity_m*.

    Hits are clustered by *cluster_dt* seconds (keep first of each cluster).
    Each item is the original sample tuple ``(lon, lat, time_sec, ring|None)``.
    """
    if not samples:
        return []
    lon, lat = float(lon), float(lat)
    hits = []
    any_ring = False
    for sample in samples:
        ring = sample[3] if len(sample) > 3 else None
        if ring and len(ring) >= 3:
            any_ring = True
            if point_in_ring(lon, lat, ring):
                hits.append(sample)
    if not hits and not any_ring:
        # No FOV geometry recorded — proximity fallback along the track.
        for sample in samples:
            if haversine_m((lon, lat), (sample[0], sample[1])) <= proximity_m:
                hits.append(sample)

    if not hits:
        return []

    hits.sort(key=lambda s: float(s[2]))
    clustered = []
    last_t = None
    for sample in hits:
        t = float(sample[2])
        if last_t is not None and (t - last_t) < float(cluster_dt):
            continue
        clustered.append(sample)
        last_t = t
        if len(clustered) >= int(max_hits):
            break
    return clustered
