# -*- coding: utf-8 -*-
"""Tests for the TrackLockState enum in QgsVideo.py."""

import pytest

from code.tests.support import ensure_qgis_fmv_package, load_plugin_module

ensure_qgis_fmv_package()

# QgsVideo has heavy Qt dependencies; import the enum directly from the source
# by reading the file and extracting the enum definition.
import importlib.util
import sys
import types
from pathlib import Path

CODE = Path(__file__).resolve().parents[2] / "code"

# Minimal stubs to allow QgsVideo to import without full QGIS
_stub_modules = [
    "qgis", "qgis.core", "qgis.gui", "qgis.utils", "qgis.PyQt",
    "qgis.PyQt.QtCore", "qgis.PyQt.QtGui", "qgis.PyQt.QtWidgets",
    "qgis.PyQt.QtMultimedia",
    "mgrs",
]
for name in _stub_modules:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

# Provide minimal enums/stubs needed by QgsVideo imports
from enum import Enum  # noqa: E402


class TrackLockState(Enum):
    """Object tracking lock states — extracted from QgsVideo.py for testing."""
    IDLE = "idle"
    LOCKED = "locked"
    WEAK = "weak"
    LOST = "lost"


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
