# -*- coding: utf-8 -*-
"""End-to-end pymisb KLV parsing using MISB ST 0902.5 sample packets."""

from pathlib import Path

from pymisb.klvdata.common import packet_checksum
from pymisb.klvdata.misb0601 import UASLocalMetadataSet
from pymisb.klvdata.streamparser import StreamParser

DATA_DIR = Path(__file__).resolve().parent / "data"


class TestMisbSamplePackets:
    def test_dynamic_constant_checksum(self):
        packet = (DATA_DIR / "DynamicConstantMISMMSPacketData.bin").read_bytes()
        assert packet_checksum(packet) == b"\x3e\x1e"

    def test_dynamic_only_checksum(self):
        packet = (DATA_DIR / "DynamicOnlyMISMMSPacketData.bin").read_bytes()
        assert packet_checksum(packet) == b"\xc8\x50"

    def test_dynamic_constant_metadata_fields(self):
        packet = (DATA_DIR / "DynamicConstantMISMMSPacketData.bin").read_bytes()
        meta = next(iter(StreamParser(packet)))
        assert isinstance(meta, UASLocalMetadataSet)
        assert 50 < meta.SensorLatitude < 70
        assert 100 < meta.SensorLongitude < 150
        assert meta.FrameCenterLatitude is not None
        assert meta.FrameCenterLongitude is not None
