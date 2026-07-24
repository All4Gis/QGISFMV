# -*- coding: utf-8 -*-
"""Qt QMediaPlayer adapter used when neither OpenCV nor FFmpeg are available."""

import os

from qgis.PyQt.QtCore import QObject, QUrl, pyqtSignal

from QGISFMV.utils.media.QgsFmvMediaProbe import _url_to_path
from QGISFMV.utils.media.QgsFmvMediaTypes import (
    BufferedMedia,
    EndOfMedia,
    InvalidMedia,
    LoadedMedia,
    LoadingMedia,
    NoMedia,
    PlayingState,
    StalledMedia,
    StoppedState,
    BufferingMedia,
    PausedState,
)

try:
    from qgis.PyQt.QtMultimedia import QMediaPlayer, QAudioOutput

    _HAS_QT_MEDIA = True
except ImportError:
    QMediaPlayer = None
    QAudioOutput = None
    _HAS_QT_MEDIA = False


class QtMediaPlayerAdapter(QObject):
    """Qt QMediaPlayer adapter used when neither OpenCV nor FFmpeg are available."""

    durationChanged = pyqtSignal(int)
    positionChanged = pyqtSignal(int)
    frameDisplayed = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(int)
    playbackRateChanged = pyqtSignal(float)
    playbackLooped = pyqtSignal()

    _QT_STATUS = None
    _QT_STATE = None

    def __init__(self, parent=None):
        super().__init__(parent)
        if not _HAS_QT_MEDIA:
            raise RuntimeError("Qt multimedia is not available")

        if self._QT_STATUS is None:
            self._QT_STATUS = {
                QMediaPlayer.MediaStatus.NoMedia: NoMedia,
                QMediaPlayer.MediaStatus.LoadingMedia: LoadingMedia,
                QMediaPlayer.MediaStatus.LoadedMedia: LoadedMedia,
                QMediaPlayer.MediaStatus.StalledMedia: StalledMedia,
                QMediaPlayer.MediaStatus.BufferingMedia: BufferingMedia,
                QMediaPlayer.MediaStatus.BufferedMedia: BufferedMedia,
                QMediaPlayer.MediaStatus.EndOfMedia: EndOfMedia,
                QMediaPlayer.MediaStatus.InvalidMedia: InvalidMedia,
            }
            self._QT_STATE = {
                QMediaPlayer.PlaybackState.PlayingState: PlayingState,
                QMediaPlayer.PlaybackState.PausedState: PausedState,
                QMediaPlayer.PlaybackState.StoppedState: StoppedState,
            }

        self._player = QMediaPlayer(parent)
        self._audio = QAudioOutput(parent)
        self._player.setAudioOutput(self._audio)
        self._videoWidget = None
        self._error = ""
        self._status = NoMedia
        self._state = StoppedState
        self._hasCapture = False
        self._autoPlayWhenReady = False
        self._loops = 1
        self._muted = False
        self._rate = 1.0
        self._fmvPlaylist = None
        self._lastPositionMs = 0

        self._player.durationChanged.connect(self._emitDurationChanged)
        self._player.positionChanged.connect(self._onPositionChanged)
        self._player.mediaStatusChanged.connect(self._onMediaStatus)
        self._player.playbackStateChanged.connect(self._onPlaybackState)
        self._player.playbackRateChanged.connect(self._emitPlaybackRateChanged)
        if hasattr(self._player, "errorOccurred"):
            self._player.errorOccurred.connect(self._onError)

    def audioOutput(self):
        return self._audio

    def setVideoWidget(self, videoWidget):
        self._videoWidget = videoWidget
        sink = None
        if videoWidget is not None:
            if hasattr(videoWidget, "videoSink"):
                sink = videoWidget.videoSink()
            elif hasattr(videoWidget, "_videoSink"):
                sink = videoWidget._videoSink
        if sink is not None:
            self._player.setVideoSink(sink)

    def setAutoPlayWhenReady(self, enabled=True):
        self._autoPlayWhenReady = bool(enabled)

    def setSource(self, url):
        self._error = ""
        if not isinstance(url, QUrl):
            url = QUrl(url)
        path = _url_to_path(url)
        is_stream = path and "://" in path
        if not path or (not is_stream and not os.path.isfile(path)):
            self._status = InvalidMedia
            self._error = "File not found"
            self._hasCapture = False
            self.mediaStatusChanged.emit(self._status)
            return
        self._hasCapture = False
        self._player.setSource(url)

    def play(self):
        if self._hasCapture:
            self._player.play()
        else:
            self._autoPlayWhenReady = True

    def pause(self):
        self._player.pause()

    def stop(self):
        self._player.stop()

    def setPosition(self, ms):
        self._player.setPosition(int(ms))

    def position(self):
        return int(self._player.position())

    def duration(self):
        return int(self._player.duration())

    def setPlaybackRate(self, rate):
        self._player.setPlaybackRate(float(rate))

    def playbackRate(self):
        return float(self._player.playbackRate())

    def setMuted(self, muted):
        self._muted = bool(muted)
        self._audio.setMuted(self._muted)

    def isMuted(self):
        return self._muted

    def setLoops(self, loops):
        self._loops = int(loops)
        if hasattr(self._player, "setLoops"):
            loops_value = QMediaPlayer.Loops.Infinite if loops == -1 else max(1, loops)
            self._player.setLoops(loops_value)

    def errorString(self):
        return self._error

    def playbackState(self):
        return self._state

    def _emitDurationChanged(self, duration):
        self.durationChanged.emit(int(duration))

    def _emitPlaybackRateChanged(self, rate):
        self.playbackRateChanged.emit(float(rate))

    def _onPositionChanged(self, positionMs):
        positionMs = int(positionMs)
        if (
            self._state == PlayingState
            and self._loops == -1
            and self._lastPositionMs > 1000
            and positionMs + 1000 < self._lastPositionMs
        ):
            self.playbackLooped.emit()
        self._lastPositionMs = positionMs
        self.positionChanged.emit(positionMs)
        if self._state == PlayingState:
            self.frameDisplayed.emit(positionMs)

    def _onMediaStatus(self, status):
        self._status = self._QT_STATUS.get(status, NoMedia)
        self._hasCapture = self._status in (LoadedMedia, BufferedMedia, EndOfMedia)
        self.mediaStatusChanged.emit(self._status)
        if self._status == LoadedMedia and self._autoPlayWhenReady:
            self._autoPlayWhenReady = False
            self.play()

    def _onPlaybackState(self, state):
        self._state = self._QT_STATE.get(state, StoppedState)
        self.playbackStateChanged.emit(self._state)

    def _onError(self, _error, message=""):
        self._error = message or str(_error)
        self._status = InvalidMedia
        self._hasCapture = False
        self.mediaStatusChanged.emit(self._status)


# Private alias matching the former Multimedia module name.
_QtMediaPlayerAdapter = QtMediaPlayerAdapter
