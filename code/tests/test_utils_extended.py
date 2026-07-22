# -*- coding: utf-8 -*-
"""Tests for utility functions in QgsFmvUtils (no QGIS runtime)."""

import pytest

try:
    from qgis.PyQt.QtCore import QSettings  # noqa: F401
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False

pytestmark = pytest.mark.skipif(not HAS_QGIS, reason="QGIS runtime not available")


class TestSecondsToTime:
    """Test the _seconds_to_time function."""

    @pytest.fixture
    def seconds_to_time(self):
        from code.tests.support import load_plugin_module

        utils = load_plugin_module(
            "utils/core/QgsFmvUtils.py", "QGISFMV.utils.core.QgsFmvUtils"
        )
        return utils._seconds_to_time

    def test_zero_seconds(self, seconds_to_time):
        assert seconds_to_time(0) == "00:00:00"

    def test_one_second(self, seconds_to_time):
        assert seconds_to_time(1) == "00:00:01"

    def test_one_minute(self, seconds_to_time):
        assert seconds_to_time(60) == "00:01:00"

    def test_one_hour(self, seconds_to_time):
        assert seconds_to_time(3600) == "01:00:00"

    def test_complex_time(self, seconds_to_time):
        assert seconds_to_time(3661) == "01:01:01"

    def test_large_time(self, seconds_to_time):
        assert seconds_to_time(86399) == "23:59:59"

    def test_float_truncated(self, seconds_to_time):
        assert seconds_to_time(65.7) == "00:01:05"

    def test_negative(self, seconds_to_time):
        # Negative seconds should still produce a formatted string
        result = seconds_to_time(-1)
        assert ":" in result


class TestSpawn:
    """Test the _spawn function."""

    @pytest.fixture
    def spawn(self):
        from code.tests.support import load_plugin_module

        utils = load_plugin_module(
            "utils/core/QgsFmvUtils.py", "QGISFMV.utils.core.QgsFmvUtils"
        )
        return utils._spawn

    def test_returns_popen(self, spawn):
        import subprocess

        proc = spawn(["--version"], t="ffprobe")
        assert isinstance(proc, subprocess.Popen)
        proc.kill()
        proc.wait()
