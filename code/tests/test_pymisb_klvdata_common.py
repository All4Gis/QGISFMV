# -*- coding: utf-8 -*-
"""Tests for pymisb.klvdata.common (BER, datetime, hex helpers)."""

from pathlib import Path

import pytest
from pymisb.klvdata.common import (
    ber_decode,
    ber_encode,
    bytes_to_datetime,
    bytes_to_hexstr,
    datetime_to_bytes,
    hexstr_to_bytes,
    packet_checksum,
)


class TestDateTime:
    def test_datetime_roundtrip(self):
        sample = b"\x00\x04\x60\x50\x58\x4e\x01\x80"
        assert datetime_to_bytes(bytes_to_datetime(sample)) == sample


class TestBERLength:
    @pytest.mark.parametrize(
        "encoded",
        [
            b"\x00",
            b"\x01",
            b"\x08",
            b"\x7f",
            b"\x81\x80",
            b"\x81\xff",
            b"\x82\xff\xff",
            b"\x83\xff\xff\xff",
        ],
    )
    def test_ber_decode_encode_roundtrip(self, encoded):
        assert ber_encode(ber_decode(encoded)) == encoded

    @pytest.mark.parametrize(
        "value", [0, 1, 8, 127, 128, 254, 255, 256, 900, 9000, 90000, 900000]
    )
    def test_ber_encode_decode_values(self, value):
        assert ber_decode(ber_encode(value)) == value


class TestHexStrings:
    def test_hexstr_to_bytes(self):
        assert hexstr_to_bytes("06 0E 2B 34") == b"\x06\x0e\x2b\x34"

    def test_bytes_to_hexstr(self):
        assert bytes_to_hexstr(b"\x06\x0e\x2b\x34") == "06 0E 2B 34"


class TestChecksum:
    def test_dynamic_only_sample(self):
        data_path = (
            Path(__file__).resolve().parent / "data" / "DynamicOnlyMISMMSPacketData.bin"
        )
        packet = data_path.read_bytes()
        assert packet_checksum(packet) == b"\xc8\x50"

    def test_dynamic_constant_sample(self):
        data_path = (
            Path(__file__).resolve().parent
            / "data"
            / "DynamicConstantMISMMSPacketData.bin"
        )
        packet = data_path.read_bytes()
        assert packet_checksum(packet) == b"\x3e\x1e"
