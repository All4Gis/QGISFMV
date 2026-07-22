# -*- coding: utf-8 -*-
"""Tests for pymisb.klvdata.streamparser (migrated from legacy klvdata tests)."""

from pathlib import Path

from pymisb.klvdata.misb0601 import UASLocalMetadataSet
from pymisb.klvdata.streamparser import StreamParser

DATA_DIR = Path(__file__).resolve().parent / "data"


class TestStreamParser:
    def test_parses_dynamic_constant_sample(self):
        packet = (DATA_DIR / "DynamicConstantMISMMSPacketData.bin").read_bytes()
        parsed = list(StreamParser(packet))
        assert len(parsed) == 1
        assert isinstance(parsed[0], UASLocalMetadataSet)
        assert parsed[0].SensorLatitude is not None
        assert parsed[0].SensorLongitude is not None

    def test_parses_dynamic_only_sample(self):
        packet = (DATA_DIR / "DynamicOnlyMISMMSPacketData.bin").read_bytes()
        parsed = list(StreamParser(packet))
        assert len(parsed) >= 1
        assert all(isinstance(item, UASLocalMetadataSet) for item in parsed)
