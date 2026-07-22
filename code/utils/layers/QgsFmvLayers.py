# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import QCoreApplication, QPointF, QSettings

from QGISFMV.utils.settings.QgsFmvSettings import (
    load as _load_settings,
    get_layer,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from qgis.core import (
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsMarkerSymbol,
    QgsLayerTreeLayer,
    QgsField,
    QgsFields,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsPoint,
    QgsLineString,
    QgsPolygon,
    QgsUnitTypes,
    Qgis,
)

from qgis.utils import iface
from QGISFMV.utils.layers.QgsFmvStyles import FmvLayerStyles as S
from QGISFMV.utils.layers.QgsFmvLayerStyleStore import (
    apply_or_default as applyLayerStyle,
    ensure_watch as ensureLayerStyleWatch,
)
try:
    from qgis._3d import (
        QgsPhongMaterialSettings,
        QgsVectorLayer3DRenderer,
        QgsLine3DSymbol,
        QgsPoint3DSymbol,
        QgsPolygon3DSymbol,
    )
    _HAS_3D = True
except ImportError:
    QgsPhongMaterialSettings = None
    QgsVectorLayer3DRenderer = None
    QgsLine3DSymbol = None
    QgsPoint3DSymbol = None
    QgsPolygon3DSymbol = None
    _HAS_3D = False

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
_trajectory_active_feature = {}
_object_track_active_feature = {}
_beam_feature_ids = {}
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
        _trajectory_active_feature.pop(key, None)
        _object_track_active_feature.pop(key, None)
        _beam_feature_ids.pop(key, None)
    else:
        _trajectory_active_feature.clear()
        _object_track_active_feature.clear()
        _beam_feature_ids.clear()


def beginNewTrajectorySegment(group_name=None):
    """Start a new trajectory line on the next telemetry update (e.g. video loop)."""
    global groupName
    key = group_name if group_name is not None else groupName
    if key:
        _trajectory_active_feature[key] = None


def _add_trajectory_segment(trajectoryLyr, point, lon, lat, alt, segment_key, ele):
    """Append a new trajectory feature and make it the active segment."""
    trajectoryLyr.startEditing()
    line = QgsLineString([point, QgsPoint(lon, lat, alt)])
    feature = QgsFeature()
    feature.setAttributes([lon, lat, alt])
    feature.setGeometry(QgsGeometry(line))
    trajectoryLyr.addFeatures([feature])
    if segment_key:
        _trajectory_active_feature[segment_key] = _latest_feature_id(trajectoryLyr)
    CommonLayer(trajectoryLyr)


def _remember_beam_feature_ids(layer, group_key):
    """Cache beam feature ids after the initial four-feature insert."""
    global _beam_feature_ids
    ids = _sorted_feature_ids(layer)
    if len(ids) >= 4:
        _beam_feature_ids[group_key] = ids[:4]


def _beam_ids_for_layer(layer, group_key):
    """Return the four beam feature ids, refreshing the cache if needed."""
    ids = _beam_feature_ids.get(group_key)
    if ids and len(ids) >= 4:
        if all(layer.getFeature(fid).isValid() for fid in ids[:4]):
            return ids[:4]
    ids = _sorted_feature_ids(layer)
    if len(ids) >= 4:
        _beam_feature_ids[group_key] = ids[:4]
        return ids[:4]
    return ids

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
    _upsert_single_feature(
        posLyr,
        [int(track_id), str(backend or ""), lon, lat, alt],
        QgsGeometry.fromPointXY(QgsPointXY(lon, lat)),
    )


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


def UpdateFootPrintData(
    packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele
):
    """Update Footprint Values"""
    global crtSensorSrc, groupName
    imgSS = packet.ImageSourceSensor

    footprintLyr = qgsu.selectLayerByName(Footprint_lyr, groupName)

    try:
        if all(
            v is not None
            for v in [
                footprintLyr,
                cornerPointUL,
                cornerPointUR,
                cornerPointLR,
                cornerPointLL,
            ]
        ) and all(
            v >= 2
            for v in [
                len(cornerPointUL),
                len(cornerPointUR),
                len(cornerPointLR),
                len(cornerPointLL),
            ]
        ):
            if imgSS != crtSensorSrc:
                applyLayerStyle(
                    footprintLyr, Footprint_lyr, SetDefaultFootprintStyle, imgSS
                )
                crtSensorSrc = imgSS

            corners = [cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]
            ring = QgsLineString([_corner_point_3d(c) for c in corners] + [_corner_point_3d(corners[0])])
            polygon = QgsPolygon()
            polygon.setExteriorRing(ring)
            surface = QgsGeometry(polygon)
            attrib = {
                i: corners[i // 2][1 - (i % 2)] for i in range(8)
            }

            provider = footprintLyr.dataProvider()
            flat_attrs = [coord for c in corners for coord in (c[1], c[0])]
            if footprintLyr.featureCount() == 0:
                feature = QgsFeature(footprintLyr.fields())
                feature.setAttributes(flat_attrs)
                feature.setGeometry(surface)
                provider.addFeatures([feature])
            else:
                fetId = _first_feature_id(footprintLyr)
                if fetId is None:
                    return
                provider.changeAttributeValues({fetId: attrib})
                provider.changeGeometryValues({fetId: surface})

            _refresh_memory_layer(footprintLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvLayers", "Failed Update FootPrint Layer! : "
            ),
            str(e),
        )


def _corner_point_3d(corner, default_z=0.0):
    """Build a 3D map point from a corner tuple (lat, lon[, alt])."""
    z = default_z
    if corner is not None and len(corner) > 2 and corner[2] is not None:
        try:
            z = float(corner[2])
        except (TypeError, ValueError):
            pass
    return QgsPoint(float(corner[1]), float(corner[0]), z)


def _update_beam_corner(beam_id, lon, lat, alt, corner, provider):
    """Update a single beam corner's attributes and geometry."""
    provider.changeAttributeValues(
        {beam_id: {0: lon, 1: lat, 2: alt, 3: corner[1], 4: corner[0]}}
    )
    provider.changeGeometryValues(
        {beam_id: QgsGeometry(QgsLineString(QgsPoint(lon, lat, alt), _corner_point_3d(corner)))}
    )


def _add_beam_corner(lon, lat, alt, corner, beamsLyr):
    """Create and add a single beam corner feature."""
    feature = QgsFeature()
    feature.setAttributes([lon, lat, alt, corner[1], corner[0]])
    feature.setGeometry(
        QgsLineString(QgsPoint(lon, lat, alt), _corner_point_3d(corner))
    )
    beamsLyr.addFeatures([feature])


def UpdateBeamsData(
    packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele
):
    """Update Beams Values"""
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude

    global groupName
    beamsLyr = qgsu.selectLayerByName(Beams_lyr, groupName)

    try:
        if all(
            v is not None
            for v in [beamsLyr, lat, lon, alt, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]
        ) and all(
            v >= 2
            for v in [len(cornerPointUL), len(cornerPointUR), len(cornerPointLR), len(cornerPointLL)]
        ):
            lon, lat, alt = float(lon), float(lat), float(alt)
            corners = [cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]
            if beamsLyr.featureCount() == 0:
                beamsLyr.startEditing()
                for corner in corners:
                    _add_beam_corner(lon, lat, alt, corner, beamsLyr)
                _remember_beam_feature_ids(beamsLyr, groupName)
                CommonLayer(beamsLyr)
            else:
                beam_ids = _beam_ids_for_layer(beamsLyr, groupName)
                if len(beam_ids) < 4:
                    return
                provider = beamsLyr.dataProvider()
                for beam_id, corner in zip(beam_ids[:4], corners):
                    _update_beam_corner(beam_id, lon, lat, alt, corner, provider)
                _refresh_memory_layer(beamsLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate("QgsFmvUtils", "Failed Update Beams Layer! : "),
            str(e),
        )


def UpdateTrajectoryData(packet, ele):
    """Update Trajectory Values"""
    from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance

    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude

    global groupName
    trajectoryLyr = qgsu.selectLayerByName(Trajectory_lyr, groupName)

    try:
        if all(v is not None for v in [trajectoryLyr, lat, lon, alt]):
            lon, lat, alt = float(lon), float(lat), float(alt)
            point = QgsPoint(lon, lat, alt)

            segment_key = groupName
            force_new_segment = (
                segment_key in _trajectory_active_feature
                and _trajectory_active_feature[segment_key] is None
                and trajectoryLyr.featureCount() > 0
            )

            if trajectoryLyr.featureCount() == 0 or force_new_segment:
                _add_trajectory_segment(
                    trajectoryLyr, point, lon, lat, alt, segment_key, ele
                )
                return

            feature_id = _trajectory_active_feature.get(segment_key)
            if feature_id is None or not trajectoryLyr.getFeature(feature_id).isValid():
                feature_id = _latest_feature_id(trajectoryLyr)
            if feature_id is None:
                return
            if segment_key:
                _trajectory_active_feature[segment_key] = feature_id

            feature = trajectoryLyr.getFeature(feature_id)
            const_line = feature.geometry().constGet()
            if isinstance(const_line, QgsLineString):
                line = QgsLineString(const_line)
            else:
                line = QgsLineString()

            if line.numPoints() > 0:
                last = line.pointN(line.numPoints() - 1)
                dist = _geo_distance((last.x(), last.y()), (lon, lat))
                if dist < TRAJECTORY_MIN_STEP_METERS:
                    return
                if dist >= TRAJECTORY_LOOP_BREAK_METERS:
                    _add_trajectory_segment(
                        trajectoryLyr, point, lon, lat, alt, segment_key, ele
                    )
                    return

            provider = trajectoryLyr.dataProvider()
            line.addVertex(point)
            provider.changeGeometryValues(
                {feature_id: QgsGeometry(line)}
            )
            provider.changeAttributeValues(
                {feature_id: {0: lon, 1: lat, 2: alt}}
            )
            _refresh_memory_layer(trajectoryLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Trajectory Layer! : "
            ),
            str(e),
        )


def UpdateFrameAxisData(imgSS, sensor, framecenter, ele):
    """Update Frame Axis Values"""
    global crtSensorSrc2, groupName

    lat = sensor[0]
    lon = sensor[1]
    alt = sensor[2]
    fc_lat = framecenter[0]
    fc_lon = framecenter[1]
    fc_alt = framecenter[2]

    frameaxisLyr = qgsu.selectLayerByName(FrameAxis_lyr, groupName)

    try:
        if all(v is not None for v in [frameaxisLyr, lat, lon, alt, fc_lat, fc_lon]):
            lon, lat, alt = float(lon), float(lat), float(alt)
            fc_lon, fc_lat, fc_alt = float(fc_lon), float(fc_lat), float(fc_alt or 0.0)
            if imgSS != crtSensorSrc2:
                applyLayerStyle(
                    frameaxisLyr, FrameAxis_lyr, SetDefaultFrameAxisStyle, imgSS
                )
                crtSensorSrc2 = imgSS
            _upsert_single_feature(
                frameaxisLyr,
                [lon, lat, alt, fc_lon, fc_lat, fc_alt],
                QgsGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(fc_lon, fc_lat, fc_alt))),
            )

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Frame axis Layer! : "
            ),
            str(e),
        )


def _upsert_single_feature(layer, attrs, geometry):
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


def UpdateFrameCenterData(packet, ele):
    """Update FrameCenter Values"""
    lat = packet[0]
    lon = packet[1]
    alt = packet[2]

    if alt is None:
        alt = 0.0

    global groupName
    frameCenterLyr = qgsu.selectLayerByName(FrameCenter_lyr, groupName)

    try:
        if all(v is not None for v in [frameCenterLyr, lat, lon, alt]):
            SetDefaultFrameCenterStyle(frameCenterLyr)
            _upsert_single_feature(
                frameCenterLyr,
                [lon, lat, alt],
                QgsGeometry.fromPointXY(QgsPointXY(lon, lat)),
            )

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Frame Center Layer! : "
            ),
            str(e),
        )


def UpdatePlatformData(packet, ele):
    """Update PlatForm Values"""
    global crtPltTailNum, groupName, _last_user_platform_icon

    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    PlatformHeading = packet.PlatformHeadingAngle
    platformTailNumber = packet.PlatformTailNumber
    platformLyr = qgsu.selectLayerByName(Platform_lyr, groupName)

    try:
        if all(v is not None for v in [platformLyr, lat, lon, alt]):
            lon, lat, alt = float(lon), float(lat), float(alt)
            heading = float(PlatformHeading) if PlatformHeading is not None else 0.0
            tailKey = platformTailNumber or "DEFAULT"
            user_icon = get_user_platform_icon()
            if user_icon:
                if (
                    user_icon != _last_user_platform_icon
                    or platformLyr.featureCount() == 0
                ):
                    applyPlatformIconStyle(platformLyr, user_icon)
                    _last_user_platform_icon = user_icon
            elif tailKey != crtPltTailNum or platformLyr.featureCount() == 0:
                applyLayerStyle(
                    platformLyr, Platform_lyr, SetDefaultPlatformStyle, tailKey
                )
                crtPltTailNum = tailKey

            platformLyr.renderer().symbol().setAngle(heading)
            _upsert_single_feature(
                platformLyr,
                [lon, lat, alt],
                QgsGeometry(QgsPoint(lon, lat, alt)),
            )

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Platform Layer! : "
            ),
            str(e),
        )


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
                     MeasureDistance_lyr, MeasureArea_lyr):
        existing = qgsu.selectLayerByName(lyr_name, groupName)
        if existing is not None:
            ensureLayerStyleWatch(existing, lyr_name)


def _create_layer_if_missing(lyr_name, factory, fields, geom_type, style_fn, style_args):
    """Create a layer if it doesn't exist in the current group, apply style, and add to map."""
    if qgsu.selectLayerByName(lyr_name, groupName) is not None:
        return
    layer = factory(None, fields, epsg, lyr_name, geom_type)
    applyLayerStyle(layer, lyr_name, style_fn, *style_args)
    addLayerNoCrsDialog(layer, group=groupName)


# ---------------------------------------------------------------------------
# Data-driven style registry
# ---------------------------------------------------------------------------

# kwargs mappers: style dict -> QgsSymbol.createSimple kwargs


def _fill_kwargs(style):
    return {
        "color": style["COLOR"],
        "outline_color": style["OUTLINE_COLOR"],
        "outline_style": style["OUTLINE_STYLE"],
        "outline_width": style["OUTLINE_WIDTH"],
    }


def _line_kwargs(style):
    return {
        "color": style["COLOR"],
        "width": style["WIDTH"],
        "customdash": style.get("customdash", "0"),
        "use_custom_dash": style.get("use_custom_dash", "0"),
    }


def _marker_kwargs(style):
    return {
        "name": style["NAME"],
        "color": style.get("COLOR", style["LINE_COLOR"]),
        "outline_color": style["LINE_COLOR"],
        "outline_width": style["LINE_WIDTH"],
        "size": style["SIZE"],
    }


def _frame_center_kwargs(style):
    return {
        "name": style["NAME"],
        "line_color": style["LINE_COLOR"],
        "line_width": style["LINE_WIDTH"],
        "size": style["SIZE"],
    }


def _beams_kwargs(style):
    c = QColor.fromRgba(style["COLOR"])
    return {
        "color": f"{c.red()},{c.green()},{c.blue()},{c.alpha()}",
        "width": "0.7",
        "line_style": "dash",
        "customdash": "5;4",
        "use_custom_dash": "1",
    }


def _frame_axis_style(sensor="DEFAULT"):
    """Merge sensor and frame-axis style dicts for the frame axis line."""
    sensor_style = S.getSensor(sensor)
    frame_axis = S.getFrameAxis()
    return {
        "OUTLINE_COLOR": sensor_style["OUTLINE_COLOR"],
        "OUTLINE_WIDTH": sensor_style["OUTLINE_WIDTH"],
        "OUTLINE_STYLE": frame_axis["OUTLINE_STYLE"],
    }


def _frame_axis_kwargs(style):
    return {
        "color": style["OUTLINE_COLOR"],
        "width": style["OUTLINE_WIDTH"],
        "outline_style": style["OUTLINE_STYLE"],
    }


def _measure_distance_kwargs(style):
    return {
        "color": style["COLOR"],
        "width": style["WIDTH"],
        "line_style": "solid",
        "capstyle": "round",
        "joinstyle": "round",
    }


# Labeling helpers


def _label_object_position(layer, style):
    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()
    text_format.setFont(
        QFont(style["LABEL_FONT"], style["LABEL_FONT_SIZE"], QFont.Weight.Bold)
    )
    text_format.setSize(style["LABEL_FONT_SIZE"])
    text_format.setColor(QColor(style["LABEL_FONT_COLOR"]))
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(style["LABEL_BUFFER_SIZE"])
    buffer_settings.setColor(QColor(style["LABEL_BUFFER_COLOR"]))
    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)
    layer_settings.fieldName = "'TRACK ' || coalesce(\"track_id\", '')"
    layer_settings.isExpression = True
    layer_settings.placement = QgsPalLayerSettings.Placement.OverPoint
    layer.setLabeling(QgsVectorLayerSimpleLabeling(layer_settings))
    layer.setLabelsEnabled(True)


def _label_point(layer, style):
    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()
    text_format.setFont(
        QFont(
            style["LABEL_FONT"],
            style["LABEL_FONT_SIZE"],
            QFont.Weight.Bold,
        )
    )
    text_format.setColor(QColor(style["LABEL_FONT_COLOR"]))
    text_format.setSize(style["LABEL_SIZE"])

    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(float(style.get("LABEL_BUFFER_SIZE", 1.4)))
    buffer_settings.setColor(QColor(style["LABEL_BUFFER_COLOR"]))

    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)

    layer_settings.fieldName = "number"
    layer_settings.placement = QgsPalLayerSettings.Placement.OverPoint
    layer_settings.enabled = True
    layer_settings.dist = 0
    layer_settings.offsetType = QgsPalLayerSettings.OffsetType.FromPoint
    layer_settings.offset = QPointF(
        float(style.get("LABEL_OFFSET_X", 2.0)),
        float(style.get("LABEL_OFFSET_Y", -2.0)),
    )
    layer_settings.offsetUnit = QgsUnitTypes.RenderMillimeters

    quadrant = getattr(QgsPalLayerSettings, "QuadrantAboveRight", None)
    if quadrant is None and hasattr(QgsPalLayerSettings, "QuadrantOffset"):
        quadrant = QgsPalLayerSettings.QuadrantOffset.QuadrantAboveRight
    if quadrant is not None:
        layer_settings.quadrantOffset = quadrant

    layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
    layer.setLabelsEnabled(True)
    layer.setLabeling(layer_settings)


# Custom apply functions for non-standard symbol types


def _apply_military_symbol(layer):
    """Rule-based SVG renderer for NATO military symbols."""
    from QGISFMV.player.dialogs.QgsFmvMilitarySymbols import (
        MILITARY_SYMBOLS,
        symbol_svg_path,
    )

    default_sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
    renderer = QgsRuleBasedRenderer(default_sym)
    root = renderer.rootRule()
    root.removeChildAt(0)

    for symbol_id, _name, _category, _filename in MILITARY_SYMBOLS:
        svg_path = symbol_svg_path(symbol_id)
        if not svg_path or not os.path.isfile(svg_path):
            continue
        svg_layer = QgsSvgMarkerSymbolLayer(svg_path)
        svg_layer.setSize(8)
        svg_layer.setSizeUnit(QgsUnitTypes.RenderMillimeters)
        point_symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
        point_symbol.deleteSymbolLayer(0)
        point_symbol.appendSymbolLayer(svg_layer)
        rule = QgsRuleBasedRenderer.Rule(point_symbol)
        rule.setFilterExpression(f'"symbol_id" = \'{symbol_id}\'')
        rule.setActive(True)
        root.appendChild(rule)

    layer.setRenderer(renderer)

    layer_settings = QgsPalLayerSettings()
    layer_settings.fieldName = "unit_name"
    layer_settings.enabled = True
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial", 8, QFont.Weight.Bold))
    text_format.setColor(QColor("#000000"))
    layer_settings.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(layer_settings))
    layer.setLabelsEnabled(True)


def _apply_line_modify(layer):
    """Modify the existing line renderer symbol in place."""
    style = S.getDrawingLine()
    symbol = layer.renderer().symbol()
    symbol.setColor(style["COLOR"])
    symbol.setWidth(style["WIDTH"])


# Style registry: maps config keys to style configurations.
#
# Each entry:
#   "symbol_type" : "fill" | "line" | "marker" | "svg_marker" | "custom" | "modify"
#   "get_style"   : callable(*args) -> dict   (ignored for "custom" / "modify")
#   "map_kwargs"  : callable(style_dict) -> dict for createSimple
#   "default_args": tuple of default positional args for get_style
#   "labeling"    : optional callable(layer, style_dict)
#   "refresh"     : bool -- refresh layer tree style after applying

_STYLE_REGISTRY = {
    "footprint": {
        "symbol_type": "fill",
        "get_style": S.getSensor,
        "map_kwargs": _fill_kwargs,
        "default_args": ("DEFAULT",),
    },
    "beams": {
        "symbol_type": "line",
        "get_style": S.getBeam,
        "map_kwargs": _beams_kwargs,
        "default_args": ("DEFAULT",),
    },
    "trajectory": {
        "symbol_type": "line",
        "get_style": S.getTrajectory,
        "map_kwargs": _line_kwargs,
        "default_args": ("DEFAULT",),
    },
    "object_track": {
        "symbol_type": "line",
        "get_style": S.getObjectTrack,
        "map_kwargs": _line_kwargs,
        "default_args": (),
        "refresh": True,
    },
    "object_position": {
        "symbol_type": "marker",
        "get_style": S.getObjectPosition,
        "map_kwargs": _marker_kwargs,
        "default_args": (),
        "labeling": _label_object_position,
        "refresh": True,
    },
    "platform": {
        "symbol_type": "svg_marker",
        "get_style": S.getPlatform,
        "default_args": ("DEFAULT",),
        "refresh": True,
    },
    "frame_center": {
        "symbol_type": "marker",
        "get_style": S.getFrameCenterPoint,
        "map_kwargs": _frame_center_kwargs,
        "default_args": (),
    },
    "frame_axis": {
        "symbol_type": "line",
        "get_style": _frame_axis_style,
        "map_kwargs": _frame_axis_kwargs,
        "default_args": ("DEFAULT",),
    },
    "military_symbol": {
        "symbol_type": "custom",
        "apply_fn": _apply_military_symbol,
    },
    "point": {
        "symbol_type": "marker",
        "get_style": S.getDrawingPoint,
        "map_kwargs": _marker_kwargs,
        "default_args": (),
        "labeling": _label_point,
    },
    "line": {
        "symbol_type": "modify",
        "apply_fn": _apply_line_modify,
    },
    "polygon": {
        "symbol_type": "fill",
        "get_style": S.getDrawingPolygon,
        "map_kwargs": _fill_kwargs,
        "default_args": (),
    },
    "measure_distance": {
        "symbol_type": "line",
        "get_style": S.getMeasureDistance,
        "map_kwargs": _measure_distance_kwargs,
        "default_args": (),
        "labeling": lambda layer, s: _apply_measure_labeling(
            layer, "label", "#e0f7fa", line=True
        ),
        "refresh": True,
    },
    "measure_area": {
        "symbol_type": "fill",
        "get_style": S.getMeasureArea,
        "map_kwargs": _fill_kwargs,
        "default_args": (),
        "labeling": lambda layer, s: _apply_measure_labeling(
            layer, "label", "#fff8e1", line=False
        ),
        "refresh": True,
    },
}


def _apply_style(layer, config_key, *args):
    """Apply a default style to *layer* using the style registry.

    *args* override the entry's ``default_args`` when provided.
    """
    config = _STYLE_REGISTRY[config_key]
    symbol_type = config["symbol_type"]

    # Custom: delegate entirely to the apply_fn
    if symbol_type in ("custom", "modify"):
        config["apply_fn"](layer)
        return

    # Standard symbol creation
    effective_args = args if args else config["default_args"]
    style_dict = config["get_style"](*effective_args)
    map_fn = config.get("map_kwargs")
    kwargs = map_fn(style_dict) if map_fn else {}

    if symbol_type == "fill":
        symbol = QgsFillSymbol.createSimple(kwargs)
    elif symbol_type == "line":
        symbol = QgsLineSymbol.createSimple(kwargs)
    elif symbol_type == "marker":
        symbol = QgsMarkerSymbol.createSimple(kwargs)
    elif symbol_type == "svg_marker":
        svg_layer = QgsSvgMarkerSymbolLayer.create(style_dict)
        symbol = QgsMarkerSymbol([svg_layer])
    else:
        raise ValueError(f"Unknown symbol_type: {symbol_type}")

    layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    labeling_fn = config.get("labeling")
    if labeling_fn:
        labeling_fn(layer, style_dict)

    if config.get("refresh"):
        _refresh_layer_tree_style(layer)


# ---------------------------------------------------------------------------
# Backward-compatible thin wrappers
# ---------------------------------------------------------------------------


def SetDefaultFootprintStyle(layer, sensor="DEFAULT"):
    """Footprint Symbol"""
    _apply_style(layer, "footprint", sensor)


def SetDefaultFootprint3DStyle(layer):
    """Footprint 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(0, 188, 212, 180))
    material.setAmbient(QColor(0, 151, 167))
    symbol = QgsPolygon3DSymbol()
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)
    if hasattr(symbol, "setHeight"):
        symbol.setHeight(2.0)

    _apply_vector_layer_3d_renderer(layer, symbol)


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

_FM3D_RENDERER_SYMBOLS = {}


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


def _fmv_3d_layer_styles():
    return [
        (Footprint_lyr, SetDefaultFootprint3DStyle),
        (Beams_lyr, SetDefaultBeams3DStyle),
        (Trajectory_lyr, SetDefaultTrajectory3DStyle),
        (FrameAxis_lyr, SetDefaultFrameAxis3DStyle),
        (Platform_lyr, SetDefaultPlatform3DStyle),
        (FrameCenter_lyr, SetDefaultFrameCenter3DStyle),
    ]


def _apply_vector_layer_3d_renderer(layer, symbol):
    """Apply a 3D symbol without replacing an existing renderer (QGIS SIP crash)."""
    renderer = layer.renderer3D()
    if renderer is None or not isinstance(renderer, QgsVectorLayer3DRenderer):
        renderer = QgsVectorLayer3DRenderer()
        renderer.setLayer(layer)
        layer.setRenderer3D(renderer)
    _FM3D_RENDERER_SYMBOLS[layer.id()] = (renderer, symbol)
    renderer.setSymbol(symbol)


def ensure_fmv_3d_renderers(group_name=None, force=False):
    """Ensure FMV layers have 3D renderers using absolute Z from telemetry."""
    if not _HAS_3D:
        return []
    key = group_name if group_name is not None else groupName
    if not key:
        return []
    ready = []
    for lyr_name, style_fn in _fmv_3d_layer_styles():
        layer = qgsu.selectLayerByName(lyr_name, key)
        if layer is None:
            continue
        if not force and isinstance(layer.renderer3D(), QgsVectorLayer3DRenderer):
            ready.append(layer)
            continue
        try:
            style_fn(layer)
            if hasattr(layer, "trigger3DUpdate"):
                layer.trigger3DUpdate()
            ready.append(layer)
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                "",
                "3D renderer setup failed for %s: %s" % (lyr_name, exc),
                onlyLog=True,
            )
    return ready


def SetDefaultTrajectoryStyle(layer):
    """Trajectory Symbol"""
    _apply_style(layer, "trajectory")


def SetDefaultObjectTrackStyle(layer):
    """Object tracking path style (amber, distinct from platform trajectory)."""
    _apply_style(layer, "object_track")


def SetDefaultObjectPositionStyle(layer):
    """Live tracked-object marker style."""
    _apply_style(layer, "object_position")


def SetDefaultPlatformStyle(layer, platform="DEFAULT"):
    """Platform Symbol"""
    _apply_style(layer, "platform", platform)


def SetDefaultPlatform3DStyle(layer):
    """Platform 3D Symbol — simple sphere (stable across QGIS SIP ownership)."""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 255, 255))
    material.setAmbient(QColor(200, 220, 235))
    symbol = QgsPoint3DSymbol()
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)
    symbol.setShape(Qgis.Point3DShape.Sphere)
    symbol.setShapeProperties({"radius": 25})

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultTrajectory3DStyle(layer):
    """Trajectory 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(38, 198, 218))
    material.setAmbient(QColor(0, 151, 167))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(5)
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultFrameAxis3DStyle(layer):
    """Frame Axis 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 64, 129))
    material.setAmbient(QColor(194, 24, 91))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(3)
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultBeams3DStyle(layer):
    """Beams 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 235, 59))
    material.setAmbient(QColor(255, 193, 7))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(5)
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultFrameCenterStyle(layer):
    """Frame Center Symbol"""
    _apply_style(layer, "frame_center")


def SetDefaultFrameCenter3DStyle(layer):
    """Frame Center 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 64, 129))
    material.setAmbient(QColor(194, 24, 91))
    symbol = QgsPoint3DSymbol()
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)
    symbol.setShape(Qgis.Point3DShape.Sphere)
    symbol.setShapeProperties({"radius": 8})

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultFrameAxisStyle(layer, sensor="DEFAULT"):
    """Line Symbol"""
    _apply_style(layer, "frame_axis", sensor)


def SetDefaultMilitarySymbolStyle(layer):
    """Rule-based SVG renderer for NATO military symbols."""
    _apply_style(layer, "military_symbol")


def SetDefaultPointStyle(layer):
    """Point Symbol"""
    _apply_style(layer, "point")


def SetDefaultLineStyle(layer):
    """Line Symbol"""
    _apply_style(layer, "line")


def SetDefaultPolygonStyle(layer):
    """Polygon Symbol"""
    _apply_style(layer, "polygon")


def _apply_measure_labeling(layer, field_name="label", color="#ffffff", line=True):
    """Bold buffered labels for measure layers."""
    settings = QgsPalLayerSettings()
    settings.fieldName = field_name
    settings.isExpression = False
    settings.enabled = True
    placement = QgsPalLayerSettings.Placement
    if line:
        settings.placement = getattr(placement, "Line", placement.AroundPoint)
    else:
        settings.placement = getattr(placement, "Centroid", placement.AroundPoint)
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    text_format.setSize(9)
    text_format.setColor(QColor(color))
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(1.2)
    buffer_settings.setColor(QColor(20, 30, 40, 220))
    text_format.setBuffer(buffer_settings)
    settings.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


def SetDefaultMeasureDistanceStyle(layer):
    """Cyan dashed line + length labels for measure distance."""
    _apply_style(layer, "measure_distance")


def SetDefaultMeasureAreaStyle(layer):
    """Amber translucent fill + area labels for measure area."""
    _apply_style(layer, "measure_area")


def SetDefaultBeamsStyle(layer, beam="DEFAULT"):
    """Beams Symbol"""
    _apply_style(layer, "beams", beam)


def RestoreDefaultLayerStyles():
    """Clear saved symbology and re-apply plugin defaults on open FMV layers."""
    from QGISFMV.utils.layers.QgsFmvLayerStyleStore import clear, ensure_watch
    from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get

    clear()

    defaults = {
        settings_get("LAYERS", "footprint_lyr", Footprint_lyr): (
            SetDefaultFootprintStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "beams_lyr", Beams_lyr): (
            SetDefaultBeamsStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "trajectory_lyr", Trajectory_lyr): (
            SetDefaultTrajectoryStyle,
            (),
        ),
        settings_get("LAYERS", "frameaxis_lyr", FrameAxis_lyr): (
            SetDefaultFrameAxisStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "platform_lyr", Platform_lyr): (
            SetDefaultPlatformStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "point_lyr", Point_lyr): (SetDefaultPointStyle, ()),
        settings_get("LAYERS", "symbol_lyr", Symbol_lyr): (SetDefaultMilitarySymbolStyle, ()),
        settings_get("LAYERS", "framecenter_lyr", FrameCenter_lyr): (
            SetDefaultFrameCenterStyle,
            (),
        ),
        settings_get("LAYERS", "line_lyr", Line_lyr): (SetDefaultLineStyle, ()),
        settings_get("LAYERS", "polygon_lyr", Polygon_lyr): (
            SetDefaultPolygonStyle,
            (),
        ),
        settings_get("LAYERS", "objecttrack_lyr", ObjectTrack_lyr): (
            SetDefaultObjectTrackStyle,
            (),
        ),
        settings_get("LAYERS", "objectposition_lyr", ObjectPosition_lyr): (
            SetDefaultObjectPositionStyle,
            (),
        ),
        settings_get("LAYERS", "measuredistance_lyr", MeasureDistance_lyr): (
            SetDefaultMeasureDistanceStyle,
            (),
        ),
        settings_get("LAYERS", "measurearea_lyr", MeasureArea_lyr): (
            SetDefaultMeasureAreaStyle,
            (),
        ),
    }

    restored = 0
    for layer in _layerreg.mapLayers().values():
        entry = defaults.get(layer.name())
        if entry is None:
            continue
        fn, args = entry
        fn(layer, *args)
        ensure_watch(layer, layer.name())
        layer.triggerRepaint()
        restored += 1

    if iface is not None:
        for layer in _layerreg.mapLayers().values():
            if layer.name() in defaults:
                try:
                    iface.layerTreeView().refreshLayerSymbology(layer.id())
                except Exception as exc:
                    log.debug(
                        "Layer tree refresh failed for %s: %s", layer.name(), exc
                    )
    return restored


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
