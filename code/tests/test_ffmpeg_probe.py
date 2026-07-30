# -*- coding: utf-8 -*-
"""Tests for FFmpeg probe utilities (requires qgis.PyQt stubs or QGIS)."""

import pytest

pytest.importorskip("qgis")

from code.tests.support import load_plugin_module

probe = load_plugin_module(
    "utils/media/QgsFfmpegProbe.py", "QGISFMV.utils.media.QgsFfmpegProbe"
)


class TestParseTimecode:
    def test_simple_seconds(self):
        assert probe._parse_timecode("12.5") == 12.5

    def test_minutes_seconds(self):
        assert probe._parse_timecode("01:30.5") == 90.5

    def test_hours_minutes_seconds(self):
        assert probe._parse_timecode("01:02:03.0") == 3723.0

    def test_zero(self):
        assert probe._parse_timecode("0") == 0.0


class TestMediaDuration:
    def test_returns_float(self):
        result = probe._media_duration("nonexistent.mp4")
        assert isinstance(result, float)

    def test_returns_zero_for_missing(self):
        assert probe._media_duration("nonexistent.mp4") == 0.0


class TestProbeJson:
    def test_returns_none_for_empty_path(self):
        assert probe.probe_json("") is None

    def test_returns_none_for_none_path(self):
        assert probe.probe_json(None) is None

    def test_returns_none_for_missing_file(self):
        assert probe.probe_json("/nonexistent/video.mp4") is None

    def test_returns_none_for_invalid_path(self):
        assert probe.probe_json(12345) is None


class TestIsValidMedia:
    def test_returns_false_for_missing(self):
        assert probe.is_valid_media("/nonexistent/video.mp4") is False

    def test_returns_bool(self):
        result = probe.is_valid_media("/nonexistent/video.mp4")
        assert isinstance(result, bool)


class TestIsValidStream:
    def test_returns_false_for_non_stream(self):
        assert probe.is_valid_stream("/local/file.mp4") is False

    def test_returns_false_for_invalid_uri(self):
        assert probe.is_valid_stream("") is False


class TestProbeJsonToFile:
    def test_raises_for_missing_file(self, tmp_path):
        output = tmp_path / "output.json"
        with pytest.raises(OSError):
            probe.probe_json_to_file("/nonexistent/video.mp4", str(output))


class TestConvertVideo:
    def test_returns_none_for_missing_input(self, tmp_path, monkeypatch):
        monkeypatch.setattr(probe, "ffmpeg_path", "/usr/bin/ffmpeg")
        task = type("Task", (), {"isCanceled": lambda: False})()
        result = probe.convert_video(
            task, "/nonexistent/in.mp4", str(tmp_path / "out.mp4")
        )
        assert result is None
