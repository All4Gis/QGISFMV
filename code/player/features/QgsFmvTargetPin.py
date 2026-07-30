# -*- coding: utf-8 -*-
"""Target Pin / Cue — pin a map point; HUD shows range, bearing, next FOV hit."""

from __future__ import annotations

import time

from QGISFMV.geo.QgsFmvSpatial import metadata_lat_lon, target_cue_state
from QGISFMV.utils.constants import TARGET_PIN_ALERT_COOLDOWN_MS
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class TargetPinController:
    """Pin a ground point; cue range/bearing/FOV and alert when coverage enters."""

    def __init__(self, player):
        self.player = player
        self._pin_lon = None
        self._pin_lat = None
        self._arming = False  # map tool active to place the pin
        self._tool = None
        self._prev_tool = None
        self._rubber = None
        self._was_in_fov = False
        self._last_alert_ms = 0
        self._last_label = ""

    def hasPin(self):
        return self._pin_lon is not None and self._pin_lat is not None

    def pin(self):
        """Return ``(lat, lon)`` or ``None``."""
        if not self.hasPin():
            return None
        return self._pin_lat, self._pin_lon

    def isArming(self):
        return self._arming

    def setArming(self, active):
        """Enable/disable click-to-pin map tool (exclusive vs seek/Time Machine/Lookback)."""
        active = bool(active)
        if active == self._arming:
            return self._arming
        if active:
            self._disarm_map_seek()
            ok = self._install_tool()
            self._arming = ok
            if ok:
                qgsu.showUserAndLogMessage(
                    "",
                    "Target Pin armed — click the map to lock a cue point.",
                    onlyLog=True,
                )
        else:
            self._uninstall_tool()
            self._arming = False
        return self._arming

    def setPin(self, lon, lat):
        """Lock the cue at WGS84 ``(lon, lat)`` and draw a map marker."""
        try:
            lon, lat = float(lon), float(lat)
        except (TypeError, ValueError):
            return False
        self._pin_lon, self._pin_lat = lon, lat
        self._was_in_fov = False
        self._show_marker(lon, lat)
        # Drop arming tool after a successful pin so other map tools can resume.
        if self._arming:
            self.setArming(False)
            action = getattr(self.player, "actionPin_Target", None)
            if action is not None and action.isChecked():
                action.blockSignals(True)
                action.setChecked(False)
                action.blockSignals(False)
        qgsu.showUserAndLogMessage(
            "",
            f"Target pinned @ {lat:.5f}, {lon:.5f}",
            onlyLog=True,
        )
        return True

    def clear(self):
        """Remove pin, marker, and HUD cue."""
        self._pin_lon = self._pin_lat = None
        self._was_in_fov = False
        self._last_label = ""
        self._clear_marker()
        self._push_hud("")
        if self._arming:
            self.setArming(False)

    def jumpToNextFov(self):
        """Seek to the next recorded FOV visit of the pin (after playhead)."""
        if not self.hasPin():
            qgsu.showUserAndLogMessage("", "No target pin set.", onlyLog=True)
            return None
        from QGISFMV.geo.QgsFmvSpatial import next_lookback_after

        seek = getattr(self.player, "mapSeekController", None)
        samples = getattr(getattr(seek, "index", None), "samples", []) or []
        t = float(getattr(self.player, "currentInfo", 0.0) or 0.0)
        nxt = next_lookback_after(self._pin_lon, self._pin_lat, samples, t + 0.05)
        if nxt is None:
            qgsu.showUserAndLogMessage(
                "",
                "No future FOV hit for this pin in the geo/time index.",
                onlyLog=True,
            )
            return None
        if seek is not None and hasattr(seek, "_seek_to"):
            seek._seek_to(nxt[2])
            if hasattr(seek, "_show_ghost"):
                ring = nxt[3] if len(nxt) > 3 else None
                seek._show_ghost(ring, nxt[0], nxt[1])
        qgsu.showUserAndLogMessage(
            "",
            f"Jumped to next FOV @ {float(nxt[2]):.1f}s",
            onlyLog=True,
        )
        return float(nxt[2])

    def updateFromMetadata(self, metadata_dict):
        """Refresh HUD cue; emit FOV-enter alert once when coverage begins."""
        if not self.hasPin():
            return None
        pos = metadata_lat_lon(metadata_dict, prefer_frame_center=True)
        if pos is None:
            pos = metadata_lat_lon(metadata_dict, prefer_frame_center=False)
        if pos is None:
            return None
        from_lat, from_lon = pos
        t = float(getattr(self.player, "currentInfo", 0.0) or 0.0)
        footprint = None
        try:
            from QGISFMV.player.features.QgsFmvGeofence import (
                footprint_ring_from_session,
            )

            footprint = footprint_ring_from_session(
                getattr(self.player, "session", None)
            )
        except Exception as exc:
            log.debug("target pin footprint: %s", exc)
        seek = getattr(self.player, "mapSeekController", None)
        samples = getattr(getattr(seek, "index", None), "samples", []) or []
        state = target_cue_state(
            self._pin_lon,
            self._pin_lat,
            from_lon,
            from_lat,
            t,
            samples=samples,
            footprint_ring=footprint,
        )
        self._last_label = state["label"]
        self._push_hud(state["label"])
        in_fov = bool(state["in_fov"])
        if in_fov and not self._was_in_fov:
            self._on_enter_fov(state)
        self._was_in_fov = in_fov
        return state

    def _on_enter_fov(self, state):
        now = int(time.time() * 1000)
        if now - self._last_alert_ms < int(TARGET_PIN_ALERT_COOLDOWN_MS):
            return
        self._last_alert_ms = now
        msg = f"TARGET CUE: pin entered FOV ({state.get('label', 'TGT')})"
        am = getattr(self.player, "alertManager", None)
        if am is not None and hasattr(am, "alertTriggered"):
            try:
                am.alertTriggered.emit(msg)
                return
            except Exception as exc:
                log.debug("target pin alert emit: %s", exc)
        hud = getattr(self.player, "hudOverlay", None)
        if hud is not None and hasattr(hud, "setAlertBanner"):
            hud.setAlertBanner(msg, ttl_ms=3500)

    def _push_hud(self, label):
        hud = getattr(self.player, "hudOverlay", None)
        if hud is not None and hasattr(hud, "setTargetCue"):
            try:
                hud.setTargetCue(label)
            except Exception as exc:
                log.debug("HUD target cue: %s", exc)

    def _disarm_map_seek(self):
        seek = getattr(self.player, "mapSeekController", None)
        if seek is None:
            return
        for method in ("setActive", "setTimeMachine", "setLookback"):
            fn = getattr(seek, method, None)
            if callable(fn):
                try:
                    fn(False)
                except Exception:
                    pass
        for name in (
            "actionClick_to_Seek",
            "actionTime_Machine",
            "actionLookback",
        ):
            action = getattr(self.player, name, None)
            if action is not None and action.isChecked():
                action.blockSignals(True)
                action.setChecked(False)
                action.blockSignals(False)

    def _canvas(self):
        iface = getattr(self.player, "iface", None)
        if iface is None:
            return None
        try:
            return iface.mapCanvas()
        except Exception:
            return None

    def _to_wgs84(self, canvas, point):
        lon, lat = float(point.x()), float(point.y())
        try:
            from qgis.core import (
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransform,
                QgsProject,
            )

            crs = canvas.mapSettings().destinationCrs()
            if crs.isValid() and crs.authid() != "EPSG:4326":
                xform = QgsCoordinateTransform(
                    crs,
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    QgsProject.instance(),
                )
                p = xform.transform(point)
                lon, lat = float(p.x()), float(p.y())
        except Exception as exc:
            log.debug("target pin CRS: %s", exc)
        return lon, lat

    def _install_tool(self):
        canvas = self._canvas()
        if canvas is None:
            return False
        try:
            from qgis.gui import QgsMapTool
            from qgis.PyQt.QtCore import Qt
        except Exception as exc:
            log.debug("target pin map tool: %s", exc)
            return False

        ctrl = self

        class _PinTool(QgsMapTool):
            def __init__(self, cnv):
                super().__init__(cnv)
                try:
                    self.setCursor(Qt.CursorShape.CrossCursor)
                except Exception:
                    pass

            def canvasReleaseEvent(self, event):
                try:
                    point = self.toMapCoordinates(event.pos())
                except Exception:
                    return
                lon, lat = ctrl._to_wgs84(canvas, point)
                ctrl.setPin(lon, lat)

        try:
            self._prev_tool = canvas.mapTool()
            self._tool = _PinTool(canvas)
            canvas.setMapTool(self._tool)
            return True
        except Exception as exc:
            log.debug("install pin tool: %s", exc)
            return False

    def _uninstall_tool(self):
        canvas = self._canvas()
        if canvas is None:
            self._tool = None
            return
        try:
            if self._tool is not None and canvas.mapTool() is self._tool:
                if self._prev_tool is not None:
                    canvas.setMapTool(self._prev_tool)
                else:
                    canvas.unsetMapTool(self._tool)
        except Exception as exc:
            log.debug("uninstall pin tool: %s", exc)
        self._tool = None
        self._prev_tool = None

    def _show_marker(self, lon, lat):
        canvas = self._canvas()
        if canvas is None:
            return
        try:
            from qgis.core import (
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransform,
                QgsGeometry,
                QgsPointXY,
                QgsProject,
                QgsWkbTypes,
            )
            from qgis.gui import QgsRubberBand
            from qgis.PyQt.QtGui import QColor

            self._clear_marker()
            rb = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PointGeometry)
            rb.setColor(QColor(255, 200, 0, 230))
            rb.setWidth(4)
            try:
                rb.setIcon(QgsRubberBand.IconType.ICON_CROSS)
                rb.setIconSize(18)
            except Exception:
                pass
            pt = QgsPointXY(lon, lat)
            crs = canvas.mapSettings().destinationCrs()
            if crs.isValid() and crs.authid() != "EPSG:4326":
                xform = QgsCoordinateTransform(
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    crs,
                    QgsProject.instance(),
                )
                pt = xform.transform(pt)
            rb.setToGeometry(QgsGeometry.fromPointXY(pt), None)
            rb.show()
            self._rubber = rb
        except Exception as exc:
            log.debug("target pin marker: %s", exc)

    def _clear_marker(self):
        if self._rubber is None:
            return
        try:
            self._rubber.reset()
            self._rubber.hide()
        except Exception as exc:
            log.debug("clear pin marker: %s", exc)
        self._rubber = None
