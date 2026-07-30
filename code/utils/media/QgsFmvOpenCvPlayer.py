# -*- coding: utf-8 -*-
"""QMediaPlayer-compatible player driven by OpenCV or FFmpeg decode workers."""

import os
import time

try:
    import cv2
except ImportError:
    cv2 = None

from qgis.PyQt.QtCore import QObject, QThread, QTimer, pyqtSignal

from QGISFMV.utils.media.QgsFmvDecodeWorkers import (
    FfmpegDecodeWorker,
    FrameDecodeWorker,
)
from QGISFMV.utils.media.QgsFmvMediaProbe import _ffmpeg_available, _url_to_path
from QGISFMV.utils.media.QgsFmvMediaTypes import (
    EndOfMedia,
    InvalidMedia,
    LoadedMedia,
    LoadingMedia,
    NoMedia,
    PausedState,
    PlayingState,
    StoppedState,
)


class OpenCvMediaPlayer(QObject):
    """QMediaPlayer-compatible player using OpenCV VideoCapture or FFmpeg pipe."""

    durationChanged = pyqtSignal(int)
    positionChanged = pyqtSignal(int)
    frameDisplayed = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(int)
    playbackRateChanged = pyqtSignal(float)
    playbackLooped = pyqtSignal()

    def __init__(self, parent=None, decode_worker_factory=None):
        super().__init__(parent)
        self._path = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._onTick)
        self._positionMs = 0
        self._durationMs = 0
        self._fps = 25.0
        self._rate = 1.0
        self._state = StoppedState
        self._status = NoMedia
        self._videoWidget = None
        self._muted = False
        self._loops = 1
        self._error = ""
        self._lastNotifyMs = 0
        self._openGeneration = 0
        self._hasCapture = False
        self._forceNotifyNext = False
        self._autoPlayWhenReady = False
        self._decodeBusy = False
        self._pendingSeekMs = None
        self._isStream = False
        self._playStartMono = None
        self._streamFrameCount = 0
        self._ffmpegBackend = decode_worker_factory is FfmpegDecodeWorker

        self._openTimeout = QTimer(self)
        self._openTimeout.setSingleShot(True)
        self._openTimeout.timeout.connect(self._onOpenTimeout)

        # Unparented: parented QThreads abort Qt if still running when destroyed.
        self._decodeThread = QThread()
        worker_factory = decode_worker_factory or FrameDecodeWorker
        self._decodeWorker = worker_factory()
        self._decodeWorker.moveToThread(self._decodeThread)
        self._decodeWorker.frameReady.connect(self._onFrameReady)
        self._decodeWorker.openFinished.connect(self._onOpenFinished)
        self._decodeThread.start()

    def setVideoWidget(self, videoWidget):
        """Set the video output widget for frame rendering."""
        self._videoWidget = videoWidget

    def setAutoPlayWhenReady(self, enabled=True):
        """Enable auto-play once the media source is ready."""
        self._autoPlayWhenReady = bool(enabled)

    def _closeCapture(self):
        self._timer.stop()
        self._openTimeout.stop()
        self._decodeWorker.releaseRequested.emit()
        self._hasCapture = False
        self._decodeBusy = False
        self._pendingSeekMs = None
        self._openGeneration += 1

    def shutdown(self):
        """Stop the decode thread cleanly before the player is destroyed."""
        from QGISFMV.utils.core.QgsFmvThreads import stop_qthread

        self._timer.stop()
        self._openTimeout.stop()
        # Ask the worker to drop capture/ffmpeg, then stop its event loop.
        try:
            self._decodeWorker.releaseRequested.emit()
        except Exception as exc:
            from QGISFMV.utils.logging import log

            log.debug("decodeWorker releaseRequested emit failed: %s", exc)
        thread = self._decodeThread
        self._decodeThread = None
        self._hasCapture = False
        self._decodeBusy = False
        stop_qthread(thread)

    def setSource(self, url):
        """Set the media source URL and prepare for playback."""
        self._closeCapture()
        self._error = ""
        path = _url_to_path(url)
        is_stream = path and "://" in path
        if not path or (not is_stream and not os.path.isfile(path)):
            self._status = InvalidMedia
            self._error = "File not found"
            self.mediaStatusChanged.emit(self._status)
            return

        if cv2 is None and not self._ffmpegBackend:
            self._status = InvalidMedia
            self._error = "Native video decoder is not installed"
            self.mediaStatusChanged.emit(self._status)
            return

        if cv2 is None and not _ffmpeg_available():
            self._status = InvalidMedia
            self._error = "FFmpeg is not configured"
            self.mediaStatusChanged.emit(self._status)
            return

        self._status = LoadingMedia
        self.mediaStatusChanged.emit(self._status)
        self._path = path
        self._isStream = bool(is_stream)
        self._openGeneration += 1
        generation = self._openGeneration
        if self._ffmpegBackend:
            self._openTimeout.start(90000)
        self._decodeWorker.openPathRequested.emit(path, generation)

    def _onOpenTimeout(self):
        if self._status != LoadingMedia:
            return
        self._status = InvalidMedia
        self._error = "Video open timed out (FFmpeg)"
        self._autoPlayWhenReady = False
        self._hasCapture = False
        self._openTimeout.stop()
        self.mediaStatusChanged.emit(self._status)

    def _onOpenFinished(self, result):
        self._openTimeout.stop()
        if result.get("generation") != self._openGeneration:
            return

        if not result.get("ok"):
            self._status = InvalidMedia
            self._error = result.get("error") or "Cannot open video"
            self._autoPlayWhenReady = False
            self.mediaStatusChanged.emit(self._status)
            return

        self._fps = result["fps"]
        self._durationMs = result["durationMs"]
        self._isStream = bool(result.get("isStream"))
        self._positionMs = 0
        self._lastNotifyMs = 0
        self._state = StoppedState
        self._status = LoadedMedia
        self._hasCapture = True
        self.mediaStatusChanged.emit(self._status)
        self.durationChanged.emit(self._durationMs)
        self._showFrameAt(0, forceNotify=True)
        if self._autoPlayWhenReady:
            self._autoPlayWhenReady = False
            self.play()

    def _showFrameAt(self, ms, forceNotify=False):
        if self._decodeBusy:
            self._pendingSeekMs = int(ms)
            if forceNotify:
                self._forceNotifyNext = True
            return
        self._decodeBusy = True
        self._forceNotifyNext = forceNotify or self._forceNotifyNext
        self._decodeWorker.decodeRequested.emit(int(ms))

    def _requestNextFrame(self):
        if self._decodeBusy:
            return
        self._decodeBusy = True
        self._decodeWorker.decodeNextRequested.emit()

    def _onFrameReady(self, positionMs, qimg):
        self._decodeBusy = False

        if qimg is None:
            if positionMs < 0 and self._state == PlayingState:
                self._timer.stop()
                self._state = PausedState
                self._status = EndOfMedia
                self.playbackStateChanged.emit(self._state)
                self.mediaStatusChanged.emit(self._status)
            pending = self._pendingSeekMs
            self._pendingSeekMs = None
            if pending is not None:
                self._showFrameAt(pending)
            return

        if (
            qimg is not None
            and self._videoWidget is not None
            and hasattr(self._videoWidget, "surface")
        ):
            self._videoWidget.surface.pushFrame(qimg)

        if self._isStream:
            if self._state == PlayingState:
                if self._playStartMono is None:
                    self._playStartMono = time.monotonic()
                self._streamFrameCount += 1
                self._positionMs = int((time.monotonic() - self._playStartMono) * 1000)
            elif positionMs >= 0:
                self._positionMs = max(0, int(positionMs))
            else:
                self._positionMs = 0
            self._lastNotifyMs = self._positionMs
            self.positionChanged.emit(self._positionMs)
            self.frameDisplayed.emit(self._positionMs)
        elif positionMs >= 0:
            self._positionMs = positionMs
            self._lastNotifyMs = self._positionMs
            self.positionChanged.emit(self._positionMs)
            self.frameDisplayed.emit(self._positionMs)
        self._forceNotifyNext = False

        pending = self._pendingSeekMs
        self._pendingSeekMs = None
        if pending is not None:
            self._showFrameAt(pending)
        elif self._state == PlayingState and self._isStream:
            self._requestNextFrame()

    def _scheduleStreamDecode(self):
        if self._state == PlayingState and self._isStream and not self._decodeBusy:
            self._requestNextFrame()

    def play(self):
        """Start or resume media playback."""
        if not self._hasCapture:
            self._autoPlayWhenReady = True
            return
        if self._positionMs >= self._durationMs and self._durationMs > 0:
            self._showFrameAt(0, forceNotify=True)
        if self._isStream:
            self._playStartMono = time.monotonic()
            self._streamFrameCount = 0
            self._positionMs = 0
            self._lastNotifyMs = -1
        self._state = PlayingState
        self.playbackStateChanged.emit(self._state)
        interval = max(1, int(1000.0 / (self._fps * max(0.1, self._rate))))
        if self._isStream:
            interval = max(interval, 33)
            self._scheduleStreamDecode()
        self._timer.start(interval)

    def pause(self):
        """Pause media playback."""
        self._timer.stop()
        if self._state != StoppedState:
            self._state = PausedState
            self.playbackStateChanged.emit(self._state)

    def stop(self):
        """Stop playback and reset to the beginning."""
        self._timer.stop()
        self._state = StoppedState
        self._playStartMono = None
        self._streamFrameCount = 0
        self.playbackStateChanged.emit(self._state)
        self._showFrameAt(0, forceNotify=True)

    def _onTick(self):
        if not self._hasCapture or self._decodeBusy:
            return
        if self._isStream:
            self._scheduleStreamDecode()
            return
        if (
            not self._isStream
            and self._durationMs
            and self._positionMs >= self._durationMs
        ):
            if self._loops == -1:
                self.playbackLooped.emit()
                self._showFrameAt(0, forceNotify=True)
                return
            self._positionMs = self._durationMs
            self._showFrameAt(self._positionMs, forceNotify=True)
            self._timer.stop()
            self._state = PausedState
            self._status = EndOfMedia
            self.playbackStateChanged.emit(self._state)
            self.mediaStatusChanged.emit(self._status)
            return
        self._requestNextFrame()

    def setPosition(self, ms):
        """Seek to position *ms* in milliseconds."""
        self._showFrameAt(ms, forceNotify=True)

    def position(self):
        """Return the current playback position in milliseconds."""
        return self._positionMs

    def duration(self):
        """Return the total media duration in milliseconds."""
        return self._durationMs

    def setPlaybackRate(self, rate):
        """Set the playback speed multiplier."""
        rate = float(rate)
        if rate == self._rate:
            return
        self._rate = max(0.1, rate)
        self.playbackRateChanged.emit(self._rate)
        if self._state == PlayingState:
            interval = max(1, int(1000.0 / (self._fps * self._rate)))
            self._timer.start(interval)

    def playbackRate(self):
        """Return the current playback speed multiplier."""
        return self._rate

    def setMuted(self, muted):
        """Enable or disable audio muting."""
        self._muted = bool(muted)

    def isMuted(self):
        """Return True when audio is muted."""
        return self._muted

    def setLoops(self, loops):
        """Set loop count (-1 for infinite, 1 for no loop)."""
        self._loops = int(loops)

    def errorString(self):
        """Return the last error message, or empty string."""
        return self._error

    def playbackState(self):
        """Return the current playback state constant."""
        return self._state
