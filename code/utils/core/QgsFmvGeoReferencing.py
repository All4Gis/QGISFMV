# -*- coding: utf-8 -*-
"""Georeferencing utilities: GCP transforms, corner estimation, DEM intersection."""

from math import sin, atan, tan, sqrt, radians, pi, degrees, isfinite

import numpy as np

try:
    from osgeo import gdal, osr
except ImportError:
    gdal = None
    osr = None

try:
    from cv2 import findHomography

    _HAS_CV2 = True
except ImportError:
    findHomography = None
    _HAS_CV2 = False

from QGISFMV.utils.logging import log
from QGISFMV.utils.core.QgsFmvUtilsState import globalVariablesState
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.layers.QgsFmvLayers import (
    UpdateFootPrintData,
    UpdateBeamsData,
)
from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance, destination as _geo_destination

DEFAULT_TARGET_WIDTH = 200.0


# ---------------------------------------------------------------------------
# Homography helpers
# ---------------------------------------------------------------------------

def _find_homography_numpy(src_pts, dst_pts):
    """Perspective homography without OpenCV (DLT, 3x3)."""
    src = np.asarray(src_pts, dtype=np.float32)
    dst = np.asarray(dst_pts, dtype=np.float32)
    rows = []
    for i in range(src.shape[0]):
        x, y = src[i]
        u, v = dst[i]
        rows.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        rows.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])
    A = np.array(rows, dtype=np.float32)
    _, _, Vt = np.linalg.svd(A)
    H = Vt[-1].reshape(3, 3)
    if abs(H[2, 2]) > 1e-12:
        H = H / H[2, 2]
    return H


def _find_homography(src_pts, dst_pts):
    src = np.asarray(src_pts, dtype=np.float32)
    dst = np.asarray(dst_pts, dtype=np.float32)
    if findHomography is not None:
        try:
            H, _ = findHomography(src, dst)
            if H is not None:
                return H
        except Exception as e:
            log.debug("OpenCV findHomography failed, using numpy fallback: %s", e)
    return _find_homography_numpy(src, dst)


# ---------------------------------------------------------------------------
# DEM / DTM helpers
# ---------------------------------------------------------------------------

def hasElevationModel():
    """Check if DEM is loaded"""
    from QGISFMV.utils.core.QgsFmvUtils import dtm_data
    return bool(dtm_data)


def GetDemAltAt(lon, lat):
    """Return the DTM elevation at (lon, lat), or 0 if no DTM is loaded."""
    from QGISFMV.utils.core.QgsFmvUtils import (
        dtm_data,
        dtm_transform,
        dtm_colLowerBound,
        dtm_rowLowerBound,
    )
    alt = 0
    if dtm_transform is None or not dtm_data:
        return float(alt)

    xOrigin = dtm_transform[0]
    yOrigin = dtm_transform[3]
    pixelWidth = dtm_transform[1]
    pixelHeight = -dtm_transform[5]

    col = int((lon - xOrigin) / pixelWidth)
    row = int((yOrigin - lat) / pixelHeight)
    try:
        alt = dtm_data[row - dtm_rowLowerBound][col - dtm_colLowerBound]
    except IndexError:
        pass

    return float(alt)


def GetLine3DIntersectionWithDEM(sensorPt, targetPt):
    """Obtain height for points, intersecting with DEM."""
    from QGISFMV.utils.core.QgsFmvUtils import (
        dtm_data,
        dtm_transform,
        dtm_buffer,
        dtm_colLowerBound,
        dtm_rowLowerBound,
    )
    sensorLat = sensorPt[0]
    sensorLon = sensorPt[1]
    sensorAlt = sensorPt[2]
    targetLat = targetPt[0]
    targetLon = targetPt[1]
    try:
        targetAlt = targetPt[2]
    except (IndexError, TypeError) as e:
        log.debug("GetLine3DIntersectionWithDEM: no target altitude, using frame center: %s", e)
        targetAlt = GetFrameCenter()[2]

    distance = _geo_distance([sensorLat, sensorLon], [targetLat, targetLon])
    distance = sqrt(distance**2 + (targetAlt - sensorAlt) ** 2)
    dLat = (targetLat - sensorLat) / distance
    dLon = (targetLon - sensorLon) / distance
    dAlt = (targetAlt - sensorAlt) / distance

    if dtm_transform is None or not dtm_data:
        result = list(targetPt)
        result.append(targetAlt)
        return result

    xOrigin = dtm_transform[0]
    yOrigin = dtm_transform[3]
    pixelWidth = dtm_transform[1]
    pixelHeight = -dtm_transform[5]

    pixelWidthMeter = pixelWidth * (pi / 180.0) * 6378137.0
    step = int(pixelWidthMeter)
    max_k = int(dtm_buffer * pixelWidthMeter)
    rlb = dtm_rowLowerBound
    clb = dtm_colLowerBound

    # Walk along the 3D ray until we cross the DTM surface (diffAlt <= 0).
    for k in range(0, max_k, step):
        lon = sensorLon + k * dLon
        lat = sensorLat + k * dLat
        alt = sensorAlt + k * dAlt

        col = int((lon - xOrigin) / pixelWidth)
        row = int((yOrigin - lat) / pixelHeight)
        try:
            diffAlt = alt - dtm_data[row - rlb][col - clb]
        except Exception:
            log.debug("DEM point not found after all iterations.")
            break
        if diffAlt <= 0:
            return [lat, lon, alt]

    # Fallback: return original point with target elevation.
    result = list(targetPt)
    result.append(targetAlt)
    return result


# ---------------------------------------------------------------------------
# State accessors
# ---------------------------------------------------------------------------

def GetSensor():
    """Get Sensor values"""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    return [gv.getSensorLatitude(), gv.getSensorLongitude(), gv.getSensorTrueAltitude()]


def GetFrameCenter():
    """Get Frame Center values"""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    sensorTrueAltitude = gv.getSensorTrueAltitude()
    # if sensor height is null, compute it from sensor altitude.
    if gv.getFrameCenterElevation() is None:
        if sensorTrueAltitude is not None:
            gv.setFrameCenterElevation(sensorTrueAltitude - 500)
        else:
            gv.setFrameCenterElevation(0)

    return [
        gv.getFrameCenterLat(),
        gv.getFrameCenterLon(),
        gv.getFrameCenterElevation(),
    ]


def GetGCPGeoTransform():
    """Return Geotransform"""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    return gv.getTransform()


def GetGeotransform_affine():
    """Get current frame affine transformation"""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    return gv.getAffineTransform()


def SetImageSize(w, h):
    """Set Image Size — skip if unchanged to avoid redundant state updates."""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    if gv is None or w <= 0 or h <= 0:
        return
    if gv.getXSize() == w and gv.getYSize() == h:
        return
    gv.setXSize(w)
    gv.setYSize(h)


def GetImageWidth():
    """Get Image Width"""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    if gv is None:
        return 0
    return gv.getXSize()


def GetImageHeight():
    """Get Image Height"""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    if gv is None:
        return 0
    return gv.getYSize()


# ---------------------------------------------------------------------------
# Affine / transform helpers
# ---------------------------------------------------------------------------

def _affineTransformIsUsable(affine):
    if affine is None or len(affine) != 6:
        return False
    return all(isfinite(v) for v in affine)


def _refreshAffineFromStoredCorners():
    """Recompute GDAL affine when corners are known but image size was still zero."""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    if gv is None:
        return False
    ul = gv.getCornerUL()
    ur = gv.getCornerUR()
    lr = gv.getCornerLR()
    ll = gv.getCornerLL()
    if None in (ul, ur, lr, ll):
        return False
    if any(v is None for corner in (ul, ur, lr, ll) for v in corner):
        return False
    if gv.getXSize() <= 0 or gv.getYSize() <= 0:
        return False
    lat = gv.getFrameCenterLat()
    lon = gv.getFrameCenterLon()
    if lat is None or lon is None:
        return False
    SetGCPsToGeoTransform(ul, ur, lr, ll, lon, lat, hasElevationModel())
    return _affineTransformIsUsable(gv.getAffineTransform())


def _footprint_inputs_changed(packet):
    """Return True when footprint corner inputs differ from the last computed geometry."""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    if gv is None:
        return True
    if packet.CornerLatitudePoint1Full is None:
        return True

    ul = gv.getCornerUL()
    ur = gv.getCornerUR()
    lr = gv.getCornerLR()
    ll = gv.getCornerLL()
    if None in (ul, ur, lr, ll):
        return True

    def corner_changed(lat, lon, stored):
        return (
            abs(float(lat) - float(stored[0])) > 1e-8
            or abs(float(lon) - float(stored[1])) > 1e-8
        )

    return any(
        (
            corner_changed(
                packet.CornerLatitudePoint1Full,
                packet.CornerLongitudePoint1Full,
                ul,
            ),
            corner_changed(
                packet.CornerLatitudePoint2Full,
                packet.CornerLongitudePoint2Full,
                ur,
            ),
            corner_changed(
                packet.CornerLatitudePoint3Full,
                packet.CornerLongitudePoint3Full,
                lr,
            ),
            corner_changed(
                packet.CornerLatitudePoint4Full,
                packet.CornerLongitudePoint4Full,
                ll,
            ),
        )
    )


# ---------------------------------------------------------------------------
# GCP / GeoTransform
# ---------------------------------------------------------------------------

def SetGCPsToGeoTransform(
    cornerPointUL,
    cornerPointUR,
    cornerPointLR,
    cornerPointLL,
    frameCenterLon,
    frameCenterLat,
    ele,
):
    """Make Geotranform from pixel to lon lat coordinates"""
    from QGISFMV.utils.core.QgsFmvUtils import gv
    gcps = []
    gv.setCornerUL(cornerPointUL)
    gv.setCornerUR(cornerPointUR)
    gv.setCornerLR(cornerPointLR)
    gv.setCornerLL(cornerPointLL)
    gv.setFrameCenter(frameCenterLat, frameCenterLon)

    xSize = gv.getXSize()
    ySize = gv.getYSize()

    Height = GetFrameCenter()[2]

    gcp = gdal.GCP(
        cornerPointUL[1], cornerPointUL[0], Height, 0, 0, "Corner Upper Left", "1"
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        cornerPointUR[1], cornerPointUR[0], Height, xSize, 0, "Corner Upper Right", "2"
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        cornerPointLR[1],
        cornerPointLR[0],
        Height,
        xSize,
        ySize,
        "Corner Lower Right",
        "3",
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        cornerPointLL[1], cornerPointLL[0], Height, 0, ySize, "Corner Lower Left", "4"
    )
    gcps.append(gcp)
    gcp = gdal.GCP(
        frameCenterLon, frameCenterLat, Height, xSize / 2, ySize / 2, "Center", "5"
    )
    gcps.append(gcp)

    at = gdal.GCPsToGeoTransform(gcps)
    gv.setAffineTransform(at)

    src = np.float32(
        np.array(
            [
                [0.0, 0.0],
                [xSize, 0.0],
                [xSize, ySize],
                [0.0, ySize],
                [xSize / 2.0, ySize / 2.0],
            ]
        )
    )
    dst = np.float32(
        np.array(
            [
                [cornerPointUL[0], cornerPointUL[1]],
                [cornerPointUR[0], cornerPointUR[1]],
                [cornerPointLR[0], cornerPointLR[1]],
                [cornerPointLL[0], cornerPointLL[1]],
                [frameCenterLat, frameCenterLon],
            ]
        )
    )

    geotransform = None
    try:
        geotransform = _find_homography(src, dst)
        if geotransform is not None:
            gv.setTransform(geotransform)
    except Exception as e:
        log.debug("SetGCPsToGeoTransform homography failed: %s", e)

    if geotransform is None:
        qgsu.showUserAndLogMessage(
            "", "Unable to extract a geotransform.", onlyLog=True
        )

    return


def _update_footprint_beams_gcp(packet, ul, ur, lr, ll, frame_center, ele):
    """Shared helper: update footprint polygon, sensor beams, and GCP geotransform."""
    UpdateFootPrintData(packet, ul, ur, lr, ll, ele)
    UpdateBeamsData(packet, ul, ur, lr, ll, ele)
    SetGCPsToGeoTransform(ul, ur, lr, ll, frame_center[1], frame_center[0], ele)


# ---------------------------------------------------------------------------
# Corner estimation
# ---------------------------------------------------------------------------

def CornerEstimationWithOffsets(packet):
    """Corner estimation using Offsets
    :param packet: Metada packet
    """
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
        if hasElevationModel():
            cornerPointUL = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointUL)
            cornerPointUR = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointUR)
            cornerPointLR = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointLR)
            cornerPointLL = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointLL)
            frameCenterPoint = GetLine3DIntersectionWithDEM(
                GetSensor(), frameCenterPoint
            )

        _update_footprint_beams_gcp(
            packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL,
            frameCenterPoint, hasElevationModel(),
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
        slant_to_center = sqrt(distance_to_center ** 2 + sensorGroundAltitude ** 2)
        half_cross_track = targetWidth * aspect_ratio / 2.0

        # Angular half-width of the target footprint as seen from the sensor.
        half_target_angle = degrees(atan(half_target_width / distance_to_center))

        # Angular elevation and depression angles for near/far edges of the footprint.
        center_elevation_angle = degrees(atan(distance_to_center / sensorGroundAltitude))
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
        near_cross_track = half_target_width - dist_to_near_edge * tan(radians(half_target_angle))
        far_cross_track = half_target_width + dist_to_far_edge * tan(radians(half_target_angle))

        # Distances from frame center to each corner pair (near-left/right, far-left/right).
        near_corner_dist = sqrt(dist_to_near_edge ** 2 + near_cross_track ** 2)
        far_corner_dist = sqrt(dist_to_far_edge ** 2 + far_cross_track ** 2)

        # Angular offsets for the near and far cross-track corners.
        near_cross_angle = degrees(atan(near_cross_track / dist_to_near_edge))
        far_cross_angle = degrees(atan(far_cross_track / dist_to_far_edge))

        # Compute four corners: UL, UR (far edge), LR, LL (near edge).
        bearing_ul = (absolute_heading + 360.0 - far_cross_angle) % 360.0
        cornerPointUL = list(reversed(_geo_destination(center_point, far_corner_dist, bearing_ul)))

        bearing_ur = (absolute_heading + far_cross_angle) % 360.0
        cornerPointUR = list(reversed(_geo_destination(center_point, far_corner_dist, bearing_ur)))

        bearing_lr = (absolute_heading + 180.0 - near_cross_angle) % 360.0
        cornerPointLR = list(reversed(_geo_destination(center_point, near_corner_dist, bearing_lr)))

        bearing_ll = (absolute_heading + 180.0 + near_cross_angle) % 360.0
        cornerPointLL = list(reversed(_geo_destination(center_point, near_corner_dist, bearing_ll)))

        frameCenterPoint = [frameCenterLat, frameCenterLon, frameCenterElevation]

        if frameCenterPoint[0] is None and frameCenterPoint[1] is None:
            from QGISFMV.utils.core.QgsFmvUtils import gv
            gv.setTransform(None)
            return True
        if hasElevationModel():
            cornerPointUL = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointUL)
            cornerPointUR = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointUR)
            cornerPointLR = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointLR)
            cornerPointLL = GetLine3DIntersectionWithDEM(GetSensor(), cornerPointLL)
            frameCenterPoint = GetLine3DIntersectionWithDEM(
                GetSensor(), frameCenterPoint
            )

        if sensor is not None:
            return cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL

        _update_footprint_beams_gcp(
            packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL,
            frameCenterPoint, hasElevationModel(),
        )

    except Exception as e:
        qgsu.showUserAndLogMessage(
            "CornerEstimationWithoutOffsets failed! : ",
            str(e),
        )
        return False

    return True
