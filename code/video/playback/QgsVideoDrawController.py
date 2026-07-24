# -*- coding: utf-8 -*-
"""Drawing/measurement tool controller extracted from VideoWidget (QgsVideo.py).

Owns the draw-list mutations (points, lines, polygons, censure, military
symbols, measurements), the tool Set*/removeLast*/removeAll* logic, the
placement-hint flashing, and the drag-rubberband bookkeeping used by the
mouse event handlers.
"""
from qgis.PyQt.QtCore import QPoint, QRect, QSize
from qgis.core import QgsPointXY, QgsWkbTypes

from QGISFMV.utils.core.QgsFmvUtils import GetGCPGeoTransform, qmouse_pos
from QGISFMV.utils.logging import log
from QGISFMV.utils.layers.QgsFmvLayers import (
    AddDrawPointOnMap,
    AddDrawLineOnMap,
    AddDrawPolygonOnMap,
    AddDrawMilitarySymbolOnMap,
    RemoveLastDrawPolygonOnMap,
    RemoveAllDrawPolygonOnMap,
    RemoveLastDrawPointOnMap,
    RemoveAllDrawPointOnMap,
    RemoveLastDrawMilitarySymbolOnMap,
    RemoveAllDrawMilitarySymbolOnMap,
    RemoveAllDrawLineOnMap,
    SyncMeasureDistanceOnMap,
    SyncMeasureAreaOnMap,
)
from QGISFMV.video.playback.QgsVideoState import MOUSE_MOVE_EVENT


class VideoDrawController:
    """Owns drawing/measurement tool state mutations for a VideoWidget."""

    def __init__(self, widget):
        self._widget = widget

    # ------------------------------------------------------------------
    # Line drawer
    # ------------------------------------------------------------------

    def remove_last_line(self):
        """Remove Last Line Objects"""
        w = self._widget
        if w.drawLines:
            # Remove trailing mouseMoveEvent entry if present
            if w.drawLines[-1][-1] == MOUSE_MOVE_EVENT:
                w.drawLines.pop()
            # Find the last separator [None, None, None] and delete everything after it
            sep_idx = -1
            for i in range(len(w.drawLines) - 1, -1, -1):
                if w.drawLines[i][0] is None:
                    sep_idx = i
                    break
            if sep_idx >= 0:
                del w.drawLines[sep_idx:]
            else:
                w.drawLines.clear()
            w.UpdateSurface()
            AddDrawLineOnMap(w.drawLines)

    def remove_last_segment_line(self):
        """Remove Last Segment Line Objects"""
        w = self._widget
        if not w.drawLines:
            return
        # Remove trailing mouseMoveEvent entry if present
        if w.drawLines[-1][-1] == MOUSE_MOVE_EVENT:
            w.drawLines.pop()
        if not w.drawLines:
            return
        # Remove the last point (current segment endpoint)
        w.drawLines.pop()
        # If we hit a separator, remove it too
        if w.drawLines and w.drawLines[-1][0] is None:
            w.drawLines.pop()
        w.UpdateSurface()
        AddDrawLineOnMap(w.drawLines)

    def remove_all_lines(self):
        """Resets Line List"""
        w = self._widget
        if w.drawLines:
            w.drawLines = []
            w.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawLineOnMap(w._map_group())

    def add_line_vertex(self, Longitude, Latitude, Altitude):
        """Add a vertex to the line being drawn."""
        w = self._widget
        w.drawLines.append([Longitude, Latitude, Altitude])
        AddDrawLineOnMap(w.drawLines)

    # ------------------------------------------------------------------
    # Point drawer
    # ------------------------------------------------------------------

    def remove_last_point(self):
        """Remove All Point Drawer Objects"""
        w = self._widget
        if w.drawPtPos:
            del w.drawPtPos[-1]
            w.UpdateSurface()
            RemoveLastDrawPointOnMap(w._map_group())

    def remove_all_point(self):
        """Remove All Point Drawer Objects"""
        w = self._widget
        if w.drawPtPos:
            w.drawPtPos = []
            w.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPointOnMap(w._map_group())

    def place_point(self, Longitude, Latitude, Altitude):
        """Place a drawing point on the video and map layer."""
        w = self._widget
        pointIndex = len(w.drawPtPos) + 1
        AddDrawPointOnMap(pointIndex, Longitude, Latitude, Altitude)
        w.drawPtPos.append([Longitude, Latitude, Altitude])

    # ------------------------------------------------------------------
    # Polygon drawer
    # ------------------------------------------------------------------

    def remove_all_polygon(self):
        """Remove All Polygon Drawer Objects"""
        w = self._widget
        if w.drawPolygon:
            w.drawPolygon = []
            w.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPolygonOnMap(w._map_group())

    def remove_last_polygon(self):
        """Remove Last Polygon Drawer Objects"""
        w = self._widget
        if w.drawPolygon:
            # Remove trailing mouseMoveEvent entry if present
            if w.drawPolygon[-1][-1] == MOUSE_MOVE_EVENT:
                w.drawPolygon.pop()
            # Find the last separator [None, None, None] and delete everything after it
            sep_idx = -1
            for i in range(len(w.drawPolygon) - 1, -1, -1):
                if w.drawPolygon[i][0] is None:
                    sep_idx = i
                    break
            if sep_idx >= 0:
                del w.drawPolygon[sep_idx:]
            else:
                w.drawPolygon.clear()

            w.UpdateSurface()
            # remove last index layer
            RemoveLastDrawPolygonOnMap(w._map_group())

    def add_polygon_vertex(self, Longitude, Latitude, Altitude):
        """Add a vertex to the polygon being drawn."""
        w = self._widget
        w.rubbers.poly_canvas.addPoint(QgsPointXY(Longitude, Latitude))
        w.poly_coordinates.extend(QgsPointXY(Longitude, Latitude))
        w.drawPolygon.append([Longitude, Latitude, Altitude])

    # ------------------------------------------------------------------
    # Censure
    # ------------------------------------------------------------------

    def remove_all_censure(self):
        """Remove All Censure Objects"""
        w = self._widget
        if w.drawCesure:
            w.drawCesure = []
            w.UpdateSurface()

    def remove_last_censured(self):
        """Remove Last Censure Objects"""
        w = self._widget
        if w.drawCesure:
            del w.drawCesure[-1]
            w.UpdateSurface()

    def finish_censure_selection(self):
        """Consume the censure-video rubberband drag into drawCesure."""
        w = self._widget
        geom = w.rubbers.censure_video.geometry()
        w.rubbers.censure_video.hide()
        w.drawCesure.append([geom])
        w.update()

    # ------------------------------------------------------------------
    # Military symbols
    # ------------------------------------------------------------------

    def remove_last_military_symbol(self):
        """Remove the last military symbol from the video and map layers."""
        w = self._widget
        if w.drawMilSymbols:
            del w.drawMilSymbols[-1]
            w.UpdateSurface()
            RemoveLastDrawMilitarySymbolOnMap(w._map_group())

    def remove_all_military_symbols(self):
        """Remove all military symbols from the video and map layers."""
        w = self._widget
        if w.drawMilSymbols:
            w.drawMilSymbols = []
            w.UpdateSurface()
            RemoveAllDrawMilitarySymbolOnMap(w._map_group())

    def set_selected_military_symbol(self, symbol_id, unit_name=""):
        """Set the active military symbol type for the next placement click."""
        w = self._widget
        w._selectedMilSymbolId = symbol_id or "f_inf"
        w._selectedMilSymbolLabel = unit_name or ""

    def place_military_symbol(self, Longitude, Latitude, Altitude):
        """Place a military symbol on the video and map layer."""
        w = self._widget
        symbol_index = len(w.drawMilSymbols) + 1
        symbol_id = getattr(w, "_selectedMilSymbolId", "f_inf")
        unit_name = getattr(w, "_selectedMilSymbolLabel", "")
        AddDrawMilitarySymbolOnMap(symbol_index, Longitude, Latitude, Altitude,
                                   symbol_id, unit_name)
        w.drawMilSymbols.append([Longitude, Latitude, Altitude, symbol_id, unit_name])
        player = getattr(w, "_player", None) or getattr(w, "parent", None)
        if player is not None and hasattr(player, "_refreshMilSymbolPlacedCount"):
            player._refreshMilSymbolPlacedCount()

    def flash_military_symbol_placement_hint(self, pulses=8):
        """Flash a visual hint prompting the user to click and place a symbol."""
        w = self._widget
        w._toolHintFlash = max(w._toolHintFlash, pulses)
        w._toolHintText = w.tr("Click here on the video to place the military symbol")
        if not w._toolHintTimer.isActive():
            w._toolHintTimer.start()
        w.update()

    # ------------------------------------------------------------------
    # Measure distance / area
    # ------------------------------------------------------------------

    def reset_measure_distance(self):
        """Resets Measure Distance List"""
        w = self._widget
        w.drawMeasureDistance = []
        self.sync_measure_distance_map()

    def reset_measure_area(self):
        """Resets Measure Area List"""
        w = self._widget
        w.drawMeasureArea = []
        self.sync_measure_area_map()

    def sync_measure_distance_map(self):
        """Refresh the rubber band and persistent layer for distance measurements."""
        w = self._widget
        w.rubbers.measure_dist_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)
        # Always refresh the persistent measure layer (keeps finished chains).
        try:
            w._sync_draw_group()
            SyncMeasureDistanceOnMap(w.drawMeasureDistance, w._map_group())
        except Exception as exc:
            log.debug("SyncMeasureDistanceOnMap failed: %s", exc)
        if not w._interaction.measureDistance:
            return
        for pt in w.drawMeasureDistance:
            if not pt or pt[0] is None:
                continue
            # Rubber band uses geographic lon/lat as canvas points (EPSG:4326 project)
            w.rubbers.measure_dist_canvas.addPoint(QgsPointXY(pt[0], pt[1]))

    def sync_measure_area_map(self):
        """Refresh the rubber band and persistent layer for area measurements."""
        w = self._widget
        w.rubbers.measure_area_canvas.reset(
            QgsWkbTypes.GeometryType.PolygonGeometry
        )
        try:
            w._sync_draw_group()
            SyncMeasureAreaOnMap(w.drawMeasureArea, w._map_group())
        except Exception as exc:
            log.debug("SyncMeasureAreaOnMap failed: %s", exc)
        if not w._interaction.measureArea:
            return
        for pt in w.drawMeasureArea:
            if not pt or pt[0] is None:
                continue
            w.rubbers.measure_area_canvas.addPoint(QgsPointXY(pt[0], pt[1]))

    def set_measure_distance(self, value):
        """Set measure Distance
        @type value: bool
        @param value:
        @return:
        """
        w = self._widget
        w._interaction.measureDistance = value
        if value:
            self.flash_tool_placement_hint(
                w.tr("Click on the video to measure distance, double-click to finish")
            )
        else:
            self.sync_measure_distance_map()
            self.clear_tool_hint()
        w.update()

    def set_measure_area(self, value):
        """Set measure Area
        @type value: bool
        @param value:
        @return:
        """
        w = self._widget
        w._interaction.measureArea = value
        if value:
            self.flash_tool_placement_hint(
                w.tr("Click on the video to measure area, double-click to finish")
            )
        else:
            self.sync_measure_area_map()
            self.clear_tool_hint()
        w.update()

    # ------------------------------------------------------------------
    # Placement-hint flashing (generic banner)
    # ------------------------------------------------------------------

    def flash_tool_placement_hint(self, text, pulses=8):
        """Show a flashing banner hint for the active drawing/measurement tool."""
        w = self._widget
        w._toolHintFlash = max(w._toolHintFlash, pulses)
        w._toolHintText = text
        if not w._toolHintTimer.isActive():
            w._toolHintTimer.start()
        w.update()

    def tick_tool_hint_flash(self):
        """Advance the placement-hint flash timer by one tick."""
        w = self._widget
        if w._toolHintFlash <= 0:
            w._toolHintTimer.stop()
            return
        w._toolHintFlash -= 1
        w.update()

    def clear_tool_hint(self):
        """Reset tool-placement hint state and stop the flash timer."""
        w = self._widget
        w._toolHintFlash = 0
        w._toolHintText = ""
        w._toolHintTimer.stop()

    # ------------------------------------------------------------------
    # Tool toggles
    # ------------------------------------------------------------------

    def set_hand_draw(self, value):
        """Set Hand Draw
        @type value: bool
        @param value:
        @return:
        """
        self._widget._interaction.HandDraw = value

    def set_censure(self, value):
        """Set Censure Video Parts
        @type value: bool
        @param value:
        @return:
        """
        w = self._widget
        w._interaction.censure = value
        w.update()

    def set_military_symbol_drawer(self, value):
        """Enable or disable the military symbol placement mode."""
        w = self._widget
        w._interaction.militarySymbolDrawer = value
        if not value:
            w._milSymbolPreview = None
            self.clear_tool_hint()
        else:
            self.flash_military_symbol_placement_hint()
        w.update()

    def set_point_drawer(self, value):
        """Set Point Drawer
        @type value: bool
        @param value:
        """
        w = self._widget
        w._interaction.pointDrawer = value
        if value:
            self.flash_tool_placement_hint(w.tr("Click on the video to place a point"))
        else:
            self.clear_tool_hint()
        w.update()

    def set_line_drawer(self, value):
        """Set Line Drawer
        @type value: bool
        """
        w = self._widget
        w._interaction.lineDrawer = value
        if value:
            self.flash_tool_placement_hint(w.tr("Double-click on the video to draw lines"))
        else:
            self.clear_tool_hint()
        w.update()

    def set_polygon_drawer(self, value):
        """Set Polygon Drawer
        @type value: bool
        """
        w = self._widget
        w._interaction.polygonDrawer = value
        if value:
            self.flash_tool_placement_hint(
                w.tr("Click on the video to draw a polygon, double-click to finish")
            )
        else:
            self.clear_tool_hint()
        w.update()

    # ------------------------------------------------------------------
    # Bulk reset
    # ------------------------------------------------------------------

    def restore_drawer(self):
        """Remove and restore all Drawer Options"""
        w = self._widget
        w._interaction.clear()
        # Magnifier Glass
        w.dragPos = QPoint()
        w.tapTimer.stop()

    def remove_video_drawings(self):
        """Remove Video Drawings"""
        w = self._widget
        (
            w.poly_coordinates,
            w.drawPtPos,
            w.drawMilSymbols,
            w.drawLines,
            w.drawMeasureDistance,
            w.drawMeasureArea,
            w.drawPolygon,
        ) = ([], [], [], [], [], [], [])

    def add_move_event_value(self, values, Longitude, Latitude, Altitude):
        """
        Remove and Add move value for fluid drawing

        @type values: list
        @param values: Points list

        @type Longitude: float
        @param Longitude: Longitude value

        @type Latitude: float
        @param Latitude: Latitude value

        @type Altitude: float
        @param Altitude: Altitude value

        """
        w = self._widget
        values[:] = [pt for pt in values if pt[-1] != MOUSE_MOVE_EVENT]
        values.append([Longitude, Latitude, Altitude, MOUSE_MOVE_EVENT])
        w.UpdateSurface()

    # ------------------------------------------------------------------
    # Mouse event dispatch helpers
    # ------------------------------------------------------------------

    def handle_double_click(self):
        """Handle a double-click for the active line/measure/polygon tool.

        Returns True if the double-click was consumed by a tool (caller
        should stop further mouseDoubleClickEvent processing).
        """
        w = self._widget
        if GetGCPGeoTransform() is not None and w._interaction.lineDrawer:
            w.drawLines.append([None, None, None])
            return True

        if GetGCPGeoTransform() is not None and w._interaction.measureDistance:
            # Close the current chain; keep the measure tool checked/active
            # so the user can start another measurement immediately.
            w.drawMeasureDistance.append([None, None, None])
            self.sync_measure_distance_map()
            w.UpdateSurface()
            return True

        if GetGCPGeoTransform() is not None and w._interaction.measureArea:
            # Close the current polygon; keep the measure tool checked/active.
            w.drawMeasureArea.append([None, None, None])
            self.sync_measure_area_map()
            w.UpdateSurface()
            return True

        if GetGCPGeoTransform() is not None and w._interaction.polygonDrawer:
            ok = AddDrawPolygonOnMap(w.poly_coordinates)
            # Prevent invalid geometry (Polygon with 2 points)
            if not ok:
                return True

            w.drawPolygon.append([None, None, None])

            # Empty RubberBand
            for _ in range(w.rubbers.poly_canvas.numberOfVertices()):
                w.rubbers.poly_canvas.removeLastPoint()
            # Empty List
            w.poly_coordinates = []
            return True

        return False

    def handle_click(self, Longitude, Latitude, Altitude):
        """Dispatch a click to the active drawing/measurement tool."""
        w = self._widget
        if w._interaction.pointDrawer:
            self.place_point(Longitude, Latitude, Altitude)
        if w._interaction.militarySymbolDrawer:
            self.place_military_symbol(Longitude, Latitude, Altitude)
        if w._interaction.polygonDrawer:
            self.add_polygon_vertex(Longitude, Latitude, Altitude)
        if w._interaction.lineDrawer:
            self.add_line_vertex(Longitude, Latitude, Altitude)
        if w._interaction.measureDistance:
            w.drawMeasureDistance.append([Longitude, Latitude, Altitude])
            self.sync_measure_distance_map()
        if w._interaction.measureArea:
            w.drawMeasureArea.append([Longitude, Latitude, Altitude])
            self.sync_measure_area_map()

    def start_drag_rubberbands(self):
        """Show rubberbands for drag-based tools (object tracking, censure)."""
        w = self._widget
        if w._interaction.objectTracking:
            w.rubbers.tracking_video.setGeometry(QRect(w.origin, QSize()))
            w.rubbers.tracking_video.show()
        if w._interaction.censure:
            w.rubbers.censure_video.setGeometry(QRect(w.origin, QSize()))
            w.rubbers.censure_video.show()

    def update_drag_rubberbands(self, event):
        """Update object tracking and censure rubberbands during drag."""
        w = self._widget
        mp = qmouse_pos(event)
        if not w.rubbers.tracking_video.isHidden():
            w.rubbers.tracking_video.setGeometry(
                QRect(w.origin, mp).normalized()
            )
        if not w.rubbers.censure_video.isHidden():
            w.rubbers.censure_video.setGeometry(
                QRect(w.origin, mp).normalized()
            )
