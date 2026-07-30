# -*- coding: utf-8 -*-
"""Minimal playlist driving OpenCvMediaPlayer / Qt adapters."""

from qgis.PyQt.QtCore import QObject, QUrl

from QGISFMV.utils.media.QgsFmvMediaTypes import PlaylistLoop, PlaylistSequential


class _MediaShim(object):
    """Thin wrapper providing a ``canonicalUrl()`` for playlist compatibility."""

    def __init__(self, url):
        self._url = url

    def canonicalUrl(self):
        return self._url


class FmvPlaylist(QObject):
    """Minimal playlist driving OpenCvMediaPlayer."""

    Sequential = PlaylistSequential
    Loop = PlaylistLoop

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._current = -1
        self._mode = PlaylistSequential
        self._player = None

    def setPlayer(self, player):
        """Bind the playlist to a media player instance."""
        self._player = player
        self._applyMode()

    def addMedia(self, content):
        """Append a media URL/path to the playlist."""
        self._items.append(content)
        return True

    def removeMedia(self, idx):
        """Remove the item at index *idx* from the playlist."""
        if 0 <= idx < len(self._items):
            del self._items[idx]
            if self._current >= len(self._items):
                self._current = len(self._items) - 1
            return True
        return False

    def mediaCount(self):
        """Return the number of items in the playlist."""
        return len(self._items)

    def media(self, x):
        """Return a shim wrapping the URL at index *x*."""
        if 0 <= x < len(self._items):
            return _MediaShim(self._items[x])
        return _MediaShim(QUrl())

    def currentIndex(self):
        """Return the index of the currently playing item."""
        return self._current

    def nextIndex(self):
        """Return the index of the next item, or -1 if at end."""
        if not self._items:
            return -1
        if self._mode == PlaylistLoop:
            return self._current
        nxt = self._current + 1
        return nxt if nxt < len(self._items) else -1

    def setCurrentIndex(self, row):
        """Set the current playlist index and load the media."""
        if 0 <= row < len(self._items):
            self._current = row
            if self._player is not None:
                self._player.setSource(self._items[row])

    def setPlaybackMode(self, mode):
        """Set the playback mode (Sequential or Loop)."""
        self._mode = mode
        self._applyMode()

    def _applyMode(self):
        if self._player is None:
            return
        self._player.setLoops(-1 if self._mode == PlaylistLoop else 1)


def createPlaylist(parent=None):
    """Create and return a new FmvPlaylist instance."""
    return FmvPlaylist(parent)


def attachPlaylist(player, playlist):
    """Bind *playlist* to *player* so track changes drive playback."""
    playlist.setPlayer(player)
    player._fmvPlaylist = playlist


def getPlaylist(player):
    """Return the playlist attached to *player*, or None."""
    return getattr(player, "_fmvPlaylist", None)


def mediaUrlToContent(url):
    """Return *url* as-is (compatibility shim for QMediaContent)."""
    return url
