# -*- coding: utf-8 -*-
"""Tests for pymisb MISB local sets (migrated from legacy klvdata tests)."""

from pathlib import Path

from pymisb.klvdata.common import bytes_to_hexstr
from pymisb.klvdata.misb0601 import PrecisionTimeStamp, UASLocalMetadataSet

DATA_DIR = Path(__file__).resolve().parent / "data"


class TestUASLocalMetadataSet:
    def test_dynamic_constant_packet_roundtrip(self):
        klv = (DATA_DIR / "DynamicConstantMISMMSPacketData.bin").read_bytes()
        key = klv[0:16]
        length = klv[16:18]
        value = klv[18:]

        parsed = UASLocalMetadataSet(value)
        assert parsed.key == key
        assert parsed.length == length
        assert parsed.value == value
        assert bytes(parsed) == klv
        assert len(parsed.items) >= 20

    def test_nested_security_local_set_sample(self):
        key = b"\x06\x0e+4\x02\x0b\x01\x01\x0e\x01\x03\x01\x01\x00\x00\x00"
        length = b"\x1e"
        value = b"0\x1c\x01\x01\x01\x02\x01\x07\x03\x05//USA\x0c\x01\x07\r\x06\x00U\x00S\x00A\x16\x02\x00\n"
        klv = key + length + value

        parsed = UASLocalMetadataSet(value)
        assert parsed.key == key
        assert parsed.length == length
        assert bytes(parsed) == klv


class TestPrecisionTimeStamp:
    def test_timestamp_tlv_roundtrip(self):
        key = b"\x02"
        length = b"\x08"
        value = b"\x00\x04\x60\x50\x58\x4e\x01\x80"
        klv = key + length + value

        element = PrecisionTimeStamp(value)
        assert element.key == key
        assert element.length == length
        assert bytes_to_hexstr(bytes(element.value)) == bytes_to_hexstr(value)
        assert bytes(element) == klv
        assert str(element.value) == "2009-01-12 22:08:22+00:00"
