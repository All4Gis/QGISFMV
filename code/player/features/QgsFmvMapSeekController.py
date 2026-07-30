# -*- coding: utf-8 -*-
"""Click-to-seek and Map Time Machine (hover scrub + ghost FOV)."""

from __future__ import annotations

import time

from QGISFMV.geo.QgsFmvSpatial import (
    haversine_m,
    lookback_samples,
    metadata_lat_lon,
    nearest_sample,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class GeoTimeIndex:
    """Throttled geo/time index with optional footprint rings per sample.

    Each sample is ``(lon, lat, time_sec, footprint_ring|None)``.
    """

    def __init__(self, max_samples=8000, min_step_m=8.0, min_dt_sec=0.4):
        self.max_samples = int(max_samples)
        self.min_step_m = float(min_step_m)
        self.min_dt_sec = float(min_dt_sec)
        self.samples = []

    def clear(self):
        self.samples.clear()

    def add(self, lon, lat, time_sec, footprint=None):
        try:
            lon, lat, time_sec = float(lon), float(lat), float(time_sec)
        except (TypeError, ValueError):
            return False
        ring = None
        if footprint and len(footprint) >= 3:
            try:
                ring = [(float(p[0]), float(p[1])) for p in footprint]
            except (TypeError, ValueError, IndexError):
                ring = None
        if self.samples:
            prev = self.samples[-1]
            if abs(time_sec - prev[2]) < self.min_dt_sec:
                if haversine_m((lon, lat), (prev[0], prev[1])) < self.min_step_m:
                    # Refresh footprint on the last sample if we now have one.
                    if ring is not None and prev[3] is None:
                        self.samples[-1] = (prev[0], prev[1], prev[2], ring)
                    return False
        self.samples.append((lon, lat, time_sec, ring))
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[::2][-self.max_samples :]
        return True

    def nearest(self, lon, lat):
        return nearest_sample(float(lon), float(lat), self.samples)

    def lookback(self, lon, lat, cluster_dt=2.0, max_hits=40):
        """Samples whose FOV covered ``(lon, lat)`` (clustered)."""
        return lookback_samples(
            lon, lat, self.samples, cluster_dt=cluster_dt, max_hits=max_hits
        )


class MapSeekController:
    """Click-to-seek, Map Time Machine, and Lookback (“what did we see here?”)."""

    def __init__(self, player):
        self.player = player
        self.index = GeoTimeIndex()
        self._tool = None
        self._prev_tool = None
        self._active = False  # click-to-seek
        self._time_machine = False
        self._lookback = False
        self._rubber = None
        self._last_scrub_ms = 0
        self._last_scrub_t = None
        self._scrub_min_ms = 90
        self._scrub_min_dt = 0.12
        self._lookback_hits = []
        self._lookback_idx = -1

    def clear(self):
        self.index.clear()
        self._clear_ghost()

    def recordFromMetadata(self, metadata_dict, time_sec=None):
        """Append a sample (platform/frame-center + optional footprint) from telemetry."""
        pos = metadata_lat_lon(metadata_dict, prefer_frame_center=False)
        if pos is None:
            pos = metadata_lat_lon(metadata_dict, prefer_frame_center=True)
        if pos is None:
            return
        lat, lon = pos
        if time_sec is None:
            time_sec = float(getattr(self.player, "currentInfo", 0.0) or 0.0)
        footprint = None
        try:
            from QGISFMV.player.features.QgsFmvGeofence import (
                footprint_ring_from_session,
            )

            footprint = footprint_ring_from_session(
                getattr(self.player, "session", None)
            )
        except Exception as exc:
            log.debug("geotime footprint capture: %s", exc)
        self.index.add(lon, lat, time_sec, footprint=footprint or None)

    def seekNearest(self, lon, lat, show_ghost=False):
        """Seek the player to the nearest indexed sample. Returns time_sec or None."""
        sample = self.index.nearest(lon, lat)
        if sample is None:
            qgsu.showUserAndLogMessage(
                "",
                "No geo/time index yet — play the video with telemetry first.",
                level=1,
            )
            return None
        time_sec = sample[2]
        footprint = sample[3] if len(sample) > 3 else None
        if not self._seek_to(time_sec):
            return None
        if show_ghost:
            self._show_ghost(footprint, sample[0], sample[1])
        return time_sec

    def scrubNearest(self, lon, lat):
        """Throttled hover scrub for Time Machine mode."""
        now = int(time.time() * 1000)
        if now - self._last_scrub_ms < self._scrub_min_ms:
            return None
        sample = self.index.nearest(lon, lat)
        if sample is None:
            return None
        time_sec = sample[2]
        if (
            self._last_scrub_t is not None
            and abs(time_sec - self._last_scrub_t) < self._scrub_min_dt
        ):
            # Still refresh ghost if we have a footprint.
            if sample[3]:
                self._show_ghost(sample[3], sample[0], sample[1])
            return self._last_scrub_t
        self._last_scrub_ms = now
        self._last_scrub_t = time_sec
        if self._seek_to(time_sec):
            self._show_ghost(
                sample[3] if len(sample) > 3 else None, sample[0], sample[1]
            )
            return time_sec
        return None

    def _seek_to(self, time_sec):
        player = self.player
        try:
            if hasattr(player, "playbackController") and hasattr(
                player.playbackController, "seek"
            ):
                player.playbackController.seek(time_sec)
            elif hasattr(player, "player") and player.player is not None:
                player.player.setPosition(int(time_sec * 1000))
            qgsu.showUserAndLogMessage(
                "",
                f"Seek → {time_sec:.1f}s",
                onlyLog=True,
            )
            return True
        except Exception as exc:
            log.debug("seek failed: %s", exc)
            return False

    @property
    def active(self):
        return self._active

    @property
    def timeMachineActive(self):
        return self._time_machine

    @property
    def lookbackActive(self):
        return self._lookback

    def _uncheck_action(self, name):
        action = getattr(self.player, name, None)
        if action is not None and action.isChecked():
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)

    def _exclusive_off(self, keep=None):
        """Turn off sibling map tools (except *keep*)."""
        modes = {
            "click": ("_active", "actionClick_to_Seek"),
            "timemachine": ("_time_machine", "actionTime_Machine"),
            "lookback": ("_lookback", "actionLookback"),
        }
        for mode, (attr, action_name) in modes.items():
            if mode == keep:
                continue
            if getattr(self, attr):
                setattr(self, attr, False)
                self._uncheck_action(action_name)
        if keep is None or not getattr(self, modes[keep][0], False):
            # Tool will be reinstalled by caller when enabling.
            pass

    def setActive(self, active):
        """Enable/disable simple click-to-seek."""
        active = bool(active)
        if active == self._active:
            return self._active
        if active:
            self._disarm_target_pin()
            was_tool = self._tool is not None
            self._exclusive_off(keep="click")
            if was_tool or self._tool is not None:
                self._uninstall_tool()
            ok = self._install_tool(mode="click")
            self._active = ok
        else:
            self._uninstall_tool()
            self._active = False
        return self._active

    def setTimeMachine(self, active):
        """Enable/disable Map Time Machine (hover scrub + ghost FOV)."""
        active = bool(active)
        if active == self._time_machine:
            return self._time_machine
        if active:
            self._disarm_target_pin()
            self._exclusive_off(keep="timemachine")
            self._uninstall_tool()
            ok = self._install_tool(mode="timemachine")
            self._time_machine = ok
            if ok:
                qgsu.showUserAndLogMessage(
                    "",
                    "Time Machine armed — move the mouse along the flight path.",
                    level=0,
                )
        else:
            self._uninstall_tool()
            self._time_machine = False
            self._clear_ghost()
        return self._time_machine

    def setLookback(self, active):
        """Enable/disable Lookback — click a ground point to list FOV visits."""
        active = bool(active)
        if active == self._lookback:
            return self._lookback
        if active:
            self._disarm_target_pin()
            self._exclusive_off(keep="lookback")
            self._uninstall_tool()
            ok = self._install_tool(mode="lookback")
            self._lookback = ok
            if ok:
                qgsu.showUserAndLogMessage(
                    "",
                    "Lookback armed — click a place on the map to see when we looked at it.",
                    level=0,
                )
        else:
            self._uninstall_tool()
            self._lookback = False
            self._lookback_hits = []
            self._lookback_idx = -1
            self._clear_ghost()
        return self._lookback

    def _disarm_target_pin(self):
        """Release Target Pin arming so map tools don't fight over the canvas."""
        pin = getattr(self.player, "targetPinController", None)
        if pin is None or not pin.isArming():
            return
        try:
            pin.setArming(False)
        except Exception:
            pass
        action = getattr(self.player, "actionPin_Target", None)
        if action is not None and action.isChecked():
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)

    def runLookback(self, lon, lat):
        """Query FOV visits at ``(lon, lat)``, seek to first, offer a jump list."""
        hits = self.index.lookback(lon, lat)
        self._lookback_hits = hits
        self._lookback_idx = 0 if hits else -1
        if not hits:
            qgsu.showUserAndLogMessage(
                "",
                "Lookback: this place was never inside a recorded footprint "
                "(play longer with telemetry, or click closer to the track).",
                level=1,
            )
            return []
        sample = hits[0]
        self._seek_to(sample[2])
        self._show_ghost(sample[3] if len(sample) > 3 else None, sample[0], sample[1])
        qgsu.showUserAndLogMessage(
            "",
            f"Lookback: seen {len(hits)} time(s) — jumped to {sample[2]:.1f}s",
            level=0,
        )
        self._show_lookback_dialog(lon, lat, hits)
        return hits

    def seekLookbackIndex(self, index):
        """Seek to lookback hit *index* and show ghost FOV."""
        if not self._lookback_hits:
            return None
        if index < 0 or index >= len(self._lookback_hits):
            return None
        self._lookback_idx = index
        sample = self._lookback_hits[index]
        self._seek_to(sample[2])
        self._show_ghost(sample[3] if len(sample) > 3 else None, sample[0], sample[1])
        return sample[2]

    def _show_lookback_dialog(self, lon, lat, hits):
        """List FOV visit times; double-click / Accept jumps the video."""
        try:
            from qgis.PyQt.QtWidgets import (
                QDialog,
                QDialogButtonBox,
                QLabel,
                QListWidget,
                QListWidgetItem,
                QVBoxLayout,
            )
            from qgis.PyQt.QtCore import Qt
        except Exception as exc:
            log.debug("lookback dialog unavailable: %s", exc)
            return

        parent = self.player
        dlg = QDialog(parent if hasattr(parent, "windowTitle") else None)
        dlg.setWindowTitle("Lookback — What did we see here?")
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg)
        layout.addWidget(
            QLabel(
                f"Point ({lon:.5f}, {lat:.5f}) was inside the sensor FOV "
                f"{len(hits)} time(s).\nDouble-click a row to jump:"
            )
        )
        lst = QListWidget()
        for i, sample in enumerate(hits):
            t = float(sample[2])
            m, s = divmod(int(t), 60)
            h, m = divmod(m, 60)
            label = f"{i + 1}.  {h:02d}:{m:02d}:{s:02d}   ({t:.1f}s)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, i)
            lst.addItem(item)
        layout.addWidget(lst)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Close
        )
        layout.addWidget(buttons)

        def _jump(item):
            idx = item.data(Qt.ItemDataRole.UserRole)
            self.seekLookbackIndex(int(idx))

        def _ok():
            row = lst.currentRow()
            if row >= 0:
                self.seekLookbackIndex(row)
            dlg.accept()

        lst.itemDoubleClicked.connect(_jump)
        buttons.accepted.connect(_ok)
        buttons.rejected.connect(dlg.reject)
        try:
            dlg.exec()
        except Exception as exc:
            log.debug("lookback dialog exec: %s", exc)

    def toggle(self):
        return self.setActive(not self._active)

    def toggleTimeMachine(self):
        return self.setTimeMachine(not self._time_machine)

    def toggleLookback(self):
        return self.setLookback(not self._lookback)

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
            log.debug("map seek CRS transform: %s", exc)
        return lon, lat

    def _install_tool(self, mode="click"):
        canvas = self._canvas()
        if canvas is None:
            return False
        try:
            from qgis.gui import QgsMapTool
            from qgis.PyQt.QtCore import Qt
        except Exception as exc:
            log.debug("QgsMapTool unavailable: %s", exc)
            return False

        ctrl = self

        class _MapTimeTool(QgsMapTool):
            def __init__(self, cnv, tool_mode):
                super().__init__(cnv)
                self._mode = tool_mode
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
                if self._mode == "timemachine":
                    ctrl.seekNearest(lon, lat, show_ghost=True)
                elif self._mode == "lookback":
                    ctrl.runLookback(lon, lat)
                else:
                    ctrl.seekNearest(lon, lat, show_ghost=False)

            def canvasMoveEvent(self, event):
                if self._mode != "timemachine":
                    return
                try:
                    point = self.toMapCoordinates(event.pos())
                except Exception:
                    return
                lon, lat = ctrl._to_wgs84(canvas, point)
                ctrl.scrubNearest(lon, lat)

            def deactivate(self):
                ctrl._clear_ghost()
                super().deactivate()

        try:
            self._prev_tool = canvas.mapTool()
            self._tool = _MapTimeTool(canvas, mode)
            canvas.setMapTool(self._tool)
            if mode == "click":
                qgsu.showUserAndLogMessage(
                    "",
                    "Click-to-seek armed — click near the trajectory on the map.",
                    level=0,
                )
            elif mode == "lookback":
                pass  # message already shown in setLookback
            return True
        except Exception as exc:
            log.debug("install map seek tool failed: %s", exc)
            return False

    def _uninstall_tool(self):
        canvas = self._canvas()
        self._clear_ghost()
        if canvas is None:
            self._tool = None
            return
        try:
            if self._prev_tool is not None:
                canvas.setMapTool(self._prev_tool)
            elif self._tool is not None and canvas.mapTool() is self._tool:
                canvas.unsetMapTool(self._tool)
        except Exception as exc:
            log.debug("uninstall seek tool: %s", exc)
        self._tool = None
        self._prev_tool = None

    def _show_ghost(self, footprint, lon, lat):
        """Draw a translucent ghost FOV (footprint) or a point marker on the canvas."""
        canvas = self._canvas()
        if canvas is None:
            return
        try:
            from qgis.gui import QgsRubberBand
            from qgis.core import (
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransform,
                QgsProject,
                QgsPointXY,
                QgsWkbTypes,
            )
            from qgis.PyQt.QtGui import QColor
        except Exception as exc:
            log.debug("rubber band unavailable: %s", exc)
            return

        self._clear_ghost()
        try:
            crs = canvas.mapSettings().destinationCrs()
            xform = None
            if crs.isValid() and crs.authid() != "EPSG:4326":
                xform = QgsCoordinateTransform(
                    QgsCoordinateReferenceSystem("EPSG:4326"),
                    crs,
                    QgsProject.instance(),
                )

            def _map_pt(x, y):
                p = QgsPointXY(float(x), float(y))
                if xform is not None:
                    p = xform.transform(p)
                return p

            if footprint and len(footprint) >= 3:
                rb = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
                rb.setFillColor(QColor(255, 196, 0, 55))
                rb.setStrokeColor(QColor(255, 170, 0, 220))
                rb.setWidth(2)
                for x, y in footprint:
                    rb.addPoint(_map_pt(x, y), False)
                rb.addPoint(_map_pt(footprint[0][0], footprint[0][1]), True)
            else:
                rb = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
                rb.setColor(QColor(255, 170, 0, 230))
                rb.setWidth(8)
                rb.addPoint(_map_pt(lon, lat), True)
            rb.show()
            self._rubber = rb
            canvas.refresh()
        except Exception as exc:
            log.debug("ghost FOV failed: %s", exc)

    def _clear_ghost(self):
        rb = self._rubber
        self._rubber = None
        if rb is None:
            return
        try:
            rb.reset()
            canvas = self._canvas()
            if canvas is not None:
                canvas.scene().removeItem(rb)
        except Exception as exc:
            log.debug("clear ghost: %s", exc)
