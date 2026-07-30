# -*- coding: utf-8 -*-
"""Telemetry HUD painted directly on the video widget (no overlay QWidget)."""

import time

from qgis.PyQt.QtCore import QPointF, Qt
from qgis.PyQt.QtGui import QColor, QPainter, QFont, QPen, QBrush


class HudOverlay:
    """HUD state + painter; rendered inside VideoWidget.paintEvent to avoid Qt crashes."""

    def __init__(self, video_widget=None):
        self._video_widget = video_widget
        self._visible = False
        self._lat = None
        self._lon = None
        self._alt = None
        self._frame_center_lat = None
        self._frame_center_lon = None
        self._frame_center_elev = None
        self._timestamp = ""
        self._place_label = ""
        self._target_cue = ""
        self._video_size = (0, 0)
        self._alert_msg = ""
        self._alert_until = 0.0

    def _request_repaint(self):
        widget = self._video_widget
        if widget is not None:
            widget.update()

    def setVideoSize(self, w, h):
        """Update the known video dimensions for HUD layout calculations."""
        self._video_size = (w, h)
        self._request_repaint()

    def _sensor_altitude(self, gv):
        alts = gv.getSensorTrueAltitude()
        if isinstance(alts, (list, tuple)):
            for alt in alts:
                if alt is not None:
                    return alt
            return None
        return alts

    def updateFromState(self, gv):
        """Pull live telemetry from the global state object."""
        if gv is None:
            return
        self._lat = gv.getSensorLatitude()
        self._lon = gv.getSensorLongitude()
        self._alt = self._sensor_altitude(gv)
        self._frame_center_lat = gv.getFrameCenterLat()
        self._frame_center_lon = gv.getFrameCenterLon()
        self._frame_center_elev = gv.getFrameCenterElevation()
        self._request_repaint()

    def setTimestamp(self, ts):
        """Set the timestamp string displayed in the HUD."""
        self._timestamp = ts or ""
        self._request_repaint()

    def setPlaceLabel(self, label):
        """Set the reverse-geocoded place name shown on the HUD."""
        self._place_label = str(label or "")
        self._request_repaint()

    def setTargetCue(self, label):
        """Set the target-pin cue line (range / bearing / next FOV)."""
        self._target_cue = str(label or "")
        self._request_repaint()

    def toggle(self):
        """Toggle HUD visibility and return the new state."""
        self._visible = not self._visible
        self._request_repaint()
        return self._visible

    def setAlertBanner(self, msg, ttl_ms=3500):
        """Flash a top alert banner for *ttl_ms* (shown even if HUD is off)."""
        self._alert_msg = str(msg or "")
        self._alert_until = time.time() + max(0.5, float(ttl_ms) / 1000.0)
        self._request_repaint()

    def _alert_active(self):
        return bool(self._alert_msg) and time.time() < self._alert_until

    def paint(self, painter, width, height):
        """Draw HUD elements using the video widget's active painter."""
        if width < 10 or height < 10:
            return
        if painter is None or not painter.isActive():
            return

        # Sentinel / alert flash — independent of HUD toggle.
        if self._alert_active():
            painter.save()
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                banner_h = max(28, min(44, height // 12))
                painter.setBrush(QBrush(QColor(180, 24, 24, 200)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(0, 0, width, banner_h)
                font = QFont(
                    "Courier", max(10, min(14, width // 70)), QFont.Weight.Bold
                )
                painter.setFont(font)
                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.drawText(
                    QPointF(12, banner_h * 0.68),
                    self._alert_msg[:120],
                )
            finally:
                painter.restore()

        # Target pin cue — visible even if HUD strip is off.
        if self._target_cue:
            painter.save()
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                top = (
                    8
                    if not self._alert_active()
                    else max(28, min(44, height // 12)) + 4
                )
                font = QFont("Courier", max(9, min(12, width // 85)), QFont.Weight.Bold)
                painter.setFont(font)
                metrics = painter.fontMetrics()
                text = self._target_cue[:72]
                tw = metrics.horizontalAdvance(text) + 16
                th = metrics.height() + 8
                x = max(8, width - tw - 10)
                painter.setBrush(QBrush(QColor(20, 20, 20, 170)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(x, top, tw, th, 4, 4)
                painter.setPen(QPen(QColor(255, 200, 40)))
                painter.drawText(QPointF(x + 8, top + th * 0.72), text)
            finally:
                painter.restore()

        if not self._visible:
            return

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            strip_h = min(120, height // 4)
            painter.setBrush(QBrush(QColor(0, 0, 0, 140)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, height - strip_h, width, strip_h, 6, 6)

            font = QFont("Courier", max(10, min(13, width // 80)), QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(QPen(QColor(0, 255, 65)))

            y0 = height - strip_h + 18
            x_left = 12
            x_right = width // 2 + 12
            line_h = 18

            def _fmt(v, decimals=6):
                if v is None:
                    return "N/A"
                try:
                    return f"{float(v):.{decimals}f}"
                except (TypeError, ValueError):
                    return str(v)

            lines_left = [
                f" LAT   {_fmt(self._lat)}",
                f" LON   {_fmt(self._lon)}",
                f" ALT   {_fmt(self._alt, 1)} m",
            ]
            lines_right = [
                f" FCLAT {_fmt(self._frame_center_lat)}",
                f" FCLON {_fmt(self._frame_center_lon)}",
                f" FCELV {_fmt(self._frame_center_elev, 1)} m",
            ]
            if self._place_label:
                lines_right.append(f" PLACE {self._place_label[:42]}")

            for i, txt in enumerate(lines_left):
                painter.drawText(QPointF(x_left, y0 + i * line_h), txt)
            for i, txt in enumerate(lines_right):
                painter.drawText(QPointF(x_right, y0 + i * line_h), txt)

            if self._timestamp:
                small_font = QFont("Courier", max(8, min(11, width // 100)))
                painter.setFont(small_font)
                painter.setPen(QPen(QColor(255, 255, 255, 200)))
                painter.drawText(QPointF(width / 2 - 60, 18), f"TS: {self._timestamp}")

            painter.setPen(QPen(QColor(0, 255, 65, 180), 2))
            bracket = 25
            margin = 20
            painter.drawLine(margin, margin, margin + bracket, margin)
            painter.drawLine(margin, margin, margin, margin + bracket)
            painter.drawLine(width - margin, margin, width - margin - bracket, margin)
            painter.drawLine(width - margin, margin, width - margin, margin + bracket)

            by = height - strip_h - margin
            painter.drawLine(margin, by, margin + bracket, by)
            painter.drawLine(margin, by, margin, by - bracket)
            painter.drawLine(width - margin, by, width - margin - bracket, by)
            painter.drawLine(width - margin, by, width - margin, by - bracket)
        finally:
            painter.restore()
