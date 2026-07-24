# -*- coding: utf-8 -*-
"""Object tracking controller extracted from VideoWidget (QgsVideo.py).

Owns the OpenCV tracker lifecycle (init/update/stop) and the rubberband +
persistent-layer publishing that goes along with it. Tracking *state*
(``_isinit``, ``_last_track_bbox``, ``_track_id``, ``_track_lock_state``, ...)
stays on the widget itself since it is read directly by the paint pipeline;
this controller only owns the logic that mutates it.
"""
from qgis.PyQt.QtCore import Qt, QPoint, QRect, QSize, QCoreApplication
from qgis.core import Qgis as QGis, QgsPointXY, QgsWkbTypes

from QGISFMV.utils.core.QgsImageMat import convertQImageToMat
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.vision.QgsObjectTracker import create_object_tracker
from QGISFMV.utils.layers.QgsFmvLayers import (
    BeginObjectTrack,
    UpdateObjectTrack,
    ClearObjectTracks,
)
from QGISFMV.video.playback.QgsVideoState import TrackLockState
from QGISFMV.video.playback.QgsVideoUtils import VideoUtils as vut

try:
    from cv2 import resize, cvtColor, COLOR_RGB2BGR
except ImportError:
    resize = None
    cvtColor = None
    COLOR_RGB2BGR = None


class ObjectTrackingController:
    """Runs OpenCV-based object tracking on behalf of a VideoWidget."""

    def __init__(self, widget):
        self._widget = widget

    def set_enabled(self, value):
        """Set Object Tracking
        @type value: bool
        @param value:
        @return:
        """
        w = self._widget
        w._interaction.objectTracking = value
        if not value:
            self.stop(lost=False)
        w.update()

    def clear(self):
        """Clear live rubberband + persistent Object Track layers."""
        w = self._widget
        w.rubbers.track_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)
        try:
            ClearObjectTracks(w._map_group())
        except Exception as exc:
            log.debug("ClearObjectTracks failed: %s", exc)
        w.update()

    def stop(self, lost=False):
        """Stop the active tracker and reset tracking state."""
        w = self._widget
        w._track_timer.stop()
        was_init = w._isinit
        w._isinit = False
        w._last_track_bbox = None
        w._track_misses = 0
        w._track_lock_state = TrackLockState.LOST if lost else TrackLockState.IDLE
        try:
            if hasattr(w, "tracker"):
                del w.tracker
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

    def publish_sample(self, bbox):
        """Update rubberband + persistent layers for the bbox center."""
        w = self._widget
        offset = w.surface.videoRect()
        xc = bbox[0] + (bbox[2] / 2)
        yc = bbox[1] + (bbox[3] / 2)
        p = QPoint(int(xc + offset.x()), int(yc + offset.y()))
        Longitude, Latitude, Altitude = vut.GetPointCommonCoords(p, w.surface)
        if Longitude is None or Latitude is None:
            return
        w.rubbers.track_canvas.addPoint(QgsPointXY(Longitude, Latitude))
        try:
            w._sync_draw_group()
            UpdateObjectTrack(
                Longitude,
                Latitude,
                Altitude,
                w._track_id,
                w._tracker_backend or "",
            )
        except Exception as exc:
            log.debug("UpdateObjectTrack failed: %s", exc)

    def update(self):
        """Run OpenCV tracker off paintEvent (keeps QGIS UI responsive)."""
        w = self._widget
        if not w._interaction.objectTracking or not w._isinit:
            return
        if not w._isPlaybackActive():
            return
        result = self.tracking_mat(w.trackingFrame())
        if result is None:
            return
        try:
            ok, bbox = w.tracker.update(result)
        except Exception as exc:
            log.debug("Object tracker update failed: %s", exc)
            ok = False
            bbox = None
        if ok and bbox is not None:
            w._track_misses = 0
            w._track_lock_state = TrackLockState.LOCKED
            w._last_track_bbox = bbox
            self.publish_sample(bbox)
            w.update()
            return

        w._track_misses += 1
        if w._track_misses >= 3:
            w._track_lock_state = TrackLockState.WEAK
            w.update()
        if w._track_misses >= w._track_max_misses:
            self.stop(lost=True)
            w.update()

    def tracking_mat(self, qimg):
        """Return the given QImage scaled to the video rect, as an OpenCV mat."""
        w = self._widget
        if qimg is None or qimg.isNull():
            return None
        offset = w.surface.videoRect()
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

    def start_tracking_from_selection(self):
        """Initialize an OpenCV tracker from the drawn tracking-video rubberband.

        Called from ``mouseReleaseEvent`` while object tracking is active.
        """
        w = self._widget
        geom = w.rubbers.tracking_video.geometry()
        offset = w.surface.videoRect()
        rect = QRect(
            geom.x() - offset.x(),
            geom.y() - offset.y(),
            geom.width(),
            geom.height(),
        ).normalized()
        w.rubbers.tracking_video.hide()
        w.rubbers.track_canvas.reset(QgsWkbTypes.GeometryType.LineGeometry)

        if rect.width() < 2 or rect.height() < 2:
            return

        result = self.tracking_mat(w.trackingFrame())
        if result is None:
            return

        w.tracker, w._tracker_backend = create_object_tracker()
        bbox = (int(rect.x()), int(rect.y()), int(rect.width()), int(rect.height()))
        try:
            ok = w.tracker.init(result, bbox)
        except Exception as exc:
            log.debug("Object tracker init failed: %s", exc)
            return
        if ok is False:
            w._isinit = False
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

        w._track_id += 1
        w._track_misses = 0
        w._track_lock_state = TrackLockState.LOCKED
        w._isinit = True
        w._last_track_bbox = bbox
        try:
            w._sync_draw_group()
            BeginObjectTrack(w._track_id, w._tracker_backend or "")
        except Exception as exc:
            log.debug("BeginObjectTrack failed: %s", exc)
        self.publish_sample(bbox)
        w._track_timer.start()
        w.update()
        if not w._isPlaybackActive() and hasattr(w.parent, "ensurePlaying"):
            w.parent.ensurePlaying()
