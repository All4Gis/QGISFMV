# -*- coding: utf-8 -*-
"""Tests for Nominatim reverse-geocode helpers (no live network / no QGIS)."""

from unittest.mock import MagicMock, patch

from code.tests.support import load_plugin_module


def _mod():
    return load_plugin_module(
        "utils/media/QgsFmvGeocode.py", "QGISFMV.utils.media.QgsFmvGeocode"
    )


class TestReverseGeocodeLabel:
    def test_city_and_state(self):
        mod = _mod()
        label = mod.reverseGeocodeLabelFromJson(
            {
                "display_name": "Long, Display, Name, Here",
                "address": {"city": "Madrid", "state": "Comunidad de Madrid"},
            }
        )
        assert label == "Madrid, Comunidad de Madrid"

    def test_falls_back_to_short_display_name(self):
        mod = _mod()
        label = mod.reverseGeocodeLabelFromJson(
            {"display_name": "Puerta del Sol, Madrid, España"}
        )
        assert label == "Puerta del Sol, Madrid"

    def test_error_payload(self):
        mod = _mod()
        assert mod.reverseGeocodeLabelFromJson({"error": "Unable to geocode"}) == "-"

    def test_empty_payload(self):
        mod = _mod()
        assert mod.reverseGeocodeLabelFromJson(None) == "-"


class TestFetchReverseGeocode:
    def test_sends_user_agent_and_rewrites_legacy_url(self):
        mod = _mod()
        mock_resp = MagicMock()
        mock_resp.read.return_value = (
            b'{"display_name":"A, B, C","address":{"town":"Sevilla","state":"Andaluc\\u00eda"}}'
        )
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False

        legacy = (
            "https://nominatim.openstreetmap.org/reverse.php"
            "?format=json&lat={}&lon={}"
        )
        with patch("urllib.request.urlopen", return_value=mock_resp) as urlopen:
            label = mod.fetchReverseGeocodeLabel(legacy, 37.3891, -5.9845)

        assert label == "Sevilla, Andalucía"
        req = urlopen.call_args[0][0]
        # urllib normalizes the header key to "User-agent"
        ua = req.headers.get("User-agent") or req.headers.get("User-Agent")
        assert ua and "QGIS-FMV" in ua
        assert "/reverse?" in req.full_url
        assert "reverse.php" not in req.full_url

    def test_normalize_legacy_url(self):
        mod = _mod()
        assert "reverse.php" not in mod.normalizeReverseGeocodeUrl(
            "https://nominatim.openstreetmap.org/reverse.php?format=json&lat=1&lon=2"
        )
