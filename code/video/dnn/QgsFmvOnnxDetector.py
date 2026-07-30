# -*- coding: utf-8 -*-
"""Optional ONNX / YOLO detection via OpenCV DNN (same cv2 as object tracking)."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from QGISFMV.utils.logging import log

SEGMENTATION_FILTER_KEYS: Tuple[str, ...] = (
    "building",
    "road",
    "vehicle",
    "person",
    "fire",
    "smoke",
    "flood",
)

# COCO 80 classes (YOLOv5/v8 default training set)
COCO_CLASS_NAMES: Tuple[str, ...] = (
    "person",
    "bicycle",
    "car",
    "motorcycle",
    "airplane",
    "bus",
    "train",
    "truck",
    "boat",
    "traffic light",
    "fire hydrant",
    "stop sign",
    "parking meter",
    "bench",
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
    "backpack",
    "umbrella",
    "handbag",
    "tie",
    "suitcase",
    "frisbee",
    "skis",
    "snowboard",
    "sports ball",
    "kite",
    "baseball bat",
    "baseball glove",
    "skateboard",
    "surfboard",
    "tennis racket",
    "bottle",
    "wine glass",
    "cup",
    "fork",
    "knife",
    "spoon",
    "bowl",
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "donut",
    "cake",
    "chair",
    "couch",
    "potted plant",
    "bed",
    "dining table",
    "toilet",
    "tv",
    "laptop",
    "mouse",
    "remote",
    "keyboard",
    "cell phone",
    "microwave",
    "oven",
    "toaster",
    "sink",
    "refrigerator",
    "book",
    "clock",
    "vase",
    "scissors",
    "teddy bear",
    "hair drier",
    "toothbrush",
)

# VisDrone DET (aerial / UAV imagery) — standard 10-class ordering.
VISDRONE_CLASS_NAMES: Tuple[str, ...] = (
    "pedestrian",
    "people",
    "bicycle",
    "car",
    "van",
    "truck",
    "tricycle",
    "awning-tricycle",
    "bus",
    "motor",
)

# Built-in COCO class ids when dnn_<filter>_class_ids is not set in settings.ini.
# Building / road / fire / smoke / flood need a custom ONNX or explicit class ids.
FILTER_COCO_CLASSES: Dict[str, Tuple[int, ...]] = {
    "vehicle": (2, 3, 5, 7),  # car, motorcycle, bus, truck
    "person": (0,),
    "building": (),
    "road": (),
    "fire": (),
    "smoke": (),
    "flood": (),
}

# VisDrone defaults for FMV / aerial video (vehicle + person filters).
FILTER_VISDRONE_CLASSES: Dict[str, Tuple[int, ...]] = {
    "vehicle": (3, 4, 5, 8, 9),  # car, van, truck, bus, motor
    "person": (0, 1),  # pedestrian, people
    "building": (),
    "road": (),
    "fire": (),
    "smoke": (),
    "flood": (),
}

_detection_cache: Dict[str, OnnxYoloDetector] = {}
_load_failures: set = set()


def _forward_outputs(net) -> List[np.ndarray]:
    """Normalize cv2.dnn forward() return type (list, dict, or single ndarray)."""
    outputs = net.forward()
    if isinstance(outputs, dict):
        return list(outputs.values())
    if isinstance(outputs, np.ndarray):
        return [outputs]
    if isinstance(outputs, (list, tuple)):
        return list(outputs)
    return [outputs]


def _nms_indices(idxs) -> List[int]:
    """Normalize cv2.dnn.NMSBoxes return type across OpenCV versions."""
    if idxs is None:
        return []
    if isinstance(idxs, dict):
        try:
            idxs = list(idxs.values())
        except Exception as _exc:
            log.debug("NMS dict values conversion failed: %s", _exc)
            return []
    try:
        flat = np.asarray(idxs).reshape(-1)
    except Exception as _exc:
        log.debug("NMS indices reshape failed: %s", _exc)
        return []
    out: List[int] = []
    for raw in flat:
        try:
            out.append(int(raw))
            continue
        except (TypeError, ValueError):
            pass
        if isinstance(raw, (list, tuple, np.ndarray)) and len(raw):
            try:
                out.append(int(raw[0]))
            except (TypeError, ValueError, IndexError):
                pass
    return out


def _get_cv2():
    try:
        from QGISFMV.video.filters.QgsFmvFilterCore import _get_cv2_module

        return _get_cv2_module()
    except Exception as _exc:
        log.debug("FilterCore cv2 import failed: %s", _exc)
        try:
            import cv2

            return cv2
        except Exception as _exc:
            log.debug("Direct cv2 import failed: %s", _exc)
            return None


def _model_profile() -> str:
    """Return dnn_model_profile: aerial (VisDrone), coco, or custom."""
    try:
        from QGISFMV.utils.settings.QgsFmvSettings import get

        profile = (
            (get("DNN", "dnn_model_profile", "aerial") or "aerial").strip().lower()
        )
        if profile in ("custom", "coco", "aerial", "visdrone"):
            if profile == "visdrone":
                return "aerial"
            return profile
        model = (get("DNN", "onnx_model", "") or "").lower()
        if "visdrone" in model:
            return "aerial"
        if "yolov8n" in model or "coco" in model:
            return "coco"
    except Exception as _exc:
        log.debug("DNN model profile settings read failed: %s", _exc)
    return "aerial"


def _default_class_map() -> Dict[str, Tuple[int, ...]]:
    if _model_profile() == "coco":
        return FILTER_COCO_CLASSES
    return FILTER_VISDRONE_CLASSES


def class_names_for_model(model_path: str) -> Tuple[str, ...]:
    """Return the class name tuple for a given ONNX model path (VisDrone or COCO)."""
    path = (model_path or "").lower()
    if "visdrone" in path:
        return VISDRONE_CLASS_NAMES
    if "yolov8n" in path or "coco" in path:
        return COCO_CLASS_NAMES
    profile = _model_profile()
    if profile == "coco":
        return COCO_CLASS_NAMES
    return VISDRONE_CLASS_NAMES


def _parse_class_ids(raw: str) -> Tuple[int, ...]:
    ids = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit() or (part.startswith("-") and part[1:].isdigit()):
            ids.append(int(part))
    return tuple(ids)


def _dnn_base_settings() -> Optional[dict]:
    try:
        from QGISFMV.utils.settings.QgsFmvSettings import get

        enabled = str(get("DNN", "use_dnn_detection", "false")).strip().lower()
        if enabled not in ("1", "true", "yes", "on"):
            return None
        return {
            "global_model": (get("DNN", "onnx_model", "") or "").strip(),
            "input_size": int(get("DNN", "onnx_input_size", "640") or 640),
            "confidence": float(get("DNN", "onnx_confidence", "0.35") or 0.35),
            "nms": float(get("DNN", "onnx_nms", "0.45") or 0.45),
            "model_type": (get("DNN", "onnx_model_type", "yolov8") or "yolov8")
            .strip()
            .lower(),
        }
    except Exception as _exc:
        log.debug("DNN base settings read failed: %s", _exc)
        return None


def _model_path_for_filter(filter_key: str) -> Optional[str]:
    base = _dnn_base_settings()
    if base is None:
        return None
    try:
        from QGISFMV.utils.settings.QgsFmvSettings import get

        override = (get("DNN", "onnx_model_{}".format(filter_key), "") or "").strip()
    except Exception as _exc:
        log.debug("DNN filter model override read failed: %s", _exc)
        override = ""
    path = override or base["global_model"]
    if path and os.path.isfile(path):
        return path
    return None


def class_ids_for_filter(filter_key: str) -> Tuple[int, ...]:
    """Return ONNX class ids for a segmentation filter (settings override COCO defaults)."""
    try:
        from QGISFMV.utils.settings.QgsFmvSettings import get

        raw = get("DNN", "dnn_{}_class_ids".format(filter_key), "")
        parsed = _parse_class_ids(raw)
        if parsed:
            return parsed
    except Exception as _exc:
        log.debug("DNN class ids settings read failed: %s", _exc)
    return _default_class_map().get(filter_key, ())


def dnn_enabled_for_filter(filter_key: str) -> bool:
    """True when DNN is on, a model exists, and class ids are configured for this filter."""
    if _dnn_base_settings() is None:
        return False
    if filter_key not in SEGMENTATION_FILTER_KEYS:
        return False
    if not class_ids_for_filter(filter_key):
        return False
    return _model_path_for_filter(filter_key) is not None


def dnn_status_text() -> str:
    """Return a human-readable summary of DNN detection readiness."""
    base = _dnn_base_settings()
    if not base:
        return (
            "DNN off — set [DNN] use_dnn_detection=true and onnx_model in settings.ini"
        )
    enabled = [key for key in SEGMENTATION_FILTER_KEYS if dnn_enabled_for_filter(key)]
    if not enabled:
        profile = _model_profile()
        if profile == "aerial":
            hint = "vehicle/person use VisDrone class ids when profile=aerial"
        else:
            hint = "vehicle/person use COCO class ids when profile=coco"
        return "DNN on but no filter ready — set dnn_<filter>_class_ids ({})".format(
            hint
        )
    model = base["global_model"]
    return "DNN ON ({}) filters: {}".format(
        base["model_type"],
        ", ".join(enabled),
    ) + ("" if not model else " model={}".format(os.path.basename(model)))


class OnnxYoloDetector:
    """Lazy-loaded YOLO ONNX net via cv2.dnn.readNetFromONNX."""

    def __init__(
        self, model_path: str, input_size: int = 640, model_type: str = "yolov8"
    ):
        cv2 = _get_cv2()
        if cv2 is None:
            raise RuntimeError("OpenCV is not available")
        if not hasattr(cv2, "dnn") or not hasattr(cv2.dnn, "readNetFromONNX"):
            raise RuntimeError("OpenCV DNN ONNX support is not available in this build")
        self._cv2 = cv2
        self._net = cv2.dnn.readNetFromONNX(model_path)
        self._input_size = max(320, int(input_size))
        self._model_type = model_type
        self._class_names = class_names_for_model(model_path)
        try:
            self._net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self._net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        except Exception as _exc:
            log.debug("ONNX preferable backend/target setup failed: %s", _exc)

    def detect(
        self,
        rgb: np.ndarray,
        class_ids: Optional[Sequence[int]] = None,
        conf_threshold: float = 0.35,
        nms_threshold: float = 0.45,
    ) -> List[Tuple[int, int, int, int, float, int, str]]:
        """Run inference; returns (x0, y0, x1, y1, confidence, class_id, class_name)."""
        h, w = rgb.shape[:2]
        length = max(h, w)
        square = np.zeros((length, length, 3), dtype=np.uint8)
        square[0:h, 0:w] = rgb
        letterbox_scale = length / float(self._input_size)
        blob = self._cv2.dnn.blobFromImage(
            square,
            scalefactor=1.0 / 255.0,
            size=(self._input_size, self._input_size),
            swapRB=True,
            crop=False,
        )
        self._net.setInput(blob)
        outputs = _forward_outputs(self._net)
        if self._model_type.startswith("yolov5"):
            return self._postprocess_yolov5(
                outputs,
                conf_threshold,
                nms_threshold,
                letterbox_scale,
                (h, w),
                class_ids,
            )
        return self._postprocess_yolov8(
            outputs, conf_threshold, nms_threshold, letterbox_scale, (h, w), class_ids
        )

    def _postprocess_yolov8(
        self,
        outputs,
        conf_threshold,
        nms_threshold,
        letterbox_scale,
        orig_hw,
        class_ids,
    ):
        """Match Ultralytics YOLOv8-OpenCV-ONNX-Python letterbox + transpose postprocess."""
        cv2 = self._cv2
        h, w = orig_hw
        if not outputs:
            return []
        out = outputs[0]
        if out.ndim == 3:
            out = out[0]
        out = cv2.transpose(out)
        allowed = None if class_ids is None else set(int(c) for c in class_ids)

        boxes: List[List[float]] = []
        scores: List[float] = []
        cids: List[int] = []
        for row in out:
            cls_scores = row[4:]
            cid = int(np.argmax(cls_scores))
            conf = float(cls_scores[cid])
            if conf < conf_threshold:
                continue
            if allowed is not None and cid not in allowed:
                continue
            cx, cy, bw, bh = row[:4]
            boxes.append(
                [float(cx - 0.5 * bw), float(cy - 0.5 * bh), float(bw), float(bh)]
            )
            scores.append(conf)
            cids.append(cid)

        if not boxes:
            return []

        idxs = _nms_indices(
            cv2.dnn.NMSBoxes(boxes, scores, conf_threshold, nms_threshold)
        )
        if not idxs:
            return []

        results = []
        for i in idxs:
            bx, by, bw, bh = boxes[i]
            x0 = max(0, int(bx * letterbox_scale))
            y0 = max(0, int(by * letterbox_scale))
            x1 = min(w, int((bx + bw) * letterbox_scale))
            y1 = min(h, int((by + bh) * letterbox_scale))
            if x1 <= x0 or y1 <= y0:
                continue
            cid = cids[i]
            names = self._class_names
            name = names[cid] if 0 <= cid < len(names) else str(cid)
            results.append((x0, y0, x1, y1, scores[i], cid, name))
        return results

    def _postprocess_yolov5(
        self,
        outputs,
        conf_threshold,
        nms_threshold,
        letterbox_scale,
        orig_hw,
        class_ids,
    ):
        cv2 = self._cv2
        h, w = orig_hw
        if not outputs:
            return []
        preds = outputs[0]
        if preds.ndim == 3:
            preds = preds[0]
        if preds.shape[-1] < 85:
            return []
        obj = preds[:, 4]
        cls = preds[:, 5:]
        class_ids_all = np.argmax(cls, axis=1)
        confidences = obj * cls[np.arange(cls.shape[0]), class_ids_all]
        keep = confidences >= conf_threshold
        if class_ids is not None:
            allowed = set(int(c) for c in class_ids)
            keep &= np.isin(class_ids_all, list(allowed))
        if not np.any(keep):
            return []
        preds = preds[keep]
        confidences = confidences[keep]
        class_ids_all = class_ids_all[keep]

        boxes = []
        scores = []
        cids = []
        for row, conf, cid in zip(preds, confidences, class_ids_all):
            cx, cy, bw, bh = row[:4]
            boxes.append(
                [
                    float(cx - 0.5 * bw),
                    float(cy - 0.5 * bh),
                    float(bw),
                    float(bh),
                ]
            )
            scores.append(float(conf))
            cids.append(int(cid))

        idxs = _nms_indices(
            cv2.dnn.NMSBoxes(boxes, scores, conf_threshold, nms_threshold)
        )
        if not idxs:
            return []
        results = []
        for i in idxs:
            bx, by, bw, bh = boxes[i]
            x0 = max(0, int(bx * letterbox_scale))
            y0 = max(0, int(by * letterbox_scale))
            x1 = min(w, int((bx + bw) * letterbox_scale))
            y1 = min(h, int((by + bh) * letterbox_scale))
            if x1 <= x0 or y1 <= y0:
                continue
            cid = cids[i]
            names = self._class_names
            name = names[cid] if 0 <= cid < len(names) else str(cid)
            results.append((x0, y0, x1, y1, scores[i], cid, name))
        return results


def _get_detector(model_path: str) -> Optional[OnnxYoloDetector]:
    base = _dnn_base_settings()
    if base is None or not model_path:
        return None
    if model_path in _load_failures:
        return None
    det = _detection_cache.get(model_path)
    if det is not None:
        return det
    try:
        det = OnnxYoloDetector(
            model_path,
            input_size=base["input_size"],
            model_type=base["model_type"],
        )
        _detection_cache[model_path] = det
        return det
    except Exception as exc:
        log.warning("ONNX model load failed (%s): %s", model_path, exc)
        _load_failures.add(model_path)
        return None


def boxes_to_score_map(
    shape: Tuple[int, int],
    detections: Sequence[Tuple[int, int, int, int, float, int, str]],
) -> Tuple[np.ndarray, List[Tuple[int, int, int, int]]]:
    """Build a float score map and box list from DNN detections."""
    h, w = shape
    score = np.zeros((h, w), dtype=np.float64)
    boxes: List[Tuple[int, int, int, int]] = []
    for x0, y0, x1, y1, conf, _cid, _name in detections:
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, x1), min(h, y1)
        if x1 <= x0 or y1 <= y0:
            continue
        boxes.append((x0, y0, x1, y1))
        score[y0:y1, x0:x1] = np.maximum(score[y0:y1, x0:x1], conf)
    return score, boxes


def try_dnn_detection(
    rgb: np.ndarray,
    filter_key: str,
) -> Optional[Tuple[np.ndarray, List[Tuple[int, int, int, int]], str]]:
    """
    Run YOLO ONNX for a segmentation filter.

    Returns (score_map, boxes, engine_label) or None → classical OpenCV fallback.
    """
    base = _dnn_base_settings()
    if base is None:
        return None
    class_ids = class_ids_for_filter(filter_key)
    if not class_ids:
        return None
    model_path = _model_path_for_filter(filter_key)
    if not model_path:
        return None
    detector = _get_detector(model_path)
    if detector is None:
        return None
    detections = detector.detect(
        rgb,
        class_ids=class_ids,
        conf_threshold=base["confidence"],
        nms_threshold=base["nms"],
    )
    score, boxes = boxes_to_score_map(rgb.shape[:2], detections)
    label = base["model_type"].upper() if base["model_type"] else "YOLO"
    return score, boxes, label


def reset_dnn_cache():
    """Clear cached nets (call after settings change)."""
    _detection_cache.clear()
    _load_failures.clear()
