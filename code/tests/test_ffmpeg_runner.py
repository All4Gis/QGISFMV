# -*- coding: utf-8 -*-
"""Tests for unified FFmpeg subprocess runner."""

from code.tests.support import load_plugin_module
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def runner():
    return load_plugin_module(
        "utils/media/QgsFfmpegRunner.py",
        "QGISFMV.utils.media.QgsFfmpegRunner",
    )


class TestFfmpegRunner:
    @patch("subprocess.Popen")
    def test_spawn_probe_uses_ffprobe(self, popen_mock, runner):
        popen_mock.return_value = MagicMock()
        with patch.object(runner, "ensure_paths", return_value=("ffmpeg", "ffprobe")):
            runner._ffmpeg_path = "ffmpeg"
            runner._ffprobe_path = "ffprobe"
            runner.spawn(["-show_format", "file.ts"], t="probe")
        args = popen_mock.call_args[0][0]
        assert args[0] == "ffprobe"

    @patch("subprocess.Popen")
    def test_spawn_encode_adds_preset(self, popen_mock, runner):
        popen_mock.return_value = MagicMock()
        with patch.object(runner, "ensure_paths", return_value=("ffmpeg", "ffprobe")):
            runner._ffmpeg_path = "ffmpeg"
            runner._ffprobe_path = "ffprobe"
            runner.spawn(["-i", "in.mp4", "-c:v", "libx264", "out.mp4"], t="ffmpeg")
        args = popen_mock.call_args[0][0]
        assert args[0] == "ffmpeg"
        assert "-preset" in args
        assert "ultrafast" in args

    @patch("subprocess.Popen")
    def test_popen_ffmpeg_raises_when_missing(self, popen_mock, runner):
        with patch.object(runner, "ensure_paths", return_value=("", "")):
            runner._ffmpeg_path = ""
            with patch("shutil.which", return_value=None):
                with pytest.raises(RuntimeError, match="not configured"):
                    runner.popen_ffmpeg(["-i", "x"])

    def test_invalidate_resets_defaults(self, runner):
        runner._ffmpeg_path = "/tmp/custom/ffmpeg"
        runner._ffprobe_path = "/tmp/custom/ffprobe"
        runner.invalidate_paths()
        assert "ffmpeg" in runner._ffmpeg_path
        assert "ffprobe" in runner._ffprobe_path
