# -*- coding: utf-8 -*-
"""Tests for detection geometry helpers (IoU / NMS / tracking) — no QGIS GUI."""

import numpy as np

from code.tests.support import ensure_qgis_fmv_package, load_plugin_module


def _geom():
    ensure_qgis_fmv_package()
    return load_plugin_module(
        "video/filters/QgsFmvDetectionGeometry.py",
        "QGISFMV.video.filters.QgsFmvDetectionGeometry",
    )


class TestBoxIoU:
    def test_identical_boxes(self):
        g = _geom()
        box = (0, 0, 10, 10)
        assert g._box_iou(box, box) == pytest_approx_one()

    def test_no_overlap(self):
        g = _geom()
        assert g._box_iou((0, 0, 5, 5), (10, 10, 20, 20)) == 0.0

    def test_partial_overlap(self):
        g = _geom()
        iou = g._box_iou((0, 0, 10, 10), (5, 5, 15, 15))
        assert 0.1 < iou < 0.5


def pytest_approx_one():
    return 1.0


class TestNmsBoxes:
    def test_empty(self):
        g = _geom()
        boxes, scores = g._nms_boxes([], [])
        assert boxes == [] and scores == []

    def test_keeps_highest_overlapping(self):
        g = _geom()
        boxes = [(0, 0, 10, 10), (1, 1, 11, 11), (50, 50, 60, 60)]
        scores = [0.9, 0.8, 0.7]
        kept_boxes, kept_scores = g._nms_boxes(boxes, scores, iou_thresh=0.3)
        assert len(kept_boxes) == 2
        assert kept_scores[0] == 0.9
        assert (50, 50, 60, 60) in kept_boxes


class TestRegionScores:
    def test_mean_inside_box(self):
        g = _geom()
        score = np.zeros((20, 20), dtype=np.float32)
        score[5:10, 5:10] = 1.0
        out = g._region_scores(score, [(5, 5, 10, 10), (0, 0, 2, 2)])
        assert out[0] == pytest_approx_one()
        assert out[1] == 0.0


class TestTrackIds:
    def test_assigns_stable_ids(self, monkeypatch):
        g = _geom()
        g.reset_detection_state()
        # Force tracking on without settings.
        tuning = load_plugin_module(
            "video/filters/QgsFmvFilterTuning.py",
            "QGISFMV.video.filters.QgsFmvFilterTuning",
        )
        monkeypatch.setattr(tuning, "tracking_enabled", lambda: True)
        ids1 = g._assign_track_ids("vehicles", [(0, 0, 10, 10)])
        ids2 = g._assign_track_ids("vehicles", [(1, 1, 11, 11)])
        assert ids1 == [1]
        assert ids2 == [1]

    def test_disabled_returns_empty(self, monkeypatch):
        g = _geom()
        g.reset_detection_state()
        tuning = load_plugin_module(
            "video/filters/QgsFmvFilterTuning.py",
            "QGISFMV.video.filters.QgsFmvFilterTuning",
        )
        monkeypatch.setattr(tuning, "tracking_enabled", lambda: False)
        assert g._assign_track_ids("vehicles", [(0, 0, 10, 10)]) == []


class TestResetDetectionState:
    def test_clears_globals(self):
        g = _geom()
        g._detection_ema["x"] = 1
        g._track_state["y"] = 2
        g.reset_detection_state()
        assert g._detection_ema == {}
        assert g._track_state == {}
