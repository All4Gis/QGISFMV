# -*- coding: utf-8 -*-
"""Per-class detection scorers (building, road, vehicle, person, fire, smoke, flood)."""

from __future__ import annotations

import numpy as np

from QGISFMV.utils.logging import log
from QGISFMV.video.filters.QgsFmvFilterCore import (
    FilterCore,
    _HAS_NDIMAGE,
    _get_cv2_module,
    _ndimage,
)
from QGISFMV.video.filters.QgsFmvDetectionPipeline import (
    _detect_fallback_generic,
    _motion_boost,
    _run_opencv_pipeline_for,
)


def _building_structure_score(rgb):
    r, g, b, lum, chroma, exg = FilterCore.rgb_channels(rgb)
    mag = FilterCore.edge_mag(lum)
    peak = float(np.percentile(mag, 92)) + 1e-6
    # Buildings: textured, low vegetation, moderate saturation, structured edges.
    return (
        np.clip(mag / peak, 0, 1)
        * (1.0 - np.clip(np.maximum(exg, 0.0) / 55.0, 0, 1))
        * np.clip(1.0 - chroma / 70.0, 0.15, 1.0)
        * np.clip(1.0 - np.abs(lum - 140.0) / 130.0, 0.2, 1.0)
    )


def _road_surface_score(rgb):
    _r, _g, _b, lum, chroma, exg = FilterCore.rgb_channels(rgb)
    h, s, v = FilterCore.rgb_to_hsv(rgb)
    # Asphalt: low saturation, mid value, not green.
    score = (
        np.clip(1.0 - s / 55.0, 0, 1)
        * np.clip(1.0 - np.abs(v - 120.0) / 90.0, 0, 1)
        * np.clip(1.0 - np.maximum(exg, 0.0) / 45.0, 0, 1)
        * np.clip(1.0 - chroma / 45.0, 0, 1)
    )
    return FilterCore.smooth(score, sigma=1.4)


def _vehicle_blob_score(rgb):
    """FMV-friendly vehicle score: local contrast blobs (light or dark), not road-only."""
    _r, _g, _b, lum, _chroma, exg = FilterCore.rgb_channels(rgb)
    h, w = lum.shape
    sigma = max(4.0, min(h, w) / 72.0)
    local = FilterCore.smooth(lum, sigma=sigma)
    local_contrast = np.abs(lum - local)
    p95 = float(np.percentile(local_contrast, 95)) + 1e-6
    contrast = np.clip(local_contrast / p95, 0, 1)

    edges = FilterCore.edge_mag(lum)
    peak_e = float(np.percentile(edges, 90)) + 1e-6
    edge_norm = np.clip(edges / peak_e, 0, 1)

    not_veg = np.clip(1.0 - np.maximum(exg, 0.0) / 55.0, 0, 1)
    road = _road_surface_score(rgb)
    motion = _motion_boost(lum)

    try:
        from QGISFMV.video.filters.QgsFmvFilterTuning import is_aerial_profile

        road_mix = (0.30 + 0.70 * road) if is_aerial_profile() else (0.55 + 0.45 * road)
    except Exception as _exc:
        log.debug("is_aerial_profile import failed, using default road mix: %s", _exc)
        road_mix = 0.55 + 0.45 * road

    score = contrast * edge_norm * not_veg * road_mix * (0.82 + 0.18 * motion)
    return np.clip(score, 0, 1)


def _building_detect_opencv(_rgb, score):
    cv2 = _get_cv2_module()
    gray = cv2.cvtColor(_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 25, 95)
    edge_norm = cv2.GaussianBlur(edges.astype(np.float64) / 255.0, (5, 5), 0)
    merged = score * (0.50 + 0.50 * edge_norm)
    out, boxes, _labels, _mask = _run_opencv_pipeline_for(
        "building",
        cv2,
        merged,
    )
    return out, boxes


def _building_detect_fallback(_rgb, score):
    return _detect_fallback_generic("building", score)


def _road_detect_opencv(_rgb, score):
    cv2 = _get_cv2_module()
    h, w = score.shape
    kw = max(15, w // 18)
    kh = max(3, h // 80 | 1)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
    out, boxes, _labels, mask_u8 = _run_opencv_pipeline_for(
        "road",
        cv2,
        score,
        close_kernel=close_kernel,
    )
    if boxes:
        keep = np.zeros(score.shape, dtype=bool)
        for x0, y0, x1, y1 in boxes:
            keep[y0:y1, x0:x1] = True
        keep |= (mask_u8 > 0) & (score > 0.50)
        out = score * np.clip(keep.astype(np.float64) + 0.18, 0, 1)
    return out, boxes


def _road_detect_fallback(_rgb, score):
    out, boxes = _detect_fallback_generic("road", score)
    if boxes:
        keep = np.zeros(score.shape, dtype=bool)
        for x0, y0, x1, y1 in boxes:
            keep[y0:y1, x0:x1] = True
        keep |= score > 0.55
        out = score * np.clip(keep.astype(np.float64) + 0.18, 0, 1)
    return out, boxes


def _vehicle_detect_opencv(_rgb, score):
    cv2 = _get_cv2_module()
    gray = cv2.cvtColor(_rgb, cv2.COLOR_RGB2GRAY)
    ksize = max(9, int(min(gray.shape) / 36) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    contrast = np.maximum(tophat, blackhat).astype(np.float64)
    p95 = float(np.percentile(contrast, 95)) + 1e-6
    contrast = np.clip(contrast / p95, 0, 1)
    edges = cv2.Canny(gray, 35, 110)
    edge_norm = cv2.GaussianBlur(edges.astype(np.float64) / 255.0, (3, 3), 0)
    merged = score * (0.50 + 0.50 * edge_norm) * (0.55 + 0.45 * contrast)
    out, boxes, _labels, _mask = _run_opencv_pipeline_for(
        "vehicle",
        cv2,
        merged,
    )
    return out, boxes


def _vehicle_detect_fallback(_rgb, score):
    return _detect_fallback_generic("vehicle", score)


def _person_score(rgb):
    _r, _g, _b, lum, _chroma, exg = FilterCore.rgb_channels(rgb)
    if _HAS_NDIMAGE:
        gx = np.abs(_ndimage.sobel(lum, axis=1, mode="nearest"))
        gy = np.abs(_ndimage.sobel(lum, axis=0, mode="nearest"))
    else:
        gx = np.abs(np.diff(lum, axis=1, prepend=lum[:, :1]))
        gy = np.abs(np.diff(lum, axis=0, prepend=lum[:1, :]))
    vert = gy * np.clip(gy / (gx + 1e-6), 0.8, 4.0)
    peak = float(np.percentile(vert, 92)) + 1e-6
    motion = _motion_boost(lum)
    return np.clip(
        np.clip(vert / peak, 0, 1)
        * np.clip(1.0 - np.abs(lum - 120.0) / 120.0, 0.2, 1.0)
        * np.clip(1.0 - np.maximum(exg, 0) / 65.0, 0.25, 1.0)
        * (0.78 + 0.22 * motion),
        0,
        1,
    )


def _person_detect_opencv(_rgb, score):
    cv2 = _get_cv2_module()
    gray = cv2.cvtColor(_rgb, cv2.COLOR_RGB2GRAY)
    h = gray.shape[0]
    kh = max(9, h // 36 | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, kh))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel).astype(np.float64)
    p90 = float(np.percentile(tophat, 90)) + 1e-6
    merged = score * np.clip(0.65 + 0.35 * (tophat / p90), 0, 1)
    out, boxes, _labels, _mask = _run_opencv_pipeline_for(
        "person",
        cv2,
        merged,
    )
    return out, boxes


def _person_detect_fallback(_rgb, score):
    return _detect_fallback_generic("person", score)


def _fire_score(rgb):
    h, s, v = FilterCore.rgb_to_hsv(rgb)
    r, g, b, lum, _c, _e = FilterCore.rgb_channels(rgb)
    warm = ((h <= 22) | (h >= 160)) & (s >= 70) & (v >= 80)
    score = warm.astype(np.float64)
    score *= np.clip((r - b) / 40.0, 0, 1)
    score *= np.clip((r - 60.0) / 120.0, 0, 1)
    score *= np.clip(lum / 55.0, 0, 1)
    return np.clip(score, 0, 1)


def _fire_detect_opencv(_rgb, score):
    cv2 = _get_cv2_module()
    hsv = cv2.cvtColor(_rgb, cv2.COLOR_RGB2HSV)
    mask1 = cv2.inRange(
        hsv,
        np.array([0, 70, 80], dtype=np.uint8),
        np.array([22, 255, 255], dtype=np.uint8),
    )
    mask2 = cv2.inRange(
        hsv,
        np.array([160, 70, 80], dtype=np.uint8),
        np.array([179, 255, 255], dtype=np.uint8),
    )
    warm = cv2.bitwise_or(mask1, mask2).astype(np.float64) / 255.0
    merged = np.maximum(score, warm * 0.85)
    out, boxes, _labels, mask_u8 = _run_opencv_pipeline_for(
        "fire",
        cv2,
        merged,
    )
    if not boxes and not np.any(mask_u8):
        out = merged * 0.0
    return out, boxes


def _fire_detect_fallback(_rgb, score):
    out, boxes = _detect_fallback_generic("fire", score)
    if not boxes and float(np.max(score)) < 0.12:
        out = score * 0.0
    return out, boxes


def _smoke_score(rgb):
    h, s, v = FilterCore.rgb_to_hsv(rgb)
    _r, _g, _b, lum, _chroma, exg = FilterCore.rgb_channels(rgb)
    edges = FilterCore.edge_mag(lum)
    peak_e = float(np.percentile(edges, 88)) + 1e-6
    score = (
        np.clip(1.0 - s / 45.0, 0, 1)
        * np.clip((v - 100.0) / 90.0, 0, 1)
        * np.clip((235.0 - v) / 90.0, 0, 1)
        * np.clip(1.0 - edges / peak_e, 0, 1)
        * np.clip(1.0 - np.maximum(exg, 0) / 45.0, 0, 1)
    )
    blur = FilterCore.smooth(lum, sigma=2.0)
    score *= np.clip(1.0 - np.abs(lum - blur) / 30.0, 0, 1)
    return np.clip(score, 0, 1)


def _smoke_detect_opencv(_rgb, score):
    cv2 = _get_cv2_module()
    hsv = cv2.cvtColor(_rgb, cv2.COLOR_RGB2HSV)
    color = (
        cv2.inRange(
            hsv,
            np.array([0, 0, 100], dtype=np.uint8),
            np.array([180, 45, 235], dtype=np.uint8),
        ).astype(np.float64)
        / 255.0
    )
    gray = cv2.cvtColor(_rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 40, 120).astype(np.float64) / 255.0
    merged = score * (0.55 + 0.45 * color) * (1.0 - 0.75 * edges)
    out, boxes, _labels, _mask = _run_opencv_pipeline_for(
        "smoke",
        cv2,
        merged,
    )
    return out, boxes


def _smoke_detect_fallback(_rgb, score):
    return _detect_fallback_generic("smoke", score)


def _flood_score(rgb):
    h, s, v = FilterCore.rgb_to_hsv(rgb)
    r, g, b, lum, _chroma, exg = FilterCore.rgb_channels(rgb)
    water_h = (h >= 85) & (h <= 135)
    score = water_h.astype(np.float64)
    score *= np.clip((b - r) / 25.0, 0, 1)
    score *= np.clip(s / 30.0, 0, 1) * np.clip(1.0 - s / 160.0, 0, 1)
    score *= np.clip(1.0 - np.abs(v - 130.0) / 100.0, 0, 1)
    score *= np.clip(1.0 - np.maximum(exg, 0) / 40.0, 0, 1)
    return np.clip(score, 0, 1)


def _flood_detect_opencv(_rgb, score):
    cv2 = _get_cv2_module()
    hsv = cv2.cvtColor(_rgb, cv2.COLOR_RGB2HSV)
    color = (
        cv2.inRange(
            hsv,
            np.array([85, 20, 35], dtype=np.uint8),
            np.array([135, 170, 220], dtype=np.uint8),
        ).astype(np.float64)
        / 255.0
    )
    merged = np.maximum(score, color * 0.90)
    h, w = score.shape
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (max(7, w // 40 | 1), max(7, h // 40 | 1))
    )
    out, boxes, _labels, _mask = _run_opencv_pipeline_for(
        "flood",
        cv2,
        merged,
        close_kernel=close_kernel,
    )
    return out, boxes


def _flood_detect_fallback(_rgb, score):
    return _detect_fallback_generic("flood", score)
