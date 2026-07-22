# -*- coding: utf-8 -*-
"""Tests for MISB packet coordinate extraction."""

from pathlib import Path

import pymisb.klvdata  # noqa: F401
from pymisb.klvdata.streamparser import StreamParser


class TestMisbCoords:
    def test_sample_packet_exposes_frame_center(self):
        data_path = (
            Path(__file__).resolve().parent
            / "data"
            / "DynamicConstantMISMMSPacketData.bin"
        )
        raw = data_path.read_bytes()
        packet = next(iter(StreamParser(raw)))
        assert packet.FrameCenterLatitude is not None
        assert packet.FrameCenterLongitude is not None

    def test_coords_from_stream_helper(self):
        data_path = (
            Path(__file__).resolve().parent
            / "data"
            / "DynamicConstantMISMMSPacketData.bin"
        )
        raw = data_path.read_bytes()
        coords = []
        for packet in StreamParser(raw):
            lat = packet.FrameCenterLatitude or packet.SensorLatitude
            lon = packet.FrameCenterLongitude or packet.SensorLongitude
            if lat is not None and lon is not None:
                coords = [lat, lon]
                break
        assert len(coords) == 2

    def test_precision_timestamp_from_sample_packet(self):
        data_path = (
            Path(__file__).resolve().parent
            / "data"
            / "DynamicConstantMISMMSPacketData.bin"
        )
        raw = data_path.read_bytes()
        packet = next(iter(StreamParser(raw)))
        stamp = packet.items.get(b"\x02")
        assert stamp is not None
        assert stamp.value is not None
        ts_value = stamp.value.value if hasattr(stamp.value, "value") else stamp.value
        assert ts_value.timestamp() > 1_000_000_000
