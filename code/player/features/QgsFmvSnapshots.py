# -*- coding: utf-8 -*-
"""Automatic frame snapshots — capture frames on metadata change or interval."""

import os

from qgis.PyQt.QtCore import QTimer

from QGISFMV.utils.core.QgsFmvUtils import getVideoFolder
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class AutoSnapshot:
    """Captures frames at interval or on significant metadata change."""

    def __init__(self, player):
        self.player = player
        self._active = False
        self._interval_ms = 5000  # default 5 seconds
        self._output_dir = None
        self._count = 0
        self._last_lat = None
        self._last_lon = None
        self._change_threshold = 0.001  # ~111m
        # Parent must be a QObject (player is QDockWidget); AutoSnapshot is not.
        self._timer = QTimer(player)
        self._timer.timeout.connect(self._capture)

    def toggle(self):
        """Toggle auto-snapshot on/off and return the new active state."""
        if self._active:
            self.stop()
        else:
            self.start()
        return self._active

    def start(self):
        """Start the auto-snapshot timer."""
        if self.player is None or self.player.fileName is None:
            return
        folder = getVideoFolder(self.player.fileName)
        self._output_dir = os.path.join(folder, "snapshots")
        os.makedirs(self._output_dir, exist_ok=True)
        self._count = 0
        self._last_lat = None
        self._last_lon = None
        self._active = True
        self._timer.start(self._interval_ms)
        qgsu.showUserAndLogMessage(
            "",
            f"Auto-snapshots started (interval: {self._interval_ms // 1000}s)",
            onlyLog=True,
        )

    def stop(self):
        """Stop the auto-snapshot timer."""
        self._timer.stop()
        self._active = False
        qgsu.showUserAndLogMessage(
            "",
            f"Auto-snapshots stopped ({self._count} captured)",
            onlyLog=True,
        )

    def _capture(self):
        if self.player is None or self.player.closing:
            self.stop()
            return
        vw = getattr(self.player, "videoWidget", None)
        if vw is None:
            return
        img = vw.currentFrame()
        if img is None or img.isNull():
            return

        # Check for significant position change (optional smarter capture)
        data = getattr(self.player, "data", None)
        if data is not None:
            lat = lon = None
            for key in data:
                if "Sensor Latitude" in str(data[key][0]):
                    lat = data[key][1]
                if "Sensor Longitude" in str(data[key][0]):
                    lon = data[key][1]
            if lat is not None and lon is not None:
                try:
                    lat, lon = float(lat), float(lon)
                    if self._last_lat is not None:
                        dlat = abs(lat - self._last_lat)
                        dlon = abs(lon - self._last_lon)
                        if (
                            dlat < self._change_threshold
                            and dlon < self._change_threshold
                        ):
                            return  # no significant move, skip
                    self._last_lat = lat
                    self._last_lon = lon
                except (TypeError, ValueError):
                    pass

        self._count += 1
        filename = os.path.join(self._output_dir, f"snapshot_{self._count:05d}.png")
        img.save(filename, "PNG")
