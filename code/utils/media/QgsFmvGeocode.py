# -*- coding: utf-8 -*-
"""Reverse geocoding helpers (Nominatim-compatible).

Nominatim's usage policy requires an identifying ``User-Agent``.  Background
threads (video manager load) use urllib; the GUI path can use Qt networking.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

try:
    from QGISFMV.utils.logging import log
except ImportError:
    import logging

    log = logging.getLogger("qgis_fmv")

# Nominatim usage policy: identify the application.
GEOCODE_USER_AGENT = "QGIS-FMV/4.00 (https://github.com/All4Gis/QGISFMV)"


def normalizeReverseGeocodeUrl(url):
    """Prefer Nominatim ``/reverse`` over legacy ``reverse.php``."""
    if not url:
        return url
    return url.replace(
        "nominatim.openstreetmap.org/reverse.php?",
        "nominatim.openstreetmap.org/reverse?",
    )


def reverseGeocodeLabelFromJson(data):
    """Build a short Start Location label from a Nominatim JSON payload."""
    if not data or data.get("error"):
        return "-"
    try:
        address = data.get("address") or {}
        locality = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality")
            or address.get("suburb")
            or address.get("hamlet")
            or address.get("city_district")
        )
        region = (
            address.get("state")
            or address.get("province")
            or address.get("county")
            or address.get("region")
            or address.get("state_district")
        )
        country = address.get("country")
        if locality and region:
            return "{}, {}".format(locality, region)
        if locality and country:
            return "{}, {}".format(locality, country)
        if locality:
            return locality
        display = data.get("display_name") or ""
        if display:
            parts = [p.strip() for p in display.split(",") if p.strip()]
            if len(parts) >= 2:
                return ", ".join(parts[:2])
            return display
        return "-"
    except Exception as exc:
        log.debug("reverseGeocodeLabel parse failed: %s", exc)
        return "-"


def fetchReverseGeocodeJson(url_template, centerLat, centerLon, timeout=8):
    """HTTP GET reverse-geocode JSON via urllib (thread-safe).

    Parameters
    ----------
    url_template : str
        Template with two ``{}`` placeholders for lat and lon.
    """
    if not url_template or centerLat is None or centerLon is None:
        return None
    try:
        url = normalizeReverseGeocodeUrl(
            url_template.format(str(centerLat), str(centerLon))
        )
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": GEOCODE_USER_AGENT,
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
        log.warning(
            "Reverse geocode failed for %s, %s: %s", centerLat, centerLon, exc
        )
        return None
    except Exception as exc:
        log.warning(
            "Reverse geocode failed for %s, %s: %s", centerLat, centerLon, exc
        )
        return None


def fetchReverseGeocodeLabel(url_template, centerLat, centerLon, timeout=8):
    """Return a short address label, or ``"-"`` on failure."""
    return reverseGeocodeLabelFromJson(
        fetchReverseGeocodeJson(url_template, centerLat, centerLon, timeout=timeout)
    )
