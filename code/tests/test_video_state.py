# -*- coding: utf-8 -*-
"""Tests for video state classes (no QGIS runtime)."""

import pytest

from code.tests.support import load_plugin_module


class TestInteractionState:
    @pytest.fixture
    def state(self):
        module = load_plugin_module(
            "video/playback/QgsVideoState.py", "QGISFMV.video.playback.QgsVideoState"
        )
        return module.InteractionState()

    def test_initial_all_false(self, state):
        assert state.pointDrawer is False
        assert state.measureDistance is False
        assert state.measureArea is False
        assert state.lineDrawer is False
        assert state.polygonDrawer is False
        assert state.magnifier is False
        assert state.stamp is False
        assert state.objectTracking is False
        assert state.censure is False
        assert state.HandDraw is False

    def test_clear_resets_to_default(self, state):
        state.pointDrawer = True
        state.magnifier = True
        state.objectTracking = True
        state.clear()
        assert state.pointDrawer is False
        assert state.magnifier is False
        assert state.objectTracking is False

    def test_set_flags_independently(self, state):
        state.pointDrawer = True
        state.measureDistance = True
        assert state.polygonDrawer is False
        assert state.lineDrawer is False

    def test_clear_then_set(self, state):
        state.pointDrawer = True
        state.clear()
        state.measureArea = True
        assert state.pointDrawer is False
        assert state.measureArea is True


class TestFilterState:
    @pytest.fixture
    def state(self):
        module = load_plugin_module(
            "video/playback/QgsVideoState.py", "QGISFMV.video.playback.QgsVideoState"
        )
        return module.FilterState()

    def test_initial_all_false(self, state):
        assert state.contrastFilter is False
        assert state.monoFilter is False
        assert state.MirroredHFilter is False
        assert state.edgeDetectionFilter is False
        assert state.grayColorFilter is False
        assert state.invertColorFilter is False
        assert state.brightnessContrastFilter is False

    def test_initial_brightness_contrast_zero(self, state):
        assert state.brightness == 0
        assert state.contrastLevel == 0

    def test_clear_resets_all(self, state):
        state.contrastFilter = True
        state.brightness = 50
        state.contrastLevel = 25
        state.clear()
        assert state.contrastFilter is False
        assert state.brightness == 0
        assert state.contrastLevel == 0

    def test_has_filters_slow_none(self, state):
        assert state.hasFiltersSlow() is False

    def test_has_filters_slow_contrast(self, state):
        state.contrastFilter = True
        assert state.hasFiltersSlow() is True

    def test_has_filters_slow_edge_detection(self, state):
        state.edgeDetectionFilter = True
        assert state.hasFiltersSlow() is True

    def test_has_filters_slow_brightness_contrast(self, state):
        state.brightnessContrastFilter = True
        assert state.hasFiltersSlow() is True

    def test_has_filters_slow_fast_filters_not_slow(self, state):
        state.monoFilter = True
        state.MirroredHFilter = True
        state.grayColorFilter = True
        state.invertColorFilter = True
        assert state.hasFiltersSlow() is False
