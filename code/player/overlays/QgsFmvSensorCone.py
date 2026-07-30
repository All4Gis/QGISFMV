# -*- coding: utf-8 -*-
"""Sensor Coverage Cone overlay — shows the sensor FOV on the QGIS map canvas."""

import math

from qgis.core import (
    QgsGeometry,
    QgsPointXY,
    QgsFeature,
    QgsVectorLayer,
    QgsField,
    QgsFillSymbol,
    QgsRendererCategory,
    QgsCategorizedSymbolRenderer,
)
from qgis.PyQt.QtCore import QVariant

from QGISFMV.player.overlays._base import VectorOverlayBase

_SENSOR_CONE_LAYER_NAME = "Sensor Coverage Cone"


class SensorConeOverlay(VectorOverlayBase):
    """Maintain a polygon layer that visualizes the sensor FOV cone on the map."""

    def __init__(self):
        super().__init__()
        self._last_sensor = None
        self._last_frame_center = None
        self._last_fov_v = None
        self._last_fov_h = None

    def _create_layer(self):
        vl = QgsVectorLayer("Polygon?crs=EPSG:4326", _SENSOR_CONE_LAYER_NAME, "memory")
        provider = vl.dataProvider()
        provider.addAttributes(
            [
                QgsField("sensor_lat", QVariant.Double),
                QgsField("sensor_lon", QVariant.Double),
                QgsField("frame_lat", QVariant.Double),
                QgsField("frame_lon", QVariant.Double),
                QgsField("fov_v", QVariant.Double),
                QgsField("fov_h", QVariant.Double),
                QgsField("slant_range", QVariant.Double),
                QgsField("altitude", QVariant.Double),
            ]
        )
        vl.updateFields()

        symbol = QgsFillSymbol.createSimple(
            {
                "color": "30,100,200,60",
                "outline_color": "30,100,200,180",
                "outline_width": "0.5",
                "outline_style": "dash",
            }
        )
        vl.setRenderer(
            QgsCategorizedSymbolRenderer("", [QgsRendererCategory("", symbol, "")])
        )
        vl.setOpacity(0.35)
        vl.triggerRepaint()
        return vl

    def update(self, packet, group_name=None):
        """Update the cone geometry from a KLV metadata packet."""
        if not self._visible:
            return

        sensor_lat = getattr(packet, "SensorLatitude", None)
        sensor_lon = getattr(packet, "SensorLongitude", None)
        frame_lat = getattr(packet, "FrameCenterLatitude", None)
        frame_lon = getattr(packet, "FrameCenterLongitude", None)
        fov_v = getattr(packet, "SensorVerticalFieldOfView", None)
        fov_h = getattr(packet, "SensorHorizontalFieldOfView", None)
        slant = getattr(packet, "SlantRange", None)
        altitude = getattr(packet, "SensorTrueAltitude", None)

        if sensor_lat is None or sensor_lon is None:
            return
        if frame_lat is None or frame_lon is None:
            return
        if fov_h is None or fov_h <= 0:
            return

        layer = self._ensureLayer(group_name)
        if layer is None:
            return

        cone_geom = self._buildCone(
            sensor_lat, sensor_lon, frame_lat, frame_lon, fov_h, slant, altitude
        )
        if cone_geom is None:
            return

        provider = layer.dataProvider()
        # Use the provider only — mixing edit-buffer deletes with provider adds
        # can leave duplicate features or a stuck edit state.
        old_ids = [feat.id() for feat in layer.getFeatures()]
        if old_ids:
            provider.deleteFeatures(old_ids)

        feature = QgsFeature(layer.fields())
        feature.setGeometry(cone_geom)
        feature.setAttributes(
            [
                sensor_lat,
                sensor_lon,
                frame_lat,
                frame_lon,
                fov_v or 0.0,
                fov_h,
                slant or 0.0,
                altitude or 0.0,
            ]
        )
        provider.addFeatures([feature])
        layer.updateExtents()
        layer.triggerRepaint()

    def _buildCone(
        self,
        sensor_lat,
        sensor_lon,
        frame_lat,
        frame_lon,
        fov_h_deg,
        slant_range,
        altitude,
    ):
        """Build a polygon cone from sensor to frame center area."""
        from QGISFMV.geo.QgsGeoUtils import (
            destination as _geo_destination,
            bearing as _geo_bearing,
        )

        bearing = _geo_bearing((sensor_lon, sensor_lat), (frame_lon, frame_lat))

        # Distance from sensor to frame center (meters)
        from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance

        dist = _geo_distance((sensor_lon, sensor_lat), (frame_lon, frame_lat))

        # Cone length: use slant range or distance to frame center
        cone_len = dist * 1.3  # extend 30% beyond frame center
        if slant_range and slant_range > 0:
            cone_len = max(cone_len, slant_range * 0.8)

        # Half-angle of the cone
        half_fov = fov_h_deg / 2.0

        # Build cone points: sensor -> left edge -> far center -> right edge
        n_segments = 12
        points = []
        for i in range(n_segments + 1):
            frac = i / float(n_segments)
            angle_offset = -half_fov + frac * fov_h_deg
            bearing_deg = bearing + angle_offset

            d = cone_len * (0.5 + 0.5 * math.sin(frac * math.pi))

            dest_lon, dest_lat = _geo_destination(
                (sensor_lon, sensor_lat), d, bearing_deg
            )
            points.append(QgsPointXY(dest_lon, dest_lat))

        # Close the polygon
        points.append(points[0])
        return QgsGeometry.fromPolygonXY([points])
