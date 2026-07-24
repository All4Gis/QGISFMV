# -*- coding: utf-8 -*-
"""Cursor geo-label formatting and canvas-cursor helpers extracted from
VideoWidget (QgsVideo.py).

Owns the map-canvas cursor marker (rubberband) and the Lon/Lat/Alt (or MGRS)
label shown in the player's status bar while hovering over a georeferenced
video.
"""
import mgrs

from qgis.core import (
    QgsProject,
    QgsPointXY,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
)

from QGISFMV.utils.core.QgsFmvUtils import hasElevationModel
from QGISFMV.utils.logging import log

# Cached project instance — avoids QgsProject.instance() in hot paths.
_project_instance = None


def _get_project():
    global _project_instance
    if _project_instance is None:
        _project_instance = QgsProject.instance()
    return _project_instance


class CursorController:
    """Owns the georeferenced canvas cursor marker and its coordinate label."""

    def __init__(self, widget):
        self._widget = widget

    def clear_rubberband(self):
        """Hide the map cursor marker."""
        w = self._widget
        w._cursorOnVideo = False
        w._lastCursorMapPoint = None
        w.rubbers.cursor_canvas.reset(QgsWkbTypes.GeometryType.PointGeometry)

    def update_rubberband(self, mapPt, force=False):
        """Move the canvas cursor marker without remove/add flicker."""
        w = self._widget
        if (
            not force
            and w._lastCursorMapPoint is not None
            and abs(w._lastCursorMapPoint.x() - mapPt.x()) < 1e-12
            and abs(w._lastCursorMapPoint.y() - mapPt.y()) < 1e-12
        ):
            return

        if w.rubbers.cursor_canvas.numberOfVertices() > 0:
            w.rubbers.cursor_canvas.movePoint(mapPt, 0)
        else:
            w.rubbers.cursor_canvas.addPoint(mapPt)
        w._lastCursorMapPoint = QgsPointXY(mapPt)

    def refresh(self):
        """Re-draw the canvas cursor from the last known video position."""
        w = self._widget
        if not w._cursorOnVideo:
            return
        if w.lastMouseX == -1 or w.lastMouseY == -1:
            return
        w.mouseMoveEvent(None, useLast=True, force=True)

    def update_georeferenced(self, Longitude, Latitude, Altitude, event, force):
        """Update cursor position on the map canvas when georeferencing is active."""
        w = self._widget
        canvas = w._map_canvas()
        if canvas is None:
            return
        tr = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            canvas.mapSettings().destinationCrs(),
            _get_project().transformContext(),
        )
        mapPt = tr.transform(QgsPointXY(Longitude, Latitude))
        self.update_rubberband(mapPt, force=force)

        if w._interaction.militarySymbolDrawer:
            w._milSymbolPreview = [
                Longitude, Latitude, Altitude,
                w._selectedMilSymbolId, w._selectedMilSymbolLabel,
            ]
            w.update()

        self.update_coords_label(Longitude, Latitude, Altitude)

        if w._interaction.polygonDrawer:
            w._draw.add_move_event_value(w.drawPolygon, Longitude, Latitude, Altitude)
        if w._interaction.lineDrawer:
            w._draw.add_move_event_value(w.drawLines, Longitude, Latitude, Altitude)
        if w._interaction.measureDistance and w.drawMeasureDistance:
            w._draw.add_move_event_value(w.drawMeasureDistance, Longitude, Latitude, Altitude)
            w._draw.sync_measure_distance_map()
        if w._interaction.measureArea and w.drawMeasureArea:
            w._draw.add_move_event_value(w.drawMeasureArea, Longitude, Latitude, Altitude)
            w._draw.sync_measure_area_map()

    def format_mgrs_label(self, Latitude, Longitude):
        """Format the MGRS coordinate label as HTML."""
        try:
            mgrsCoords = mgrs.MGRS().toMgrs(Latitude, Longitude)
        except Exception as exc:
            log.debug("MGRS conversion failed: %s", exc)
            mgrsCoords = ""
        value = mgrsCoords if mgrsCoords else "-"
        return (
            "<span style='font-size:10pt; font-weight:bold;'>MGRS : </span>"
            "<span style='font-size:9pt; font-weight:normal;'>%s</span>" % value
        )

    def format_geo_label(self, Longitude, Latitude, Altitude):
        """Format Lon/Lat/Alt coordinates as HTML."""
        lon_txt = "%.5f" % Longitude
        lat_txt = "%.5f" % Latitude
        alt_txt = ("%.0f" % Altitude) if hasElevationModel() else "-"

        return (
            "<span style='font-size:10pt; font-weight:bold;'>Lon : </span>"
            "<span style='font-size:9pt; font-weight:normal;'>%s</span>" % lon_txt
            + "<span style='font-size:10pt; font-weight:bold;'> Lat : </span>"
            "<span style='font-size:9pt; font-weight:normal;'>%s</span>" % lat_txt
            + "<span style='font-size:10pt; font-weight:bold;'> Alt : </span>"
            "<span style='font-size:9pt; font-weight:normal;'>%s</span>" % alt_txt
        )

    def update_coords_label(self, Longitude, Latitude, Altitude):
        """Set the cursor coordinate label in the player status bar."""
        w = self._widget
        if w._MGRS:
            txt = self.format_mgrs_label(Latitude, Longitude)
        else:
            txt = self.format_geo_label(Longitude, Latitude, Altitude)
        w.parent.lb_cursor_coord.setText(txt)

    def clear_coords_label(self):
        """Clear the cursor coordinate label when no georeferencing is available."""
        w = self._widget
        w.parent.lb_cursor_coord.setText(
            "<span style='font-size:10pt; font-weight:bold;'>Lon :</span>"
            "<span style='font-size:9pt; font-weight:normal;'>-</span>"
            "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>"
            "<span style='font-size:9pt; font-weight:normal;'>-</span>"
            "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>"
            "<span style='font-size:9pt; font-weight:normal;'>-</span>"
        )
