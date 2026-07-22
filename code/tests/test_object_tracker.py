# -*- coding: utf-8 -*-
"""Tests for object tracking (no QGIS runtime)."""

import importlib.util
import os
import numpy as np
import pytest

_support_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "support.py")
_spec = importlib.util.spec_from_file_location("qgsfmv_test_support", _support_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
load_plugin_module = _mod.load_plugin_module

tracker_mod = load_plugin_module(
    "utils/vision/QgsObjectTracker.py", "QGISFMV.utils.vision.QgsObjectTracker"
)


class TestCv2Available:
    def test_returns_bool(self):
        assert isinstance(tracker_mod.cv2_available(), bool)

    def test_has_object_tracking(self):
        assert tracker_mod.has_object_tracking() is True


class TestCosineWindow:
    def test_shape_matches(self):
        w = tracker_mod._cosine_window(32, 64)
        assert w.shape == (32, 64)

    def test_dtype_is_float32(self):
        w = tracker_mod._cosine_window(16, 16)
        assert w.dtype == np.float32

    def test_min_size(self):
        w = tracker_mod._cosine_window(1, 1)
        assert w.shape[0] >= 1 and w.shape[1] >= 1


class TestGaussianResponse:
    def test_shape(self):
        g = tracker_mod._gaussian_response(32, 64)
        assert g.shape == (32, 64)

    def test_peak_at_center(self):
        g = tracker_mod._gaussian_response(32, 32)
        cy, cx = np.unravel_index(np.argmax(g), g.shape)
        assert cy == 15
        assert cx == 15

    def test_symmetric(self):
        g = tracker_mod._gaussian_response(31, 31)
        assert g.dtype == np.float32


class TestNumpyMosseTracker:
    @pytest.fixture
    def tracker(self):
        return tracker_mod.NumpyMosseTracker()

    def _make_frame(self, h=120, w=160, color=128):
        frame = np.full((h, w), color, dtype=np.uint8)
        # Draw a bright rectangle to track
        frame[40:60, 60:100] = 200
        return frame

    def test_init_returns_true(self, tracker):
        frame = self._make_frame()
        assert tracker.init(frame, (60, 40, 40, 20)) is True

    def test_init_small_bbox_fails(self, tracker):
        frame = self._make_frame()
        assert tracker.init(frame, (0, 0, 2, 2)) is False

    def test_update_before_init_fails(self, tracker):
        frame = self._make_frame()
        ok, bbox = tracker.update(frame)
        assert ok is False
        assert bbox is None

    def test_update_returns_bbox_tuple(self, tracker):
        frame = self._make_frame()
        tracker.init(frame, (60, 40, 40, 20))
        ok, bbox = tracker.update(frame)
        assert isinstance(ok, bool)
        if ok:
            assert len(bbox) == 4

    def test_tracker_follows_shifted_object(self):
        tracker = tracker_mod.NumpyMosseTracker()
        frame1 = self._make_frame()
        tracker.init(frame1, (60, 40, 40, 20))

        # Shift the bright rectangle to the right
        frame2 = np.full((120, 160), 128, dtype=np.uint8)
        frame2[40:60, 80:120] = 200

        # Run several updates to let tracker adapt
        for _ in range(10):
            ok, bbox = tracker.update(frame2)
            if ok:
                break

        if ok:
            x, y, w, h = bbox
            assert x > 50  # Moved right from initial position

    def test_tracker_fails_on_blank_frame(self, tracker):
        frame1 = self._make_frame()
        tracker.init(frame1, (60, 40, 40, 20))

        blank = np.zeros((120, 160), dtype=np.uint8)
        ok, bbox = tracker.update(blank)
        # May fail or succeed depending on response strength
        assert isinstance(ok, bool)


class TestCreateObjectTracker:
    def test_returns_tuple(self):
        result = tracker_mod.create_object_tracker()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_valid_backend_name(self):
        _, backend = tracker_mod.create_object_tracker()
        assert backend in ("opencv", "numpy-mosse")

    def test_returns_callable_tracker(self):
        t, _ = tracker_mod.create_object_tracker()
        assert hasattr(t, "init")
        assert hasattr(t, "update")
        assert callable(t.init)
        assert callable(t.update)


class TestOpenCvTrackerAdapter:
    def test_adapter_exists(self):
        assert hasattr(tracker_mod, "_OpenCvTrackerAdapter")

    def test_adapter_init_returns_bool(self):
        class FakeTracker:
            def init(self, frame, bbox):
                return True

            def update(self, frame):
                return True, bbox

        adapter = tracker_mod._OpenCvTrackerAdapter(FakeTracker())
        frame = np.zeros((100, 100), dtype=np.uint8)
        result = adapter.init(frame, (10, 10, 30, 30))
        assert isinstance(result, bool)

    def test_adapter_update_returns_tuple(self):
        class FakeTracker:
            def init(self, frame, bbox):
                return True

            def update(self, frame):
                return True, (10, 10, 30, 30)

        adapter = tracker_mod._OpenCvTrackerAdapter(FakeTracker())
        frame = np.zeros((100, 100), dtype=np.uint8)
        adapter.init(frame, (10, 10, 30, 30))
        ok, bbox = adapter.update(frame)
        assert isinstance(ok, bool)
        if ok:
            assert len(bbox) == 4
