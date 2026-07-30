# -*- coding: utf-8 -*-
"""Georeferencing utilities: GCP transforms, corner estimation, DEM intersection."""

from math import isfinite, pi, sqrt

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

from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance
from QGISFMV.utils.layers.QgsFmvLayers import UpdateBeamsData, UpdateFootPrintData
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

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
        dtm_colLowerBound,
        dtm_data,
        dtm_rowLowerBound,
        dtm_transform,
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
        dtm_buffer,
        dtm_colLowerBound,
        dtm_data,
        dtm_rowLowerBound,
        dtm_transform,
    )

    sensorLat = sensorPt[0]
    sensorLon = sensorPt[1]
    sensorAlt = sensorPt[2]
    targetLat = targetPt[0]
    targetLon = targetPt[1]
    try:
        targetAlt = targetPt[2]
    except (IndexError, TypeError) as e:
        log.debug(
            "GetLine3DIntersectionWithDEM: no target altitude, using frame center: %s",
            e,
        )
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


# Shared helper lives above; corner-point estimation lives in
# QgsFmvCornerEstimation.py (imported by QgsFmvUtils / callers directly).
