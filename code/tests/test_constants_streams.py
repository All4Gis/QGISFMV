# -*- coding: utf-8 -*-
"""
Tests for geodesic constants and stream utilities (no QGIS runtime).

Geographic constants are now in QgsGeoUtils (previously in constants.py).
Stream utilities are in QgsFmvStreamUtils.
"""

import math
import pytest


# ---------------------------------------------------------------------------
# Geographic constants — now embedded in QgsGeoUtils
# ---------------------------------------------------------------------------
class TestGeoConstants:
    """Test geographic constants used by QgsGeoUtils."""

    def test_earth_mean_radius(self):
        """Earth mean radius should be ~6371 km."""
        from QGISFMV.geo.QgsGeoUtils import _EARTH_MEAN_RADIUS
        assert 6_000_000 < _EARTH_MEAN_RADIUS < 7_000_000

    def test_earth_mean_radius_approximate(self):
        """Earth mean radius should be approximately 6371008.8 m."""
        from QGISFMV.geo.QgsGeoUtils import _EARTH_MEAN_RADIUS
        assert _EARTH_MEAN_RADIUS == pytest.approx(6_371_008.8, rel=1e-6)

    def test_destination_uses_correct_radius(self):
        """1 degree of latitude at equator ≈ 111.32 km."""
        from QGISFMV.geo.QgsGeoUtils import destination
        # Go 1 degree north from equator
        lon, lat = destination((0.0, 0.0), 111_320, 0.0)
        assert lat == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Stream utilities — inline tests (no QGIS needed)
# ---------------------------------------------------------------------------
class TestStreamUtils:
    """Test stream URI detection and building."""

    def _is_stream(self, uri):
        """Check if a URI is a stream URI (inline implementation)."""
        if not uri:
            return False
        schemes = ("udp://", "rtp://", "rtsp://", "tcp://", "http://", "https://")
        return any(uri.lower().startswith(s) for s in schemes)

    def _stream_display_name(self, uri):
        """Extract display name from stream URI."""
        if not uri:
            return ""
        # udp://239.1.1.1:5000 -> 239.1.1.1:5000
        name = uri.split("://", 1)[-1] if "://" in uri else uri
        return name

    def _build_stream_uri(self, scheme, host, port):
        """Build a stream URI."""
        if not isinstance(port, (int, float)):
            raise TypeError("port must be a number")
        if port < 1 or port > 65535:
            raise ValueError("port must be 1-65535")
        return f"{scheme}://{host}:{int(port)}"

    def test_is_stream_uri_udp(self):
        assert self._is_stream("udp://239.1.1.1:5000")

    def test_is_stream_uri_tcp(self):
        assert self._is_stream("tcp://192.168.1.100:8080")

    def test_is_stream_uri_rtsp(self):
        assert self._is_stream("rtsp://camera.local/stream")

    def test_is_stream_uri_rtp(self):
        assert self._is_stream("rtp://239.1.1.1:5000")

    def test_is_stream_uri_rtmp(self):
        # rtmp is not a supported stream scheme
        assert not self._is_stream("rtmp://server/live/stream")

    def test_is_stream_uri_http(self):
        assert self._is_stream("http://server.com/video.m3u8")

    def test_is_stream_uri_https(self):
        assert self._is_stream("https://server.com/video.m3u8")

    def test_is_not_stream_uri_local(self):
        assert not self._is_stream("/path/to/video.mp4")

    def test_is_not_stream_uri_empty(self):
        assert not self._is_stream("")

    def test_is_not_stream_uri_none(self):
        assert not self._is_stream(None)

    def test_is_not_stream_uri_no_scheme(self):
        assert not self._is_stream("just-a-string")

    def test_stream_display_name_local(self):
        assert self._stream_display_name("/path/to/video.mp4") == "/path/to/video.mp4"

    def test_stream_display_name_udp(self):
        assert self._stream_display_name("udp://239.1.1.1:5000") == "239.1.1.1:5000"

    def test_build_stream_uri_udp(self):
        assert self._build_stream_uri("udp", "239.1.1.1", 5000) == "udp://239.1.1.1:5000"

    def test_build_stream_uri_tcp(self):
        assert self._build_stream_uri("tcp", "192.168.1.100", 8080) == "tcp://192.168.1.100:8080"

    def test_build_stream_uri_rtsp(self):
        assert self._build_stream_uri("rtsp", "camera.local", 554) == "rtsp://camera.local:554"

    def test_build_stream_uri_no_port_raises(self):
        with pytest.raises(TypeError):
            self._build_stream_uri("udp", "239.1.1.1", "abc")

    def test_validate_stream_endpoint_valid(self):
        uri = self._build_stream_uri("udp", "239.1.1.1", 5000)
        assert self._is_stream(uri)

    def test_validate_stream_endpoint_invalid_port(self):
        with pytest.raises(ValueError):
            self._build_stream_uri("udp", "239.1.1.1", 99999)
