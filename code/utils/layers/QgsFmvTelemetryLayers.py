# -*- coding: utf-8 -*-
"""Live telemetry -> map layer updates, extracted from QgsFmvLayers.py.

Owns the per-KLV-packet Update* functions (footprint, beams, trajectory,
frame axis, frame center, platform) plus the per-video-group caches they
need to upsert single-feature layers and grow trajectory/beam geometry
incrementally instead of rebuilding it every frame.

Generic layer helpers (CommonLayer, layer-name constants, groupName,
feature-id lookups, style-cache mutable globals such as ``crtSensorSrc``)
still live in QgsFmvLayers.py and are accessed here through a module
reference (``_base()``) so this module always sees their live values —
mirrors the pattern already used by QgsFmvDrawLayers.py.
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsPointXY,
    QgsPolygon,
)

from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.layers.QgsFmvLayerStyleStore import (
    apply_or_default as applyLayerStyle,
)
from QGISFMV.utils.layers.QgsFmvLayerDefaults import (
    SetDefaultFootprintStyle,
    SetDefaultFrameAxisStyle,
    SetDefaultFrameCenterStyle,
    SetDefaultPlatformStyle,
)

# Per-video-group caches. Kept here (not in QgsFmvLayers) per the module split;
# QgsFmvLayers imports these dicts by reference so ``layers_mod._trajectory_active_feature``
# etc. keep working for existing callers/tests (mutable object, shared identity).
_trajectory_active_feature = {}
_beam_feature_ids = {}


def _base():
    """Lazily resolve QgsFmvLayers to dodge the circular import at load time.

    QgsFmvLayers.py re-exports this module's functions for backward
    compatibility, so importing QgsFmvLayers eagerly here (at module scope)
    could fail if this module happens to load first. Deferring the import
    to call time guarantees both modules are fully initialized.
    """
    import QGISFMV.utils.layers.QgsFmvLayers as _mod
    return _mod


def reset_caches(key):
    """Clear trajectory / beam caches for one group (truthy key) or all."""
    if key:
        _trajectory_active_feature.pop(key, None)
        _beam_feature_ids.pop(key, None)
    else:
        _trajectory_active_feature.clear()
        _beam_feature_ids.clear()


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


def _upsert_single_feature(layer, attrs, geometry):
    """Create the first feature or update an existing one in a single-feature memory layer."""
    base = _base()
    if layer.featureCount() == 0:
        layer.startEditing()
        feature = QgsFeature(layer.fields())
        feature.setAttributes(attrs)
        feature.setGeometry(geometry)
        layer.addFeatures([feature])
        base.CommonLayer(layer)
    else:
        fid = base._first_feature_id(layer)
        if fid is None:
            return
        provider = layer.dataProvider()
        provider.changeAttributeValues({fid: {i: v for i, v in enumerate(attrs)}})
        provider.changeGeometryValues({fid: geometry})
        base._refresh_memory_layer(layer)


def _remember_beam_feature_ids(layer, group_key):
    """Cache beam feature ids after the initial four-feature insert."""
    global _beam_feature_ids
    ids = _base()._sorted_feature_ids(layer)
    if len(ids) >= 4:
        _beam_feature_ids[group_key] = ids[:4]


def _beam_ids_for_layer(layer, group_key):
    """Return the four beam feature ids, refreshing the cache if needed."""
    ids = _beam_feature_ids.get(group_key)
    if ids and len(ids) >= 4:
        if all(layer.getFeature(fid).isValid() for fid in ids[:4]):
            return ids[:4]
    ids = _base()._sorted_feature_ids(layer)
    if len(ids) >= 4:
        _beam_feature_ids[group_key] = ids[:4]
        return ids[:4]
    return ids


def _add_trajectory_segment(trajectoryLyr, point, lon, lat, alt, segment_key, ele):
    """Append a new trajectory feature and make it the active segment."""
    base = _base()
    trajectoryLyr.startEditing()
    line = QgsLineString([point, QgsPoint(lon, lat, alt)])
    feature = QgsFeature()
    feature.setAttributes([lon, lat, alt])
    feature.setGeometry(QgsGeometry(line))
    trajectoryLyr.addFeatures([feature])
    if segment_key:
        _trajectory_active_feature[segment_key] = base._latest_feature_id(trajectoryLyr)
    base.CommonLayer(trajectoryLyr)


def UpdateFootPrintData(
    packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele
):
    """Update Footprint Values"""
    base = _base()
    imgSS = packet.ImageSourceSensor

    footprintLyr = qgsu.selectLayerByName(base.Footprint_lyr, base.groupName)

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
            if imgSS != base.crtSensorSrc:
                applyLayerStyle(
                    footprintLyr, base.Footprint_lyr, SetDefaultFootprintStyle, imgSS
                )
                base.crtSensorSrc = imgSS

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
                fetId = base._first_feature_id(footprintLyr)
                if fetId is None:
                    return
                provider.changeAttributeValues({fetId: attrib})
                provider.changeGeometryValues({fetId: surface})

            base._refresh_memory_layer(footprintLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvLayers", "Failed Update FootPrint Layer! : "
            ),
            str(e),
        )


def UpdateBeamsData(
    packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele
):
    """Update Beams Values"""
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude

    base = _base()
    beamsLyr = qgsu.selectLayerByName(base.Beams_lyr, base.groupName)

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
                _remember_beam_feature_ids(beamsLyr, base.groupName)
                base.CommonLayer(beamsLyr)
            else:
                beam_ids = _beam_ids_for_layer(beamsLyr, base.groupName)
                if len(beam_ids) < 4:
                    return
                provider = beamsLyr.dataProvider()
                for beam_id, corner in zip(beam_ids[:4], corners):
                    _update_beam_corner(beam_id, lon, lat, alt, corner, provider)
                base._refresh_memory_layer(beamsLyr)

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

    base = _base()
    trajectoryLyr = qgsu.selectLayerByName(base.Trajectory_lyr, base.groupName)

    try:
        if all(v is not None for v in [trajectoryLyr, lat, lon, alt]):
            lon, lat, alt = float(lon), float(lat), float(alt)
            point = QgsPoint(lon, lat, alt)

            segment_key = base.groupName
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
                feature_id = base._latest_feature_id(trajectoryLyr)
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
                if dist < base.TRAJECTORY_MIN_STEP_METERS:
                    return
                if dist >= base.TRAJECTORY_LOOP_BREAK_METERS:
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
            base._refresh_memory_layer(trajectoryLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate(
                "QgsFmvUtils", "Failed Update Trajectory Layer! : "
            ),
            str(e),
        )


def UpdateFrameAxisData(imgSS, sensor, framecenter, ele):
    """Update Frame Axis Values"""
    base = _base()

    lat = sensor[0]
    lon = sensor[1]
    alt = sensor[2]
    fc_lat = framecenter[0]
    fc_lon = framecenter[1]
    fc_alt = framecenter[2]

    frameaxisLyr = qgsu.selectLayerByName(base.FrameAxis_lyr, base.groupName)

    try:
        if all(v is not None for v in [frameaxisLyr, lat, lon, alt, fc_lat, fc_lon]):
            lon, lat, alt = float(lon), float(lat), float(alt)
            fc_lon, fc_lat, fc_alt = float(fc_lon), float(fc_lat), float(fc_alt or 0.0)
            if imgSS != base.crtSensorSrc2:
                applyLayerStyle(
                    frameaxisLyr, base.FrameAxis_lyr, SetDefaultFrameAxisStyle, imgSS
                )
                base.crtSensorSrc2 = imgSS
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


def UpdateFrameCenterData(packet, ele):
    """Update FrameCenter Values"""
    lat = packet[0]
    lon = packet[1]
    alt = packet[2]

    if alt is None:
        alt = 0.0

    base = _base()
    frameCenterLyr = qgsu.selectLayerByName(base.FrameCenter_lyr, base.groupName)

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
    base = _base()

    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    PlatformHeading = packet.PlatformHeadingAngle
    platformTailNumber = packet.PlatformTailNumber
    platformLyr = qgsu.selectLayerByName(base.Platform_lyr, base.groupName)

    try:
        if all(v is not None for v in [platformLyr, lat, lon, alt]):
            lon, lat, alt = float(lon), float(lat), float(alt)
            heading = float(PlatformHeading) if PlatformHeading is not None else 0.0
            tailKey = platformTailNumber or "DEFAULT"
            user_icon = base.get_user_platform_icon()
            if user_icon:
                if (
                    user_icon != base._last_user_platform_icon
                    or platformLyr.featureCount() == 0
                ):
                    base.applyPlatformIconStyle(platformLyr, user_icon)
                    base._last_user_platform_icon = user_icon
            elif tailKey != base.crtPltTailNum or platformLyr.featureCount() == 0:
                applyLayerStyle(
                    platformLyr, base.Platform_lyr, SetDefaultPlatformStyle, tailKey
                )
                base.crtPltTailNum = tailKey

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
