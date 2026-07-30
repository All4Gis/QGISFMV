# -*- coding: utf-8 -*-
"""Shared OpenCV / numpy detection engine: temporal smoothing, overlays, CC pipelines."""

from __future__ import annotations

import numpy as np

import QGISFMV.video.filters.QgsFmvDetectionGeometry as _geom
from QGISFMV.utils.logging import log
from QGISFMV.video.filters.QgsFmvDetectionGeometry import (
    _assign_track_ids,
    _multiscale_score,
    _nms_boxes,
    _region_scores,
)
from QGISFMV.video.filters.QgsFmvFilterCore import (
    _HAS_NDIMAGE,
    FilterCore,
    _get_cv2_module,
    opencv_available,
)


def _clahe_rgb(rgb):
    """Light CLAHE on L channel — helps small aerial objects in haze."""
    cv2 = _get_cv2_module()
    if cv2 is None:
        return rgb
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)


def _ema_score(name, score, alpha=0.40):
    """Temporal exponential average — stabilizes flicker across frames."""
    prev = _geom._detection_ema.get(name)
    if prev is None or prev.shape != score.shape:
        _geom._detection_ema[name] = score.astype(np.float32)
        return _geom._detection_ema[name]
    out = alpha * score + (1.0 - alpha) * prev
    _geom._detection_ema[name] = out
    return out


def _motion_boost(lum):
    """Return [0,1] motion magnitude vs previous detection frame."""
    cur = FilterCore.smooth(lum, sigma=1.0)
    if (
        _geom._detection_prev_gray is None
        or _geom._detection_prev_gray.shape != cur.shape
    ):
        _geom._detection_prev_gray = cur
        return np.zeros_like(cur)
    diff = np.abs(cur - _geom._detection_prev_gray)
    _geom._detection_prev_gray = cur
    peak = float(np.percentile(diff, 95)) + 1e-6
    return np.clip(diff / peak, 0.0, 1.0)


def _confidence_overlay(
    rgb,
    score,
    tint_rgb,
    label,
    abs_thr=0.45,
    boxes=None,
    box_color=None,
    box_scores=None,
    track_ids=None,
    adaptive_min_cov=1.5,
    weight_gate=0.35,
    adaptive_percentile=86,
    engine=None,
):
    """Pro overlay: high-confidence pixels with adaptive fallback when too sparse."""
    s = np.clip(np.asarray(score, dtype=np.float64), 0.0, None)
    s = FilterCore.smooth(s, sigma=1.1)
    # Soft weight above absolute threshold (not "always color N% of frame").
    weight = np.clip((s - abs_thr) / max(1.0 - abs_thr, 1e-3), 0.0, 1.0)
    weight = FilterCore.smooth(weight, sigma=0.8)
    cov = 100.0 * float(np.mean(weight > weight_gate))
    if cov < adaptive_min_cov:
        pos = s[s > 0.04]
        if pos.size > 32:
            thr = float(np.percentile(pos, adaptive_percentile))
            weight = np.clip((s - thr) / max(1.0 - thr, 1e-3), 0.0, 1.0)
            weight = FilterCore.smooth(weight, sigma=0.8)
            cov = 100.0 * float(np.mean(weight > weight_gate))
    if cov < 0.5 and float(np.max(s)) > 0.05:
        thr = float(np.percentile(s, 88))
        weight = np.clip((s - thr) / max(1.0 - thr, 1e-3), 0.0, 1.0)
        weight = FilterCore.smooth(weight, sigma=0.8)
        cov = 100.0 * float(np.mean(weight > weight_gate))
    tint = np.asarray(tint_rgb, dtype=np.float64)
    base = rgb.astype(np.float64)
    from QGISFMV.utils.constants import (
        CONFIDENCE_BASE_BRIGHTNESS,
        CONFIDENCE_TINT_INTENSITY,
        CONFIDENCE_TINT_RANGE,
    )

    out = base * (
        CONFIDENCE_BASE_BRIGHTNESS + CONFIDENCE_TINT_RANGE * (1.0 - weight[..., None])
    )
    out = out * (1.0 - CONFIDENCE_TINT_INTENSITY * weight[..., None]) + tint * (
        CONFIDENCE_TINT_INTENSITY * weight[..., None]
    )
    out = np.clip(out, 0, 255).astype(np.uint8)
    nboxes = 0
    if boxes:
        from QGISFMV.video.filters.QgsFmvFilterTuning import show_box_confidence

        bc = box_color or (255, 255, 255)
        for idx, (x0, y0, x1, y1) in enumerate(boxes):
            FilterCore.draw_box_numpy(out, x0, y0, x1, y1, bc, thickness=2)
            nboxes += 1
            if opencv_available() and show_box_confidence():
                parts = []
                if track_ids and idx < len(track_ids):
                    parts.append(f"#{track_ids[idx]}")
                if box_scores and idx < len(box_scores):
                    parts.append(f"{int(box_scores[idx] * 100)}%")
                if parts:
                    cv2 = _get_cv2_module()
                    if cv2 is not None:
                        try:
                            cv2.putText(
                                out,
                                " ".join(parts),
                                (int(x0) + 2, max(14, int(y0) - 4)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.45,
                                (255, 255, 255),
                                1,
                                cv2.LINE_AA,
                            )
                        except Exception as exc:
                            log.debug("cv2.putText failed: %s", exc)
    if engine is None:
        engine = "CV" if opencv_available() else ("SCIPY" if _HAS_NDIMAGE else "NUMPY")
    FilterCore.draw_filter_banner(
        out,
        f"{str(label)} [{str(engine)}] det:{nboxes} {float(cov):.0f}%",
        tint_rgb,
    )
    return out, weight


def _opencv_detection_pipeline(
    cv2,
    score,
    *,
    percentile=84,
    default_thr=0.25,
    min_pos=48,
    open_size=3,
    close_size=5,
    close_kernel=None,
    min_area_frac=0.0001,
    max_area_frac=0.5,
    aspect_range=(0.2, 8.0),
    min_extent=0.12,
    max_boxes=40,
    prefer_vertical=False,
    mask_blend=0.45,
    filter_key=None,
):
    """Threshold score map, morph, CC boxes — shared OpenCV detection path."""
    from QGISFMV.video.filters.QgsFmvFilterTuning import apply_aerial_pipeline_kw

    tuned = apply_aerial_pipeline_kw(
        filter_key,
        percentile=percentile,
        default_thr=default_thr,
        min_pos=min_pos,
        min_extent=min_extent,
        min_area_frac=min_area_frac,
        mask_blend=mask_blend,
    )
    percentile = tuned["percentile"]
    default_thr = tuned["default_thr"]
    min_pos = tuned.get("min_pos", min_pos)
    min_extent = tuned["min_extent"]
    min_area_frac = tuned["min_area_frac"]
    mask_blend = tuned["mask_blend"]
    pos = score[score > 0.04]
    thr = float(np.percentile(pos, percentile)) if pos.size > min_pos else default_thr
    mask_u8 = (score > thr).astype(np.uint8) * 255
    k_open = cv2.getStructuringElement(cv2.MORPH_RECT, (open_size, open_size))
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, k_open)
    k_close = close_kernel or cv2.getStructuringElement(
        cv2.MORPH_RECT, (close_size, close_size)
    )
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, k_close)

    h, w = score.shape
    frame = float(h * w)
    boxes = []
    num, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        mask_u8, connectivity=8
    )
    min_area = frame * min_area_frac
    max_area = frame * max_area_frac
    for i in range(1, num):
        area = float(stats[i, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue
        x0 = int(stats[i, cv2.CC_STAT_LEFT])
        y0 = int(stats[i, cv2.CC_STAT_TOP])
        bw = int(stats[i, cv2.CC_STAT_WIDTH])
        bh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if bw < 5 or bh < 5:
            continue
        aspect = bw / float(max(bh, 1))
        if prefer_vertical:
            aspect = bh / float(max(bw, 1))
        if aspect < aspect_range[0] or aspect > aspect_range[1]:
            continue
        extent = area / float(max(bw * bh, 1))
        if extent < min_extent:
            continue
        patch = score[y0 : y0 + bh, x0 : x0 + bw]
        conf = float(patch.mean()) if patch.size else 0.0
        boxes.append((x0, y0, x0 + bw, y0 + bh, conf))
    boxes.sort(key=lambda t: t[4], reverse=True)
    from QGISFMV.video.filters.QgsFmvFilterTuning import box_nms_iou

    cand = boxes[: max_boxes * 2]
    if cand:
        coords = [(a, b, c, d) for a, b, c, d, _ in cand]
        confs = [t[4] for t in cand]
        coords, _confs = _nms_boxes(coords, confs, iou_thresh=box_nms_iou())
        boxes = coords[:max_boxes]
    else:
        boxes = []

    mask_bool = mask_u8 > 0
    if boxes:
        keep = np.zeros(score.shape, dtype=bool)
        for x0, y0, x1, y1 in boxes:
            keep[y0:y1, x0:x1] |= labels[y0:y1, x0:x1] > 0
        out_score = score * np.maximum(
            keep.astype(np.float64), mask_bool.astype(np.float64) * mask_blend
        )
    else:
        out_score = score * mask_bool.astype(np.float64)
    return out_score, boxes, labels, mask_u8


def _fallback_detection_pipeline(
    score,
    *,
    percentile=84,
    default_thr=0.28,
    open_iter=1,
    close_iter=1,
    min_area_frac=0.0001,
    max_area_frac=0.5,
    aspect_range=(0.2, 8.0),
    min_extent=0.12,
    max_boxes=40,
    prefer_vertical=False,
    mask_blend=0.45,
    filter_key=None,
):
    """SciPy/numpy fallback matching the OpenCV detection pipeline."""
    from QGISFMV.video.filters.QgsFmvFilterTuning import apply_aerial_pipeline_kw

    tuned = apply_aerial_pipeline_kw(
        filter_key,
        percentile=percentile,
        default_thr=default_thr,
        min_extent=min_extent,
        min_area_frac=min_area_frac,
        mask_blend=mask_blend,
    )
    percentile = tuned["percentile"]
    default_thr = tuned["default_thr"]
    min_extent = tuned["min_extent"]
    min_area_frac = tuned["min_area_frac"]
    mask_blend = tuned["mask_blend"]
    min_pos = int(tuned.get("min_pos", 48))
    pos = score[score > 0.04]
    thr = float(np.percentile(pos, percentile)) if pos.size > min_pos else default_thr
    mask = FilterCore.morph_mask(
        score > thr, open_iter=open_iter, close_iter=close_iter
    )
    boxes = FilterCore.label_boxes(
        mask,
        min_area_frac=min_area_frac,
        max_area_frac=max_area_frac,
        aspect_range=aspect_range,
        min_extent=min_extent,
        max_boxes=max_boxes * 2,
        prefer_vertical=prefer_vertical,
    )
    if boxes:
        confs = _region_scores(score, boxes)
        from QGISFMV.video.filters.QgsFmvFilterTuning import box_nms_iou

        boxes, _confs = _nms_boxes(boxes, confs, iou_thresh=box_nms_iou())
        boxes = boxes[:max_boxes]
    if boxes:
        keep = np.zeros(score.shape, dtype=bool)
        for x0, y0, x1, y1 in boxes:
            keep[y0:y1, x0:x1] |= mask[y0:y1, x0:x1]
        out_score = score * np.maximum(
            keep.astype(np.float64), mask.astype(np.float64) * mask_blend
        )
    else:
        out_score = score * mask.astype(np.float64)
    return out_score, boxes


def _run_detection(
    rgb,
    score_fn,
    opencv_fn,
    fallback_fn,
    ema_key,
    ema_alpha,
    overlay_kwargs,
    dnn_filter_key=None,
):
    """Run OpenCV detection when available, else scipy/numpy fallback."""
    from QGISFMV.video.filters.QgsFmvFilterTuning import (
        clahe_before_detection,
        dnn_fallback_when_empty,
    )
    from QGISFMV.video.filters.QgsFmvFilterTuning import ema_alpha as tuned_ema_alpha
    from QGISFMV.video.filters.QgsFmvFilterTuning import tune_overlay_options

    overlay_kwargs = tune_overlay_options(dict(overlay_kwargs))
    ema_alpha = tuned_ema_alpha(ema_alpha)
    work_rgb = rgb
    if clahe_before_detection():
        work_rgb = _clahe_rgb(rgb)

    if dnn_filter_key:
        try:
            from QGISFMV.video.dnn.QgsFmvOnnxDetector import try_dnn_detection

            dnn = try_dnn_detection(work_rgb, dnn_filter_key)
            if dnn is not None:
                raw_score, boxes, engine = dnn
                if boxes or not dnn_fallback_when_empty():
                    score = _ema_score(ema_key, raw_score, alpha=ema_alpha)
                    track_ids = _assign_track_ids(ema_key, boxes)
                    opts = dict(overlay_kwargs)
                    opts["boxes"] = boxes
                    opts["box_scores"] = _region_scores(score, boxes) if boxes else None
                    opts["track_ids"] = track_ids
                    opts["engine"] = engine
                    tint = opts.pop("tint_rgb")
                    label = opts.pop("label")
                    result, weight = _confidence_overlay(
                        rgb, score, tint, label, **opts
                    )
                    _notify_map_detections(
                        ema_key, boxes, track_ids, opts.get("box_scores")
                    )
                    return result, weight, engine, boxes
        except Exception as _exc:
            log.debug("DNN detection failed, falling back to classical: %s", _exc)
    engine = "CV"
    score_map = _multiscale_score(work_rgb, score_fn)
    try:
        if _get_cv2_module() is not None:
            raw_score, boxes = opencv_fn(work_rgb, score_map)
        else:
            raise RuntimeError("OpenCV unavailable")
    except Exception as _exc:
        log.debug("OpenCV detection pipeline failed, using fallback: %s", _exc)
        engine = "SCIPY" if _HAS_NDIMAGE else "NUMPY"
        raw_score, boxes = fallback_fn(work_rgb, score_map)
    score = _ema_score(ema_key, raw_score, alpha=ema_alpha)
    track_ids = _assign_track_ids(ema_key, boxes)
    opts = dict(overlay_kwargs)
    opts["boxes"] = boxes
    opts["box_scores"] = _region_scores(score, boxes) if boxes else None
    opts["track_ids"] = track_ids
    opts["engine"] = engine
    tint = opts.pop("tint_rgb")
    label = opts.pop("label")
    result, weight = _confidence_overlay(rgb, score, tint, label, **opts)
    _notify_map_detections(ema_key, boxes, track_ids, opts.get("box_scores"))
    return result, weight, engine, boxes


def _notify_map_detections(class_name, boxes, track_ids, scores):
    """Best-effort publish of detection boxes onto the map (georeferenced)."""
    if not boxes:
        return
    try:
        from QGISFMV.video.filters.QgsFmvDetectionMap import notify_detections

        notify_detections(class_name, boxes, track_ids=track_ids, scores=scores)
    except Exception as exc:
        log.debug("notify_detections failed: %s", exc)


# Filter-specific pipeline parameter defaults — avoids repeating long kwarg
# lists in every _detect_opencv_X / _detect_fallback_X pair.
_FALLBACK_FILTER_CONFIG = {
    "building": dict(
        percentile=82,
        default_thr=0.28,
        open_iter=1,
        close_iter=2,
        min_area_frac=0.0012,
        max_area_frac=0.35,
        aspect_range=(0.25, 5.0),
        min_extent=0.16,
        max_boxes=40,
        mask_blend=0.0,
        filter_key="building",
    ),
    "road": dict(
        percentile=78,
        default_thr=0.32,
        open_iter=1,
        close_iter=3,
        min_area_frac=0.0015,
        max_area_frac=0.55,
        aspect_range=(1.2, 30.0),
        min_extent=0.10,
        max_boxes=25,
        mask_blend=0.35,
        filter_key="road",
    ),
    "vehicle": dict(
        percentile=84,
        default_thr=0.22,
        open_iter=1,
        close_iter=1,
        min_area_frac=0.00005,
        max_area_frac=0.025,
        aspect_range=(0.35, 5.0),
        min_extent=0.10,
        max_boxes=60,
        filter_key="vehicle",
    ),
    "person": dict(
        percentile=82,
        default_thr=0.22,
        open_iter=1,
        close_iter=2,
        min_area_frac=0.0002,
        max_area_frac=0.06,
        aspect_range=(1.5, 7.0),
        min_extent=0.14,
        max_boxes=30,
        prefer_vertical=True,
        mask_blend=0.0,
        filter_key="person",
    ),
    "fire": dict(
        percentile=78,
        default_thr=0.18,
        open_iter=1,
        close_iter=2,
        min_area_frac=0.00015,
        max_area_frac=0.35,
        aspect_range=(0.2, 8.0),
        min_extent=0.12,
        max_boxes=25,
        mask_blend=0.35,
        filter_key="fire",
    ),
    "smoke": dict(
        percentile=80,
        default_thr=0.24,
        open_iter=1,
        close_iter=3,
        min_area_frac=0.002,
        max_area_frac=0.55,
        aspect_range=(0.3, 12.0),
        min_extent=0.12,
        max_boxes=20,
        filter_key="smoke",
    ),
    "flood": dict(
        percentile=78,
        default_thr=0.22,
        open_iter=1,
        close_iter=3,
        min_area_frac=0.0015,
        max_area_frac=0.70,
        aspect_range=(0.2, 20.0),
        min_extent=0.10,
        max_boxes=20,
        filter_key="flood",
    ),
}

_OPENCV_FILTER_CONFIG = {
    "building": dict(
        percentile=82,
        default_thr=0.28,
        close_size=7,
        min_area_frac=0.0012,
        max_area_frac=0.35,
        aspect_range=(0.25, 5.0),
        min_extent=0.16,
        max_boxes=40,
        filter_key="building",
    ),
    "road": dict(
        percentile=78,
        default_thr=0.32,
        min_area_frac=0.0015,
        max_area_frac=0.55,
        aspect_range=(1.2, 30.0),
        min_extent=0.10,
        max_boxes=25,
        mask_blend=0.35,
        filter_key="road",
    ),
    "vehicle": dict(
        percentile=82,
        default_thr=0.20,
        min_area_frac=0.00005,
        max_area_frac=0.025,
        aspect_range=(0.35, 5.0),
        min_extent=0.10,
        max_boxes=60,
        filter_key="vehicle",
    ),
    "person": dict(
        percentile=82,
        default_thr=0.22,
        close_size=7,
        min_area_frac=0.0002,
        max_area_frac=0.06,
        aspect_range=(1.5, 7.0),
        min_extent=0.14,
        max_boxes=30,
        prefer_vertical=True,
        mask_blend=0.0,
        filter_key="person",
    ),
    "fire": dict(
        percentile=78,
        default_thr=0.18,
        close_size=7,
        min_area_frac=0.00015,
        max_area_frac=0.35,
        aspect_range=(0.2, 8.0),
        min_extent=0.12,
        max_boxes=25,
        mask_blend=0.35,
        filter_key="fire",
    ),
    "smoke": dict(
        percentile=80,
        default_thr=0.24,
        close_size=9,
        min_area_frac=0.002,
        max_area_frac=0.55,
        aspect_range=(0.3, 12.0),
        min_extent=0.12,
        max_boxes=20,
        filter_key="smoke",
    ),
    "flood": dict(
        percentile=78,
        default_thr=0.22,
        min_area_frac=0.0015,
        max_area_frac=0.70,
        aspect_range=(0.2, 20.0),
        min_extent=0.10,
        max_boxes=20,
        filter_key="flood",
    ),
}


def _detect_fallback_generic(filter_key, score):
    """Run fallback pipeline using params from _FALLBACK_FILTER_CONFIG."""
    return _fallback_detection_pipeline(
        score,
        **_FALLBACK_FILTER_CONFIG[filter_key],
    )


def _run_opencv_pipeline_for(filter_key, cv2, merged, **overrides):
    """Run _opencv_detection_pipeline with config lookup + caller overrides."""
    params = dict(_OPENCV_FILTER_CONFIG[filter_key])
    params.update(overrides)
    return _opencv_detection_pipeline(cv2, merged, **params)
