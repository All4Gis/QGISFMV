# -*- coding: utf-8 -*-
"""Geo/map helpers for the FMV analysis report.

Owns footprint/sensor-position lookups and the mini-map extent/projection
math used by the PDF report, extracted from QgsFmvReportGenerator.py.
"""
from qgis.core import QgsRectangle

from QGISFMV.utils.logging import log
from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.player.overlays.QgsFmvMiniMap import create_osm_basemap
from QGISFMV.player.dialogs.QgsFmvReportMetadata import (
    _find_metadata_value,
    _metadata_leaf_entries,
    _normalize_key,
)


def _corners_from_footprint_feature(feature):
    """Extract footprint corners as (lon, lat) tuples from a layer feature."""
    field_names = feature.fields().names()
    corners = []
    for idx in range(1, 5):
        lon_field = f"clon{idx}"
        lat_field = f"clat{idx}"
        if lon_field not in field_names or lat_field not in field_names:
            continue
        try:
            lon = float(feature[lon_field])
            lat = float(feature[lat_field])
        except (TypeError, ValueError):
            continue
        corners.append((lon, lat))
    if len(corners) >= 3:
        return corners

    geometry = feature.geometry()
    if geometry is None or geometry.isEmpty():
        return []

    try:
        polygon = geometry.asPolygon()
        if polygon and polygon[0]:
            return [(pt.x(), pt.y()) for pt in polygon[0]]
    except Exception as exc:
        log.debug("Footprint asPolygon failed: %s", exc)

    try:
        for part in geometry.asMultiPolygon():
            if part and part[0]:
                return [(pt.x(), pt.y()) for pt in part[0]]
    except Exception as exc:
        log.debug("Footprint asMultiPolygon failed: %s", exc)

    try:
        const = geometry.constGet()
        if const is not None and hasattr(const, "exteriorRing"):
            ring = const.exteriorRing()
            if ring is not None:
                return [
                    (ring.pointN(i).x(), ring.pointN(i).y())
                    for i in range(ring.numPoints())
                ]
    except Exception as exc:
        log.debug("Footprint exteriorRing failed: %s", exc)

    try:
        vertices = []
        for vertex in geometry.vertices():
            vertices.append((vertex.x(), vertex.y()))
        if len(vertices) >= 3:
            if vertices[0] == vertices[-1]:
                vertices = vertices[:-1]
            return vertices
    except Exception as exc:
        log.debug("Footprint vertices iteration failed: %s", exc)
    return []


def _footprint_corners_for_report(data, group_name):
    """Collect footprint corners from QGIS layer, metadata, or live gv state."""
    # Source 1: QGIS footprint layer
    layer_name = settings_get("LAYERS", "footprint_lyr", "Footprint")
    layer = qgsu.selectLayerByName(layer_name, group_name) if group_name else None
    if layer is not None and layer.featureCount() > 0:
        for feature in layer.getFeatures():
            corners = _corners_from_footprint_feature(feature)
            if len(corners) >= 3:
                return corners

    # Source 2: MISB metadata corner/point fields
    corners = []
    for point_idx in range(1, 5):
        lat = lon = None
        point_token = str(point_idx)
        for label, value in _metadata_leaf_entries(data):
            key_lower = _normalize_key(label)
            if point_token not in key_lower:
                continue
            if "corner" not in key_lower and "point" not in key_lower:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if "latitude" in key_lower:
                lat = numeric
            elif "longitude" in key_lower:
                lon = numeric
        if lat is not None and lon is not None:
            corners.append((lon, lat))
    if len(corners) >= 3:
        return corners

    # Source 3: live gv state
    try:
        from QGISFMV.utils.core.QgsFmvUtils import gv
    except Exception as exc:
        log.debug("gv import failed for footprint corners: %s", exc)
        return []

    corners = []
    for getter in (gv.getCornerUL, gv.getCornerUR, gv.getCornerLR, gv.getCornerLL):
        point = getter()
        if point is None or len(point) < 2:
            continue
        lat, lon = float(point[0]), float(point[1])
        corners.append((lon, lat))
    return corners


def _sensor_position_from_layer(group_name):
    if not group_name:
        return None, None
    platform_name = settings_get("LAYERS", "platform_lyr", "Platform")
    layer = qgsu.selectLayerByName(platform_name, group_name)
    if layer is None or layer.featureCount() == 0:
        return None, None

    for feature in layer.getFeatures():
        lat = lon = None
        field_names = feature.fields().names()
        if "latitude" in field_names and "longitude" in field_names:
            try:
                lat = float(feature["latitude"])
                lon = float(feature["longitude"])
            except (TypeError, ValueError):
                pass
        if lat is None or lon is None:
            geometry = feature.geometry()
            if geometry is not None and not geometry.isEmpty():
                try:
                    point = geometry.asPoint()
                    lon, lat = point.x(), point.y()
                except Exception as exc:
                    try:
                        point = geometry.constGet()
                        if point is not None:
                            lon, lat = point.x(), point.y()
                    except Exception as nested_exc:
                        log.debug(
                            "Platform geometry parse failed: %s / %s",
                            exc,
                            nested_exc,
                        )
        if lat is not None and lon is not None:
            return lat, lon
    return None, None


def _sensor_position_for_report(data):
    lat = lon = None
    lat_text = _find_metadata_value(data, "sensor", "latitude")
    lon_text = _find_metadata_value(data, "sensor", "longitude")
    if lat_text == "—":
        lat_text = _find_metadata_value(data, "platform", "latitude")
    if lon_text == "—":
        lon_text = _find_metadata_value(data, "platform", "longitude")

    for raw, target in ((lat_text, "lat"), (lon_text, "lon")):
        if raw == "—":
            continue
        try:
            if target == "lat":
                lat = float(raw)
            else:
                lon = float(raw)
        except (TypeError, ValueError):
            pass

    if lat is None or lon is None:
        try:
            from QGISFMV.utils.core.QgsFmvUtils import gv

            if gv is not None:
                if lat is None:
                    lat = gv.getSensorLatitude()
                if lon is None:
                    lon = gv.getSensorLongitude()
                if lat is not None:
                    lat = float(lat)
                if lon is not None:
                    lon = float(lon)
        except Exception as exc:
            log.debug("Sensor position from gv failed: %s", exc)

    return lat, lon


def _sensor_position_for_report_with_group(data, group_name=None, player=None):
    lat, lon = _sensor_position_for_report(data)
    if lat is not None and lon is not None:
        return lat, lon

    if group_name:
        lat, lon = _sensor_position_from_layer(group_name)
        if lat is not None and lon is not None:
            return lat, lon

    packet = getattr(player, "_lastMetadataPacket", None) if player else None
    if packet is not None:
        try:
            if lat is None and packet.SensorLatitude is not None:
                lat = float(packet.SensorLatitude)
            if lon is None and packet.SensorLongitude is not None:
                lon = float(packet.SensorLongitude)
        except (TypeError, ValueError, AttributeError):
            pass
    return lat, lon


def _create_osm_basemap_layer():
    """Temporary OSM XYZ layer for report map rendering."""
    return create_osm_basemap("OSM-report")


def _extent_from_corners(corners):
    if len(corners) < 3:
        return None
    extent = QgsRectangle()
    for lon, lat in corners:
        extent.combineExtentWith(QgsRectangle(lon, lat, lon, lat))
    if extent.isNull() or extent.isEmpty():
        return None
    return extent


def _padded_map_extent(extent, padding_factor=0.4, minimum_span=0.0003):
    if extent is None or extent.isNull() or extent.isEmpty():
        return extent
    span = max(extent.width(), extent.height(), minimum_span)
    pad = span * padding_factor
    return QgsRectangle(
        extent.xMinimum() - pad,
        extent.yMinimum() - pad,
        extent.xMaximum() + pad,
        extent.yMaximum() + pad,
    )


def _geo_to_pixel(lon, lat, extent, width_px, height_px):
    if extent.width() <= 0 or extent.height() <= 0:
        return 0.0, 0.0
    x = (lon - extent.xMinimum()) / extent.width() * width_px
    y = (1.0 - (lat - extent.yMinimum()) / extent.height()) * height_px
    return x, y
