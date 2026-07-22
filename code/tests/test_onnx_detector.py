# -*- coding: utf-8 -*-
"""Tests for YOLO/ONNX aerial vs COCO class tables."""

from QGISFMV.video.dnn.QgsFmvOnnxDetector import (
    FILTER_COCO_CLASSES,
    FILTER_VISDRONE_CLASSES,
    VISDRONE_CLASS_NAMES,
    class_names_for_model,
)


def test_visdrone_vehicle_and_person_ids():
    assert FILTER_VISDRONE_CLASSES["vehicle"] == (3, 4, 5, 8, 9)
    assert FILTER_VISDRONE_CLASSES["person"] == (0, 1)
    assert VISDRONE_CLASS_NAMES[3] == "car"


def test_class_names_follow_model_path():
    assert class_names_for_model("/tmp/visdrone-yolov8n.onnx")[8] == "bus"
    assert class_names_for_model("/tmp/yolov8n.onnx")[2] == "car"
    assert FILTER_COCO_CLASSES["vehicle"] == (2, 3, 5, 7)
