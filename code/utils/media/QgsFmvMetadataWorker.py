# -*- coding: utf-8 -*-
"""Background KLV parsing (keeps QGIS main thread responsive during live streams)."""

from pymisb.klvdata.element import UnknownElement
from pymisb.klvdata.streamparser import StreamParser
from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot


class MetadataParseWorker(QObject):
    """Parse raw KLV bytes on a worker thread; layer updates stay on the main thread."""

    packetReady = pyqtSignal(object)
    parseFailed = pyqtSignal(str)
    parseRequested = pyqtSignal(bytes, int, int)

    def __init__(self):
        super().__init__()
        self._busy = False
        self._pending = None
        self.parseRequested.connect(self._parsePacket)

    def clearPending(self):
        """Drop queued parses from a previous playback cycle."""
        self._pending = None

    @pyqtSlot(bytes, int, int)
    def _parsePacket(self, raw, seq, cycle):
        """Parse a raw KLV packet, queuing if busy."""
        if self._busy:
            pendingRaw, pendingSeq, pendingCycle = self._pending or (None, -1, -1)
            if pendingRaw is None or seq >= pendingSeq:
                self._pending = (raw, seq, cycle)
            return

        self._busy = True
        try:
            self._runParse(raw, seq, cycle)
        finally:
            self._busy = False
            pending = self._pending
            self._pending = None
            if pending is not None:
                self._parsePacket(*pending)

    def _runParse(self, raw, seq, cycle):
        """Run the actual KLV stream parsing."""
        if not raw:
            return

        try:
            for packet in StreamParser(raw):
                if isinstance(packet, UnknownElement):
                    continue
                packet._fmvSeq = seq
                packet._fmvCycle = cycle
                self.packetReady.emit(packet)
                return
        except Exception as exc:
            self.parseFailed.emit(str(exc))
