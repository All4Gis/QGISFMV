# -*- coding: utf-8 -*-
"""Spatial geofence rules — alert when frame-center enters / leaves an AOI."""

from __future__ import annotations

import time

from qgis.core import Qgis as QGis
from qgis.PyQt.QtCore import QCoreApplication

from QGISFMV.geo.QgsFmvSpatial import (
    close_ring,
    detections_inside_ring,
    metadata_lat_lon,
    point_in_ring,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class GeofenceRule:
    """One AOI ring with enter/exit semantics."""

    def __init__(self, ring, label="Geofence", mode="enter"):
        """
        @param ring: iterable of ``(lon, lat)``
        @param mode: ``enter`` (alert when inside) or ``exit`` (alert when outside)
        """
        self.ring = close_ring(ring)
        self.label = label or "Geofence"
        self.mode = mode if mode in ("enter", "exit") else "enter"
        self._was_inside = None

    @property
    def valid(self):
        return len(self.ring) >= 4  # closed triangle+

    def contains(self, lon, lat):
        return point_in_ring(float(lon), float(lat), self.ring)

    def check_transition(self, lon, lat):
        """Return ``(triggered, message_suffix)`` on edge transition."""
        if not self.valid:
            return False, None
        inside = self.contains(lon, lat)
        prev = self._was_inside
        self._was_inside = inside
        if prev is None:
            # First sample: alert immediately if already violating mode.
            if self.mode == "enter" and inside:
                return True, "inside AOI"
            if self.mode == "exit" and not inside:
                return True, "outside AOI"
            return False, None
        if self.mode == "enter" and inside and not prev:
            return True, "entered AOI"
        if self.mode == "exit" and (not inside) and prev:
            return True, "exited AOI"
        return False, None


def footprint_ring_from_session(session=None):
    """Build ``[(lon, lat), ...]`` from live session / gv corners."""
    try:
        if session is None:
            from QGISFMV.utils.core.QgsFmvUtils import gv as session
        corners = []
        for getter in (
            session.getCornerUL,
            session.getCornerUR,
            session.getCornerLR,
            session.getCornerLL,
        ):
            pt = getter()
            if pt is None or len(pt) < 2:
                continue
            lat, lon = float(pt[0]), float(pt[1])
            corners.append((lon, lat))
        if len(corners) >= 3:
            return close_ring(corners)
    except Exception as exc:
        log.debug("footprint_ring_from_session failed: %s", exc)
    return []


def footprint_ring_from_layer(group_name):
    """Read footprint polygon vertices from the map layer if present."""
    try:
        from QGISFMV.player.dialogs.QgsFmvReportGeo import (
            _corners_from_footprint_feature,
        )
        from QGISFMV.utils.layers.QgsFmvLayers import Footprint_lyr

        layer = qgsu.selectLayerByName(Footprint_lyr, group_name)
        if layer is None or layer.featureCount() == 0:
            return []
        for feature in layer.getFeatures():
            corners = _corners_from_footprint_feature(feature)
            if len(corners) >= 3:
                return close_ring(corners)
    except Exception as exc:
        log.debug("footprint_ring_from_layer failed: %s", exc)
    return []


class GeofenceController:
    """Owns AOI geofences and fires through the player's AlertManager signal path."""

    def __init__(self, player):
        self.player = player
        self._rules = []
        self._enabled = True
        self._watch_detections = True
        self._cooldown_ms = 2000
        self._last_alert_ms = 0
        self._aoi_layer = None

    def rules(self):
        return list(self._rules)

    def setWatchDetections(self, enabled):
        """Enable/disable AOI Detection Sentinel (AI hits inside geofence)."""
        self._watch_detections = bool(enabled)
        return self._watch_detections

    def watchDetections(self):
        return self._watch_detections

    def clear(self):
        self._rules.clear()
        self._remove_aoi_layer()

    def set_ring(self, ring, label="Geofence", mode="enter"):
        """Replace current geofences with a single AOI ring."""
        rule = GeofenceRule(ring, label=label, mode=mode)
        if not rule.valid:
            qgsu.showUserAndLogMessage(
                "",
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Geofence needs at least 3 vertices."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return False
        self._rules = [rule]
        self._draw_aoi_layer(rule.ring)
        qgsu.showUserAndLogMessage(
            "",
            QCoreApplication.translate(
                "QgsFmvPlayer", "Geofence armed (%1 vertices)."
            ).replace("%1", str(len(rule.ring) - 1)),
            level=QGis.MessageLevel.Info,
        )
        return True

    def setFromFootprint(self):
        """Arm geofence from the current video footprint."""
        player = self.player
        ring = footprint_ring_from_layer(player._videoGroupName())
        if len(ring) < 4:
            ring = footprint_ring_from_session(getattr(player, "session", None))
        if len(ring) < 4:
            qgsu.showUserAndLogMessage(
                "",
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "No footprint available yet. Play until telemetry draws a footprint.",
                ),
                level=QGis.MessageLevel.Warning,
            )
            return False
        return self.set_ring(ring, label="Footprint Geofence", mode="enter")

    def checkMetadata(self, metadata_dict):
        """Evaluate geofences against frame-center / sensor position."""
        if not self._enabled or not self._rules:
            return
        pos = metadata_lat_lon(metadata_dict, prefer_frame_center=True)
        if pos is None:
            return
        lat, lon = pos
        now = int(time.time() * 1000)
        if now - self._last_alert_ms < self._cooldown_ms:
            return
        for rule in self._rules:
            triggered, detail = rule.check_transition(lon, lat)
            if not triggered:
                continue
            self._last_alert_ms = now
            msg = f"GEOFENCE: {rule.label} ({detail})"
            self._emit_alert(msg)
            break

    def checkDetections(self, detections_by_class=None):
        """AOI Detection Sentinel — alert when AI points fall inside an armed AOI."""
        if not self._enabled or not self._watch_detections or not self._rules:
            return None
        if detections_by_class is None:
            try:
                from QGISFMV.video.filters.QgsFmvDetectionMap import last_detections

                detections_by_class = last_detections()
            except Exception:
                return None
        if not detections_by_class:
            return None

        now = int(time.time() * 1000)
        if now - self._last_alert_ms < self._cooldown_ms:
            return None

        for rule in self._rules:
            if not rule.valid:
                continue
            hits = detections_inside_ring(detections_by_class, rule.ring)
            if not hits:
                continue
            # Summarize classes for a compact alert.
            counts = {}
            for cls, _p in hits:
                # Prefer short labels: "vehicle" from "vehicle_ema" etc.
                short = cls.split("_")[0] if cls else "object"
                counts[short] = counts.get(short, 0) + 1
            parts = [f"{n}×{name}" for name, n in sorted(counts.items())]
            msg = f"SENTINEL: {', '.join(parts)} inside {rule.label}"
            self._last_alert_ms = now
            self._emit_alert(msg)
            return msg
        return None

    def _emit_alert(self, msg):
        """Fire alert signal + QGIS message (HUD banner is wired via alertTriggered)."""
        am = getattr(self.player, "alertManager", None)
        if am is not None and hasattr(am, "alertTriggered"):
            am.alertTriggered.emit(msg)
        qgsu.showUserAndLogMessage(
            "Geofence",
            msg,
            level=QGis.MessageLevel.Warning,
            duration=5,
        )

    def _draw_aoi_layer(self, ring):
        """Show AOI as a memory polygon in the current video group."""
        try:
            from qgis.core import (
                QgsFeature,
                QgsField,
                QgsFields,
                QgsGeometry,
                QgsPointXY,
                QgsVectorLayer,
            )
            from qgis.PyQt.QtCore import QVariant

            from QGISFMV.utils.layers.QgsFmvLayers import addLayerNoCrsDialog, groupName

            self._remove_aoi_layer()
            layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "FMV Geofence", "memory")
            fields = QgsFields()
            fields.append(QgsField("label", QVariant.String))
            layer.dataProvider().addAttributes(fields.toList())
            layer.updateFields()
            feat = QgsFeature(layer.fields())
            feat.setAttributes(["Geofence"])
            feat.setGeometry(
                QgsGeometry.fromPolygonXY(
                    [[QgsPointXY(float(lon), float(lat)) for lon, lat in ring]]
                )
            )
            layer.dataProvider().addFeatures([feat])
            layer.updateExtents()
            # Soft red outline
            try:
                from qgis.core import QgsFillSymbol

                symbol = QgsFillSymbol.createSimple(
                    {
                        "color": "255,64,64,40",
                        "outline_color": "255,64,64,200",
                        "outline_width": "0.6",
                    }
                )
                layer.renderer().setSymbol(symbol)
            except Exception:
                pass
            group = groupName or self.player._videoGroupName()
            addLayerNoCrsDialog(layer, group=group)
            self._aoi_layer = layer
        except Exception as exc:
            log.debug("geofence AOI layer failed: %s", exc)

    def _remove_aoi_layer(self):
        layer = self._aoi_layer
        self._aoi_layer = None
        if layer is None:
            return
        try:
            QgsProject = __import__("qgis.core", fromlist=["QgsProject"]).QgsProject
            QgsProject.instance().removeMapLayer(layer.id())
        except Exception as exc:
            log.debug("remove geofence layer: %s", exc)
