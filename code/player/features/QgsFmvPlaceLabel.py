# -*- coding: utf-8 -*-
"""Live place name under the frame-center (reverse geocode → HUD)."""

from __future__ import annotations

import threading
import time

from QGISFMV.geo.QgsFmvSpatial import haversine_m
from QGISFMV.utils.constants import PLACE_LABEL_MIN_INTERVAL_MS, PLACE_LABEL_MIN_MOVE_M
from QGISFMV.utils.logging import log


class PlaceLabelController:
    """Throttle Nominatim lookups and push short labels to the HUD."""

    def __init__(self, player):
        self.player = player
        self._enabled = False
        self._last_lon = None
        self._last_lat = None
        self._last_ms = 0
        self._label = ""
        self._busy = False
        self._lock = threading.Lock()

    def setEnabled(self, value):
        self._enabled = bool(value)
        if not self._enabled:
            self._label = ""
            self._push_hud("")
        return self._enabled

    def isEnabled(self):
        return self._enabled

    def label(self):
        return self._label

    def onFrameCenter(self, lat, lon):
        """Called from the metadata pipeline when frame-center updates."""
        if not self._enabled or lat is None or lon is None:
            return
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return
        now = int(time.time() * 1000)
        if now - self._last_ms < PLACE_LABEL_MIN_INTERVAL_MS:
            return
        if self._last_lat is not None:
            if (
                haversine_m((lon, lat), (self._last_lon, self._last_lat))
                < PLACE_LABEL_MIN_MOVE_M
            ):
                return
        if self._busy:
            return
        self._busy = True
        self._last_lat, self._last_lon, self._last_ms = lat, lon, now
        threading.Thread(
            target=self._fetch,
            args=(lat, lon),
            daemon=True,
            name="fmv-place-label",
        ).start()

    def _fetch(self, lat, lon):
        try:
            from QGISFMV.utils.core.QgsFmvUtils import fetchReverseGeocodeLabel

            label = fetchReverseGeocodeLabel(lat, lon) or ""
            if label in ("-", ""):
                label = ""
            with self._lock:
                self._label = label
            self._push_hud(label)
        except Exception as exc:
            log.debug("place label fetch failed: %s", exc)
        finally:
            self._busy = False

    def _push_hud(self, label):
        hud = getattr(self.player, "hudOverlay", None)
        if hud is not None and hasattr(hud, "setPlaceLabel"):
            try:
                hud.setPlaceLabel(label)
            except Exception as exc:
                log.debug("HUD place label: %s", exc)
