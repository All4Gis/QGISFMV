# -*- coding: utf-8 -*-
"""QGIS FMV map layers: group/layer creation, generic layer helpers, object
tracking, and platform-icon handling.

Telemetry-driven Update* functions live in QgsFmvTelemetryLayers.py; default
symbology (SetDefault*Style, 3D renderers) lives in QgsFmvLayerDefaults.py.
Both are re-exported below for backward-compatible imports, and both read
this module's live layer-name constants / ``groupName`` / style-cache
globals through a module reference (their own ``_base()`` helper) since
QgsFmvSettings.reloadRuntime() refreshes those constants with ``setattr``.
"""
import os
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import QCoreApplication, QSettings

from QGISFMV.utils.settings.QgsFmvSettings import (
    get_layer,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from qgis.core import (
    QgsMarkerSymbol,
    QgsLayerTreeLayer,
    QgsField,
    QgsFields,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsPoint,
    QgsLineString,
)

from qgis.utils import iface
from QGISFMV.utils.layers.QgsFmvStyles import FmvLayerStyles as S
from QGISFMV.utils.layers.QgsFmvLayerStyleStore import (
    apply_or_default as applyLayerStyle,
    ensure_watch as ensureLayerStyleWatch,
)

# Backward-compatible re-exports: telemetry Update* functions and their
# per-group caches now live in QgsFmvTelemetryLayers.py. The caches are
# imported by reference (mutable dicts) so existing callers/tests that poke
# ``QgsFmvLayers._trajectory_active_feature`` etc. directly keep working.
from QGISFMV.utils.layers.QgsFmvTelemetryLayers import (  # noqa: E402,F401
    UpdateFootPrintData,
    UpdateBeamsData,
    UpdateTrajectoryData,
    UpdateFrameAxisData,
    UpdateFrameCenterData,
    UpdatePlatformData,
    _trajectory_active_feature,
    _beam_feature_ids,
    reset_caches as _reset_telemetry_caches,
)

# Backward-compatible re-exports: default symbology now lives in
# QgsFmvLayerDefaults.py, kept importable from here for existing callers.
from QGISFMV.utils.layers.QgsFmvLayerDefaults import (  # noqa: E402,F401
    SetDefaultFootprintStyle,
    SetDefaultFootprint3DStyle,
    SetDefaultTrajectoryStyle,
    SetDefaultObjectTrackStyle,
    SetDefaultObjectPositionStyle,
    SetDefaultDetectionsStyle,
    SetDefaultDetectionTrailStyle,
    SetDefaultPlatformStyle,
    SetDefaultPlatform3DStyle,
    SetDefaultTrajectory3DStyle,
    SetDefaultFrameAxis3DStyle,
    SetDefaultBeams3DStyle,
    SetDefaultFrameCenterStyle,
    SetDefaultFrameCenter3DStyle,
    SetDefaultFrameAxisStyle,
    SetDefaultMilitarySymbolStyle,
    SetDefaultPointStyle,
    SetDefaultLineStyle,
    SetDefaultPolygonStyle,
    SetDefaultMeasureDistanceStyle,
    SetDefaultMeasureAreaStyle,
    SetDefaultBeamsStyle,
    ensure_fmv_3d_renderers,
    RestoreDefaultLayerStyles,
)

Platform_lyr = get_layer("platform_lyr")
Beams_lyr = get_layer("beams_lyr")
Footprint_lyr = get_layer("footprint_lyr")
FrameCenter_lyr = get_layer("framecenter_lyr")
FrameAxis_lyr = get_layer("frameaxis_lyr")
Point_lyr = get_layer("point_lyr")
Symbol_lyr = get_layer("symbol_lyr")
Line_lyr = get_layer("line_lyr")
Polygon_lyr = get_layer("polygon_lyr")
ObjectTrack_lyr = get_layer("objecttrack_lyr")
ObjectPosition_lyr = get_layer("objectposition_lyr")
Detections_lyr = get_layer("detections_lyr")
DetectionTrail_lyr = get_layer("detectiontrail_lyr")
MeasureDistance_lyr = get_layer("measuredistance_lyr")
MeasureArea_lyr = get_layer("measurearea_lyr")
frames_g = get_layer("frames_g")
Trajectory_lyr = get_layer("trajectory_lyr")
epsg = get_layer("epsg")
groupName = None

encoding = "utf-8"

_layerreg = QgsProject.instance()
crtSensorSrc = crtSensorSrc2 = crtPltTailNum = "DEFAULT"
TRAJECTORY_MIN_STEP_METERS = 5.0
TRAJECTORY_LOOP_BREAK_METERS = 150.0
OBJECT_TRACK_MIN_STEP_METERS = 2.5
_object_track_active_feature = {}
_last_user_platform_icon = None
_cached_platform_icon_path = None
_cached_platform_icon_valid = False


def _first_feature_id(layer):
    """Return the first feature id in a layer, or None."""
    if layer is None:
        return None
    for feature in layer.getFeatures():
        return feature.id()
    return None


def _sorted_feature_ids(layer):
    """Return sorted feature ids for a vector layer."""
    if layer is None:
        return []
    return sorted(feature.id() for feature in layer.getFeatures())


def _latest_feature_id(layer):
    """Return the last feature id in a vector layer, or None."""
    if layer is None:
        return None
    last = None
    for feature in layer.getFeatures():
        last = feature.id()
    return last


def resetLayerCaches(group_name=None):
    """Clear trajectory / beam / object-track caches for one group or all."""
    global groupName
    key = group_name if group_name is not None else groupName
    if key:
        _object_track_active_feature.pop(key, None)
    else:
        _object_track_active_feature.clear()
    _reset_telemetry_caches(key)


def beginNewTrajectorySegment(group_name=None):
    """Start a new trajectory line on the next telemetry update (e.g. video loop)."""
    global groupName
    key = group_name if group_name is not None else groupName
    if key:
        _trajectory_active_feature[key] = None


# Field type identifiers for QGIS 4 / Qt6.
from qgis.PyQt.QtCore import QMetaType

TYPE_MAP = {
    str: QMetaType.Type.QString,
    float: QMetaType.Type.Double,
    int: QMetaType.Type.Int,
    bool: QMetaType.Type.Bool,
}

Point = "Point"
PointZ = "PointZ"
LineZ = "LineStringZ"
Line = "LineString"
Polygon = "Polygon"
PolygonZ = "PolygonZ"


def _draw_group(group_name=None):
    """Resolve the video group used by draw helpers."""
    return group_name if group_name is not None else groupName


def _truncate_layer(layer_name, group_name=None):
    """Remove all features from a memory layer."""
    layer = qgsu.selectLayerByName(layer_name, group_name)
    if layer is None:
        return
    layer.startEditing()
    layer.dataProvider().truncate()
    CommonLayer(layer)


def _update_object_position_layer(track_id, backend, lon, lat, alt):
    """Keep a single point feature for the live tracked object."""
    posLyr = qgsu.selectLayerByName(ObjectPosition_lyr, groupName)
    if posLyr is None:
        return
    _upsert_single_object_position_feature(
        posLyr,
        [int(track_id), str(backend or ""), lon, lat, alt],
        QgsGeometry.fromPointXY(QgsPointXY(lon, lat)),
    )


def _upsert_single_object_position_feature(layer, attrs, geometry):
    """Create the first feature or update an existing one in a single-feature memory layer."""
    if layer.featureCount() == 0:
        layer.startEditing()
        feature = QgsFeature(layer.fields())
        feature.setAttributes(attrs)
        feature.setGeometry(geometry)
        layer.addFeatures([feature])
        CommonLayer(layer)
    else:
        fid = _first_feature_id(layer)
        if fid is None:
            return
        provider = layer.dataProvider()
        provider.changeAttributeValues({fid: {i: v for i, v in enumerate(attrs)}})
        provider.changeGeometryValues({fid: geometry})
        _refresh_memory_layer(layer)


def BeginObjectTrack(track_id, backend=""):
    """Mark that the next UpdateObjectTrack should open a new line feature."""
    if groupName:
        _object_track_active_feature[groupName] = None
    return None


def _add_object_track_segment(trackLyr, point, lon, lat, alt, track_id, backend):
    """Create a new Object Track line starting at point."""
    trackLyr.startEditing()
    feature = QgsFeature()
    feature.setAttributes([int(track_id), str(backend or ""), lon, lat, alt])
    line = QgsLineString()
    line.addVertex(point)
    feature.setGeometry(QgsGeometry(line))
    trackLyr.addFeatures([feature])
    CommonLayer(trackLyr)
    feature_id = _latest_feature_id(trackLyr)
    if groupName:
        _object_track_active_feature[groupName] = feature_id
    return feature_id


def UpdateObjectTrack(lon, lat, alt, track_id, backend=""):
    """Append a georeferenced sample to the active object track (throttled)."""
    from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance

    trackLyr = qgsu.selectLayerByName(ObjectTrack_lyr, groupName)
    if trackLyr is None or lon is None or lat is None:
        return False

    try:
        lon, lat = float(lon), float(lat)
        alt = float(alt) if alt is not None else 0.0
    except (TypeError, ValueError):
        return False

    point = QgsPoint(lon, lat, alt)
    segment_key = groupName
    force_new = (
        segment_key in _object_track_active_feature
        and _object_track_active_feature[segment_key] is None
    )
    feature_id = _object_track_active_feature.get(segment_key)

    if force_new or feature_id is None or not trackLyr.getFeature(feature_id).isValid():
        feature_id = _add_object_track_segment(
            trackLyr, point, lon, lat, alt, track_id, backend
        )
        _update_object_position_layer(track_id, backend, lon, lat, alt)
        return feature_id is not None

    feature = trackLyr.getFeature(feature_id)
    const_line = feature.geometry().constGet() if feature.geometry() else None
    if isinstance(const_line, QgsLineString):
        line = QgsLineString(const_line)
    else:
        line = QgsLineString()

    if line.numPoints() > 0:
        last = line.pointN(line.numPoints() - 1)
        if _geo_distance((last.x(), last.y()), (lon, lat)) < OBJECT_TRACK_MIN_STEP_METERS:
            _update_object_position_layer(track_id, backend, lon, lat, alt)
            return True

    provider = trackLyr.dataProvider()
    line.addVertex(point)
    provider.changeGeometryValues({feature_id: QgsGeometry(line)})
    provider.changeAttributeValues(
        {
            feature_id: {
                0: int(track_id),
                1: str(backend or ""),
                2: lon,
                3: lat,
                4: alt,
            }
        }
    )
    _refresh_memory_layer(trackLyr)
    _update_object_position_layer(track_id, backend, lon, lat, alt)
    return True


def ClearObjectTracks(group_name=None):
    """Remove all object-track geometry from the current video group."""
    key = _draw_group(group_name)
    for lyr_name in (ObjectTrack_lyr, ObjectPosition_lyr):
        _truncate_layer(lyr_name, key)
    if key:
        _object_track_active_feature.pop(key, None)


def SetcrtSensorSrc():
    """Set Style based on Sensor type"""
    global crtSensorSrc, crtSensorSrc2
    crtSensorSrc = crtSensorSrc2 = "DEFAULT"


def SetcrtPltTailNum():
    """Set Style based on Platform Type Number"""
    global crtPltTailNum, _last_user_platform_icon, _cached_platform_icon_valid, _cached_platform_icon_path
    crtPltTailNum = "DEFAULT"
    _last_user_platform_icon = None
    _cached_platform_icon_valid = False
    _cached_platform_icon_path = None


# Must match code/ui/resources.qrc and Platform tab items in ui_FmvSettings.ui
PLATFORM_ICON_FILES = (
    "platform_default.svg",
    "plat_super_puma.svg",
    "plat_N97826.svg",
    "plat_VH-ZXX.svg",
    "plat_ADS15.svg",
    "plat_dji.svg",
    "plat_military_jet.svg",
    "plat_military_heli.svg",
    "plat_uav_fw.svg",
    "plat_reaper.svg",
    "plat_tank.svg",
    "plat_ship.svg",
    "plat_copter_news.svg",
)


def platform_icon_resource(filename):
    """Qt resource path for a platform SVG (embedded via resources.qrc)."""
    return ":/imgFMV/images/platforms/%s" % filename


def _platform_icon_label(filename):
    """Return a human-readable label for a platform icon filename."""
    stem = os.path.splitext(filename)[0]
    if stem == "platform_default":
        return "Default"
    if stem.startswith("plat_"):
        stem = stem[5:]
    return stem.replace("_", " ").replace("-", " ").title()


def _is_platform_icon_path(icon_path):
    """True if path is a Qt resource or an existing file."""
    if not icon_path:
        return False
    path = str(icon_path)
    if path.startswith(":/"):
        return True
    return os.path.isfile(path)


def list_platform_icon_choices():
    """Return platform icons from Qt resources (same set as FMV Settings / qrc)."""
    return [
        {
            "label": _platform_icon_label(filename),
            "path": platform_icon_resource(filename),
            "filename": filename,
        }
        for filename in PLATFORM_ICON_FILES
    ]


def get_user_platform_icon(settings=None):
    """Return the user-selected platform icon path, or None."""
    global _cached_platform_icon_path, _cached_platform_icon_valid

    if _cached_platform_icon_valid:
        return _cached_platform_icon_path

    from QGISFMV.utils.core.QgsFmvUtils import getNameSpace

    store = settings or QSettings()
    icon_path = store.value(getNameSpace() + "/Options/platform/icon")
    if icon_path:
        icon_path = str(icon_path)
        base = os.path.basename(icon_path)
        # Prefer Qt resources (works after plugin install / zip); migrate old file paths.
        if base in PLATFORM_ICON_FILES:
            icon_path = platform_icon_resource(base)
        if _is_platform_icon_path(icon_path):
            _cached_platform_icon_path = icon_path
            _cached_platform_icon_valid = True
            return icon_path
    _cached_platform_icon_path = None
    _cached_platform_icon_valid = True
    return None


def set_user_platform_icon(icon_path, settings=None):
    """Save the user-selected platform icon path to QSettings."""
    global _cached_platform_icon_path, _cached_platform_icon_valid
    from QGISFMV.utils.core.QgsFmvUtils import getNameSpace

    store = settings or QSettings()
    store.setValue(getNameSpace() + "/Options/platform/icon", icon_path)
    _cached_platform_icon_valid = False
    _cached_platform_icon_path = None


def _refresh_layer_tree_style(layer):
    """Refresh map and layer-tree legend after a symbol change."""
    if layer is None:
        return
    layer.triggerRepaint()
    try:
        if iface is not None:
            iface.layerTreeView().refreshLayerSymbology(layer.id())
    except Exception as exc:
        log.debug("Layer tree symbology refresh failed: %s", exc)


def applyPlatformIconStyle(layer, icon_path):
    """Apply a custom SVG/PNG icon to the platform layer."""
    if layer is None or not icon_path:
        return
    base = S.getPlatform("DEFAULT")
    svg_style = {
        "name": icon_path,
        "outline": base["OUTLINE"],
        "outline-width": base["OUTLINE_WIDTH"],
        "size": base["SIZE"],
    }
    symbol_layer = QgsSvgMarkerSymbolLayer.create(svg_style)
    symbol = QgsMarkerSymbol([symbol_layer])
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    _refresh_layer_tree_style(layer)


def refresh_platform_icon_layers(group_name=None):
    """Re-apply the user-selected platform icon to the active platform layer."""
    global _last_user_platform_icon

    icon_path = get_user_platform_icon()
    if not icon_path:
        return False

    target_group = group_name or groupName
    if not target_group:
        return False

    platform_lyr = qgsu.selectLayerByName(Platform_lyr, target_group)
    if platform_lyr is None:
        return False

    applyPlatformIconStyle(platform_lyr, icon_path)
    CommonLayer(platform_lyr)
    _last_user_platform_icon = icon_path
    return True


def CommonLayer(value):
    """Common commands Layers"""
    if value is None:
        return
    if value.isEditable():
        try:
            value.commitChanges()
        except Exception as exc:
            try:
                value.rollBack()
            except Exception as rollback_exc:
                log.debug(
                    "Layer rollback after commit failure failed: %s", rollback_exc
                )
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvLayers", "Layer commit failed: "),
                str(exc),
                onlyLog=True,
            )
            return
    value.updateExtents()
    _refresh_layer_tree_style(value)
    value.triggerRepaint()


def _refresh_memory_layer(layer):
    """Refresh display after direct dataProvider edits (no edit session)."""
    if layer is None:
        return
    if layer.isEditable():
        try:
            layer.rollBack()
        except Exception as exc:
            log.debug("Memory layer rollback failed for %s: %s", layer.name(), exc)
    layer.updateExtents()
    _refresh_layer_tree_style(layer)
    layer.triggerRepaint()


def CreateGroupByName(name=frames_g, visible=False):
    """Create subgroup for georeferenced frames if it does not exist."""
    global groupName
    root = _layerreg.layerTreeRoot()
    videogroup = root.findGroup(groupName)
    if videogroup is None:
        return
    group = videogroup.findGroup(name)
    if group is None:
        group = videogroup.insertGroup(-1, name)
    group.setItemVisibilityCheckedRecursive(visible)
    group.setExpanded(visible)


def RemoveGroupByName(name=frames_g):
    """Remove a layer-tree group and all map layers it contains (recursive)."""
    root = _layerreg.layerTreeRoot()
    group = root.findGroup(name)
    if group is None:
        return
    layer_ids = [tree_layer.layerId() for tree_layer in group.findLayers()]
    if layer_ids:
        _layerreg.removeMapLayers(layer_ids)
    # Group node may remain empty after layer removal — drop it if still present.
    group = root.findGroup(name)
    if group is not None:
        root.removeChildNode(group)


def CreateVideoLayers(ele, name):
    """Create all FMV map layers for a video group."""
    global groupName
    groupName = name

    # Watch existing layers for style changes.
    _watch_existing_layers()

    # Remove corrupt memory layers that need recreation.
    for lyr_name in (Footprint_lyr, Beams_lyr, Trajectory_lyr, FrameAxis_lyr,
                     Platform_lyr, FrameCenter_lyr):
        _remove_invalid_memory_layer(lyr_name, groupName)

    # Layer definitions: (name, factory, fields, geom_type, style_fn, style_args)
    layer_defs = [
        (Footprint_lyr, newPolygonsLayer, _FOOTPRINT_FIELDS, PolygonZ,
         SetDefaultFootprintStyle, ("DEFAULT",)),
        (Beams_lyr, newLinesLayer,
         ["longitude", "latitude", "altitude", "Corner Longitude", "Corner Latitude"],
         LineZ, SetDefaultBeamsStyle, ("DEFAULT",)),
        (Trajectory_lyr, newLinesLayer,
         ["longitude", "latitude", "altitude"], LineZ,
         SetDefaultTrajectoryStyle, ()),
        (FrameAxis_lyr, newLinesLayer,
         ["longitude", "latitude", "altitude", "Corner Longitude",
          "Corner Latitude", "Corner altitude"],
         LineZ, SetDefaultFrameAxisStyle, ("DEFAULT",)),
        (Platform_lyr, newPointsLayer,
         ["longitude", "latitude", "altitude"], PointZ,
         SetDefaultPlatformStyle, ("DEFAULT",)),
        (Point_lyr, newPointsLayer,
         ["number", "longitude", "latitude", "altitude"], Point,
         SetDefaultPointStyle, ()),
        (Symbol_lyr, newPointsLayer,
         ["number", "symbol_id", "unit_name", "longitude", "latitude", "altitude"],
         Point, SetDefaultMilitarySymbolStyle, ()),
        (FrameCenter_lyr, newPointsLayer,
         ["longitude", "latitude", "altitude"], Point,
         SetDefaultFrameCenterStyle, ()),
        (Line_lyr, newLinesLayer, [], Line,
         SetDefaultLineStyle, ()),
        (Polygon_lyr, newPolygonsLayer,
         ["Centroid_longitude", "Centroid_latitude", "Centroid_altitude", "Area"],
         Polygon, SetDefaultPolygonStyle, ()),
        (ObjectTrack_lyr, newLinesLayer,
         ["track_id", "backend", "longitude", "latitude", "altitude"], LineZ,
         SetDefaultObjectTrackStyle, ()),
        (ObjectPosition_lyr, newPointsLayer,
         ["track_id", "backend", "longitude", "latitude", "altitude"], PointZ,
         SetDefaultObjectPositionStyle, ()),
        (Detections_lyr, newPointsLayer,
         ["track_id", "class", ("score", float), "longitude", "latitude", "altitude"],
         Point, SetDefaultDetectionsStyle, ()),
        (DetectionTrail_lyr, newPointsLayer,
         ["track_id", "class", ("score", float), "longitude", "latitude", "altitude",
          ("time_sec", float)],
         Point, SetDefaultDetectionTrailStyle, ()),
        (MeasureDistance_lyr, newLinesLayer,
         [("length_m", float), "label", ("segments", int)], Line,
         SetDefaultMeasureDistanceStyle, ()),
        (MeasureArea_lyr, newPolygonsLayer,
         [("area_m2", float), "label", ("vertices", int)], Polygon,
         SetDefaultMeasureAreaStyle, ()),
    ]

    for lyr_name, factory, fields, geom_type, style_fn, style_args in layer_defs:
        _create_layer_if_missing(lyr_name, factory, fields, geom_type, style_fn, style_args)

    ensure_fmv_3d_renderers(groupName)
    QApplication.processEvents()


def _watch_existing_layers():
    """Register style-change watchers on layers that already exist."""
    for lyr_name in (Footprint_lyr, Beams_lyr, Trajectory_lyr, FrameAxis_lyr,
                     Platform_lyr, Point_lyr, Symbol_lyr, FrameCenter_lyr,
                     Line_lyr, Polygon_lyr, ObjectTrack_lyr, ObjectPosition_lyr,
                     Detections_lyr, DetectionTrail_lyr,
                     MeasureDistance_lyr, MeasureArea_lyr):
        existing = qgsu.selectLayerByName(lyr_name, groupName)
        if existing is not None:
            ensureLayerStyleWatch(existing, lyr_name)


def ensure_detections_layer():
    """Create the AI Detections layer in the current video group if missing."""
    if not groupName:
        return None
    existing = qgsu.selectLayerByName(Detections_lyr, groupName)
    if existing is not None:
        return existing
    _create_layer_if_missing(
        Detections_lyr,
        newPointsLayer,
        ["track_id", "class", ("score", float), "longitude", "latitude", "altitude"],
        Point,
        SetDefaultDetectionsStyle,
        (),
    )
    return qgsu.selectLayerByName(Detections_lyr, groupName)


def ensure_detection_trail_layer():
    """Create the accumulating AI Detection Trail layer if missing."""
    if not groupName:
        return None
    existing = qgsu.selectLayerByName(DetectionTrail_lyr, groupName)
    if existing is not None:
        return existing
    _create_layer_if_missing(
        DetectionTrail_lyr,
        newPointsLayer,
        [
            "track_id",
            "class",
            ("score", float),
            "longitude",
            "latitude",
            "altitude",
            ("time_sec", float),
        ],
        Point,
        SetDefaultDetectionTrailStyle,
        (),
    )
    return qgsu.selectLayerByName(DetectionTrail_lyr, groupName)


def _create_layer_if_missing(lyr_name, factory, fields, geom_type, style_fn, style_args):
    """Create a layer if it doesn't exist in the current group, apply style, and add to map."""
    if qgsu.selectLayerByName(lyr_name, groupName) is not None:
        return
    layer = factory(None, fields, epsg, lyr_name, geom_type)
    applyLayerStyle(layer, lyr_name, style_fn, *style_args)
    addLayerNoCrsDialog(layer, group=groupName)


_FOOTPRINT_FIELDS = [
    "clon1",
    "clat1",
    "clon2",
    "clat2",
    "clon3",
    "clat3",
    "clon4",
    "clat4",
]


def _memory_layer_source_invalid(layer):
    """Return True when a memory layer's source string looks corrupted or oversized."""
    try:
        source = layer.source() or ""
        if len(source) > 240:
            return True
        return "field=" in source
    except Exception as exc:
        log.debug("memory layer source check failed: %s", exc)
        return False


def _remove_invalid_memory_layer(layer_name, group_name):
    existing = qgsu.selectLayerByName(layer_name, group_name)
    if existing is not None and _memory_layer_source_invalid(existing):
        QgsProject.instance().removeMapLayer(existing.id())


def addLayer(layer, loadInLegend=True, group=None, isSubGroup=False):
    """
    Add one or several layers to the QGIS session and layer registry.
    @param layer: The layer object or list with layers  to add the QGIS layer registry and session.
    @param loadInLegend: True if this layer should be added to the legend.
    :return: The added layer
    """

    global groupName

    if not hasattr(layer, "__iter__"):
        layer = [layer]
    if group is not None:
        _layerreg.addMapLayers(layer, False)
        root = _layerreg.layerTreeRoot()

        if isSubGroup:
            vg = root.findGroup(groupName)
            if vg is None:
                _layerreg.addMapLayers(layer, loadInLegend)
                return layer
            g = vg.findGroup(group)
            if g is None:
                g = vg.insertGroup(-1, group)
        else:
            g = root.findGroup(group)
            if g is None:
                g = root.insertGroup(0, group)

        g.insertChildNode(0, QgsLayerTreeLayer(layer[0]))

    else:
        _layerreg.addMapLayers(layer, loadInLegend)
    return layer


def addLayerNoCrsDialog(layer, loadInLegend=True, group=None, isSubGroup=False):
    """
    Tries to add a layer from layer object
    Same as the addLayer method, but it does not ask for CRS, regardless of current
    configuration in QGIS settings
    """

    settings = QSettings()
    prjSetting3 = settings.value("/Projections/defaultBehavior")
    try:
        settings.setValue("/Projections/defaultBehavior", "")
        layer = addLayer(layer, loadInLegend, group, isSubGroup)
    finally:
        settings.setValue("/Projections/defaultBehavior", prjSetting3)
    QApplication.processEvents()
    return layer


def _toQgsField(f):
    """Convert a field name or tuple to a QgsField object."""
    if isinstance(f, QgsField):
        return f
    if isinstance(f, str):
        return QgsField(f, TYPE_MAP[str])
    return QgsField(f[0], TYPE_MAP.get(f[1], TYPE_MAP[str]))


class LayerFactory:
    """Factory for creating QGIS memory vector layers."""

    @staticmethod
    def create(filename, fields, geometry_type, crs, name=None, encoding=encoding):
        """Create a vector layer of the specified geometry type."""
        return newVectorLayer(filename, fields, geometry_type, crs, name, encoding)

    @staticmethod
    def point(filename, fields, crs, name=None, encoding=encoding):
        """Create a point layer."""
        return newVectorLayer(filename, fields, Point, crs, name, encoding)

    @staticmethod
    def point_z(filename, fields, crs, name=None, encoding=encoding):
        """Create a 3D point layer."""
        return newVectorLayer(filename, fields, PointZ, crs, name, encoding)

    @staticmethod
    def line(filename, fields, crs, name=None, encoding=encoding):
        """Create a line layer."""
        return newVectorLayer(filename, fields, Line, crs, name, encoding)

    @staticmethod
    def line_z(filename, fields, crs, name=None, encoding=encoding):
        """Create a 3D line layer."""
        return newVectorLayer(filename, fields, LineZ, crs, name, encoding)

    @staticmethod
    def polygon(filename, fields, crs, name=None, encoding=encoding):
        """Create a polygon layer."""
        return newVectorLayer(filename, fields, Polygon, crs, name, encoding)

    @staticmethod
    def polygon_z(filename, fields, crs, name=None, encoding=encoding):
        """Create a 3D polygon layer."""
        return newVectorLayer(filename, fields, PolygonZ, crs, name, encoding)


def newPointsLayer(
    filename, fields, crs, name=None, geometryType=Point, encoding=encoding
):
    """Create new Point Layer"""
    return LayerFactory.create(filename, fields, geometryType, crs, name, encoding)


def newLinesLayer(
    filename, fields, crs, name=None, geometryType=Line, encoding=encoding
):
    """Create new Line Layer"""
    return LayerFactory.create(filename, fields, geometryType, crs, name, encoding)


def newPolygonsLayer(filename, fields, crs, name=None, geometryType=Polygon, encoding=encoding):
    """Create new Polygon Layer"""
    return LayerFactory.create(filename, fields, geometryType, crs, name, encoding)


def newVectorLayer(filename, fields, geometryType, crs, name=None, encoding=encoding):
    """
    Creates a new vector layer
    @param filename: The filename to store the file. The extensions determines the type of file.
    If extension is not among the supported ones, a shapefile will be created and the file will
    get an added '.shp' to its path.
    If the filename is None, a memory layer will be created
    @param fields: the fields to add to the layer. Accepts a QgsFields object or a list of tuples (field_name, field_type)
    Accepted field types are basic Python types str, float, int and bool
    @param geometryType: The type of geometry of the layer to create.
    @param crs: The crs of the layer to create. Accepts a QgsCoordinateSystem object or a string with the CRS authId.
    @param encoding: The layer encoding
    """
    if isinstance(crs, str):
        crs = QgsCoordinateReferenceSystem(crs)
    if filename is None:
        uri = geometryType
        if crs.isValid():
            uri += "?crs=" + crs.authid()

        if name is None:
            name = "mem_layer"
        layer = QgsVectorLayer(uri, name, "memory")
        if fields:
            if isinstance(fields, QgsFields):
                qgsfields = fields
            else:
                qgsfields = QgsFields()
                for field in fields:
                    qgsfields.append(_toQgsField(field))
            provider = layer.dataProvider()
            provider.addAttributes(list(qgsfields))
            layer.updateFields()

    else:
        formats = QgsVectorFileWriter.supportedFiltersAndFormats()
        OGRCodes = {}
        for key, value in formats.items():
            extension = str(key)
            extension = extension[extension.find("*.") + 2 :]
            extension = extension[: extension.find(" ")]
            OGRCodes[extension] = value

        extension = os.path.splitext(filename)[1][1:]
        if extension not in OGRCodes:
            extension = "shp"
            filename = filename + ".shp"

        if isinstance(fields, QgsFields):
            qgsfields = fields
        else:
            qgsfields = QgsFields()
            for field in fields:
                qgsfields.append(_toQgsField(field))

        QgsVectorFileWriter(
            filename, encoding, qgsfields, geometryType, crs, OGRCodes[extension]
        )

        layer = QgsVectorLayer(filename, os.path.basename(filename), "ogr")

    return layer


# Backward-compatible re-exports: these draw/measure helpers now live in
# QgsFmvDrawLayers.py, kept importable from here for existing callers.
from QGISFMV.utils.layers.QgsFmvDrawLayers import (  # noqa: E402,F401
    AddDrawMilitarySymbolOnMap,
    RemoveLastDrawMilitarySymbolOnMap,
    RemoveAllDrawMilitarySymbolOnMap,
    AddDrawPointOnMap,
    AddDrawLineOnMap,
    RemoveAllDrawLineOnMap,
    RemoveAllDrawPolygonOnMap,
    RemoveAllDrawPointOnMap,
    RemoveLastDrawPolygonOnMap,
    RemoveLastDrawPointOnMap,
    AddDrawPolygonOnMap,
    SyncMeasureDistanceOnMap,
    SyncMeasureAreaOnMap,
)
