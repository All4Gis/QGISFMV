# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import (
    Qt,
    QRect,
    QPoint,
    QPointF,
    QEvent,
    QBasicTimer,
    QSize,
    QTimer,
    QCoreApplication,
)
from qgis.PyQt.QtGui import (
    QPalette,
    QColor,
    QBrush,
    QCursor,
    QMouseEvent,
)
from qgis.PyQt.QtWidgets import QRubberBand
from qgis.core import (
    Qgis as QGis,
    QgsProject,
    QgsPointXY,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
)
from qgis.gui import QgsRubberBand
from qgis.utils import iface

from QGISFMV.utils.media.QgsFmvMultimedia import StoppedState, PlayingState
from qgis.PyQt.QtMultimedia import QVideoSink
from qgis.PyQt.QtWidgets import QWidget as VideoWidgetBase
from QGISFMV.video.playback.QgsVideoSurface import VideoSinkSurface

# Cached project instance — avoids QgsProject.instance() in hot paths.
_project_instance = None


def _get_project():
    global _project_instance
    if _project_instance is None:
        _project_instance = QgsProject.instance()
    return _project_instance

import mgrs
from QGISFMV.video.playback.QgsVideoPaintPipeline import VideoPaintPipeline
from QGISFMV.utils.layers.QgsFmvLayers import (
    AddDrawPointOnMap,
    AddDrawLineOnMap,
    AddDrawPolygonOnMap,
    AddDrawMilitarySymbolOnMap,
    BeginObjectTrack,
    UpdateObjectTrack,
    ClearObjectTracks,
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
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.video.playback.QgsVideoState import MOUSE_MOVE_EVENT
from QGISFMV.utils.core.QgsFmvUtils import (
    convertQImageToMat,
    GetGCPGeoTransform,
    hasElevationModel,
    GetImageHeight,
    qmouse_pos,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.vision.QgsObjectTracker import create_object_tracker
from QGISFMV.video.playback.QgsVideoUtils import VideoUtils as vut
from QGISFMV.video.playback.QgsVideoState import InteractionState, FilterState
from enum import Enum


class TrackLockState(Enum):
    """Object tracking lock states."""
    IDLE = "idle"
    LOCKED = "locked"
    WEAK = "weak"
    LOST = "lost"


try:
    from cv2 import resize, cvtColor, COLOR_RGB2BGR
except ImportError:
    resize = None
    cvtColor = None
    COLOR_RGB2BGR = None


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


class VideoWidget(VideoWidgetBase):

    def __init__(self, parent=None):
        """Constructor"""
        super().__init__(parent)
        self._videoSink = QVideoSink(self)
        self.surface = VideoSinkSurface(self, self._videoSink)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

        self.rubbers = RubberBandManager(self)

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
        self.rubbers.measure_dist_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)
        # Always refresh the persistent measure layer (keeps finished chains).
        try:
            self._sync_draw_group()
            SyncMeasureDistanceOnMap(self.drawMeasureDistance, self._map_group())
        except Exception as exc:
            log.debug("SyncMeasureDistanceOnMap failed: %s", exc)
        if not self._interaction.measureDistance:
            return
        for pt in self.drawMeasureDistance:
            if not pt or pt[0] is None:
                continue
            # Rubber band uses geographic lon/lat as canvas points (EPSG:4326 project)
            self.rubbers.measure_dist_canvas.addPoint(QgsPointXY(pt[0], pt[1]))

    def _syncMeasureAreaMap(self):
        """Refresh the rubber band and persistent layer for area measurements."""
        self.rubbers.measure_area_canvas.reset(
            QgsWkbTypes.GeometryType.PolygonGeometry
        )
        try:
            self._sync_draw_group()
            SyncMeasureAreaOnMap(self.drawMeasureArea, self._map_group())
        except Exception as exc:
            log.debug("SyncMeasureAreaOnMap failed: %s", exc)
        if not self._interaction.measureArea:
            return
        for pt in self.drawMeasureArea:
            if not pt or pt[0] is None:
                continue
            self.rubbers.measure_area_canvas.addPoint(QgsPointXY(pt[0], pt[1]))

    def removeLastLine(self):
        """Remove Last Line Objects"""
        if self.drawLines:
            # Remove trailing mouseMoveEvent entry if present
            if self.drawLines[-1][-1] == MOUSE_MOVE_EVENT:
                self.drawLines.pop()
            # Find the last separator [None, None, None] and delete everything after it
            sep_idx = -1
            for i in range(len(self.drawLines) - 1, -1, -1):
                if self.drawLines[i][0] is None:
                    sep_idx = i
                    break
            if sep_idx >= 0:
                del self.drawLines[sep_idx:]
            else:
                self.drawLines.clear()
            self.UpdateSurface()
            AddDrawLineOnMap(self.drawLines)
        return

    def removeLastSegmentLine(self):
        """Remove Last Segment Line Objects"""
        if not self.drawLines:
            return
        # Remove trailing mouseMoveEvent entry if present
        if self.drawLines[-1][-1] == MOUSE_MOVE_EVENT:
            self.drawLines.pop()
        if not self.drawLines:
            return
        # Remove the last point (current segment endpoint)
        self.drawLines.pop()
        # If we hit a separator, remove it too
        if self.drawLines and self.drawLines[-1][0] is None:
            self.drawLines.pop()
        self.UpdateSurface()
        AddDrawLineOnMap(self.drawLines)
        return

    def removeAllLines(self):
        """Resets Line List"""
        if self.drawLines:
            self.drawLines = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawLineOnMap(self._map_group())

    def ResetDrawMeasureDistance(self):
        """Resets Measure Distance List"""
        self.drawMeasureDistance = []
        self._syncMeasureDistanceMap()

    def ResetDrawMeasureArea(self):
        """Resets Measure Area List"""
        self.drawMeasureArea = []
        self._syncMeasureAreaMap()

    def removeAllCensure(self):
        """Remove All Censure Objects"""
        if self.drawCesure:
            self.drawCesure = []
            self.UpdateSurface()

    def removeLastCensured(self):
        """Remove Last Censure Objects"""
        if self.drawCesure:
            del self.drawCesure[-1]
            self.UpdateSurface()

    def removeLastMilitarySymbol(self):
        """Remove the last military symbol from the video and map layers."""
        if self.drawMilSymbols:
            del self.drawMilSymbols[-1]
            self.UpdateSurface()
            RemoveLastDrawMilitarySymbolOnMap(self._map_group())
        return

    def removeAllMilitarySymbols(self):
        """Remove all military symbols from the video and map layers."""
        if self.drawMilSymbols:
            self.drawMilSymbols = []
            self.UpdateSurface()
            RemoveAllDrawMilitarySymbolOnMap(self._map_group())
        return

    def setSelectedMilitarySymbol(self, symbol_id, unit_name=""):
        """Set the active military symbol type for the next placement click."""
        self._selectedMilSymbolId = symbol_id or "f_inf"
        self._selectedMilSymbolLabel = unit_name or ""

    def flashMilitarySymbolPlacementHint(self, pulses=8):
        """Flash a visual hint prompting the user to click and place a symbol."""
        self._toolHintFlash = max(self._toolHintFlash, pulses)
        self._toolHintText = self.tr("Click here on the video to place the military symbol")
        if not self._toolHintTimer.isActive():
            self._toolHintTimer.start()
        self.update()

    def flashToolPlacementHint(self, text, pulses=8):
        """Show a flashing banner hint for the active drawing/measurement tool."""
        self._toolHintFlash = max(self._toolHintFlash, pulses)
        self._toolHintText = text
        if not self._toolHintTimer.isActive():
            self._toolHintTimer.start()
        self.update()

    def _tickToolHintFlash(self):
        if self._toolHintFlash <= 0:
            self._toolHintTimer.stop()
            return
        self._toolHintFlash -= 1
        self.update()

    def _clearToolHint(self):
        """Reset tool-placement hint state and stop the flash timer."""
        self._toolHintFlash = 0
        self._toolHintText = ""
        self._toolHintTimer.stop()

    def removeLastPoint(self):
        """Remove All Point Drawer Objects"""
        if self.drawPtPos:
            del self.drawPtPos[-1]
            self.UpdateSurface()
            RemoveLastDrawPointOnMap(self._map_group())
        return

    def removeAllPoint(self):
        """Remove All Point Drawer Objects"""
        if self.drawPtPos:
            self.drawPtPos = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPointOnMap(self._map_group())
        return

    def removeAllPolygon(self):
        """Remove All Polygon Drawer Objects"""
        if self.drawPolygon:
            self.drawPolygon = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPolygonOnMap(self._map_group())

    def removeLastPolygon(self):
        """Remove Last Polygon Drawer Objects"""
        if self.drawPolygon:
            # Remove trailing mouseMoveEvent entry if present
            if self.drawPolygon[-1][-1] == MOUSE_MOVE_EVENT:
                self.drawPolygon.pop()
            # Find the last separator [None, None, None] and delete everything after it
            sep_idx = -1
            for i in range(len(self.drawPolygon) - 1, -1, -1):
                if self.drawPolygon[i][0] is None:
                    sep_idx = i
                    break
            if sep_idx >= 0:
                del self.drawPolygon[sep_idx:]
            else:
                self.drawPolygon.clear()

            self.UpdateSurface()
            # remove last index layer
            RemoveLastDrawPolygonOnMap(self._map_group())

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

        if GetGCPGeoTransform() is not None and self._interaction.lineDrawer:
            self.drawLines.append([None, None, None])
            return

        if GetGCPGeoTransform() is not None and self._interaction.measureDistance:
            self.drawMeasureDistance.append([None, None, None])
            self.parent.actionMeasureDistance.toggle()
            return

        if GetGCPGeoTransform() is not None and self._interaction.measureArea:
            self.drawMeasureArea.append([None, None, None])
            self.parent.actionMeasureArea.toggle()
            return

        if GetGCPGeoTransform() is not None and self._interaction.polygonDrawer:

            ok = AddDrawPolygonOnMap(self.poly_coordinates)
            # Prevent invalid geometry (Polygon with 2 points)
            if not ok:
                return

            self.drawPolygon.append([None, None, None])

            # Empty RubberBand
            for _ in range(self.rubbers.poly_canvas.numberOfVertices()):
                self.rubbers.poly_canvas.removeLastPoint()
            # Empty List
            self.poly_coordinates = []
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

    def _trackingMat(self, qimg):
        if qimg is None or qimg.isNull():
            return None
        offset = self.surface.videoRect()
        if offset.isEmpty():
            return None
        try:
            target = QSize(offset.width(), offset.height())
            if resize is not None:
                frame = convertQImageToMat(qimg)
                if frame.ndim == 3 and cvtColor is not None:
                    frame = cvtColor(frame, COLOR_RGB2BGR)
                return resize(frame, (target.width(), target.height()))
            scaled = qimg.scaled(
                target,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            return convertQImageToMat(scaled)
        except Exception as exc:
            log.debug("getCurrentFrameAsMat failed: %s", exc)
            return None

    def SetInvertColor(self, value):
        """Enable or disable the color-inversion filter."""
        self._setFilter("invertColorFilter", value)

    def SetObjectTracking(self, value):
        """Set Object Tracking
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.objectTracking = value
        if not value:
            self._stop_object_tracking(lost=False)
        self.update()

    def clearObjectTrack(self):
        """Clear live rubberband + persistent Object Track layers."""
        self.rubbers.track_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)
        try:
            ClearObjectTracks(self._map_group())
        except Exception as exc:
            log.debug("ClearObjectTracks failed: %s", exc)
        self.update()

    def _stop_object_tracking(self, lost=False):
        self._track_timer.stop()
        was_init = self._isinit
        self._isinit = False
        self._last_track_bbox = None
        self._track_misses = 0
        self._track_lock_state = TrackLockState.LOST if lost else TrackLockState.IDLE
        try:
            if hasattr(self, "tracker"):
                del self.tracker
        except Exception as exc:
            log.debug("Object tracker cleanup failed: %s", exc)
        if lost and was_init:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "Object Tracking"),
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Track lost — redraw a region of interest on the video.",
                ),
                level=QGis.MessageLevel.Warning,
                duration=4,
            )

    def _publish_track_sample(self, bbox):
        """Update rubberband + persistent layers for the bbox center."""
        offset = self.surface.videoRect()
        xc = bbox[0] + (bbox[2] / 2)
        yc = bbox[1] + (bbox[3] / 2)
        p = QPoint(int(xc + offset.x()), int(yc + offset.y()))
        Longitude, Latitude, Altitude = vut.GetPointCommonCoords(p, self.surface)
        if Longitude is None or Latitude is None:
            return
        self.rubbers.track_canvas.addPoint(QgsPointXY(Longitude, Latitude))
        try:
            self._sync_draw_group()
            UpdateObjectTrack(
                Longitude,
                Latitude,
                Altitude,
                self._track_id,
                self._tracker_backend or "",
            )
        except Exception as exc:
            log.debug("UpdateObjectTrack failed: %s", exc)

    def _update_object_tracking(self):
        """Run OpenCV tracker off paintEvent (keeps QGIS UI responsive)."""
        if not self._interaction.objectTracking or not self._isinit:
            return
        if not self._isPlaybackActive():
            return
        result = self._trackingMat(self.trackingFrame())
        if result is None:
            return
        try:
            ok, bbox = self.tracker.update(result)
        except Exception as exc:
            log.debug("Object tracker update failed: %s", exc)
            ok = False
            bbox = None
        if ok and bbox is not None:
            self._track_misses = 0
            self._track_lock_state = TrackLockState.LOCKED
            self._last_track_bbox = bbox
            self._publish_track_sample(bbox)
            self.update()
            return

        self._track_misses += 1
        if self._track_misses >= 3:
            self._track_lock_state = TrackLockState.WEAK
            self.update()
        if self._track_misses >= self._track_max_misses:
            self._stop_object_tracking(lost=True)
            self.update()

    def SetMeasureDistance(self, value):
        """Set measure Distance
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.measureDistance = value
        if value:
            self.flashToolPlacementHint(self.tr("Click on the video to measure distance, double-click to finish"))
        else:
            self._syncMeasureDistanceMap()
            self._clearToolHint()
        self.update()

    def SetMeasureArea(self, value):
        """Set measure Area
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.measureArea = value
        if value:
            self.flashToolPlacementHint(self.tr("Click on the video to measure area, double-click to finish"))
        else:
            self._syncMeasureAreaMap()
            self._clearToolHint()
        self.update()

    def SetHandDraw(self, value):
        """Set Hand Draw
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.HandDraw = value

    def SetCensure(self, value):
        """Set Censure Video Parts
        @type value: bool
        @param value:
        @return:
        """
        self._interaction.censure = value
        self.update()

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
        self._interaction.clear()
        # Magnifier Glass
        self.dragPos = QPoint()
        self.tapTimer.stop()

    def RemoveCanvasRubberbands(self):
        """Remove Canvas Rubberbands"""
        self.rubbers.reset_all()

    def RemoveVideoDrawings(self):
        """Remove Video Drawings"""
        (
            self.poly_coordinates,
            self.drawPtPos,
            self.drawMilSymbols,
            self.drawLines,
            self.drawMeasureDistance,
            self.drawMeasureArea,
            self.drawPolygon,
        ) = ([], [], [], [], [], [], [])

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
        values[:] = [pt for pt in values if pt[-1] != MOUSE_MOVE_EVENT]
        values.append([Longitude, Latitude, Altitude, MOUSE_MOVE_EVENT])

        self.UpdateSurface()

    def _clearCursorRubberBand(self):
        """Hide the map cursor marker."""
        self._cursorOnVideo = False
        self._lastCursorMapPoint = None
        self.rubbers.cursor_canvas.reset(QgsWkbTypes.GeometryType.PointGeometry)

    def _updateCursorRubberBand(self, mapPt, force=False):
        """Move the canvas cursor marker without remove/add flicker."""
        if (
            not force
            and self._lastCursorMapPoint is not None
            and abs(self._lastCursorMapPoint.x() - mapPt.x()) < 1e-12
            and abs(self._lastCursorMapPoint.y() - mapPt.y()) < 1e-12
        ):
            return

        if self.rubbers.cursor_canvas.numberOfVertices() > 0:
            self.rubbers.cursor_canvas.movePoint(mapPt, 0)
        else:
            self.rubbers.cursor_canvas.addPoint(mapPt)
        self._lastCursorMapPoint = QgsPointXY(mapPt)

    def refreshCursorRubberBand(self):
        """Re-draw the canvas cursor from the last known video position."""
        if not self._cursorOnVideo:
            return
        if self.lastMouseX == -1 or self.lastMouseY == -1:
            return
        self.mouseMoveEvent(None, useLast=True, force=True)

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
            self._clearCursorRubberBand()
            return

        self._cursorOnVideo = True

        if self._interaction.any_draw_active():
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        if GetGCPGeoTransform() is not None:
            Longitude, Latitude, Altitude = vut.GetPointCommonCoords(event, self.surface)
            self._update_georeferenced_cursor(
                Longitude, Latitude, Altitude, event, force
            )
        else:
            self._clear_cursor_coords_label()

        self._update_drag_rubberbands(event)

    def _update_georeferenced_cursor(self, Longitude, Latitude, Altitude, event, force):
        """Update cursor position on the map canvas when georeferencing is active."""
        canvas = self._map_canvas()
        if canvas is None:
            return
        tr = QgsCoordinateTransform(
            QgsCoordinateReferenceSystem("EPSG:4326"),
            canvas.mapSettings().destinationCrs(),
            _get_project().transformContext(),
        )
        mapPt = tr.transform(QgsPointXY(Longitude, Latitude))
        self._updateCursorRubberBand(mapPt, force=force)

        if self._interaction.militarySymbolDrawer:
            self._milSymbolPreview = [
                Longitude, Latitude, Altitude,
                self._selectedMilSymbolId, self._selectedMilSymbolLabel,
            ]
            self.update()

        self._update_cursor_coords_label(Longitude, Latitude, Altitude)

        if self._interaction.polygonDrawer:
            self.AddMoveEventValue(self.drawPolygon, Longitude, Latitude, Altitude)
        if self._interaction.lineDrawer:
            self.AddMoveEventValue(self.drawLines, Longitude, Latitude, Altitude)
        if self._interaction.measureDistance and self.drawMeasureDistance:
            self.AddMoveEventValue(self.drawMeasureDistance, Longitude, Latitude, Altitude)
            self._syncMeasureDistanceMap()
        if self._interaction.measureArea and self.drawMeasureArea:
            self.AddMoveEventValue(self.drawMeasureArea, Longitude, Latitude, Altitude)
            self._syncMeasureAreaMap()

    def _format_mgrs_label(self, Latitude, Longitude):
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

    def _format_geo_label(self, Longitude, Latitude, Altitude):
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

    def _update_cursor_coords_label(self, Longitude, Latitude, Altitude):
        """Set the cursor coordinate label in the player status bar."""
        if self._MGRS:
            txt = self._format_mgrs_label(Latitude, Longitude)
        else:
            txt = self._format_geo_label(Longitude, Latitude, Altitude)
        self.parent.lb_cursor_coord.setText(txt)

    def _clear_cursor_coords_label(self):
        """Clear the cursor coordinate label when no georeferencing is available."""
        self.parent.lb_cursor_coord.setText(
            "<span style='font-size:10pt; font-weight:bold;'>Lon :</span>"
            "<span style='font-size:9pt; font-weight:normal;'>-</span>"
            "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>"
            "<span style='font-size:9pt; font-weight:normal;'>-</span>"
            "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>"
            "<span style='font-size:9pt; font-weight:normal;'>-</span>"
        )

    def _update_drag_rubberbands(self, event):
        """Update object tracking and censure rubberbands during drag."""
        mp = qmouse_pos(event)
        if not self.rubbers.tracking_video.isHidden():
            self.rubbers.tracking_video.setGeometry(
                QRect(self.origin, mp).normalized()
            )
        if not self.rubbers.censure_video.isHidden():
            self.rubbers.censure_video.setGeometry(
                QRect(self.origin, mp).normalized()
            )

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
            Longitude, Latitude, Altitude = vut.GetPointCommonCoords(event, self.surface)
            self._handle_draw_click(Longitude, Latitude, Altitude)

        self.origin = qmouse_pos(event)
        self._start_drag_rubberbands()
        self.update()

    def _handle_draw_click(self, Longitude, Latitude, Altitude):
        """Dispatch a click to the active drawing/measurement tool."""
        if self._interaction.pointDrawer:
            self._place_point(Longitude, Latitude, Altitude)
        if self._interaction.militarySymbolDrawer:
            self._place_military_symbol(Longitude, Latitude, Altitude)
        if self._interaction.polygonDrawer:
            self._add_polygon_vertex(Longitude, Latitude, Altitude)
        if self._interaction.lineDrawer:
            self._add_line_vertex(Longitude, Latitude, Altitude)
        if self._interaction.measureDistance:
            self.drawMeasureDistance.append([Longitude, Latitude, Altitude])
            self._syncMeasureDistanceMap()
        if self._interaction.measureArea:
            self.drawMeasureArea.append([Longitude, Latitude, Altitude])
            self._syncMeasureAreaMap()

    def _place_point(self, Longitude, Latitude, Altitude):
        """Place a drawing point on the video and map layer."""
        pointIndex = len(self.drawPtPos) + 1
        AddDrawPointOnMap(pointIndex, Longitude, Latitude, Altitude)
        self.drawPtPos.append([Longitude, Latitude, Altitude])

    def _place_military_symbol(self, Longitude, Latitude, Altitude):
        """Place a military symbol on the video and map layer."""
        symbol_index = len(self.drawMilSymbols) + 1
        symbol_id = getattr(self, "_selectedMilSymbolId", "f_inf")
        unit_name = getattr(self, "_selectedMilSymbolLabel", "")
        AddDrawMilitarySymbolOnMap(symbol_index, Longitude, Latitude, Altitude,
                                   symbol_id, unit_name)
        self.drawMilSymbols.append([Longitude, Latitude, Altitude, symbol_id, unit_name])
        player = getattr(self, "_player", None) or getattr(self, "parent", None)
        if player is not None and hasattr(player, "_refreshMilSymbolPlacedCount"):
            player._refreshMilSymbolPlacedCount()

    def _add_polygon_vertex(self, Longitude, Latitude, Altitude):
        """Add a vertex to the polygon being drawn."""
        self.rubbers.poly_canvas.addPoint(QgsPointXY(Longitude, Latitude))
        self.poly_coordinates.extend(QgsPointXY(Longitude, Latitude))
        self.drawPolygon.append([Longitude, Latitude, Altitude])

    def _add_line_vertex(self, Longitude, Latitude, Altitude):
        """Add a vertex to the line being drawn."""
        self.drawLines.append([Longitude, Latitude, Altitude])
        AddDrawLineOnMap(self.drawLines)

    def _start_drag_rubberbands(self):
        """Show rubberbands for drag-based tools (object tracking, censure)."""
        if self._interaction.objectTracking:
            self.rubbers.tracking_video.setGeometry(QRect(self.origin, QSize()))
            self.rubbers.tracking_video.show()
        if self._interaction.censure:
            self.rubbers.censure_video.setGeometry(QRect(self.origin, QSize()))
            self.rubbers.censure_video.show()

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
        self._interaction.militarySymbolDrawer = value
        if not value:
            self._milSymbolPreview = None
            self._clearToolHint()
        else:
            self.flashMilitarySymbolPlacementHint()
        self.update()

    def SetPointDrawer(self, value):
        """Set Point Drawer
        @type value: bool
        @param value:
        """
        self._interaction.pointDrawer = value
        if value:
            self.flashToolPlacementHint(self.tr("Click on the video to place a point"))
        else:
            self._clearToolHint()
        self.update()

    def SetLineDrawer(self, value):
        """Set Line Drawer
        @type value: bool
        @param value:
        """
        self._interaction.lineDrawer = value
        if value:
            self.flashToolPlacementHint(self.tr("Double-click on the video to draw lines"))
        else:
            self._clearToolHint()
        self.update()

    def SetPolygonDrawer(self, value):
        """Set Polygon Drawer
        @type value: bool
        @param value:
        """
        self._interaction.polygonDrawer = value
        if value:
            self.flashToolPlacementHint(self.tr("Click on the video to draw a polygon, double-click to finish"))
        else:
            self._clearToolHint()
        self.update()

    def mouseReleaseEvent(self, _):
        """
        @type event: QMouseEvent
        @param event:
        @return:
        """
        # Censure Draw Interaction
        if self._interaction.censure:
            geom = self.rubbers.censure_video.geometry()
            self.rubbers.censure_video.hide()
            self.drawCesure.append([geom])
            self.update()

        # Object Tracking Interaction
        if self._interaction.objectTracking:
            geom = self.rubbers.tracking_video.geometry()
            offset = self.surface.videoRect()
            rect = QRect(
                geom.x() - offset.x(),
                geom.y() - offset.y(),
                geom.width(),
                geom.height(),
            ).normalized()
            self.rubbers.tracking_video.hide()
            self.rubbers.track_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)

            if rect.width() < 2 or rect.height() < 2:
                return

            result = self._trackingMat(self.trackingFrame())
            if result is None:
                return

            self.tracker, self._tracker_backend = create_object_tracker()
            bbox = (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
            try:
                ok = self.tracker.init(result, bbox)
            except Exception as exc:
                log.debug("Object tracker init failed: %s", exc)
                return
            if ok is False:
                self._isinit = False
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate("QgsFmvPlayer", "Object Tracking"),
                    QCoreApplication.translate(
                        "QgsFmvPlayer",
                        "Could not initialize tracker on that region.",
                    ),
                    level=QGis.MessageLevel.Warning,
                    duration=3,
                )
                return

            self._track_id += 1
            self._track_misses = 0
            self._track_lock_state = TrackLockState.LOCKED
            self._isinit = True
            self._last_track_bbox = bbox
            try:
                self._sync_draw_group()
                BeginObjectTrack(self._track_id, self._tracker_backend or "")
            except Exception as exc:
                log.debug("BeginObjectTrack failed: %s", exc)
            self._publish_track_sample(bbox)
            self._track_timer.start()
            self.update()
            if not self._isPlaybackActive() and hasattr(self.parent, "ensurePlaying"):
                self.parent.ensurePlaying()
            return

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
        self._clearCursorRubberBand()
