# -*- coding: utf-8 -*-
"""Multimedia helpers: frame index, media types, probe, playlist (no QGIS GUI)."""

import sys
import types

import pytest

from code.tests.support import load_plugin_module


def _legacyFrameIndex(ms, fps):
    return max(0, int((ms / 1000.0) * fps))


def _roundedFrameIndex(ms, fps):
    return max(0, int(round((ms / 1000.0) * fps)))


class TestPlaybackFrameIndex:
    def test_thirty_fps_tick_no_longer_sticks_on_frame_zero(self):
        fps = 29.97002997002997
        step_ms = int(1000.0 / fps)
        next_ms = 0 + step_ms
        assert _legacyFrameIndex(next_ms, fps) == 0
        assert _roundedFrameIndex(next_ms, fps) == 1


class TestMediaTypes:
    @classmethod
    def setup_class(cls):
        cls.types_mod = load_plugin_module(
            "utils/media/QgsFmvMediaTypes.py",
            "QGISFMV.utils.media.QgsFmvMediaTypes",
        )

    def test_playback_state_aliases(self):
        m = self.types_mod
        assert m.PlayingState == m.PlaybackState.Playing
        assert m.PausedState == m.PlaybackState.Paused
        assert m.StoppedState == m.PlaybackState.Stopped

    def test_media_status_aliases(self):
        m = self.types_mod
        assert m.LoadedMedia == m.MediaStatus.Loaded
        assert m.EndOfMedia == m.MediaStatus.EndOfMedia
        assert m.InvalidMedia == m.MediaStatus.Invalid

    def test_playlist_mode_aliases(self):
        m = self.types_mod
        assert m.PlaylistSequential == m.PlaylistMode.Sequential
        assert m.PlaylistLoop == m.PlaylistMode.Loop


_QT_STUB_KEYS = ("qgis", "qgis.PyQt", "qgis.PyQt.QtCore")


def _snapshot_modules(keys):
    return {k: sys.modules.get(k) for k in keys}


def _restore_modules(saved):
    for key, previous in saved.items():
        if previous is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = previous


def _install_qtcore_stub(with_qobject=False):
    """Minimal qgis.PyQt.QtCore stub so media modules load without QGIS."""
    qgis = sys.modules.setdefault("qgis", types.ModuleType("qgis"))
    pyqt = sys.modules.setdefault("qgis.PyQt", types.ModuleType("qgis.PyQt"))
    qgis.PyQt = pyqt
    qtcore = types.ModuleType("qgis.PyQt.QtCore")

    class QUrl:
        def __init__(self, value=""):
            self._value = str(value)

        def toLocalFile(self):
            if "://" in self._value and not self._value.startswith("file:"):
                return ""
            if self._value.startswith("file:"):
                return self._value[len("file:") :]
            return self._value

        def toString(self):
            return self._value

    qtcore.QUrl = QUrl
    if with_qobject:

        class QObject:
            def __init__(self, parent=None):
                self._parent = parent

        qtcore.QObject = QObject
    sys.modules["qgis.PyQt.QtCore"] = qtcore
    pyqt.QtCore = qtcore


class TestMediaProbe:
    @classmethod
    def setup_class(cls):
        cls._saved = _snapshot_modules(_QT_STUB_KEYS)
        _install_qtcore_stub(with_qobject=False)
        cls.probe = load_plugin_module(
            "utils/media/QgsFmvMediaProbe.py",
            "QGISFMV.utils.media.QgsFmvMediaProbe",
        )

    @classmethod
    def teardown_class(cls):
        _restore_modules(cls._saved)
        sys.modules.pop("QGISFMV.utils.media.QgsFmvMediaProbe", None)

    def test_parse_fps_fraction(self):
        assert self.probe.parse_fps("30000/1001") == pytest.approx(29.97002997, rel=1e-6)

    def test_parse_fps_float_string(self):
        assert self.probe.parse_fps("25") == 25.0

    def test_parse_fps_defaults(self):
        assert self.probe.parse_fps(None) == 25.0
        assert self.probe.parse_fps("") == 25.0
        assert self.probe.parse_fps("bad") == 25.0
        # 0 is falsy → same default as None/""
        assert self.probe.parse_fps(0) == 25.0

    def test_parse_fps_numeric(self):
        assert self.probe.parse_fps(30) == 30.0
        assert self.probe.parse_fps(0.5) == 0.5

    def test_duration_from_ffmpeg_text(self):
        text = "Duration: 01:02:03.50, start: 0.000000"
        assert self.probe.durationMsFromText(text) == 3723500

    def test_duration_from_text_missing(self):
        assert self.probe.durationMsFromText("no duration here") == 0

    def test_validate_media_path(self):
        assert self.probe.validateMediaPath("") == "File not found"
        assert self.probe.validateMediaPath("/no/such/file.mp4") == "File not found"
        assert self.probe.validateMediaPath("udp://127.0.0.1:5000") is None

    def test_url_to_path_string(self):
        assert self.probe.url_to_path("/tmp/a.mp4") == "/tmp/a.mp4"

    def test_url_to_path_qurl_local(self):
        from qgis.PyQt.QtCore import QUrl

        assert self.probe.url_to_path(QUrl("/tmp/b.mp4")) == "/tmp/b.mp4"

    def test_url_to_path_qurl_stream(self):
        from qgis.PyQt.QtCore import QUrl

        assert self.probe.url_to_path(QUrl("udp://127.0.0.1:5000")) == "udp://127.0.0.1:5000"


class TestFmvPlaylist:
    @classmethod
    def setup_class(cls):
        cls._saved = _snapshot_modules(_QT_STUB_KEYS)
        _install_qtcore_stub(with_qobject=True)
        types_mod = load_plugin_module(
            "utils/media/QgsFmvMediaTypes.py",
            "QGISFMV.utils.media.QgsFmvMediaTypes",
        )
        sys.modules["QGISFMV.utils.media.QgsFmvMediaTypes"] = types_mod
        cls.playlist_mod = load_plugin_module(
            "utils/media/QgsFmvPlaylist.py",
            "QGISFMV.utils.media.QgsFmvPlaylist",
        )

    @classmethod
    def teardown_class(cls):
        _restore_modules(cls._saved)
        sys.modules.pop("QGISFMV.utils.media.QgsFmvPlaylist", None)

    def test_add_and_count(self):
        pl = self.playlist_mod.FmvPlaylist()
        assert pl.mediaCount() == 0
        assert pl.addMedia("/a.mp4") is True
        assert pl.addMedia("/b.mp4") is True
        assert pl.mediaCount() == 2

    def test_remove_media(self):
        pl = self.playlist_mod.FmvPlaylist()
        pl.addMedia("/a.mp4")
        pl.addMedia("/b.mp4")
        assert pl.removeMedia(0) is True
        assert pl.mediaCount() == 1
        assert pl.removeMedia(5) is False

    def test_next_index_sequential(self):
        pl = self.playlist_mod.FmvPlaylist()
        pl.addMedia("/a.mp4")
        pl.addMedia("/b.mp4")
        pl._current = 0
        pl.setPlaybackMode(self.playlist_mod.PlaylistSequential)
        assert pl.nextIndex() == 1
        pl._current = 1
        assert pl.nextIndex() == -1

    def test_next_index_loop(self):
        pl = self.playlist_mod.FmvPlaylist()
        pl.addMedia("/a.mp4")
        pl._current = 0
        pl.setPlaybackMode(self.playlist_mod.PlaylistLoop)
        assert pl.nextIndex() == 0

    def test_media_shim(self):
        pl = self.playlist_mod.FmvPlaylist()
        pl.addMedia("/clip.ts")
        assert pl.media(0).canonicalUrl() == "/clip.ts"

    def test_media_url_to_content_passthrough(self):
        assert self.playlist_mod.mediaUrlToContent("x") == "x"

    def test_attach_and_get_playlist(self):
        class FakePlayer:
            def setLoops(self, _loops):
                self.loops = _loops

        player = FakePlayer()
        pl = self.playlist_mod.createPlaylist()
        self.playlist_mod.attachPlaylist(player, pl)
        assert self.playlist_mod.getPlaylist(player) is pl
        assert player._fmvPlaylist is pl
