# -*- coding: utf-8 -*-
"""Distance Rings overlay — concentric range rings around the platform position."""

import math

from qgis.core import (
    QgsGeometry,
    QgsPointXY,
    QgsFeature,
    QgsVectorLayer,
    QgsField,
    QgsLineSymbol,
    QgsCategorizedSymbolRenderer,
    QgsRendererCategory,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsTextFormat,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

from QGISFMV.player.overlays._base import VectorOverlayBase
from QGISFMV.geo.QgsGeoUtils import destination as _geo_destination

_DISTANCE_RINGS_LAYER = "Distance Rings"
DEFAULT_RING_DISTANCES = [500, 1000, 2000, 5000]


class DistanceRingsOverlay(VectorOverlayBase):
    """Maintain concentric range rings around the platform position on the map."""

    def __init__(self):
        super().__init__()
        self._ring_distances = list(DEFAULT_RING_DISTANCES)
        self._last_lat = None
        self._last_lon = None

    def _create_layer(self):
        vl = QgsVectorLayer("LineString?crs=EPSG:4326", _DISTANCE_RINGS_LAYER, "memory")
        provider = vl.dataProvider()
        provider.addAttributes([
            QgsField("ring_dist_m", QVariant.Double),
            QgsField("ring_label", QVariant.String),
        ])
        vl.updateFields()

        symbol = QgsLineSymbol.createSimple({
            "color": "180,180,180,150", "width": "0.6", "line_style": "dash",
        })
        vl.setRenderer(QgsCategorizedSymbolRenderer("", [QgsRendererCategory("", symbol, "")]))

        settings = QgsPalLayerSettings()
        settings.fieldName = "ring_label"
        settings.isExpression = True
        settings.placement = QgsPalLayerSettings.Placement.Line
        text_format = QgsTextFormat()
        text_format.setSize(8)
        text_format.setColor(QColor(120, 120, 120))
        settings.setFormat(text_format)
        vl.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        vl.setLabelsEnabled(True)
        return vl

    def update(self, packet, group_name=None):
        """Update ring positions from the current platform location."""
        if not self._visible:
            return

        lat = getattr(packet, "SensorLatitude", None)
        lon = getattr(packet, "SensorLongitude", None)

        if lat is None or lon is None:
            return

        # Skip if position hasn't changed significantly
        if (self._last_lat is not None and self._last_lon is not None
                and abs(lat - self._last_lat) < 1e-8
                and abs(lon - self._last_lon) < 1e-8):
            return

        self._last_lat = lat
        self._last_lon = lon

        layer = self._ensureLayer(group_name)
        if layer is None:
            return

        provider = layer.dataProvider()
        # Provider-only updates avoid edit-buffer / provider mix-ups.
        old_ids = [feat.id() for feat in layer.getFeatures()]
        if old_ids:
            provider.deleteFeatures(old_ids)

        for dist_m in self._ring_distances:
            circle_geom = self._buildCircle(lat, lon, dist_m)
            if circle_geom is None:
                continue

            label = self._formatDistance(dist_m)
            feature = QgsFeature(layer.fields())
            feature.setGeometry(circle_geom)
            feature.setAttributes([dist_m, label])
            provider.addFeatures([feature])

        layer.updateExtents()
        layer.triggerRepaint()

    def _buildCircle(self, center_lat, center_lon, radius_m, n_points=64):
        """Approximate a circle on the WGS84 ellipsoid as a polygon."""
        from QGISFMV.geo.QgsGeoUtils import destination as _geo_destination

        points = []
        for i in range(n_points):
            bearing = 360.0 * i / n_points
            dest_lon, dest_lat = _geo_destination(
                (center_lon, center_lat), radius_m, bearing
            )
            points.append(QgsPointXY(dest_lon, dest_lat))

        points.append(points[0])
        return QgsGeometry.fromPolylineXY(points)

    @staticmethod
    def _formatDistance(meters):
        """Format distance for label display."""
        if meters >= 1000:
            return f"{meters / 1000:.1f} km"
        return f"{int(meters)} m"
