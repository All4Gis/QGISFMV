# -*- coding: utf-8 -*-
"""Tests for pymisb ST0601 encoder."""

import struct

from pymisb.common.encoder import (
    bcc_16,
    build_st0601_packet,
    encode_signed,
    encode_unsigned,
)
from pymisb.constants import UAS_LS_KEY


class TestEncodingHelpers:
    def test_encode_unsigned_clamps(self):
        assert encode_unsigned(400, 0, 360, 2) == encode_unsigned(360, 0, 360, 2)

    def test_encode_signed_zero(self):
        assert encode_signed(0, 20, 2) == 0


class TestBuildSt0601Packet:
    def test_packet_starts_with_uas_key(self):
        packet = build_st0601_packet({"timestamp_us": 1_700_000_000_000_000})
        assert packet.startswith(UAS_LS_KEY)

    def test_packet_includes_timestamp_tag(self):
        ts = 1_700_000_000_000_000
        packet = build_st0601_packet({"timestamp_us": ts})
        assert b"\x02\x08" in packet
        assert struct.pack(">Q", ts) in packet

    def test_bcc_matches_trailing_checksum(self):
        packet = build_st0601_packet(
            {
                "timestamp_us": 123456789000000,
                "platform_heading": 90.0,
                "sensor_lat": 40.0,
                "sensor_lon": -3.0,
            }
        )
        body, checksum = packet[:-2], struct.unpack(">H", packet[-2:])[0]
        assert checksum == bcc_16(body)
