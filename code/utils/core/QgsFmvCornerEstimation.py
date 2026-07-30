# -*- coding: utf-8 -*-
"""Footprint corner-point estimation, extracted from QgsFmvGeoReferencing.py.

Computes the four footprint corners either from MISB corner-offset fields
(``CornerEstimationWithOffsets``) or from sensor geometry (FOV, altitude,
slant range, heading) when offsets are unavailable
(``CornerEstimationWithoutOffsets``). Called once per KLV packet from
QgsFmvUtils.UpdateLayers.

Session/DEM/GCP helpers (``hasElevationModel``, ``GetSensor``,
``GetLine3DIntersectionWithDEM``, ``_update_footprint_beams_gcp``) still live
in QgsFmvGeoReferencing.py; this module reads them through a module
reference (``_base()``) to avoid a circular import at load time, since
QgsFmvGeoReferencing.py re-exports this module's functions for backward
compatibility.
"""

from math import atan, degrees, radians, sqrt, tan

from QGISFMV.geo.QgsGeoUtils import destination as _geo_destination
from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

DEFAULT_TARGET_WIDTH = 200.0


def _base():
    """Lazily resolve QgsFmvGeoReferencing to dodge the circular import at load time.

    QgsFmvGeoReferencing.py re-exports this module's functions for backward
    compatibility, so importing it eagerly here (at module scope) could fail
    if this module happens to load first. Deferring the import to call time
    guarantees both modules are fully initialized.
    """
    import QGISFMV.utils.core.QgsFmvGeoReferencing as _mod

    return _mod


def CornerEstimationWithOffsets(packet):
    """Corner estimation using Offsets
    :param packet: Metada packet
    """
    base = _base()
    try:

        OffsetLat1 = packet.OffsetCornerLatitudePoint1
        OffsetLon1 = packet.OffsetCornerLongitudePoint1
        OffsetLat2 = packet.OffsetCornerLatitudePoint2
        OffsetLon2 = packet.OffsetCornerLongitudePoint2
        OffsetLat3 = packet.OffsetCornerLatitudePoint3
        OffsetLon3 = packet.OffsetCornerLongitudePoint3
        OffsetLat4 = packet.OffsetCornerLatitudePoint4
        OffsetLon4 = packet.OffsetCornerLongitudePoint4
        frameCenterLat = packet.FrameCenterLatitude
        frameCenterLon = packet.FrameCenterLongitude

        # Lat,Lon
        cornerPointUL = (OffsetLat1 + frameCenterLat, OffsetLon1 + frameCenterLon)
        cornerPointUR = (OffsetLat2 + frameCenterLat, OffsetLon2 + frameCenterLon)
        cornerPointLR = (OffsetLat3 + frameCenterLat, OffsetLon3 + frameCenterLon)
        cornerPointLL = (OffsetLat4 + frameCenterLat, OffsetLon4 + frameCenterLon)

        frameCenterPoint = [
            packet.FrameCenterLatitude,
            packet.FrameCenterLongitude,
            packet.FrameCenterElevation,
        ]

        # If no framcenter (f.i. horizontal target) don't comptpute footprint, beams and frame center
        if frameCenterPoint[0] is None and frameCenterPoint[1] is None:
            from QGISFMV.utils.core.QgsFmvUtils import gv

            gv.setTransform(None)
            return True
        if base.hasElevationModel():
            cornerPointUL = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointUL
            )
            cornerPointUR = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointUR
            )
            cornerPointLR = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointLR
            )
            cornerPointLL = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointLL
            )
            frameCenterPoint = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), frameCenterPoint
            )

        base._update_footprint_beams_gcp(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            frameCenterPoint,
            base.hasElevationModel(),
        )

    except Exception as e:
        log.debug("CornerEstimationWithOffsets failed: %s", e)
        return False

    return True


def CornerEstimationWithoutOffsets(
    packet=None, sensor=None, frameCenter=None, FOV=None, others=None
):
    """Estimate footprint corner points when MISB offsets are not available.

    Computes the four corner coordinates from sensor geometry (FOV, altitude,
    slant range, heading) relative to the frame center position.
    """
    base = _base()
    try:
        if packet is not None:
            sensorLatitude = packet.SensorLatitude
            sensorLongitude = packet.SensorLongitude
            sensorTrueAltitude = packet.SensorTrueAltitude
            frameCenterLat = packet.FrameCenterLatitude
            frameCenterLon = packet.FrameCenterLongitude
            frameCenterElevation = packet.FrameCenterElevation
            sensorVerticalFOV = packet.SensorVerticalFieldOfView
            sensorHorizontalFOV = packet.SensorHorizontalFieldOfView
            headingAngle = packet.PlatformHeadingAngle
            sensorRelativeAzimut = packet.SensorRelativeAzimuthAngle
            targetWidth = getattr(packet, "TargetWidth", None)
            if targetWidth is None:
                targetWidth = getattr(packet, "targetWidth", None)
            slantRange = packet.SlantRange
        else:
            sensorLatitude = sensor[1]
            sensorLongitude = sensor[0]
            sensorTrueAltitude = sensor[2]
            frameCenterLat = frameCenter[1]
            frameCenterLon = frameCenter[0]
            frameCenterElevation = frameCenter[2]
            sensorVerticalFOV = FOV[0]
            sensorHorizontalFOV = FOV[1]
            headingAngle = others[0]
            sensorRelativeAzimut = others[1]
            targetWidth = others[2]
            slantRange = others[3]

        if targetWidth is None:
            targetWidth = 0
        if slantRange is None:
            slantRange = 0
        # Compute target width from slant range and FOV if not provided.
        if targetWidth == 0 and slantRange != 0:
            targetWidth = 2.0 * slantRange * tan(radians(sensorHorizontalFOV / 2.0))
        elif targetWidth == 0 and slantRange == 0:
            targetWidth = DEFAULT_TARGET_WIDTH

        if sensorTrueAltitude is None:
            return False
        # Distance from sensor to ground level (above the frame center elevation).
        if frameCenterElevation is not None and frameCenterElevation != 0:
            sensorGroundAltitude = sensorTrueAltitude - frameCenterElevation
        elif frameCenterElevation is None:
            sensorGroundAltitude = sensorTrueAltitude
        else:
            return False

        if sensorLongitude is None or sensorLatitude is None:
            return False
        if frameCenterLon is None or frameCenterLat is None:
            return False

        sensor_point = (sensorLongitude, sensorLatitude)
        center_point = (frameCenterLon, frameCenterLat)

        distance_to_center = _geo_distance(sensor_point, center_point)
        if distance_to_center == 0:
            return False

        # Aspect ratio from FOV (fallback 0.75 for standard 4:3 sensors).
        if sensorVerticalFOV > 0 and sensorHorizontalFOV > sensorVerticalFOV:
            aspect_ratio = sensorVerticalFOV / sensorHorizontalFOV
        else:
            aspect_ratio = 0.75

        # Absolute heading = platform heading + sensor relative azimuth.
        absolute_heading = (headingAngle + sensorRelativeAzimut) % 360.0
        half_target_width = targetWidth / 2.0

        # Slant range from sensor to frame center (hypotenuse of ground dist + altitude).
        slant_to_center = sqrt(distance_to_center**2 + sensorGroundAltitude**2)
        half_cross_track = targetWidth * aspect_ratio / 2.0

        # Angular half-width of the target footprint as seen from the sensor.
        half_target_angle = degrees(atan(half_target_width / distance_to_center))

        # Angular elevation and depression angles for near/far edges of the footprint.
        center_elevation_angle = degrees(
            atan(distance_to_center / sensorGroundAltitude)
        )
        footprint_half_angle = degrees(atan(half_cross_track / slant_to_center))

        near_angle = center_elevation_angle - footprint_half_angle
        far_angle = center_elevation_angle + footprint_half_angle

        # Near/far ground distances from frame center along the look direction.
        near_ground_dist = sensorGroundAltitude * tan(radians(near_angle))
        far_ground_dist = sensorGroundAltitude * tan(radians(far_angle))

        # Distances along the look direction to the near and far edges.
        dist_to_near_edge = distance_to_center - near_ground_dist
        dist_to_far_edge = far_ground_dist - distance_to_center

        # Cross-track offsets for near and far edges.
        near_cross_track = half_target_width - dist_to_near_edge * tan(
            radians(half_target_angle)
        )
        far_cross_track = half_target_width + dist_to_far_edge * tan(
            radians(half_target_angle)
        )

        # Distances from frame center to each corner pair (near-left/right, far-left/right).
        near_corner_dist = sqrt(dist_to_near_edge**2 + near_cross_track**2)
        far_corner_dist = sqrt(dist_to_far_edge**2 + far_cross_track**2)

        # Angular offsets for the near and far cross-track corners.
        near_cross_angle = degrees(atan(near_cross_track / dist_to_near_edge))
        far_cross_angle = degrees(atan(far_cross_track / dist_to_far_edge))

        # Compute four corners: UL, UR (far edge), LR, LL (near edge).
        bearing_ul = (absolute_heading + 360.0 - far_cross_angle) % 360.0
        cornerPointUL = list(
            reversed(_geo_destination(center_point, far_corner_dist, bearing_ul))
        )

        bearing_ur = (absolute_heading + far_cross_angle) % 360.0
        cornerPointUR = list(
            reversed(_geo_destination(center_point, far_corner_dist, bearing_ur))
        )

        bearing_lr = (absolute_heading + 180.0 - near_cross_angle) % 360.0
        cornerPointLR = list(
            reversed(_geo_destination(center_point, near_corner_dist, bearing_lr))
        )

        bearing_ll = (absolute_heading + 180.0 + near_cross_angle) % 360.0
        cornerPointLL = list(
            reversed(_geo_destination(center_point, near_corner_dist, bearing_ll))
        )

        frameCenterPoint = [frameCenterLat, frameCenterLon, frameCenterElevation]

        if frameCenterPoint[0] is None and frameCenterPoint[1] is None:
            from QGISFMV.utils.core.QgsFmvUtils import gv

            gv.setTransform(None)
            return True
        if base.hasElevationModel():
            cornerPointUL = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointUL
            )
            cornerPointUR = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointUR
            )
            cornerPointLR = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointLR
            )
            cornerPointLL = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), cornerPointLL
            )
            frameCenterPoint = base.GetLine3DIntersectionWithDEM(
                base.GetSensor(), frameCenterPoint
            )

        if sensor is not None:
            return cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL

        base._update_footprint_beams_gcp(
            packet,
            cornerPointUL,
            cornerPointUR,
            cornerPointLR,
            cornerPointLL,
            frameCenterPoint,
            base.hasElevationModel(),
        )

    except Exception as e:
        qgsu.showUserAndLogMessage(
            "CornerEstimationWithoutOffsets failed! : ",
            str(e),
        )
        return False

    return True
