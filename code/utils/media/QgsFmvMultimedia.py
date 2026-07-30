# -*- coding: utf-8 -*-
"""
Video playback for QGIS FMV.

Uses OpenCV when available, otherwise FFmpeg (same codecs as Windows, no LAV
Filters on macOS). Qt ``QMediaPlayer`` is only a last resort for simple formats.

Implementation is split across:
- ``QgsFmvMediaTypes`` — enums / public state aliases
- ``QgsFmvMediaProbe`` — path / duration / stream-info helpers
- ``QgsFmvDecodeWorkers`` — OpenCV + FFmpeg background workers
- ``QgsFmvOpenCvPlayer`` — QMediaPlayer-compatible OpenCV/FFmpeg player
- ``QgsFmvQtMediaAdapter`` — Qt multimedia fallback
- ``QgsFmvPlaylist`` — playlist helpers

This module remains the public façade (factories + re-exports).
"""

import platform

try:
    import cv2
except ImportError:
    cv2 = None

from QGISFMV.utils.logging import log
from QGISFMV.utils.media.QgsFmvDecodeWorkers import (  # noqa: F401
    FfmpegDecodeWorker,
    FrameDecodeWorker,
    _FfmpegDecodeWorker,
    _FrameDecodeWorker,
)
from QGISFMV.utils.media.QgsFmvMediaProbe import (  # noqa: F401
    _durationMsFromText,
    _ffmpeg_available,
    _ffmpeg_popen,
    _parse_fps,
    _probe_video_info,
    _probe_video_info_from_stderr,
    _probeDurationMs,
    _read_bytes,
    _url_to_path,
    _validateMediaPath,
    durationMsFromText,
    ffmpeg_available,
    ffmpeg_popen,
    parse_fps,
    probe_video_info,
    probe_video_info_from_stderr,
    probeDurationMs,
    read_bytes,
    url_to_path,
    validateMediaPath,
)
from QGISFMV.utils.media.QgsFmvMediaTypes import BufferedMedia  # noqa: F401
from QGISFMV.utils.media.QgsFmvMediaTypes import (
    BufferingMedia,
    EndOfMedia,
    InvalidMedia,
    LoadedMedia,
    LoadingMedia,
    MediaStatus,
    NoMedia,
    PausedState,
    PlaybackState,
    PlayingState,
    PlaylistLoop,
    PlaylistMode,
    PlaylistSequential,
    StalledMedia,
    StoppedState,
)
from QGISFMV.utils.media.QgsFmvOpenCvPlayer import OpenCvMediaPlayer
from QGISFMV.utils.media.QgsFmvPlaylist import FmvPlaylist  # noqa: F401
from QGISFMV.utils.media.QgsFmvPlaylist import (
    _MediaShim,
    attachPlaylist,
    createPlaylist,
    getPlaylist,
    mediaUrlToContent,
)
from QGISFMV.utils.media.QgsFmvQtMediaAdapter import (  # noqa: F401
    _HAS_QT_MEDIA,
    QtMediaPlayerAdapter,
    _QtMediaPlayerAdapter,
)


def createMediaPlayer(parent=None):
    """Create a media player. FFmpeg on macOS, else OpenCV, else Qt."""
    if platform.system() == "Darwin" and _ffmpeg_available():
        log.info("Media player backend: FFmpeg (macOS)")
        return (
            OpenCvMediaPlayer(parent, decode_worker_factory=FfmpegDecodeWorker),
            None,
        )
    if cv2 is not None:
        return OpenCvMediaPlayer(parent), None
    if _ffmpeg_available():
        return (
            OpenCvMediaPlayer(parent, decode_worker_factory=FfmpegDecodeWorker),
            None,
        )
    if _HAS_QT_MEDIA:
        player = QtMediaPlayerAdapter(parent)
        return player, player.audioOutput()
    player = OpenCvMediaPlayer(parent)
    return player, None


def setVideoOutput(player, videoWidget):
    """Connect the video output widget to the player."""
    player.setVideoWidget(videoWidget)


def connectStateChanged(player, slot):
    """Connect the playback-state-changed signal to *slot*."""
    player.playbackStateChanged.connect(slot)


def hasVideo(player):
    """Return True when the player has a loaded video with frames."""
    if isinstance(player, QtMediaPlayerAdapter):
        return player._hasCapture
    return (
        player._status in (LoadedMedia, BufferedMedia, EndOfMedia)
        and player._hasCapture
    )


def setVolume(_player, _audio, value):
    """Set the audio volume (0-100 scale)."""
    if _audio is not None:
        _audio.setVolume(max(0.0, min(1.0, float(value) / 100.0)))


def getVolume(_player, _audio):
    """Return the current audio volume (0-100 scale)."""
    if _audio is not None:
        return int(round(_audio.volume() * 100))
    return 0
