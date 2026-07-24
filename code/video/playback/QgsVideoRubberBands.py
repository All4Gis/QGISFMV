# -*- coding: utf-8 -*-
"""Rubber-band management extracted from VideoWidget (QgsVideo.py).

Owns every QRubberBand (video-widget overlay) and QgsRubberBand (map-canvas)
instance used while drawing, measuring, censoring, or tracking objects on the
video widget.
"""
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPalette, QColor, QBrush
from qgis.PyQt.QtWidgets import QRubberBand
from qgis.core import QgsWkbTypes
from qgis.gui import QgsRubberBand
from qgis.utils import iface


class RubberBandManager:
    """Manages all QRubberBand and QgsRubberBand instances for VideoWidget."""

    def __init__(self, widget):
        self._widget = widget
        color_black = QColor(Qt.GlobalColor.black)
        color_amber = QColor(252, 215, 108)
        color_track = QColor(255, 145, 0)
        color_measure_dist = QColor(0, 188, 212)
        color_measure_area = QColor(255, 193, 7)

        # Video-widget rubber bands (tracking + censure selection)
        self.tracking_video = QRubberBand(QRubberBand.Shape.Rectangle, widget)
        self.censure_video = QRubberBand(QRubberBand.Shape.Rectangle, widget)

        pal_track = QPalette()
        pal_track.setBrush(QPalette.ColorRole.Highlight, QBrush(color_track))
        self.tracking_video.setPalette(pal_track)

        pal_black = QPalette()
        pal_black.setBrush(QPalette.ColorRole.Highlight, QBrush(color_black))
        self.censure_video.setPalette(pal_black)

        # Map-canvas rubber bands
        canvas = iface.mapCanvas()

        self.poly_canvas = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.poly_canvas.setColor(color_amber)
        self.poly_canvas.setWidth(3)

        self.track_canvas = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.LineGeometry)
        self.track_canvas.setColor(color_track)
        self.track_canvas.setWidth(3)

        self.cursor_canvas = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PointGeometry)
        self.cursor_canvas.setWidth(4)
        self.cursor_canvas.setColor(QColor(255, 100, 100, 250))
        self.cursor_canvas.setIcon(QgsRubberBand.IconType.ICON_FULL_DIAMOND)

        self.measure_dist_canvas = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.LineGeometry)
        self.measure_dist_canvas.setColor(color_measure_dist)
        self.measure_dist_canvas.setWidth(3)

        self.measure_area_canvas = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PolygonGeometry)
        self.measure_area_canvas.setColor(color_measure_area)
        self.measure_area_canvas.setFillColor(QColor(255, 193, 7, 90))
        self.measure_area_canvas.setWidth(3)

    # ------------------------------------------------------------------
    # Bulk reset helpers
    # ------------------------------------------------------------------

    def reset_all(self):
        """Reset every canvas rubber band."""
        self.poly_canvas.reset()
        self.track_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.cursor_canvas.reset(QgsWkbTypes.GeometryType.PointGeometry)
        self.cursor_canvas.hide()
        self.measure_dist_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.measure_area_canvas.reset(QgsWkbTypes.GeometryType.PolygonGeometry)

    def reset_video_bands(self):
        """Reset the two video-widget rubber bands."""
        self.tracking_video.hide()
        self.censure_video.hide()
