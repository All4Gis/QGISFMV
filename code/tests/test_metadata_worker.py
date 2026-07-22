# -*- coding: utf-8 -*-
"""Metadata worker coalescing (no QGIS runtime)."""


class _PendingCoalescer:
    def __init__(self):
        self._pending = None

    def offer(self, raw, seq):
        pendingRaw, pendingSeq = self._pending or (None, -1)
        if pendingRaw is None or seq >= pendingSeq:
            self._pending = (raw, seq)

    def take(self):
        pending = self._pending
        self._pending = None
        return pending


class TestMetadataPendingCoalescer:
    def test_keeps_latest_seq_when_busy(self):
        coalescer = _PendingCoalescer()
        coalescer.offer(b"a", 1)
        coalescer.offer(b"b", 5)
        coalescer.offer(b"c", 3)
        assert coalescer.take() == (b"b", 5)
