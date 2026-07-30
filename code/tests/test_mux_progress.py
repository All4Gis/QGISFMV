# -*- coding: utf-8 -*-
"""Unit tests for pymisb mux progress helpers."""

from code.tests.support import ensure_pymisb_installed

import pytest


class _FakeTask(object):
    def __init__(self):
        self.progress = []
        self.cancelled = False

    def setProgress(self, value):
        self.progress.append(int(value))

    def isCanceled(self):
        return self.cancelled


def _require_mux_helpers():
    """Skip when this pymisb build no longer exposes the private helpers."""
    ensure_pymisb_installed()
    from pymisb.mux import engine

    if not hasattr(engine, "_parse_timecode") or not hasattr(
        engine, "_run_ffmpeg_with_progress"
    ):
        pytest.skip(
            "pymisb.mux.engine no longer exposes _parse_timecode / "
            "_run_ffmpeg_with_progress (API changed)"
        )
    return engine


class TestMuxProgress:
    def test_parse_timecode_seconds(self):
        engine = _require_mux_helpers()
        assert engine._parse_timecode("12.5") == 12.5

    def test_parse_timecode_hms(self):
        engine = _require_mux_helpers()
        assert engine._parse_timecode("0:01:02") == 62.0

    def test_mux_with_ffmpeg_reports_progress(self, monkeypatch, tmp_path):
        engine = _require_mux_helpers()

        video = tmp_path / "in.mp4"
        out = tmp_path / "out.ts"
        video.write_bytes(b"fake")

        task = _FakeTask()
        packets = [(0.0, b"\x01"), (1.0, b"\x02")]

        def fake_inject(tmp_ts, pkts, out_ts):
            assert pkts == packets
            from pathlib import Path

            Path(out_ts).write_bytes(b"ts")

        monkeypatch.setattr(engine, "inject_klv_into_ts", fake_inject)
        monkeypatch.setattr(engine, "_run_ffmpeg_with_progress", lambda *a, **k: True)
        monkeypatch.setattr(engine.shutil, "which", lambda name: "ffmpeg")

        engine.mux_with_ffmpeg(str(video), packets, str(out), task=task)
        assert out.is_file()
        assert task.progress[0] == 5
        assert task.progress[-1] == 100
