# -*- coding: utf-8 -*-
"""Detection geometry helpers: IoU, NMS, region scoring, multiscale, tracking."""

from __future__ import annotations

import numpy as np

from QGISFMV.video.filters.QgsFmvFilterCore import _HAS_NDIMAGE, _ndimage

_detection_ema = {}
_detection_prev_gray = None
_track_state = {}


def reset_detection_state():
    """Clear temporal detection / tracking state."""
    global _detection_ema, _detection_prev_gray, _track_state
    _detection_ema = {}
    _detection_prev_gray = None
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
            used.add(len(state["tracks"]) - 1)
        assigned.append(tid)
    state["tracks"] = [state["tracks"][i] for i in sorted(used)]
    return assigned
