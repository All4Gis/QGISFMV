# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import (
    Qt,
    QPoint,
    QPointF,
    QEvent,
    QBasicTimer,
    QTimer,
)
from qgis.PyQt.QtGui import (
    QPalette,
    QColor,
    QBrush,
    QCursor,
    QMouseEvent,
)
from qgis.utils import iface

from QGISFMV.utils.media.QgsFmvMultimedia import StoppedState, PlayingState
from qgis.PyQt.QtMultimedia import QVideoSink
from qgis.PyQt.QtWidgets import QWidget as VideoWidgetBase
from QGISFMV.video.playback.QgsVideoSurface import VideoSinkSurface
from QGISFMV.video.playback.QgsVideoPaintPipeline import VideoPaintPipeline
from QGISFMV.video.playback.QgsVideoRubberBands import RubberBandManager
from QGISFMV.video.playback.QgsVideoDrawController import VideoDrawController
from QGISFMV.video.playback.QgsVideoCursor import CursorController
from QGISFMV.video.playback.QgsVideoObjectTracking import ObjectTrackingController
from QGISFMV.utils.core.QgsFmvUtils import (
    GetGCPGeoTransform,
    GetImageHeight,
    qmouse_pos,
)
from QGISFMV.video.playback.QgsVideoUtils import VideoUtils as vut
from QGISFMV.video.playback.QgsVideoState import (
    InteractionState,
    FilterState,
    TrackLockState,
)
from QGISFMV.utils.logging import log


class VideoWidget(VideoWidgetBase):

    def __init__(self, parent=None):
        """Constructor"""
        super().__init__(parent)
        self._videoSink = QVideoSink(self)
        self.surface = VideoSinkSurface(self, self._videoSink)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self.rubbers = RubberBandManager(self)
        self._draw = VideoDrawController(self)
        self._cursor = CursorController(self)
        self._tracking = ObjectTrackingController(self)

        self._interaction = InteractionState()
        self._filterSatate = FilterState()
        self._display_refresh_timer = QTimer(self)
        self._display_refresh_timer.setSingleShot(True)
        self._display_refresh_timer.timeout.connect(self._refreshVideoDisplay)

        self._isinit = False
        self._MGRS = False

        self.drawCesure = []
        (
            self.poly_coordinates,
            self.drawPtPos,
            self.drawMilSymbols,
            self.drawLines,
            self.drawMeasureDistance,
            self.drawMeasureArea,
            self.drawPolygon,
        ) = ([], [], [], [], [], [], [])
        self._selectedMilSymbolId = "f_inf"
        self._selectedMilSymbolLabel = ""
        self._milSymbolPreview = None
        # Generalized tool placement hint (banner flash for active draw/measure tool)
        self._toolHintFlash = 0
        self._toolHintText = ""
        self._toolHintTimer = QTimer(self)
        self._toolHintTimer.setInterval(350)
        self._toolHintTimer.timeout.connect(self._tickToolHintFlash)

        self.parent = None

        color_black = QColor(Qt.GlobalColor.black)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, Qt.GlobalColor.transparent)
        self.setPalette(palette)

        self.origin, self.dragPos = QPoint(), QPoint()
        self.tapTimer = QBasicTimer()
        self.brush = QBrush(color_black)

        self.lastMouseX = -1
        self.lastMouseY = -1
        self._cursorOnVideo = False
        self._lastCursorMapPoint = None
        self.setMouseTracking(True)
        self._magnifier_cache = {"key": None, "pixmap": None}
        self._track_last = 0.0
        self._last_track_bbox = None
        self._tracker_backend = None
        self._track_id = 0
        self._track_misses = 0
        from QGISFMV.utils.constants import TRACK_MAX_MISSES, TRACK_TIMER_INTERVAL_MS

        self._track_max_misses = TRACK_MAX_MISSES
        self._track_lock_state = TrackLockState.IDLE
        self._track_timer = QTimer(self)
        self._track_timer.setInterval(TRACK_TIMER_INTERVAL_MS)
        self._track_timer.timeout.connect(self._update_object_tracking)

    def setPlayerWindow(self, player):
        """Bind the FMV player window (actions, menus, and playback state)."""
        self._player = player
        self.parent = player

    def _map_iface(self):
        """Return the QGIS iface, preferring the player's stored reference."""
        player = getattr(self, "_player", None) or getattr(self, "parent", None)
        if player is not None and getattr(player, "iface", None) is not None:
            return player.iface
        return iface

    def _map_group(self):
        """Active video layer-tree group for map draw clear/add helpers."""
        player = getattr(self, "_player", None) or getattr(self, "parent", None)
        if player is not None and hasattr(player, "_videoGroupName"):
            try:
                return player._videoGroupName()
            except Exception as exc:
                log.debug("_videoGroupName() failed: %s", exc)
                return None
        return None

    def _sync_draw_group(self):
        """Keep QgsFmvLayers.groupName aligned with this player's video group."""
        group = self._map_group()
        if not group:
            return
        import QGISFMV.utils.layers.QgsFmvLayers as _layers

        _layers.groupName = group

    def _map_canvas(self):
        map_iface = self._map_iface()
        if map_iface is None:
            return None
        return map_iface.mapCanvas()

    def _syncMeasureDistanceMap(self):
        """Refresh the rubber band and persistent layer for distance measurements."""
        self._draw.sync_measure_distance_map()

    def _syncMeasureAreaMap(self):
        """Refresh the rubber band and persistent layer for area measurements."""
        self._draw.sync_measure_area_map()

    def removeLastLine(self):
        """Remove Last Line Objects"""
        self._draw.remove_last_line()

    def removeLastSegmentLine(self):
        """Remove Last Segment Line Objects"""
        self._draw.remove_last_segment_line()

    def removeAllLines(self):
        """Resets Line List"""
        self._draw.remove_all_lines()

    def ResetDrawMeasureDistance(self):
        """Resets Measure Distance List"""
        self._draw.reset_measure_distance()

    def ResetDrawMeasureArea(self):
        """Resets Measure Area List"""
        self._draw.reset_measure_area()

    def removeAllCensure(self):
        """Remove All Censure Objects"""
        self._draw.remove_all_censure()

    def removeLastCensured(self):
        """Remove Last Censure Objects"""
        self._draw.remove_last_censured()

    def removeLastMilitarySymbol(self):
        """Remove the last military symbol from the video and map layers."""
        self._draw.remove_last_military_symbol()

    def removeAllMilitarySymbols(self):
        """Remove all military symbols from the video and map layers."""
        self._draw.remove_all_military_symbols()

    def setSelectedMilitarySymbol(self, symbol_id, unit_name=""):
        """Set the active military symbol type for the next placement click."""
        self._draw.set_selected_military_symbol(symbol_id, unit_name)

    def flashMilitarySymbolPlacementHint(self, pulses=8):
        """Flash a visual hint prompting the user to click and place a symbol."""
        self._draw.flash_military_symbol_placement_hint(pulses)

    def flashToolPlacementHint(self, text, pulses=8):
        """Show a flashing banner hint for the active drawing/measurement tool."""
        self._draw.flash_tool_placement_hint(text, pulses)

    def _tickToolHintFlash(self):
        self._draw.tick_tool_hint_flash()

    def removeLastPoint(self):
        """Remove All Point Drawer Objects"""
        self._draw.remove_last_point()

    def removeAllPoint(self):
        """Remove All Point Drawer Objects"""
        self._draw.remove_all_point()

    def removeAllPolygon(self):
        """Remove All Polygon Drawer Objects"""
        self._draw.remove_all_polygon()

    def removeLastPolygon(self):
        """Remove Last Polygon Drawer Objects"""
        self._draw.remove_last_polygon()

    def keyPressEvent(self, event):
        """Exit fullscreen
        :type event: QKeyEvent
        :param event:
        :return:
        """
        if event.key() == Qt.Key.Key_Escape and self.isFullScreen():
            self.setFullScreen(False)
            event.accept()
        elif event.key() == Qt.Key.Key_Enter and event.modifiers() & Qt.Key.Key_Alt:
            self.setFullScreen(not self.isFullScreen())
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
         Mouse double click event
        :type event: QMouseEvent
        :param event:
        :return:
        """
        if GetImageHeight() == 0:
            return

        _mp = qmouse_pos(event)
        if not vut.IsPointOnScreen(_mp.x(), _mp.y(), self.surface):
            return

        if self._draw.handle_double_click():
            return

        self.UpdateSurface()
        self.setFullScreen(not self.isFullScreen())
        self._scheduleVideoDisplayRefresh()
        event.accept()

    def _scheduleVideoDisplayRefresh(self):
        self._display_refresh_timer.start(0)

    def _refreshVideoDisplay(self):
        """Recompute video layout and repaint the cached frame (e.g. while paused)."""
        self.surface.ensureDisplayReady()
        self._magnifier_cache = {"key": None, "pixmap": None}
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._scheduleVideoDisplayRefresh()

    def videoSink(self):
        """Return the QVideoSink (Qt6 video output)"""
        return self._videoSink

    def setFullScreen(self, fullscreen):
        """Toggle fullscreen mode for the video widget."""
        if fullscreen:
            self.showFullScreen()
        else:
            self.showNormal()
        self._scheduleVideoDisplayRefresh()

    def _setFilter(self, attr, value):
        setattr(self._filterSatate, attr, value)
        if value and attr in (
            "motionDetectionFilter",
            "backgroundSubtractionFilter",
            "buildingDetectionFilter",
            "roadSegmentationFilter",
            "vehicleSegmentationFilter",
            "personSegmentationFilter",
            "fireDetectionFilter",
            "smokeDetectionFilter",
            "floodDetectionFilter",
        ):
            from QGISFMV.video.filters import reset_temporal_filter_state

            reset_temporal_filter_state()
        self.surface.refreshFilters()

    def UpdateSurface(self):
        """Repaint the video widget (overlays + current frame)."""
        self.update()

    def refreshDisplay(self):
        """Refresh layout and repaint the cached frame (safe while paused)."""
        self._refreshVideoDisplay()

    def sizeHint(self):
        """This property holds the recommended size for the widget"""
        return self.surface.surfaceFormat().sizeHint()

    def currentFrame(self):
        """Return current frame QImage"""
        return self.surface.image

    def trackingFrame(self):
        """Return the best available frame for OpenCV tracking."""
        img = self.surface.image
        if img is None or img.isNull():
            img = self.surface._rawImage
        return img

    def _isPlaybackActive(self):
        player = getattr(self.parent, "player", None)
        if player is not None and hasattr(player, "playbackState"):
            return player.playbackState() == PlayingState
        return getattr(self.parent, "playerState", StoppedState) == PlayingState

    def SetInvertColor(self, value):
        """Enable or disable the color-inversion filter."""
        self._setFilter("invertColorFilter", value)

    def SetObjectTracking(self, value):
        """Set Object Tracking
        @type value: bool
        @param value:
        @return:
        """
        self._tracking.set_enabled(value)

    def clearObjectTrack(self):
        """Clear live rubberband + persistent Object Track layers."""
        self._tracking.clear()

    def _stop_object_tracking(self, lost=False):
        self._tracking.stop(lost=lost)

    def _update_object_tracking(self):
        """Run OpenCV tracker off paintEvent (keeps QGIS UI responsive)."""
        self._tracking.update()

    def SetMeasureDistance(self, value):
        """Set measure Distance
        @type value: bool
        @param value:
        @return:
        """
        self._draw.set_measure_distance(value)

    def SetMeasureArea(self, value):
        """Set measure Area
        @type value: bool
        @param value:
        @return:
        """
        self._draw.set_measure_area(value)

    def SetHandDraw(self, value):
        """Set Hand Draw
        @type value: bool
        @param value:
        @return:
        """
        self._draw.set_hand_draw(value)

    def SetCensure(self, value):
        """Set Censure Video Parts
        @type value: bool
        @param value:
        @return:
        """
        self._draw.set_censure(value)

    def SetMGRS(self, value):
        """Set MGRS Cursor Coordinates
        @type value: bool
        @param value:
        @return:
        """
        self._MGRS = value
        if self.lastMouseX != -1 and self.lastMouseY != -1:
            self.mouseMoveEvent(None, useLast=True)

    def SetGray(self, value):
        """Enable or disable the grayscale filter."""
        self._setFilter("grayColorFilter", value)

    def SetMirrorH(self, value):
        """Enable or disable horizontal mirror."""
        self._setFilter("MirroredHFilter", value)

    def SetEdgeDetection(self, value):
        """Enable or disable the edge-detection filter."""
        self._setFilter("edgeDetectionFilter", value)

    def SetAutoContrastFilter(self, value):
        """Enable or disable the auto-contrast (CLAHE) filter."""
        self._setFilter("contrastFilter", value)

    def SetMonoFilter(self, value):
        """Enable or disable the monochrome filter."""
        self._setFilter("monoFilter", value)

    def SetBrightnessContrastFilter(self, value):
        """Enable or disable the brightness/contrast filter."""
        self._setFilter("brightnessContrastFilter", value)

    def SetBrightness(self, value):
        """Set the brightness adjustment level."""
        self._filterSatate.brightness = value

    def SetContrastLevel(self, value):
        """Set the contrast adjustment level."""
        self._filterSatate.contrastLevel = value

    def RestoreFilters(self):
        """Remove and restore all video filters"""
        from QGISFMV.video.filters import reset_temporal_filter_state

        self._filterSatate.clear()
        reset_temporal_filter_state()
        self.surface.refreshFilters()

    def RestoreDrawer(self):
        """Remove and restore all Drawer Options"""
        self._draw.restore_drawer()

    def RemoveCanvasRubberbands(self):
        """Remove Canvas Rubberbands"""
        self.rubbers.reset_all()

    def RemoveVideoDrawings(self):
        """Remove Video Drawings"""
        self._draw.remove_video_drawings()

    def paintEvent(self, event):
        """
        @type event: QPaintEvent
        @param event:
        @return:
        """
        VideoPaintPipeline.paint(self, event)

    def resizeEvent(self, _):
        """
        @type _: QMouseEvent
        @param _:
        @return:
        """
        self.surface.updateVideoRect()
        self._magnifier_cache = {"key": None, "pixmap": None}
        self._scheduleVideoDisplayRefresh()
        mini_map = getattr(self, "_miniMapRef", None)
        if mini_map is not None and mini_map._visible:
            mini_map.reposition()

    def AddMoveEventValue(self, values, Longitude, Latitude, Altitude):
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
        self._draw.add_move_event_value(values, Longitude, Latitude, Altitude)

    def refreshCursorRubberBand(self):
        """Re-draw the canvas cursor from the last known video position."""
        self._cursor.refresh()

    def mouseMoveEvent(self, event, useLast=False, force=False):
        """Handle mouse movement: update coordinates, cursor, rubberbands, and draw tools."""
        if event is not None:
            _mp = qmouse_pos(event)
            self.lastMouseX = _mp.x()
            self.lastMouseY = _mp.y()
        elif useLast:
            if self.lastMouseX == -1 or self.lastMouseY == -1:
                return
            event = QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(self.lastMouseX, self.lastMouseY),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        else:
            return

        if self._interaction.magnifier and event is not None:
            self.dragPos = qmouse_pos(event)
            self.UpdateSurface()

        _mp = qmouse_pos(event)
        if not vut.IsPointOnScreen(_mp.x(), _mp.y(), self.surface):
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self._cursor.clear_rubberband()
            return

        self._cursorOnVideo = True

        if self._interaction.any_draw_active():
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        if GetGCPGeoTransform() is not None:
            Longitude, Latitude, Altitude = vut.GetPointCommonCoords(
                event, self.surface
            )
            self._cursor.update_georeferenced(
                Longitude, Latitude, Altitude, event, force
            )
        else:
            self._cursor.clear_coords_label()

        self._draw.update_drag_rubberbands(event)

    def timerEvent(self, _):
        """Time Event (Magnifier method)"""
        if not self._interaction.magnifier:
            self.activateMagnifier()

    def mousePressEvent(self, event):
        """Handle left-click: dispatch to the active draw/measure tool."""
        if GetImageHeight() == 0:
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._interaction.magnifier:
            self.dragPos = qmouse_pos(event)
            self.tapTimer.stop()
            self.tapTimer.start(10, self)

        _mp = qmouse_pos(event)
        if not vut.IsPointOnScreen(_mp.x(), _mp.y(), self.surface):
            return

        has_gt = GetGCPGeoTransform() is not None
        if has_gt:
            Longitude, Latitude, Altitude = vut.GetPointCommonCoords(
                event, self.surface
            )
            self._draw.handle_click(Longitude, Latitude, Altitude)

        self.origin = qmouse_pos(event)
        self._draw.start_drag_rubberbands()
        self.update()

    def activateMagnifier(self):
        """Activate Magnifier Glass"""
        self.tapTimer.stop()
        self.UpdateSurface()

    def SetMagnifier(self, value):
        """Set Magnifier Glass
        @type value: bool
        @param value:
        """
        self._interaction.magnifier = value
        if not value:
            self.dragPos = QPoint()
            self.tapTimer.stop()
        self.update()

    def SetStamp(self, value):
        """Set Stamp
        @type value: bool
        @param value:
        """
        self._interaction.stamp = value
        self.update()

    def SetMilitarySymbolDrawer(self, value):
        """Enable or disable the military symbol placement mode."""
        self._draw.set_military_symbol_drawer(value)

    def SetPointDrawer(self, value):
        """Set Point Drawer
        @type value: bool
        """
        self._draw.set_point_drawer(value)

    def SetLineDrawer(self, value):
        """Set Line Drawer
        @type value: bool
        """
        self._draw.set_line_drawer(value)

    def SetPolygonDrawer(self, value):
        """Set Polygon Drawer
        @type value: bool
        """
        self._draw.set_polygon_drawer(value)

    def mouseReleaseEvent(self, _):
        """
        @type event: QMouseEvent
        @param event:
        @return:
        """
        # Censure Draw Interaction
        if self._interaction.censure:
            self._draw.finish_censure_selection()

        # Object Tracking Interaction
        if self._interaction.objectTracking:
            self._tracking.start_tracking_from_selection()

    def enterEvent(self, event):
        """Keep the canvas cursor when the pointer re-enters the video widget."""
        super().enterEvent(event)
        pos = self.mapFromGlobal(QCursor.pos())
        self.lastMouseX = pos.x()
        self.lastMouseY = pos.y()
        self.mouseMoveEvent(None, useLast=True, force=True)

    def leaveEvent(self, _):
        """
        @type _: QEvent
        @param _:
        @return:
        """
        # Remove coordinates label value
        self.parent.lb_cursor_coord.setText("")
        # Change cursor
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        # Reset mouse rubberband
        self._cursor.clear_rubberband()
