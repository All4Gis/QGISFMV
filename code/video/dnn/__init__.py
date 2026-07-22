# -*- coding: utf-8 -*-
"""YOLO / ONNX detection (OpenCV DNN)."""

__all__ = [
    "dnn_status_text",
    "reset_dnn_cache",
    "try_dnn_detection",
    "configure_aerial_dnn",
    "ensure_default_dnn_assets",
]


def __getattr__(name):
    if name in ("dnn_status_text", "reset_dnn_cache", "try_dnn_detection"):
        from QGISFMV.video.dnn import QgsFmvOnnxDetector as _mod

        return getattr(_mod, name)
    if name in ("configure_aerial_dnn", "ensure_default_dnn_assets"):
        from QGISFMV.video.dnn import QgsFmvModelSetup as _mod

        return getattr(_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
