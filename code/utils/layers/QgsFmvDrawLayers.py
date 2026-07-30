# -*- coding: utf-8 -*-
"""Map-drawing sync helpers extracted from QgsFmvLayers.py.

Owns the Add/Remove draw point/line/polygon/military-symbol functions and the
measure-distance/measure-area layer sync functions. Generic layer helpers
(CommonLayer, groupName, layer-name constants, etc.) still live in
QgsFmvLayers.py and are accessed here through a module reference so this
module always sees their live values.
"""

from itertools import groupby

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsDistanceArea,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
)
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QPolygonF
from qgis.utils import iface

from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.video.playback.QgsVideoState import MOUSE_MOVE_EVENT


def _base():
    """Lazily resolve QgsFmvLayers to dodge the circular import at load time.

    QgsFmvLayers.py re-exports this module's functions for backward
    compatibility, so importing QgsFmvLayers eagerly here (at module scope)
    could fail if this module happens to load first. Deferring the import
    to call time guarantees both modules are fully initialized.
    """
    import QGISFMV.utils.layers.QgsFmvLayers as _mod

    return _mod


def _delete_last_feature(layer_name, group_name=None):
    """Delete the most recently added feature from a memory layer."""
    layer = qgsu.selectLayerByName(layer_name, group_name)
    if layer is None:
        return
    layer.startEditing()
    ids = [feat.id() for feat in layer.getFeatures()]
    if ids:
        layer.deleteFeature(ids[-1])
        _base().CommonLayer(layer)


def AddDrawMilitarySymbolOnMap(
    pointIndex, Longitude, Latitude, Altitude, symbol_id, unit_name
):
    """Add a military symbol point on the map."""
    symbolLyr = qgsu.selectLayerByName(_base().Symbol_lyr, _base().groupName)
    if symbolLyr is None:
        return
    symbolLyr.startEditing()
    feature = QgsFeature()
    feature.setAttributes(
        [pointIndex, symbol_id, unit_name or "", Longitude, Latitude, Altitude]
    )
    feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(Longitude, Latitude)))
    symbolLyr.addFeatures([feature])
    _base().CommonLayer(symbolLyr)


def RemoveLastDrawMilitarySymbolOnMap(group_name=None):
    """Remove the most recently placed military symbol from the map layer."""
    _delete_last_feature(_base().Symbol_lyr, _base()._draw_group(group_name))


def RemoveAllDrawMilitarySymbolOnMap(group_name=None):
    """Remove all military symbols from the map layer."""
    _base()._truncate_layer(_base().Symbol_lyr, _base()._draw_group(group_name))


def AddDrawPointOnMap(pointIndex, Longitude, Latitude, Altitude):
    """add pin point on the map"""
    pointLyr = qgsu.selectLayerByName(_base().Point_lyr, _base().groupName)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    feature = QgsFeature()
    feature.setAttributes([pointIndex, Longitude, Latitude, Altitude])

    p = QgsPointXY()
    p.set(Longitude, Latitude)
    feature.setGeometry(QgsGeometry.fromPointXY(p))
    pointLyr.addFeatures([feature])
    _base().CommonLayer(pointLyr)
    return


def AddDrawLineOnMap(drawLines):
    """add Line on the map"""

    RemoveAllDrawLineOnMap()
    linelyr = qgsu.selectLayerByName(_base().Line_lyr, _base().groupName)
    if linelyr is None:
        return

    linelyr.startEditing()
    for k, v in groupby(drawLines, key=lambda x: x == [None, None, None]):
        points = []
        if k is False:
            list1 = list(v)
            for i in range(0, len(list1)):
                pt = QgsPointXY(list1[i][0], list1[i][1])
                points.append(pt)
            polyline = QgsGeometry.fromPolylineXY(points)
            f = QgsFeature()
            f.setGeometry(polyline)
            linelyr.addFeatures([f])

    _base().CommonLayer(linelyr)
    return


def RemoveAllDrawLineOnMap(group_name=None):
    """Remove all features on Line Layer"""
    _base()._truncate_layer(_base().Line_lyr, _base()._draw_group(group_name))


def RemoveAllDrawPolygonOnMap(group_name=None):
    """Remove all features on Polygon Layer"""
    _base()._truncate_layer(_base().Polygon_lyr, _base()._draw_group(group_name))


def RemoveAllDrawPointOnMap(group_name=None):
    """Remove all features on Point Layer"""
    _base()._truncate_layer(_base().Point_lyr, _base()._draw_group(group_name))


def RemoveLastDrawPolygonOnMap(group_name=None):
    """Remove Last Feature on Polygon Layer"""
    _delete_last_feature(_base().Polygon_lyr, _base()._draw_group(group_name))


def RemoveLastDrawPointOnMap(group_name=None):
    """Remove Last features on Point Layer"""
    _delete_last_feature(_base().Point_lyr, _base()._draw_group(group_name))


def AddDrawPolygonOnMap(poly_coordinates):
    """Add Polygon Layer"""
    polyLyr = qgsu.selectLayerByName(_base().Polygon_lyr, _base().groupName)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    feature = QgsFeature()
    point = QPointF()
    # create  float polygon --> construcet out of 'point'

    list_polygon = QPolygonF()
    for x in range(0, len(poly_coordinates)):
        if x % 2 == 0:
            point.setX(poly_coordinates[x])
            point.setY(poly_coordinates[x + 1])
            list_polygon.append(point)
    point.setX(poly_coordinates[0])
    point.setY(poly_coordinates[1])
    list_polygon.append(point)

    geomP = QgsGeometry.fromQPolygonF(list_polygon)
    feature.setGeometry(geomP)

    # Calculate Area WSG84 (Meters)
    area_wsg84 = QgsDistanceArea()
    area_wsg84.setSourceCrs(
        QgsCoordinateReferenceSystem.fromOgcWmsCrs("EPSG:4326"),
        _base()._layerreg.transformContext(),
    )
    if area_wsg84.sourceCrs().isGeographic():
        area_wsg84.setEllipsoid(area_wsg84.sourceCrs().ellipsoidAcronym())

    # Calculate Centroid
    try:
        centroid = feature.geometry().centroid().asPoint()
    except Exception as exc:
        log.debug("centroid calculation failed: %s", exc)
        iface.vectorLayerTools().stopEditing(polyLyr, False)
        return False

    feature.setAttributes(
        [
            centroid.x(),
            centroid.y(),
            0.0,
            area_wsg84.measurePolygon(geomP.asPolygon()[0]),
        ]
    )

    polyLyr.addFeatures([feature])

    _base().CommonLayer(polyLyr)
    return True


def _split_measure_chains(points):
    """Split [lon,lat,alt] lists on None separators into chains."""
    chains = []
    current = []
    for pt in points or []:
        if pt is None or pt[0] is None:
            if len(current) >= 2:
                chains.append(current)
            current = []
            continue
        # Skip mouse-move preview duplicates tagged as mouseMoveEvent
        if len(pt) > 3 and pt[3] == MOUSE_MOVE_EVENT:
            # Keep live preview tip for current chain
            if current:
                # Replace last preview tip if present
                if len(current[-1]) > 3 and current[-1][3] == MOUSE_MOVE_EVENT:
                    current[-1] = pt
                else:
                    current.append(pt)
            continue
        current.append(pt)
    if len(current) >= 2:
        chains.append(current)
    return chains


def _format_length_label(meters):
    """Format a distance in meters as a human-readable string (m or km)."""
    from QGISFMV.utils.formatting import format_length

    return format_length(meters)


def _format_area_label(area_m2):
    """Format an area in square meters as a human-readable string (m2, ha, or km2)."""
    from QGISFMV.utils.formatting import format_area

    return format_area(area_m2)


def SyncMeasureDistanceOnMap(points, group_name=None):
    """Rebuild Measure Distance layer features from video measure vertices."""
    from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance

    key = _base()._draw_group(group_name)
    layer = qgsu.selectLayerByName(_base().MeasureDistance_lyr, key)
    if layer is None:
        return
    provider = layer.dataProvider()
    ids = [f.id() for f in layer.getFeatures()]
    if ids:
        provider.deleteFeatures(ids)

    features = []
    for chain in _split_measure_chains(points):
        pts = [QgsPointXY(float(p[0]), float(p[1])) for p in chain]
        if len(pts) < 2:
            continue
        total = 0.0
        for i in range(len(chain) - 1):
            total += float(
                _geo_distance(
                    (chain[i][0], chain[i][1]),
                    (chain[i + 1][0], chain[i + 1][1]),
                )
            )
        feat = QgsFeature(layer.fields())
        feat.setGeometry(QgsGeometry.fromPolylineXY(pts))
        label = _format_length_label(total)
        feat.setAttributes([float(total), label, len(pts) - 1])
        features.append(feat)
    if features:
        provider.addFeatures(features)
    _base()._refresh_memory_layer(layer)


def SyncMeasureAreaOnMap(points, group_name=None):
    """Rebuild Measure Area layer features from video measure vertices."""
    from QGISFMV.geo.QgsGeoUtils import polygon_area as _geo_polygon_area

    key = _base()._draw_group(group_name)
    layer = qgsu.selectLayerByName(_base().MeasureArea_lyr, key)
    if layer is None:
        return
    provider = layer.dataProvider()
    ids = [f.id() for f in layer.getFeatures()]
    if ids:
        provider.deleteFeatures(ids)

    features = []
    for chain in _split_measure_chains(points):
        if len(chain) < 3:
            continue
        ring = [QgsPointXY(float(p[0]), float(p[1])) for p in chain]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        try:
            area_m2 = float(_geo_polygon_area(chain))
        except Exception as exc:
            log.debug("polygon area calculation failed: %s", exc)
            area_m2 = 0.0
        feat = QgsFeature(layer.fields())
        feat.setGeometry(QgsGeometry.fromPolygonXY([ring]))
        label = _format_area_label(area_m2)
        feat.setAttributes([area_m2, label, len(chain)])
        features.append(feat)
    if features:
        provider.addFeatures(features)
    _base()._refresh_memory_layer(layer)
