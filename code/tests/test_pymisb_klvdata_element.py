# -*- coding: utf-8 -*-
"""Tests for pymisb.klvdata.element (migrated from legacy klvdata tests)."""

from pymisb.klvdata.element import UnknownElement

SAMPLE_KEY = b"\x02"
SAMPLE_VALUE = b"\x00\x04\x60\x50\x58\x4e\x01\x80"


class TestUnknownElement:
    def test_key_length_value(self):
        element = UnknownElement(SAMPLE_KEY, SAMPLE_VALUE)
        assert element.key == SAMPLE_KEY
        assert element.length == b"\x08"
        assert element.value == SAMPLE_VALUE

    def test_packet_bytes(self):
        element = UnknownElement(SAMPLE_KEY, SAMPLE_VALUE)
        assert bytes(element) == b"\x02\x08\x00\x04\x60\x50\x58\x4e\x01\x80"

    def test_name_and_str(self):
        element = UnknownElement(SAMPLE_KEY, SAMPLE_VALUE)
        assert element.name == "UnknownElement"
        assert (
            str(element) == "UnknownElement: (b'\\x02', 8, b'\\x00\\x04`PXN\\x01\\x80')"
        )

    def test_repr_roundtrip(self):
        element = UnknownElement(SAMPLE_KEY, SAMPLE_VALUE)
        restored = eval(repr(element))
        assert isinstance(restored, UnknownElement)
        assert restored.key == SAMPLE_KEY
        assert restored.value == SAMPLE_VALUE
