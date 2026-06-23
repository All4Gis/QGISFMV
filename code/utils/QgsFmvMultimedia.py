# -*- coding: utf-8 -*-
"""
Qt5 / Qt6 multimedia compatibility layer for QGIS FMV.

Qt6 (QGIS 4) introduced several breaking changes in QtMultimedia:

* ``QMediaContent`` and ``QMediaPlaylist`` were removed.
* The ``QAbstractVideoSurface`` based pipeline was replaced by ``QVideoSink`` /
  ``QVideoFrame``.
* ``QMediaPlayer`` changed: ``setSource(QUrl)`` instead of
  ``setMedia(QMediaContent)``, audio is routed through a ``QAudioOutput``,
  ``playbackState()`` / ``playbackStateChanged`` instead of ``state()`` /
  ``stateChanged``, and all enums must be fully scoped.

This module hides those differences behind a small, stable API so the rest of
the plugin keeps working unchanged on both QGIS 3 / Qt5 and QGIS 4 / Qt6.
"""
from qgis.PyQt.QtCore import QT_VERSION, QObject, QUrl
from qgis.PyQt.QtMultimedia import QMediaPlayer

IS_QT6 = QT_VERSION >= 0x060000


# ---------------------------------------------------------------------------
# Playback state and media status constants (scoped enums on Qt6)
# ---------------------------------------------------------------------------
if IS_QT6:
    PlayingState = QMediaPlayer.PlaybackState.PlayingState
    PausedState = QMediaPlayer.PlaybackState.PausedState
    StoppedState = QMediaPlayer.PlaybackState.StoppedState

    NoMedia = QMediaPlayer.MediaStatus.NoMedia
    LoadingMedia = QMediaPlayer.MediaStatus.LoadingMedia
    LoadedMedia = QMediaPlayer.MediaStatus.LoadedMedia
    BufferingMedia = QMediaPlayer.MediaStatus.BufferingMedia
    BufferedMedia = QMediaPlayer.MediaStatus.BufferedMedia
    StalledMedia = QMediaPlayer.MediaStatus.StalledMedia
    InvalidMedia = QMediaPlayer.MediaStatus.InvalidMedia
    EndOfMedia = QMediaPlayer.MediaStatus.EndOfMedia
else:
    PlayingState = QMediaPlayer.PlayingState
    PausedState = QMediaPlayer.PausedState
    StoppedState = QMediaPlayer.StoppedState

    NoMedia = QMediaPlayer.NoMedia
    LoadingMedia = QMediaPlayer.LoadingMedia
    LoadedMedia = QMediaPlayer.LoadedMedia
    BufferingMedia = QMediaPlayer.BufferingMedia
    BufferedMedia = QMediaPlayer.BufferedMedia
    StalledMedia = QMediaPlayer.StalledMedia
    InvalidMedia = QMediaPlayer.InvalidMedia
    EndOfMedia = QMediaPlayer.EndOfMedia


# ---------------------------------------------------------------------------
# Player construction / wiring
# ---------------------------------------------------------------------------
def create_media_player(parent=None):
    """Create a QMediaPlayer. Returns ``(player, audio_output)``.

    ``audio_output`` is ``None`` on Qt5 (audio is handled by the player itself).
    """
    if IS_QT6:
        from qgis.PyQt.QtMultimedia import QAudioOutput
        player = QMediaPlayer(parent)
        audio = QAudioOutput(parent)
        player.setAudioOutput(audio)
        return player, audio
    player = QMediaPlayer(parent, QMediaPlayer.VideoSurface)
    return player, None


def set_video_output(player, video_widget):
    """Connect the player to the plugin video widget."""
    if IS_QT6:
        player.setVideoOutput(video_widget.videoSink())
    else:
        player.setVideoOutput(video_widget.videoSurface())


def connect_state_changed(player, slot):
    """Connect the playback-state-changed signal (renamed in Qt6)."""
    if IS_QT6:
        player.playbackStateChanged.connect(slot)
    else:
        player.stateChanged.connect(slot)


def set_notify_interval(player, interval):
    """Qt6 removed setNotifyInterval (position updates emit automatically)."""
    if hasattr(player, "setNotifyInterval"):
        player.setNotifyInterval(interval)


def has_video(player):
    if hasattr(player, "isVideoAvailable"):
        return player.isVideoAvailable()
    if hasattr(player, "hasVideo"):
        return player.hasVideo()
    return True


def set_volume(player, audio, value):
    """``value`` is an int in the 0..100 slider range."""
    if IS_QT6:
        if audio is not None:
            audio.setVolume(max(0.0, min(1.0, value / 100.0)))
    else:
        player.setVolume(int(value))


def get_volume(player, audio):
    if IS_QT6:
        return int(round(audio.volume() * 100)) if audio is not None else 0
    return player.volume()


# ---------------------------------------------------------------------------
# Playlist (QMediaPlaylist was removed in Qt6)
# ---------------------------------------------------------------------------
if IS_QT6:
    PlaylistSequential = 0
    PlaylistLoop = 1

    class _MediaShim(object):
        """Mimics the small QMediaContent surface used by the plugin."""

        def __init__(self, url):
            self._url = url

        def canonicalUrl(self):
            return self._url

    class FmvPlaylist(QObject):
        """Minimal QMediaPlaylist replacement driving a Qt6 QMediaPlayer."""

        Sequential = PlaylistSequential
        Loop = PlaylistLoop

        def __init__(self, parent=None):
            super().__init__(parent)
            self._items = []
            self._current = -1
            self._mode = PlaylistSequential
            self._player = None

        def setPlayer(self, player):
            self._player = player
            self._applyMode()

        def addMedia(self, content):
            # content is a QUrl (see media_url_to_content)
            self._items.append(content)
            return True

        def removeMedia(self, idx):
            if 0 <= idx < len(self._items):
                del self._items[idx]
                if self._current >= len(self._items):
                    self._current = len(self._items) - 1
                return True
            return False

        def mediaCount(self):
            return len(self._items)

        def media(self, x):
            if 0 <= x < len(self._items):
                return _MediaShim(self._items[x])
            return _MediaShim(QUrl())

        def currentIndex(self):
            return self._current

        def nextIndex(self):
            if not self._items:
                return -1
            if self._mode == PlaylistLoop:
                return self._current
            nxt = self._current + 1
            return nxt if nxt < len(self._items) else -1

        def setCurrentIndex(self, row):
            if 0 <= row < len(self._items):
                self._current = row
                if self._player is not None:
                    self._player.setSource(self._items[row])

        def setPlaybackMode(self, mode):
            self._mode = mode
            self._applyMode()

        def _applyMode(self):
            if self._player is None or not hasattr(self._player, "setLoops"):
                return
            try:
                if self._mode == PlaylistLoop:
                    loops = getattr(
                        getattr(QMediaPlayer, "Loops", None), "Infinite", -1)
                    self._player.setLoops(loops)
                else:
                    self._player.setLoops(1)
            except Exception:
                pass

    def create_playlist(parent=None):
        return FmvPlaylist(parent)

    def attach_playlist(player, playlist):
        playlist.setPlayer(player)
        player._fmv_playlist = playlist

    def get_playlist(player):
        return getattr(player, "_fmv_playlist", None)

    def media_url_to_content(url):
        return url

else:
    from qgis.PyQt.QtMultimedia import QMediaPlaylist, QMediaContent

    PlaylistSequential = QMediaPlaylist.Sequential
    PlaylistLoop = QMediaPlaylist.Loop

    def create_playlist(parent=None):
        return QMediaPlaylist(parent) if parent is not None else QMediaPlaylist()

    def attach_playlist(player, playlist):
        player.setPlaylist(playlist)

    def get_playlist(player):
        return player.playlist()

    def media_url_to_content(url):
        return QMediaContent(url)
