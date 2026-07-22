# -*- coding: utf-8 -*-
"""Tests for ffmpeg subprocess helper (_spawn)."""

import subprocess
from unittest.mock import MagicMock, patch


def _spawn(
    cmds, t="ffmpeg", ffmpeg_path="ffmpeg", ffprobe_path="ffprobe", windows=False
):
    """Local copy of production logic under test (keeps tests free of QGIS imports)."""
    cmds = list(cmds)
    if t == "probe":
        cmds.insert(0, ffprobe_path)
    else:
        cmds.insert(0, ffmpeg_path)
        if "-c:v" in cmds and "-preset" not in cmds:
            try:
                idx = cmds.index("-c:v") + 2
                cmds.insert(idx, "-preset")
                cmds.insert(idx + 1, "ultrafast")
            except ValueError:
                pass

    return subprocess.Popen(
        cmds,
        shell=windows,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        close_fds=(not windows),
    )


class TestSpawn:
    @patch("subprocess.Popen")
    def test_does_not_mutate_input_list(self, popen_mock):
        popen_mock.return_value = MagicMock()
        original = ["-i", "video.ts", "-map", "0:d:0", "-f", "data", "-"]
        passed = list(original)
        _spawn(passed, t="ffmpeg")
        assert passed == original

    @patch("subprocess.Popen")
    def test_probe_uses_ffprobe(self, popen_mock):
        popen_mock.return_value = MagicMock()
        _spawn(["-show_format", "file.ts"], t="probe")
        args = popen_mock.call_args[0][0]
        assert args[0] == "ffprobe"

    @patch("subprocess.Popen")
    def test_encode_adds_preset_after_codec(self, popen_mock):
        popen_mock.return_value = MagicMock()
        _spawn(["-i", "in.mp4", "-c:v", "libx264", "out.mp4"], t="ffmpeg")
        args = popen_mock.call_args[0][0]
        assert "-preset" in args
        assert "ultrafast" in args

    @patch("subprocess.Popen")
    def test_copy_does_not_add_preset(self, popen_mock):
        popen_mock.return_value = MagicMock()
        _spawn(["-i", "in.mp4", "-c", "copy", "out.mp4"], t="ffmpeg")
        args = popen_mock.call_args[0][0]
        assert "-preset" not in args
