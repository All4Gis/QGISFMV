# -*- coding: utf-8 -*-
"""AI / CV detection filters (building, road, vehicle, person, fire, smoke, flood)."""

from __future__ import annotations

import numpy as np

from QGISFMV.utils.core.QgsImageMat import convertMatToQImage, convertQImageToMat
from QGISFMV.utils.logging import log
from QGISFMV.video.filters.QgsFmvFilterCore import (
    FilterCore,
    _HAS_NDIMAGE,
    _get_cv2_module,
    opencv_available,
    _ndimage,
)

_detection_ema = {}
_detection_prev_gray = {}
_track_state = {}


def reset_detection_state():
    """Clear temporal detection / tracking state."""
    global _detection_ema, _detection_prev_gray, _track_state
    _detection_ema = {}
    _detection_prev_gray = {}
    _track_state = {}


def _box_iou(a, b):
    """Compute IoU between two bounding boxes (x0, y0, x1, y1)."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
    inter = float(iw * ih)
    if inter <= 0:
        return 0.0
    area_a = float(max(0, ax1 - ax0) * max(0, ay1 - ay0))
    area_b = float(max(0, bx1 - bx0) * max(0, by1 - by0))
    return inter / max(area_a + area_b - inter, 1e-6)


def _nms_boxes(boxes, scores, iou_thresh=0.42):
    """Apply non-max suppression to boxes/scores and return kept pairs."""
    if not boxes:
        return [], []
    boxes_arr = np.array(boxes, dtype=np.float32)
    scores_arr = np.array(scores, dtype=np.float32)
    order = np.argsort(scores_arr)[::-1]
    keep_idx = []
    while order.size:
        i = int(order[0])
        keep_idx.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        # Vectorized IoU computation
        ix0 = np.maximum(boxes_arr[i, 0], boxes_arr[rest, 0])
        iy0 = np.maximum(boxes_arr[i, 1], boxes_arr[rest, 1])
        ix1 = np.minimum(boxes_arr[i, 2], boxes_arr[rest, 2])
        iy1 = np.minimum(boxes_arr[i, 3], boxes_arr[rest, 3])
        inter = np.maximum(0, ix1 - ix0) * np.maximum(0, iy1 - iy0)
        area_i = max(0, boxes_arr[i, 2] - boxes_arr[i, 0]) * max(0, boxes_arr[i, 3] - boxes_arr[i, 1])
        area_rest = np.maximum(0, boxes_arr[rest, 2] - boxes_arr[rest, 0]) * np.maximum(0, boxes_arr[rest, 3] - boxes_arr[rest, 1])
        ious = inter / np.maximum(area_i + area_rest - inter, 1e-6)
        order = rest[ious < iou_thresh]
    return [boxes[i] for i in keep_idx], [float(scores[i]) for i in keep_idx]


def _region_scores(score, boxes):
    """Average the score map inside each bounding box."""
    out = []
    for x0, y0, x1, y1 in boxes:
        patch = score[y0:y1, x0:x1]
        out.append(float(patch.mean()) if patch.size else 0.0)
    return out


def _multiscale_score(rgb, score_fn):
    """Run *score_fn* at full and half scale, merging the responses."""
    from QGISFMV.video.filters.QgsFmvFilterTuning import multiscale_detection

    primary = score_fn(rgb)
    if not multiscale_detection() or min(rgb.shape[:2]) < 180:
        return primary
    small = rgb[::2, ::2]
    secondary = score_fn(small)
    if _HAS_NDIMAGE:
        up = _ndimage.zoom(secondary, 2, order=1)
    else:
        up = np.repeat(np.repeat(secondary, 2, axis=0), 2, axis=1)
    up = up[: primary.shape[0], : primary.shape[1]]
    return np.clip(np.maximum(primary, up * 0.92), 0.0, 1.0)


def _assign_track_ids(filter_key, boxes):
    """Light IoU tracker — stable numeric ids across frames."""
    from QGISFMV.video.filters.QgsFmvFilterTuning import tracking_enabled

    if not tracking_enabled() or not boxes:
        return []
    global _track_state
    state = _track_state.setdefault(filter_key, {"next_id": 1, "tracks": []})
    assigned = []
    used = set()
    for box in boxes:
        best_i, best_iou = -1, 0.25
        for ti, tr in enumerate(state["tracks"]):
            if ti in used:
                continue
            iou = _box_iou(box, tr["box"])
            if iou > best_iou:
                best_iou, best_i = iou, ti
        if best_i >= 0:
            tid = state["tracks"][best_i]["id"]
            state["tracks"][best_i]["box"] = box
            used.add(best_i)
        else:
            tid = state["next_id"]
            state["next_id"] += 1
            state["tracks"].append({"id": tid, "box": box})
        assigned.append(tid)
    state["tracks"] = [state["tracks"][i] for i in sorted(used)]
    return assigned


# Filter-specific pipeline parameter defaults — avoids repeating long kwarg
# lists in every _detect_opencv_X / _detect_fallback_X pair.
_FALLBACK_FILTER_CONFIG = {
    "building": dict(percentile=82, default_thr=0.28, open_iter=1, close_iter=2,
                     min_area_frac=0.0012, max_area_frac=0.35, aspect_range=(0.25, 5.0),
                     min_extent=0.16, max_boxes=40, mask_blend=0.0, filter_key="building"),
    "road": dict(percentile=78, default_thr=0.32, open_iter=1, close_iter=3,
                 min_area_frac=0.0015, max_area_frac=0.55, aspect_range=(1.2, 30.0),
                 min_extent=0.10, max_boxes=25, mask_blend=0.35, filter_key="road"),
    "vehicle": dict(percentile=84, default_thr=0.22, open_iter=1, close_iter=1,
                    min_area_frac=0.00005, max_area_frac=0.025, aspect_range=(0.35, 5.0),
                    min_extent=0.10, max_boxes=60, filter_key="vehicle"),
    "person": dict(percentile=82, default_thr=0.22, open_iter=1, close_iter=2,
                   min_area_frac=0.0002, max_area_frac=0.06, aspect_range=(1.5, 7.0),
                   min_extent=0.14, max_boxes=30, prefer_vertical=True, mask_blend=0.0,
                   filter_key="person"),
    "fire": dict(percentile=78, default_thr=0.18, open_iter=1, close_iter=2,
                 min_area_frac=0.00015, max_area_frac=0.35, aspect_range=(0.2, 8.0),
                 min_extent=0.12, max_boxes=25, mask_blend=0.35, filter_key="fire"),
    "smoke": dict(percentile=80, default_thr=0.24, open_iter=1, close_iter=3,
                  min_area_frac=0.002, max_area_frac=0.55, aspect_range=(0.3, 12.0),
                  min_extent=0.12, max_boxes=20, filter_key="smoke"),
    "flood": dict(percentile=78, default_thr=0.22, open_iter=1, close_iter=3,
                  min_area_frac=0.0015, max_area_frac=0.70, aspect_range=(0.2, 20.0),
                  min_extent=0.10, max_boxes=20, filter_key="flood"),
}

_OPENCV_FILTER_CONFIG = {
    "building": dict(percentile=82, default_thr=0.28, close_size=7,
                     min_area_frac=0.0012, max_area_frac=0.35, aspect_range=(0.25, 5.0),
                     min_extent=0.16, max_boxes=40, filter_key="building"),
    "road": dict(percentile=78, default_thr=0.32,
                 min_area_frac=0.0015, max_area_frac=0.55, aspect_range=(1.2, 30.0),
                 min_extent=0.10, max_boxes=25, mask_blend=0.35, filter_key="road"),
    "vehicle": dict(percentile=82, default_thr=0.20,
                    min_area_frac=0.00005, max_area_frac=0.025, aspect_range=(0.35, 5.0),
                    min_extent=0.10, max_boxes=60, filter_key="vehicle"),
    "person": dict(percentile=82, default_thr=0.22, close_size=7,
                   min_area_frac=0.0002, max_area_frac=0.06, aspect_range=(1.5, 7.0),
                   min_extent=0.14, max_boxes=30, prefer_vertical=True, mask_blend=0.0,
                   filter_key="person"),
    "fire": dict(percentile=78, default_thr=0.18, close_size=7,
                 min_area_frac=0.00015, max_area_frac=0.35, aspect_range=(0.2, 8.0),
                 min_extent=0.12, max_boxes=25, mask_blend=0.35, filter_key="fire"),
    "smoke": dict(percentile=80, default_thr=0.24, close_size=9,
                  min_area_frac=0.002, max_area_frac=0.55, aspect_range=(0.3, 12.0),
                  min_extent=0.12, max_boxes=20, filter_key="smoke"),
    "flood": dict(percentile=78, default_thr=0.22,
                  min_area_frac=0.0015, max_area_frac=0.70, aspect_range=(0.2, 20.0),
                  min_extent=0.10, max_boxes=20, filter_key="flood"),
}


class FmvDetectionFilters:
    """Frame-wise object detection and segmentation filters."""

    @staticmethod
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

    @staticmethod
    def _ema_score(name, score, alpha=0.40):
        """Temporal exponential average — stabilizes flicker across frames."""
        global _detection_ema
        prev = _detection_ema.get(name)
        if prev is None or prev.shape != score.shape:
            _detection_ema[name] = score.astype(np.float32)
            return _detection_ema[name]
        out = alpha * score + (1.0 - alpha) * prev
        _detection_ema[name] = out
        return out

    @staticmethod
    def _motion_boost(lum):
        """Return [0,1] motion magnitude vs previous detection frame."""
        global _detection_prev_gray
        cur = FilterCore.smooth(lum, sigma=1.0)
        if _detection_prev_gray is None or _detection_prev_gray.shape != cur.shape:
            _detection_prev_gray = cur
            return np.zeros_like(cur)
        diff = np.abs(cur - _detection_prev_gray)
        _detection_prev_gray = cur
        peak = float(np.percentile(diff, 95)) + 1e-6
        return np.clip(diff / peak, 0.0, 1.0)

    @staticmethod
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
            CONFIDENCE_BASE_BRIGHTNESS, CONFIDENCE_TINT_RANGE, CONFIDENCE_TINT_INTENSITY,
        )
        out = base * (CONFIDENCE_BASE_BRIGHTNESS + CONFIDENCE_TINT_RANGE * (1.0 - weight[..., None]))
        out = out * (1.0 - CONFIDENCE_TINT_INTENSITY * weight[..., None]) + tint * (CONFIDENCE_TINT_INTENSITY * weight[..., None])
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
            engine = "CV" if opencv_available() else (
                "SCIPY" if _HAS_NDIMAGE else "NUMPY"
            )
        FilterCore.draw_filter_banner(
            out,
            f"{str(label)} [{str(engine)}] det:{nboxes} {float(cov):.0f}%",
            tint_rgb,
        )
        return out, weight

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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
            ema_alpha as tuned_ema_alpha,
            tune_overlay_options,
        )

        overlay_kwargs = tune_overlay_options(dict(overlay_kwargs))
        ema_alpha = tuned_ema_alpha(ema_alpha)
        work_rgb = rgb
        if clahe_before_detection():
            work_rgb = FmvDetectionFilters._clahe_rgb(rgb)

        if dnn_filter_key:
            try:
                from QGISFMV.video.dnn.QgsFmvOnnxDetector import try_dnn_detection

                dnn = try_dnn_detection(work_rgb, dnn_filter_key)
                if dnn is not None:
                    raw_score, boxes, engine = dnn
                    if boxes or not dnn_fallback_when_empty():
                        score = FmvDetectionFilters._ema_score(ema_key, raw_score, alpha=ema_alpha)
                        track_ids = _assign_track_ids(ema_key, boxes)
                        opts = dict(overlay_kwargs)
                        opts["boxes"] = boxes
                        opts["box_scores"] = _region_scores(score, boxes) if boxes else None
                        opts["track_ids"] = track_ids
                        opts["engine"] = engine
                        tint = opts.pop("tint_rgb")
                        label = opts.pop("label")
                        result, weight = FmvDetectionFilters._confidence_overlay(
                            rgb, score, tint, label, **opts
                        )
                        return result, weight, engine, boxes
            except Exception as _exc:
                log.debug('DNN detection failed, falling back to classical: %s', _exc)
        engine = "CV"
        score_map = _multiscale_score(work_rgb, score_fn)
        try:
            if _get_cv2_module() is not None:
                raw_score, boxes = opencv_fn(work_rgb, score_map)
            else:
                raise RuntimeError("OpenCV unavailable")
        except Exception as _exc:
            log.debug('OpenCV detection pipeline failed, using fallback: %s', _exc)
            engine = "SCIPY" if _HAS_NDIMAGE else "NUMPY"
            raw_score, boxes = fallback_fn(work_rgb, score_map)
        score = FmvDetectionFilters._ema_score(ema_key, raw_score, alpha=ema_alpha)
        track_ids = _assign_track_ids(ema_key, boxes)
        opts = dict(overlay_kwargs)
        opts["boxes"] = boxes
        opts["box_scores"] = _region_scores(score, boxes) if boxes else None
        opts["track_ids"] = track_ids
        opts["engine"] = engine
        tint = opts.pop("tint_rgb")
        label = opts.pop("label")
        result, weight = FmvDetectionFilters._confidence_overlay(
            rgb, score, tint, label, **opts
        )
        return result, weight, engine, boxes

    @staticmethod
    def _detect_fallback_generic(filter_key, score):
        """Run fallback pipeline using params from _FALLBACK_FILTER_CONFIG."""
        return FmvDetectionFilters._fallback_detection_pipeline(
            score, **_FALLBACK_FILTER_CONFIG[filter_key],
        )

    @staticmethod
    def _run_opencv_pipeline_for(filter_key, cv2, merged, **overrides):
        """Run _opencv_detection_pipeline with config lookup + caller overrides."""
        params = dict(_OPENCV_FILTER_CONFIG[filter_key])
        params.update(overrides)
        return FmvDetectionFilters._opencv_detection_pipeline(cv2, merged, **params)

    @staticmethod
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

    @staticmethod
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
        road = FmvDetectionFilters._road_surface_score(rgb)
        motion = FmvDetectionFilters._motion_boost(lum)

        try:
            from QGISFMV.video.filters.QgsFmvFilterTuning import is_aerial_profile

            road_mix = (0.30 + 0.70 * road) if is_aerial_profile() else (0.55 + 0.45 * road)
        except Exception as _exc:
            log.debug('is_aerial_profile import failed, using default road mix: %s', _exc)
            road_mix = 0.55 + 0.45 * road

        score = (
            contrast
            * edge_norm
            * not_veg
            * road_mix
            * (0.82 + 0.18 * motion)
        )
        return np.clip(score, 0, 1)

    @staticmethod
    def _building_detect_opencv(_rgb, score):
        cv2 = _get_cv2_module()
        gray = cv2.cvtColor(_rgb, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 25, 95)
        edge_norm = cv2.GaussianBlur(edges.astype(np.float64) / 255.0, (5, 5), 0)
        merged = score * (0.50 + 0.50 * edge_norm)
        out, boxes, _labels, _mask = FmvDetectionFilters._run_opencv_pipeline_for(
            "building", cv2, merged,
        )
        return out, boxes

    @staticmethod
    def _building_detect_fallback(_rgb, score):
        return FmvDetectionFilters._detect_fallback_generic("building", score)

    @staticmethod
    def _road_detect_opencv(_rgb, score):
        cv2 = _get_cv2_module()
        h, w = score.shape
        kw = max(15, w // 18)
        kh = max(3, h // 80 | 1)
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        out, boxes, _labels, mask_u8 = FmvDetectionFilters._run_opencv_pipeline_for(
            "road", cv2, score, close_kernel=close_kernel,
        )
        if boxes:
            keep = np.zeros(score.shape, dtype=bool)
            for x0, y0, x1, y1 in boxes:
                keep[y0:y1, x0:x1] = True
            keep |= (mask_u8 > 0) & (score > 0.50)
            out = score * np.clip(keep.astype(np.float64) + 0.18, 0, 1)
        return out, boxes

    @staticmethod
    def _road_detect_fallback(_rgb, score):
        out, boxes = FmvDetectionFilters._detect_fallback_generic("road", score)
        if boxes:
            keep = np.zeros(score.shape, dtype=bool)
            for x0, y0, x1, y1 in boxes:
                keep[y0:y1, x0:x1] = True
            keep |= score > 0.55
            out = score * np.clip(keep.astype(np.float64) + 0.18, 0, 1)
        return out, boxes

    @staticmethod
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
        out, boxes, _labels, _mask = FmvDetectionFilters._run_opencv_pipeline_for(
            "vehicle", cv2, merged,
        )
        return out, boxes

    @staticmethod
    def _vehicle_detect_fallback(_rgb, score):
        return FmvDetectionFilters._detect_fallback_generic("vehicle", score)

    @staticmethod
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
        motion = FmvDetectionFilters._motion_boost(lum)
        return np.clip(
            np.clip(vert / peak, 0, 1)
            * np.clip(1.0 - np.abs(lum - 120.0) / 120.0, 0.2, 1.0)
            * np.clip(1.0 - np.maximum(exg, 0) / 65.0, 0.25, 1.0)
            * (0.78 + 0.22 * motion),
            0,
            1,
        )

    @staticmethod
    def _person_detect_opencv(_rgb, score):
        cv2 = _get_cv2_module()
        gray = cv2.cvtColor(_rgb, cv2.COLOR_RGB2GRAY)
        h = gray.shape[0]
        kh = max(9, h // 36 | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, kh))
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel).astype(np.float64)
        p90 = float(np.percentile(tophat, 90)) + 1e-6
        merged = score * np.clip(0.65 + 0.35 * (tophat / p90), 0, 1)
        out, boxes, _labels, _mask = FmvDetectionFilters._run_opencv_pipeline_for(
            "person", cv2, merged,
        )
        return out, boxes

    @staticmethod
    def _person_detect_fallback(_rgb, score):
        return FmvDetectionFilters._detect_fallback_generic("person", score)

    @staticmethod
    def _fire_score(rgb):
        h, s, v = FilterCore.rgb_to_hsv(rgb)
        r, g, b, lum, _c, _e = FilterCore.rgb_channels(rgb)
        warm = ((h <= 22) | (h >= 160)) & (s >= 70) & (v >= 80)
        score = warm.astype(np.float64)
        score *= np.clip((r - b) / 40.0, 0, 1)
        score *= np.clip((r - 60.0) / 120.0, 0, 1)
        score *= np.clip(lum / 55.0, 0, 1)
        return np.clip(score, 0, 1)

    @staticmethod
    def _fire_detect_opencv(_rgb, score):
        cv2 = _get_cv2_module()
        hsv = cv2.cvtColor(_rgb, cv2.COLOR_RGB2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 70, 80], dtype=np.uint8), np.array([22, 255, 255], dtype=np.uint8))
        mask2 = cv2.inRange(hsv, np.array([160, 70, 80], dtype=np.uint8), np.array([179, 255, 255], dtype=np.uint8))
        warm = cv2.bitwise_or(mask1, mask2).astype(np.float64) / 255.0
        merged = np.maximum(score, warm * 0.85)
        out, boxes, _labels, mask_u8 = FmvDetectionFilters._run_opencv_pipeline_for(
            "fire", cv2, merged,
        )
        if not boxes and not np.any(mask_u8):
            out = merged * 0.0
        return out, boxes

    @staticmethod
    def _fire_detect_fallback(_rgb, score):
        out, boxes = FmvDetectionFilters._detect_fallback_generic("fire", score)
        if not boxes and float(np.max(score)) < 0.12:
            out = score * 0.0
        return out, boxes

    @staticmethod
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

    @staticmethod
    def _smoke_detect_opencv(_rgb, score):
        cv2 = _get_cv2_module()
        hsv = cv2.cvtColor(_rgb, cv2.COLOR_RGB2HSV)
        color = cv2.inRange(
            hsv,
            np.array([0, 0, 100], dtype=np.uint8),
            np.array([180, 45, 235], dtype=np.uint8),
        ).astype(np.float64) / 255.0
        gray = cv2.cvtColor(_rgb, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 40, 120).astype(np.float64) / 255.0
        merged = score * (0.55 + 0.45 * color) * (1.0 - 0.75 * edges)
        out, boxes, _labels, _mask = FmvDetectionFilters._run_opencv_pipeline_for(
            "smoke", cv2, merged,
        )
        return out, boxes

    @staticmethod
    def _smoke_detect_fallback(_rgb, score):
        return FmvDetectionFilters._detect_fallback_generic("smoke", score)

    @staticmethod
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

    @staticmethod
    def _flood_detect_opencv(_rgb, score):
        cv2 = _get_cv2_module()
        hsv = cv2.cvtColor(_rgb, cv2.COLOR_RGB2HSV)
        color = cv2.inRange(
            hsv,
            np.array([85, 20, 35], dtype=np.uint8),
            np.array([135, 170, 220], dtype=np.uint8),
        ).astype(np.float64) / 255.0
        merged = np.maximum(score, color * 0.90)
        h, w = score.shape
        close_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (max(7, w // 40 | 1), max(7, h // 40 | 1))
        )
        out, boxes, _labels, _mask = FmvDetectionFilters._run_opencv_pipeline_for(
            "flood", cv2, merged, close_kernel=close_kernel,
        )
        return out, boxes

    @staticmethod
    def _flood_detect_fallback(_rgb, score):
        return FmvDetectionFilters._detect_fallback_generic("flood", score)

    @staticmethod
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

    @staticmethod
    def BuildingDetectionFilter(image):
        """Building highlight — OpenCV Canny + CC when available."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, _weight, _engine, _boxes = FmvDetectionFilters._run_detection(
            rgb,
            FmvDetectionFilters._building_structure_score,
            FmvDetectionFilters._building_detect_opencv,
            FmvDetectionFilters._building_detect_fallback,
            "building",
            0.35,
            {
                "tint_rgb": (255, 140, 0),
                "label": "BUILDING",
                "abs_thr": 0.28,
                "box_color": (255, 255, 0),
                "adaptive_min_cov": 2.0,
            },
            dnn_filter_key="building",
        )
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def RoadSegmentationFilter(image):
        """Road/asphalt segmentation — elongated OpenCV CC + lane hints."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, weight, engine, boxes = FmvDetectionFilters._run_detection(
            rgb,
            FmvDetectionFilters._road_surface_score,
            FmvDetectionFilters._road_detect_opencv,
            FmvDetectionFilters._road_detect_fallback,
            "road",
            0.30,
            {
                "tint_rgb": (255, 215, 0),
                "label": "ROAD",
                "abs_thr": 0.30,
                "box_color": (255, 0, 180),
                "adaptive_min_cov": 2.5,
            },
            dnn_filter_key="road",
        )
        lines = 0
        h, w = (int(x) for x in weight.shape[:2])
        step = int(max(10, h // 16))
        for y in range(h // 5, h * 4 // 5, step):
            row = weight[y] > 0.45
            xs = np.where(row)[0]
            if xs.size > w * 0.18:
                FilterCore.draw_line_numpy(
                    result, int(xs[0]), y, int(xs[-1]), y, (255, 0, 180)
                )
                lines += 1
        FilterCore.draw_filter_banner(
            result,
            f"ROAD [{engine}] seg:{len(boxes)} lines:{lines}",
            (255, 215, 0),
        )
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def VehicleSegmentationFilter(image):
        """Vehicle detection — OpenCV morph/CC when available, scipy fallback."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, _weight, _engine, _boxes = FmvDetectionFilters._run_detection(
            rgb,
            FmvDetectionFilters._vehicle_blob_score,
            FmvDetectionFilters._vehicle_detect_opencv,
            FmvDetectionFilters._vehicle_detect_fallback,
            "vehicle",
            0.38,
            {
                "tint_rgb": (255, 165, 0),
                "label": "VEHICLE",
                "abs_thr": 0.20,
                "box_color": (0, 200, 255),
                "adaptive_min_cov": 2.0,
            },
            dnn_filter_key="vehicle",
        )
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def PersonSegmentationFilter(image):
        """Person-like upright objects — vertical OpenCV top-hat + tall CC."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, _weight, _engine, _boxes = FmvDetectionFilters._run_detection(
            rgb,
            FmvDetectionFilters._person_score,
            FmvDetectionFilters._person_detect_opencv,
            FmvDetectionFilters._person_detect_fallback,
            "person",
            0.42,
            {
                "tint_rgb": (0, 255, 100),
                "label": "PERSON",
                "abs_thr": 0.24,
                "box_color": (0, 255, 120),
                "adaptive_min_cov": 2.0,
            },
            dnn_filter_key="person",
        )
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def FireDetectionFilter(image):
        """Fire — OpenCV HSV warm colors + CC regions."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, _weight, _engine, _boxes = FmvDetectionFilters._run_detection(
            rgb,
            FmvDetectionFilters._fire_score,
            FmvDetectionFilters._fire_detect_opencv,
            FmvDetectionFilters._fire_detect_fallback,
            "fire",
            0.48,
            {
                "tint_rgb": (255, 60, 0),
                "label": "FIRE",
                "abs_thr": 0.18,
                "box_color": (255, 220, 0),
                "adaptive_min_cov": 1.5,
            },
            dnn_filter_key="fire",
        )
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def SmokeDetectionFilter(image):
        """Smoke — low saturation OpenCV HSV + smooth texture CC."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, _weight, _engine, _boxes = FmvDetectionFilters._run_detection(
            rgb,
            FmvDetectionFilters._smoke_score,
            FmvDetectionFilters._smoke_detect_opencv,
            FmvDetectionFilters._smoke_detect_fallback,
            "smoke",
            0.35,
            {
                "tint_rgb": (190, 195, 220),
                "label": "SMOKE",
                "abs_thr": 0.22,
                "box_color": (220, 220, 255),
                "adaptive_min_cov": 2.5,
            },
            dnn_filter_key="smoke",
        )
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def FloodDetectionFilter(image):
        """Flood/water — OpenCV HSV blue/cyan band + large CC."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, _weight, _engine, _boxes = FmvDetectionFilters._run_detection(
            rgb,
            FmvDetectionFilters._flood_score,
            FmvDetectionFilters._flood_detect_opencv,
            FmvDetectionFilters._flood_detect_fallback,
            "flood",
            0.35,
            {
                "tint_rgb": (40, 130, 255),
                "label": "FLOOD",
                "abs_thr": 0.20,
                "box_color": (80, 200, 255),
                "adaptive_min_cov": 2.5,
            },
            dnn_filter_key="flood",
        )
        return convertMatToQImage(result, bgr=False)

