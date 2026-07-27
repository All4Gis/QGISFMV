# -*- coding: utf-8 -*-
"""Tests for QGISFMV.utils.constants — verify all constants are defined and sane."""

from code.tests.support import ensure_qgis_fmv_package, load_plugin_module

ensure_qgis_fmv_package()
mod = load_plugin_module("utils/constants.py")


class TestPlayerConstants:
    def test_skip_interval_positive(self):
        assert mod.SKIP_INTERVAL_MS > 0

    def test_skip_interval_is_10s(self):
        assert mod.SKIP_INTERVAL_MS == 10_000

    def test_slow_playback_rate(self):
        assert 0 < mod.SLOW_PLAYBACK_RATE < 1.0

    def test_max_videos_in_manager(self):
        assert mod.MAX_VIDEOS_IN_MANAGER >= 1


class TestTrackingConstants:
    def test_track_max_misses_positive(self):
        assert mod.TRACK_MAX_MISSES > 0

    def test_track_timer_interval_positive(self):
        assert mod.TRACK_TIMER_INTERVAL_MS > 0

    def test_track_weak_threshold_less_than_max(self):
        assert mod.TRACK_WEAK_THRESHOLD < mod.TRACK_MAX_MISSES


class TestDetectionConstants:
    def test_base_brightness_range(self):
        assert 0.0 <= mod.CONFIDENCE_BASE_BRIGHTNESS <= 1.0

    def test_tint_range_positive(self):
        assert mod.CONFIDENCE_TINT_RANGE > 0

    def test_tint_intensity_range(self):
        assert 0.0 <= mod.CONFIDENCE_TINT_INTENSITY <= 1.0


class TestMosaicConstants:
    def test_interval_positive(self):
        assert mod.MOSAIC_MIN_INTERVAL_SEC > 0

    def test_move_meters_positive(self):
        assert mod.MOSAIC_MIN_MOVE_METERS > 0

    def test_frame_dimension_positive(self):
        assert mod.MOSAIC_MAX_FRAME_DIMENSION > 0

    def test_feather_positive(self):
        assert mod.MOSAIC_FEATHER_PX > 0

    def test_output_size_positive(self):
        assert mod.MOSAIC_MAX_OUTPUT_SIZE > 0

    def test_grow_ratio_above_one(self):
        assert mod.MOSAIC_FOOTPRINT_GROW_RATIO > 1.0
