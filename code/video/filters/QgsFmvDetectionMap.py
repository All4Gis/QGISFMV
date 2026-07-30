# -*- coding: utf-8 -*-
"""Publish AI / CV detection boxes onto a georeferenced QGIS point layer."""

from __future__ import annotations

import time

from QGISFMV.geo.QgsFmvSpatial import box_center, image_xy_to_latlon
from QGISFMV.utils.constants import DETECTION_TRAIL_MAX_POINTS
from QGISFMV.utils.logging import log

_enabled = True
_trail_enabled = False
_last_publish_ms = 0
_COOLDOWN_MS = 300
_last_boxes = {}  # class_name -> list of dicts
_listeners = []  # callables(class_name, points)
_playhead_provider = None  # optional callable() -> seconds


def set_playhead_provider(callback):
    """Optional ``callback() -> float`` for trail ``time_sec`` stamps."""
    global _playhead_provider
    _playhead_provider = callback


def _playhead_sec(explicit=None):
    if explicit is not None:
        try:
            return float(explicit)
        except (TypeError, ValueError):
            return 0.0
    if _playhead_provider is not None:
        try:
            return float(_playhead_provider() or 0.0)
        except Exception:
            return 0.0
    return 0.0


def set_publish_enabled(value: bool) -> bool:
    """Globally enable/disable detection→map publishing."""
    global _enabled
    _enabled = bool(value)
    return _enabled


def is_publish_enabled() -> bool:
    return _enabled


def set_trail_enabled(value: bool) -> bool:
    """Enable/disable accumulating detection heat-trail layer."""
    global _trail_enabled
    _trail_enabled = bool(value)
    return _trail_enabled


def is_trail_enabled() -> bool:
    return _trail_enabled


def add_detection_listener(callback):
    """Register ``callback(class_name, points)`` after each successful publish."""
    if callback is not None and callback not in _listeners:
        _listeners.append(callback)


def remove_detection_listener(callback):
    try:
        _listeners.remove(callback)
    except ValueError:
        pass


def last_detections(class_name=None):
    """Return last published detections (for tests / mission package)."""
    if class_name is None:
        return dict(_last_boxes)
    return list(_last_boxes.get(class_name, []))


def detections_to_geo_points(boxes, track_ids=None, scores=None, gt=None):
    """Convert image-space boxes to ``[{lat,lon,track_id,score}, ...]`` using *gt*."""
    if not boxes or gt is None:
        return []
    out = []
    for idx, box in enumerate(boxes):
        cx, cy = box_center(box)
        ll = image_xy_to_latlon(gt, cx, cy)
        if ll is None:
            continue
        lat, lon = ll
        tid = None
        if track_ids is not None and idx < len(track_ids):
            tid = track_ids[idx]
        score = None
        if scores is not None and idx < len(scores):
            try:
                score = float(scores[idx])
            except (TypeError, ValueError):
                score = None
        out.append(
            {
                "lat": float(lat),
                "lon": float(lon),
                "track_id": int(tid) if tid is not None else idx,
                "score": score,
            }
        )
    return out


def notify_detections(class_name, boxes, track_ids=None, scores=None, time_sec=None):
    """Called from the detection pipeline when boxes are available."""
    if not _enabled or not boxes:
        return 0
    now = int(time.time() * 1000)
    global _last_publish_ms
    if now - _last_publish_ms < _COOLDOWN_MS:
        return 0
    try:
        from QGISFMV.utils.core.QgsFmvGeoReferencing import GetGCPGeoTransform

        gt = GetGCPGeoTransform()
    except Exception as exc:
        log.debug("detection map: no GCP transform: %s", exc)
        return 0
    if gt is None:
        return 0

    points = detections_to_geo_points(boxes, track_ids=track_ids, scores=scores, gt=gt)
    if not points:
        return 0
    key = str(class_name)
    _last_boxes[key] = points
    try:
        n = upsert_detection_features(key, points)
        if _trail_enabled:
            append_detection_trail(key, points, time_sec=_playhead_sec(time_sec))
        _last_publish_ms = now
        for cb in list(_listeners):
            try:
                cb(key, points)
            except Exception as exc:
                log.debug("detection listener failed: %s", exc)
        return n
    except Exception as exc:
        log.debug("upsert_detection_features failed: %s", exc)
        return 0


def upsert_detection_features(class_name, points):
    """Replace features for *class_name* on the AI Detections layer."""
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY

    from QGISFMV.utils.layers.QgsFmvLayers import (
        Detections_lyr,
        ensure_detections_layer,
        groupName,
    )
    from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

    ensure_detections_layer()
    layer = qgsu.selectLayerByName(Detections_lyr, groupName)
    if layer is None:
        return 0

    # Remove previous features for this class, keep others.
    to_delete = []
    class_idx = layer.fields().indexOf("class")
    for feat in layer.getFeatures():
        if class_idx >= 0 and str(feat.attribute(class_idx)) == str(class_name):
            to_delete.append(feat.id())
    provider = layer.dataProvider()
    if to_delete:
        provider.deleteFeatures(to_delete)

    feats = []
    for p in points:
        f = QgsFeature(layer.fields())
        score = p.get("score")
        f.setAttributes(
            [
                int(p.get("track_id", 0)),
                str(class_name),
                float(score) if score is not None else None,
                float(p["lon"]),
                float(p["lat"]),
                0.0,
            ]
        )
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p["lon"], p["lat"])))
        feats.append(f)
    if feats:
        provider.addFeatures(feats)
        layer.updateExtents()
        layer.triggerRepaint()
    return len(feats)


def append_detection_trail(class_name, points, time_sec=0.0):
    """Append points to the accumulating AI Detection Trail layer (capped)."""
    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY

    from QGISFMV.utils.layers.QgsFmvLayers import (
        DetectionTrail_lyr,
        ensure_detection_trail_layer,
        groupName,
    )
    from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

    if not points:
        return 0
    ensure_detection_trail_layer()
    layer = qgsu.selectLayerByName(DetectionTrail_lyr, groupName)
    if layer is None:
        return 0

    provider = layer.dataProvider()
    feats = []
    t = float(time_sec or 0.0)
    for p in points:
        f = QgsFeature(layer.fields())
        score = p.get("score")
        f.setAttributes(
            [
                int(p.get("track_id", 0)),
                str(class_name),
                float(score) if score is not None else None,
                float(p["lon"]),
                float(p["lat"]),
                0.0,
                t,
            ]
        )
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p["lon"], p["lat"])))
        feats.append(f)
    if not feats:
        return 0
    provider.addFeatures(feats)

    # Cap total features — delete oldest by feature id.
    ids = [feat.id() for feat in layer.getFeatures()]
    overflow = len(ids) - int(DETECTION_TRAIL_MAX_POINTS)
    if overflow > 0:
        ids.sort()
        provider.deleteFeatures(ids[:overflow])

    layer.updateExtents()
    layer.triggerRepaint()
    return len(feats)
