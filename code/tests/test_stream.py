# -*- coding: utf-8 -*-
"""Stream URI helpers (no QGIS runtime)."""

import sys
import types
from code.tests.support import load_plugin_module


def _load_stream_utils():
    probe = types.ModuleType("QGISFMV.utils.media.QgsFfmpegProbe")
    probe.is_valid_stream = lambda *args, **kwargs: False
    probe.probe_stream_json = lambda *args, **kwargs: None
    sys.modules["QGISFMV.utils.media.QgsFfmpegProbe"] = probe
    return load_plugin_module("utils/media/QgsFmvStreamUtils.py")


class TestStreamUriHelpers:
    def setup_method(self):
        self.stream = _load_stream_utils()

    def test_isStreamUri_recognizes_network_schemes(self):
        assert self.stream.isStreamUri("udp://@:5005")
        assert self.stream.isStreamUri("rtsp://127.0.0.1:8554/stream")
        assert not self.stream.isStreamUri("/tmp/video.ts")
        assert not self.stream.isStreamUri("file:///C:/video.ts")

    def test_buildStreamUri_udp_listen(self):
        assert self.stream.buildStreamUri("UDP", "127.0.0.1", "5005") == "udp://@:5005"
        assert self.stream.buildStreamUri("UDP", "0.0.0.0", "5005") == "udp://@:5005"

    def test_buildStreamUri_udp_remote(self):
        assert (
            self.stream.buildStreamUri("UDP", "192.168.1.10", "5005")
            == "udp://192.168.1.10:5005"
        )

    def test_buildStreamUri_tcp_listen(self):
        uri = self.stream.buildStreamUri("TCP", "127.0.0.1", "5005")
        assert uri == "tcp://127.0.0.1:5005?listen=1"

    def test_buildStreamUri_rtsp_path(self):
        uri = self.stream.buildStreamUri("RTSP", "camera.local", "8554", "live/main")
        assert uri == "rtsp://camera.local:8554/live/main"

    def test_validateStreamEndpoint_rejects_bad_port(self):
        ok, msg = self.stream.validateStreamEndpoint("UDP", "127.0.0.1", "abc")
        assert not ok
        assert "Port" in msg

    def test_streamDisplayName(self):
        label = self.stream.streamDisplayName("udp://@:5005")
        assert label == "UDP @:5005"

    def test_isStreamUri_rejects_empty(self):
        assert not self.stream.isStreamUri("")
        assert not self.stream.isStreamUri(None)

    def test_validate_port_range(self):
        ok, msg = self.stream.validateStreamEndpoint("UDP", "127.0.0.1", "0")
        assert not ok
        ok, _ = self.stream.validateStreamEndpoint("UDP", "127.0.0.1", "5005")
        assert ok

    def test_rtsp_requires_host(self):
        ok, msg = self.stream.validateStreamEndpoint("RTSP", "  ", "8554")
        assert not ok
        assert "Host" in msg

    def test_build_rtp(self):
        assert (
            self.stream.buildStreamUri("RTP", "10.0.0.1", "5004")
            == "rtp://10.0.0.1:5004"
        )

    def test_vlc_hint_non_empty(self):
        for proto in ("UDP", "TCP", "RTP", "RTSP"):
            assert self.stream.vlcHintText(proto)

    def test_windows_style_file_not_stream(self):
        assert not self.stream.isStreamUri(r"C:\Videos\clip.ts")
        assert not self.stream.isStreamUri("file:///C:/Videos/clip.ts")

    def test_validate_none_protocol_host_safe(self):
        ok, msg = self.stream.validateStreamEndpoint(None, None, "8554")
        assert ok is True  # non-RTSP with no host is fine
        ok, msg = self.stream.validateStreamEndpoint("RTSP", None, "8554")
        assert not ok
        assert "Host" in msg

    def test_display_name_for_local_path(self):
        assert self.stream.streamDisplayName("/tmp/clip.ts") == "clip.ts"

    def test_vlc_hint_unknown_empty(self):
        assert self.stream.vlcHintText("FOO") == ""
