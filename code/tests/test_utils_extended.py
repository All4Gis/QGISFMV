# -*- coding: utf-8 -*-
"""Tests for utility time helpers and spawn (spawn still needs ffmpeg/QGIS env)."""

import pytest

from code.tests.support import ensure_qgis_fmv_package, load_plugin_module

ensure_qgis_fmv_package()
_fmt = load_plugin_module("utils/formatting.py", "QGISFMV.utils.formatting")


class TestSecondsToTime:
    """Test seconds_to_time / legacy _seconds_to_time alias."""

    def test_zero_seconds(self):
        assert _fmt.seconds_to_time(0) == "00:00:00"

    def test_one_second(self):
        assert _fmt.seconds_to_time(1) == "00:00:01"

    def test_one_minute(self):
        assert _fmt.seconds_to_time(60) == "00:01:00"

    def test_one_hour(self):
        assert _fmt.seconds_to_time(3600) == "01:00:00"

    def test_complex_time(self):
        assert _fmt.seconds_to_time(3661) == "01:01:01"

    def test_large_time(self):
        assert _fmt.seconds_to_time(86399) == "23:59:59"

    def test_float_truncated(self):
        assert _fmt.seconds_to_time(65.7) == "00:01:05"

    def test_negative(self):
        result = _fmt.seconds_to_time(-1)
        assert ":" in result


class TestTimeToSeconds:
    def test_roundtrip(self):
        assert _fmt.time_to_seconds("01:02:03.500000") == pytest.approx(3723.5)

    def test_zero(self):
        assert _fmt.time_to_seconds("00:00:00.000000") == 0.0


class TestSpawn:
    """Test the _spawn function (needs QgsFmvUtils + ffmpeg)."""

    @pytest.fixture
    def spawn(self):
        try:
            from qgis.PyQt.QtCore import QSettings  # noqa: F401
        except ImportError:
            pytest.skip("QGIS runtime not available")
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
