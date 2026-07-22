# -*- coding: utf-8 -*-
"""Playback timing helpers (no QGIS runtime)."""


def _legacyFrameIndex(ms, fps):
    return max(0, int((ms / 1000.0) * fps))


def _roundedFrameIndex(ms, fps):
    return max(0, int(round((ms / 1000.0) * fps)))


class TestPlaybackFrameIndex:
    def test_thirty_fps_tick_no_longer_sticks_on_frame_zero(self):
        fps = 29.97002997002997
        step_ms = int(1000.0 / fps)
        next_ms = 0 + step_ms
        assert _legacyFrameIndex(next_ms, fps) == 0
        assert _roundedFrameIndex(next_ms, fps) == 1
