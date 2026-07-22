# -*- coding: utf-8 -*-
"""Tests for pymisb TS helpers."""

import os

from pymisb.common.ts import default_output, write_klv_stream


class TestDefaultOutput:
    def test_mp4_to_misb_ts(self, tmp_path):
        video = tmp_path / "flight.mp4"
        video.write_bytes(b"")
        out = default_output(str(video))
        assert out.endswith("flight_MISB.ts")
        assert os.path.dirname(out) == str(tmp_path)


class TestWriteKlvStream:
    def test_writes_concatenated_packets(self, tmp_path):
        packets = [(0.0, b"\x01\x02"), (1.0, b"\x03\x04")]
        out_path = tmp_path / "out.klv"
        result = write_klv_stream(packets, str(out_path))
        assert result == str(out_path)
        assert out_path.read_bytes() == b"\x01\x02\x03\x04"
