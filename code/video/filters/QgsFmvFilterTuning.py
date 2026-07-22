# -*- coding: utf-8 -*-
"""FMV / aerial detection filter tuning (settings.ini [FILTERS])."""

from __future__ import annotations

from typing import Any, Dict


def _get(section: str, key: str, default: str) -> str:
    """Read a settings.ini value, returning *default* on any error."""
    try:
        from QGISFMV.utils.settings.QgsFmvSettings import get

        return str(get(section, key, default) or default).strip()
    except Exception as _exc:
        from QGISFMV.utils.logging import log
        log.debug("Settings read [%s] %s failed: %s", section, key, _exc)
        return default


def _float(key: str, default: float) -> float:
    """Read a FILTERS float setting, returning *default* on parse error."""
    try:
        return float(_get("FILTERS", key, str(default)))
    except (TypeError, ValueError):
        return default


def _bool(key: str, default: bool = True) -> bool:
    """Read a FILTERS boolean setting (true/false/1/0)."""
    raw = _get("FILTERS", key, "true" if default else "false").lower()
    return raw in ("1", "true", "yes", "on")


def filter_profile() -> str:
    """Return the active filter profile (aerial, coco, etc.)."""
    return _get("FILTERS", "profile", "aerial").lower()


def is_aerial_profile() -> bool:
    """True when the active profile is aerial / FMV / UAV / VisDrone."""
    return filter_profile() in ("aerial", "fmv", "uav", "visdrone")


def pipeline_defaults(filter_key: str | None = None) -> Dict[str, Any]:
    """Shared OpenCV / numpy CC detection defaults."""
    if not is_aerial_profile():
        return {}
    area_key = {
        "vehicle": "vehicle_min_area_frac",
        "person": "person_min_area_frac",
        "building": "building_min_area_frac",
        "road": "road_min_area_frac",
    }.get(filter_key or "", "detection_min_area_frac")
    return {
        "percentile": int(_float("detection_percentile", 70)),
        "default_thr": _float("detection_default_threshold", 0.10),
        "min_pos": int(_float("detection_min_pos", 20)),
        "min_area_frac": _float(area_key, _float("detection_min_area_frac", 0.000012)),
        "min_extent": _float("detection_min_extent", 0.08),
        "mask_blend": _float("detection_mask_blend", 0.55),
    }


def ema_alpha(default: float) -> float:
    """Return the EMA smoothing alpha, profile-tuned when applicable."""
    if not is_aerial_profile():
        return default
    return _float("ema_alpha", default)


def overlay_defaults() -> Dict[str, float]:
    """Return overlay confidence thresholds tuned for the active profile."""
    if not is_aerial_profile():
        return {}
    return {
        "abs_thr": _float("overlay_abs_threshold", 0.10),
        "adaptive_min_cov": _float("overlay_adaptive_min_cov", 0.6),
        "weight_gate": _float("overlay_weight_gate", 0.12),
        "adaptive_percentile": _float("overlay_adaptive_percentile", 74),
    }


def tune_overlay_options(options: Dict[str, Any]) -> Dict[str, Any]:
    """Merge profile-tuned overlay thresholds into *options*."""
    tuned = dict(options)
    for key, val in overlay_defaults().items():
        tuned[key] = val
    return tuned


def clahe_before_detection() -> bool:
    """True when CLAHE pre-gain should run before object detection."""
    return _bool("clahe_pregain", True) and is_aerial_profile()


def dnn_fallback_when_empty() -> bool:
    """True when DNN should run as fallback if classical detection finds nothing."""
    return _bool("dnn_fallback_when_empty", True)


def multiscale_detection() -> bool:
    """True when multi-scale detection is enabled for the aerial profile."""
    return _bool("multiscale_detection", True) and is_aerial_profile()


def box_nms_iou(default: float = 0.42) -> float:
    """Return the IoU threshold for bounding-box non-max suppression."""
    return _float("box_nms_iou", default)


def show_box_confidence() -> bool:
    """True when confidence scores should be drawn on detection boxes."""
    return _bool("show_box_confidence", True)


def tracking_enabled() -> bool:
    """True when object tracking is enabled in settings."""
    return _bool("tracking_enabled", True)


def apply_aerial_pipeline_kw(filter_key: str | None = None, **kwargs: Any) -> Dict[str, Any]:
    """Merge FMV-friendly detection kwargs (lower thresholds, smaller min area)."""
    if not is_aerial_profile():
        return dict(kwargs)
    tuned = pipeline_defaults(filter_key)
    out = dict(kwargs)
    if "percentile" in out:
        out["percentile"] = min(int(out["percentile"]), int(tuned.get("percentile", 70)))
    if "default_thr" in out:
        out["default_thr"] = min(float(out["default_thr"]), float(tuned.get("default_thr", 0.10)))
    if "min_pos" in out:
        out["min_pos"] = min(int(out.get("min_pos", 48)), int(tuned.get("min_pos", 20)))
    elif "min_pos" not in out:
        out["min_pos"] = int(tuned.get("min_pos", 20))
    if "min_extent" in out:
        out["min_extent"] = min(float(out["min_extent"]), float(tuned.get("min_extent", 0.08)))
    if "min_area_frac" in out and "min_area_frac" in tuned:
        out["min_area_frac"] = min(float(out["min_area_frac"]), float(tuned["min_area_frac"]))
    if "mask_blend" in out and "mask_blend" in tuned:
        out["mask_blend"] = max(float(out["mask_blend"]), float(tuned["mask_blend"]))
    return out
