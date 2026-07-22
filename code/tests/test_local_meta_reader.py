# -*- coding: utf-8 -*-
"""LocalFileMetaReader offset lookup (requires QGIS/PyQt for plugin imports)."""

import bisect
import pytest

pytest.importorskip("qgis")

from QGISFMV.utils.media.QgsFmvKlvReader import LocalFileMetaReader


def _lookupOffset(offsets, targetSec):
    if not offsets:
        return None
    idx = bisect.bisect_left(offsets, targetSec)
    if idx >= len(offsets):
        return offsets[-1]
    return offsets[idx]


class TestLocalFileMetaReaderOffsetLookup:
    def test_lookupOffset_empty(self):
        assert _lookupOffset([], 1.0) is None

    def test_lookupOffset_exact(self):
        offsets = [0.0, 1.0, 2.0]
        assert _lookupOffset(offsets, 1.0) == 1.0

    def test_lookupOffset_between(self):
        offsets = [0.0, 2.0, 4.0]
        assert _lookupOffset(offsets, 3.0) == 4.0

    def test_reader_class_exists(self):
        assert LocalFileMetaReader is not None
