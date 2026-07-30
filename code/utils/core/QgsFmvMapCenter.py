# -*- coding: utf-8 -*-
"""Map-canvas centering/follow helpers, extracted from QgsFmvUtils.py.

Owns the "follow platform / footprint / frame center" logic used by the
Map Center menu action (``followMapCenter``) and the one-shot
``centerCanvasOnLayer`` helper. Session state (``gv``) and the FMV
layer-name constants still live in QgsFmvUtils.py — both are refreshed live
by QgsFmvSettings (``gv`` via ``setCenterMode``/``ensureGlobalState``, the
layer names via ``setattr`` in ``reloadRuntime()``) — so this module reads
them through a module reference (``_base()``) instead of importing by
value, mirroring the pattern already used by QgsFmvDrawLayers.py.
"""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
    QgsWkbTypes,
)

from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

# Cinematic (smoothed) follow — module state for lerp between centers.
_cinematic_follow = False
_cinematic_last = None  # QgsPointXY or None


def set_cinematic_follow(enabled):
    """Enable/disable smoothed map follow (lerp toward target each tick)."""
    global _cinematic_follow, _cinematic_last
    _cinematic_follow = bool(enabled)
    if not _cinematic_follow:
        _cinematic_last = None
    return _cinematic_follow


def is_cinematic_follow():
    return _cinematic_follow


def _base():
    """Lazily resolve QgsFmvUtils to dodge the circular import at load time.

    QgsFmvUtils.py re-exports this module's functions for backward
    compatibility, so importing it eagerly here (at module scope) could
    fail if this module happens to load first. Deferring the import to
    call time guarantees both modules are fully initialized.
    """
    import QGISFMV.utils.core.QgsFmvUtils as _mod

    return _mod


def _transformExtentToCanvas(extent, src_crs, iface):
    """Transform a layer extent to the map canvas CRS."""
    if extent is None or extent.isNull() or extent.isEmpty():
        return None
    canvas = iface.mapCanvas()
    dest_crs = canvas.mapSettings().destinationCrs()
    if src_crs == dest_crs:
        return extent
    xform = QgsCoordinateTransform(src_crs, dest_crs, QgsProject.instance())
    return xform.transformBoundingBox(extent)


def _layerExtentInCanvasCrs(layer, iface):
    """Return the latest feature extent transformed to the canvas CRS."""
    if layer is None:
        return None
    feature = _latest_layer_feature(layer)
    if feature is None or not feature.isValid():
        if layer.featureCount() == 0:
            return None
        extent = layer.extent()
        if extent is None or extent.isNull() or extent.isEmpty():
            return None
        return _transformExtentToCanvas(extent, layer.crs(), iface)

    geom = feature.geometry()
    if geom is None or geom.isEmpty():
        return None
    return _transformExtentToCanvas(geom.boundingBox(), layer.crs(), iface)


def _transformPointToCanvas(point, src_crs, iface):
    """Transform a map point to the canvas CRS."""
    if point is None or iface is None:
        return None
    canvas = iface.mapCanvas()
    dest_crs = canvas.mapSettings().destinationCrs()
    if src_crs == dest_crs:
        return QgsPointXY(point.x(), point.y())
    xform = QgsCoordinateTransform(src_crs, dest_crs, QgsProject.instance())
    transformed = xform.transform(QgsPointXY(point.x(), point.y()))
    return QgsPointXY(transformed.x(), transformed.y())


def _latest_layer_feature(layer):
    """Return the most recently added feature in a vector layer (O(1) for single-feature layers)."""
    if layer is None:
        return None
    for feature in layer.getFeatures():
        return feature
    return None


def _layer_center_on_canvas(layer, iface):
    """Return the current center point for a layer in canvas coordinates."""
    if layer is None or iface is None:
        return None

    feature = _latest_layer_feature(layer)
    if feature is not None and feature.isValid():
        geom = feature.geometry()
        if geom is not None and not geom.isEmpty():
            if geom.type() == QgsWkbTypes.PointGeometry:
                point = geom.asPoint()
            else:
                point = geom.centroid().asPoint()
            return _transformPointToCanvas(point, layer.crs(), iface)

    extent = layer.extent()
    if extent is not None and not extent.isNull() and not extent.isEmpty():
        center = _transformExtentToCanvas(extent, layer.crs(), iface)
        if center is not None:
            return center.center()
    return None


def _center_fallback_point(center_mode, iface):
    """Fallback map center from live telemetry when the layer has no geometry yet."""
    gv = _base().gv
    if gv is None or iface is None:
        return None
    if center_mode == 1:
        lat = gv.getSensorLatitude()
        lon = gv.getSensorLongitude()
    elif center_mode == 3:
        lat = gv.getFrameCenterLat()
        lon = gv.getFrameCenterLon()
    else:
        return None
    if lat is None or lon is None:
        return None
    point = QgsPointXY(float(lon), float(lat))
    return _transformPointToCanvas(
        point, QgsCoordinateReferenceSystem("EPSG:4326"), iface
    )


def followMapCenter(iface, centerMode, groupName):
    """
    Follow platform (1), footprint (2), or frame center/target (3).

    When a mode is active the map is re-centered on every metadata update so
    manual panning is overridden until the user unchecks the menu action.
    """
    if iface is None or not centerMode:
        return False

    from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get

    base = _base()
    platform_name = settings_get("LAYERS", "platform_lyr", base.Platform_lyr)
    footprint_name = settings_get("LAYERS", "footprint_lyr", base.Footprint_lyr)
    target_name = settings_get("LAYERS", "framecenter_lyr", base.FrameCenter_lyr)

    canvas = iface.mapCanvas()
    recentered = False

    global _cinematic_last

    if centerMode == 1:
        lyr = qgsu.selectLayerByName(platform_name, groupName)
        center = _layer_center_on_canvas(lyr, iface) or _center_fallback_point(1, iface)
        if center is not None:
            canvas.setCenter(_maybe_lerp_center(canvas, center))
            recentered = True
    elif centerMode == 2:
        lyr = qgsu.selectLayerByName(footprint_name, groupName)
        extent = _layerExtentInCanvasCrs(lyr, iface)
        if extent is not None:
            margin = max(extent.width(), extent.height()) * 0.5
            if margin <= 0:
                margin = canvas.extent().width() * 0.05
            # Footprint mode keeps hard extent (cinematic lerp is for point modes).
            canvas.setExtent(extent.buffered(margin))
            recentered = True
            _cinematic_last = None
    elif centerMode == 3:
        lyr = qgsu.selectLayerByName(target_name, groupName)
        center = _layer_center_on_canvas(lyr, iface) or _center_fallback_point(3, iface)
        if center is not None:
            canvas.setCenter(_maybe_lerp_center(canvas, center))
            recentered = True

    if recentered:
        canvas.refresh()
    return recentered


def _maybe_lerp_center(canvas, target):
    """Return target, or a lerped point when cinematic follow is on."""
    global _cinematic_last
    if not _cinematic_follow:
        _cinematic_last = QgsPointXY(target.x(), target.y())
        return target
    try:
        from QGISFMV.utils.constants import CINEMATIC_FOLLOW_ALPHA

        alpha = float(CINEMATIC_FOLLOW_ALPHA)
        cur = canvas.center()
        if _cinematic_last is not None:
            cur = _cinematic_last
        nx = cur.x() + (target.x() - cur.x()) * alpha
        ny = cur.y() + (target.y() - cur.y()) * alpha
        out = QgsPointXY(nx, ny)
        _cinematic_last = out
        return out
    except Exception:
        return target


def centerCanvasOnLayer(iface, layer_name, groupName):
    """One-shot center/zoom for the requested FMV layer."""
    from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get

    base = _base()
    mode_map = {
        settings_get("LAYERS", "platform_lyr", base.Platform_lyr): 1,
        settings_get("LAYERS", "footprint_lyr", base.Footprint_lyr): 2,
        settings_get("LAYERS", "framecenter_lyr", base.FrameCenter_lyr): 3,
    }
    mode = mode_map.get(layer_name)
    if not mode:
        return False
    return followMapCenter(iface, mode, groupName)
