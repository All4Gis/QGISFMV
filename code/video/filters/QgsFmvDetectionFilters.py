# -*- coding: utf-8 -*-
"""AI / CV detection filters (building, road, vehicle, person, fire, smoke, flood).

This module is a thin, backward-compatible façade. The actual implementation
now lives in sibling modules:

- ``QgsFmvDetectionGeometry`` — IoU / NMS / region scoring / multiscale / tracking.
- ``QgsFmvDetectionPipeline`` — shared OpenCV/numpy detection engine.
- ``QgsFmvDetectionScores`` — per-class scorers and detectors.
"""

from __future__ import annotations

import numpy as np

from QGISFMV.utils.core.QgsImageMat import convertMatToQImage, convertQImageToMat
from QGISFMV.video.filters.QgsFmvDetectionGeometry import reset_detection_state
from QGISFMV.video.filters.QgsFmvDetectionPipeline import _run_detection
from QGISFMV.video.filters.QgsFmvDetectionScores import (
    _building_detect_fallback,
    _building_detect_opencv,
    _building_structure_score,
    _fire_detect_fallback,
    _fire_detect_opencv,
    _fire_score,
    _flood_detect_fallback,
    _flood_detect_opencv,
    _flood_score,
    _person_detect_fallback,
    _person_detect_opencv,
    _person_score,
    _road_detect_fallback,
    _road_detect_opencv,
    _road_surface_score,
    _smoke_detect_fallback,
    _smoke_detect_opencv,
    _smoke_score,
    _vehicle_blob_score,
    _vehicle_detect_fallback,
    _vehicle_detect_opencv,
)
from QGISFMV.video.filters.QgsFmvFilterCore import FilterCore

__all__ = ["FmvDetectionFilters", "reset_detection_state"]


class FmvDetectionFilters:
    """Frame-wise object detection and segmentation filters."""

    # -- score helpers re-exported for backward compatibility (tests poke these) --
    _building_structure_score = staticmethod(_building_structure_score)
    _road_surface_score = staticmethod(_road_surface_score)
    _vehicle_blob_score = staticmethod(_vehicle_blob_score)
    _person_score = staticmethod(_person_score)
    _fire_score = staticmethod(_fire_score)
    _smoke_score = staticmethod(_smoke_score)
    _flood_score = staticmethod(_flood_score)

    @staticmethod
    def BuildingDetectionFilter(image):
        """Building highlight — OpenCV Canny + CC when available."""
        rgb = np.ascontiguousarray(convertQImageToMat(image, cn=3), dtype=np.uint8)
        result, _weight, _engine, _boxes = _run_detection(
            rgb,
            _building_structure_score,
            _building_detect_opencv,
            _building_detect_fallback,
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
        result, weight, engine, boxes = _run_detection(
            rgb,
            _road_surface_score,
            _road_detect_opencv,
            _road_detect_fallback,
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
        result, _weight, _engine, _boxes = _run_detection(
            rgb,
            _vehicle_blob_score,
            _vehicle_detect_opencv,
            _vehicle_detect_fallback,
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
        result, _weight, _engine, _boxes = _run_detection(
            rgb,
            _person_score,
            _person_detect_opencv,
            _person_detect_fallback,
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
        result, _weight, _engine, _boxes = _run_detection(
            rgb,
            _fire_score,
            _fire_detect_opencv,
            _fire_detect_fallback,
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
        result, _weight, _engine, _boxes = _run_detection(
            rgb,
            _smoke_score,
            _smoke_detect_opencv,
            _smoke_detect_fallback,
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
        result, _weight, _engine, _boxes = _run_detection(
            rgb,
            _flood_score,
            _flood_detect_opencv,
            _flood_detect_fallback,
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
