# -*- coding: utf-8 -*-
"""Background OpenCV filter processing to keep the video UI responsive."""

from qgis.PyQt.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from QGISFMV.video.filters import VideoFilters
from QGISFMV.video.playback.QgsVideoState import FilterState


def snapshot_filter_state(state):
    """Copy active filter flags for thread-safe processing."""
    snap = FilterState()
    if isinstance(state, FilterState):
        src = state
    elif isinstance(state, dict):
        for name in vars(FilterState()).keys():
            if name.startswith("_"):
                continue
            if name in state:
                setattr(snap, name, state[name])
        return snap
    else:
        src = state
    # Fast / legacy filters
    snap.contrastFilter = src.contrastFilter
    snap.monoFilter = src.monoFilter
    snap.MirroredHFilter = src.MirroredHFilter
    snap.edgeDetectionFilter = src.edgeDetectionFilter
    snap.grayColorFilter = src.grayColorFilter
    snap.invertColorFilter = src.invertColorFilter
    snap.brightnessContrastFilter = src.brightnessContrastFilter
    snap.brightness = src.brightness
    snap.contrastLevel = src.contrastLevel
    # OpenCV / analysis filters (must be copied — async path uses this snapshot)
    snap.claheFilter = src.claheFilter
    snap.sharpenFilter = src.sharpenFilter
    snap.motionDetectionFilter = src.motionDetectionFilter
    snap.sobelFilter = src.sobelFilter
    snap.falseColorFilter = src.falseColorFilter
    snap.exgFilter = src.exgFilter
    snap.exrFilter = src.exrFilter
    snap.variFilter = src.variFilter
    snap.nrviFilter = src.nrviFilter
    snap.backgroundSubtractionFilter = src.backgroundSubtractionFilter
    snap.dehazeFilter = src.dehazeFilter
    snap.roadEnhanceFilter = src.roadEnhanceFilter
    snap.hotspotFilter = src.hotspotFilter
    snap.buildingDetectionFilter = src.buildingDetectionFilter
    snap.roadSegmentationFilter = src.roadSegmentationFilter
    snap.vehicleSegmentationFilter = src.vehicleSegmentationFilter
    snap.personSegmentationFilter = src.personSegmentationFilter
    snap.fireDetectionFilter = src.fireDetectionFilter
    snap.smokeDetectionFilter = src.smokeDetectionFilter
    snap.floodDetectionFilter = src.floodDetectionFilter
    return snap


class FilterWorker(QObject):
    """Runs ``VideoFilters.apply`` off the GUI thread."""

    request = pyqtSignal(int, object, object)
    finished = pyqtSignal(int, object)

    def __init__(self):
        super().__init__()
        self.request.connect(self.process)

    @pyqtSlot(int, object, object)
    def process(self, seq, image, state):
        """Apply video filters to *image* on a background thread."""
        if image is None or image.isNull():
            self.finished.emit(seq, None)
            return
        try:
            # ``state`` is already a snapshot when submitted from FilterThreadPool.
            snap = state if isinstance(state, FilterState) else snapshot_filter_state(state)
            result = VideoFilters.apply(image, snap, downscale_slow=True)
            if result is None or result.isNull():
                result = VideoFilters._failure_overlay(image, "empty filter result")
            self.finished.emit(seq, result)
        except Exception as exc:
            from QGISFMV.utils.logging import log

            log.warning("Video filter failed: %s", exc, exc_info=True)
            try:
                result = VideoFilters._failure_overlay(image, str(exc))
            except Exception as exc:
                log.debug("filter overlay fallback failed: %s", exc)
                result = image
            self.finished.emit(seq, result)


class FilterThreadPool(QObject):
    """Single-slot async filter queue: drops frames while a filter job is running."""

    filtered = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self._thread = QThread()
        self._worker = FilterWorker()
        self._worker.moveToThread(self._thread)
        self._worker.finished.connect(self._handle_finished)
        self._thread.start()
        self._seq = 0
        self._busy = False
        self._pending = None

    def submit(self, image, state):
        """Queue a frame for filtering; returns False if busy (frame dropped)."""
        if image is None or image.isNull():
            return False
        # Snapshot immediately — FilterState is mutated on the UI thread.
        snap = state if isinstance(state, FilterState) else snapshot_filter_state(state)
        job = (image.copy(), snap)
        if self._busy:
            self._pending = job
            return False
        self._busy = True
        self._seq += 1
        seq = self._seq
        self._worker.request.emit(seq, job[0], job[1])
        return True

    def _handle_finished(self, seq, result):
        if seq != self._seq:
            return
        self._busy = False
        if result is not None:
            self.filtered.emit(result)
        if self._pending is not None:
            pending = self._pending
            self._pending = None
            self.submit(pending[0], pending[1])

    def shutdown(self):
        """Stop the background thread and wait for it to finish."""
        from QGISFMV.utils.core.QgsFmvThreads import stop_qthread

        self._pending = None
        self._busy = False
        try:
            self._worker.finished.disconnect(self._handle_finished)
        except Exception as exc:
            from QGISFMV.utils.logging import log
            log.debug("filter worker disconnect failed: %s", exc)
        thread = getattr(self, "_thread", None)
        self._thread = None
        stop_qthread(thread)
