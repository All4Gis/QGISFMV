# -*- coding: utf-8 -*-
"""Tests for pymisb.klvdata.klvparser (migrated from legacy klvdata tests)."""

from pathlib import Path

from pymisb.klvdata.klvparser import KLVParser

DATA_DIR = Path(__file__).resolve().parent / "data"


class TestKLVParserShortKey:
    def setup_method(self):
        self.key = b"\x02"
        self.length = b"\x08"
        self.value = b"\x00\x04\x60\x50\x58\x4e\x01\x80"
        self.packet = self.key + self.length + self.value
        self.parser = KLVParser(self.packet, key_length=1)

    def test_key(self):
        key, _value = next(self.parser)
        assert key == self.key

    def test_value(self):
        _key, value = next(self.parser)
        assert value == self.value


class TestKLVParserLongKey:
    def setup_method(self):
        self.packet = (DATA_DIR / "DynamicConstantMISMMSPacketData.bin").read_bytes()
        self.key = self.packet[0:16]
        self.length = self.packet[16:18]
        self.value = self.packet[18:]
        self.parser = KLVParser(self.packet, key_length=16)

    def test_key(self):
        key, _value = next(self.parser)
        assert key == self.key

    def test_value(self):
        _key, value = next(self.parser)
        assert value == self.value
