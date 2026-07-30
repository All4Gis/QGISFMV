# -*- coding: utf-8 -*-
"""Tests for the TrackLockState enum in QgsVideoState.py."""

from code.tests.support import load_plugin_module

import pytest

# QgsVideoState.py has no Qt/QGIS dependencies, so it can be loaded directly
# without any runtime stubs.
state_mod = load_plugin_module(
    "video/playback/QgsVideoState.py", "QGISFMV.video.playback.QgsVideoState"
)
TrackLockState = state_mod.TrackLockState


class TestTrackLockState:
    def test_idle_value(self):
        assert TrackLockState.IDLE.value == "idle"

    def test_locked_value(self):
        assert TrackLockState.LOCKED.value == "locked"

    def test_weak_value(self):
        assert TrackLockState.WEAK.value == "weak"

    def test_lost_value(self):
        assert TrackLockState.LOST.value == "lost"

    def test_all_states_are_distinct(self):
        values = [s.value for s in TrackLockState]
        assert len(values) == len(set(values))

    def test_enum_member_count(self):
        assert len(TrackLockState) == 4

    def test_comparison(self):
        assert TrackLockState.IDLE == TrackLockState.IDLE
        assert TrackLockState.IDLE != TrackLockState.LOCKED

    def test_from_value(self):
        assert TrackLockState("idle") == TrackLockState.IDLE
        assert TrackLockState("locked") == TrackLockState.LOCKED
        assert TrackLockState("weak") == TrackLockState.WEAK
        assert TrackLockState("lost") == TrackLockState.LOST

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            TrackLockState("invalid")
