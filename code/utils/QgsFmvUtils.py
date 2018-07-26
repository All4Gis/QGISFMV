# -*- coding: utf-8 -*-
import datetime
from math import *
import os
import platform
import shutil
from subprocess import Popen, PIPE, check_output, STDOUT
import threading

from PyQt5.QtCore import QCoreApplication, QBuffer, QIODevice
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QApplication
from QGIS_FMV.fmvConfig import Platform_lyr, Beams_lyr, Footprint_lyr, frames_g
from QGIS_FMV.fmvConfig import ffmpeg as ffmpeg_path
from QGIS_FMV.fmvConfig import ffprobe as ffprobe_path
from QGIS_FMV.geo import sphere as sphere
from QGIS_FMV.utils.QgsFmvLayers import addLayerNoCrsDialog
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.core import QgsApplication, QgsFeature, QgsGeometry, QgsPointXY, QgsRasterLayer
from qgis.gui import *
from homography import Homography, from_points


try:
    from cv2 import COLOR_BGR2RGB, cvtColor, GaussianBlur, COLOR_GRAY2RGB, COLOR_BGR2GRAY
    import numpy as np
except ImportError:
    None

try:
    from osgeo import gdal, osr
except ImportError:
    import gdal

try:
    from pydevd import *
except ImportError:
    None

windows = platform.system() == 'Windows'

xSize = 0
ySize = 0
geotransform = None

gcornerPointUL = None
gcornerPointUR = None
gcornerPointLR = None
gcornerPointLL = None
gframeCenterLon = None
gframeCenterLat = None

if windows:
    ffmpeg_path = ffmpeg_path + '\\win\\ffmpeg.exe'
    ffprobe_path = ffprobe_path + '\\win\\ffprobe.exe'
else:
    ffmpeg_path = ffmpeg_path + '\\linux\\ffmpeg'
    ffprobe_path = ffprobe_path + '\\linux\\ffprobe'


class callBackMetadataThread(threading.Thread):
    '''  Test : CallBack metadata in other thread  '''

    def __init__(self, cmds, type="ffmpeg"):
        self.stdout = None
        self.stderr = None
        self.cmds = cmds
        self.type = type
        self.p = None
        threading.Thread.__init__(self)

    def run(self):
        if self.type is "ffmpeg":
            self.cmds.insert(0, ffmpeg_path)
        else:
            self.cmds.insert(0, ffprobe_path)
        self.p = Popen(self.cmds,
                       shell=True,
                       stdout=PIPE,
                       stderr=PIPE, bufsize=0,
                       close_fds=(not windows))

        self.stdout, self.stderr = self.p.communicate()


def convertQImageToMat(img):
    '''  Converts a QImage into an opencv MAT format  '''
    img = img.convertToFormat(4)
    w = img.width()
    h = img.height()

    ptr = img.bits()
    ptr.setsize(img.byteCount())
    arr = np.array(ptr).reshape(h, w, 4)  # Copies the data
    return arr


def convertMatToQImage(img):
    '''  Converts an opencv MAT image to a QImage  '''
    height, width = img.shape[:2]
    if img.ndim == 3:
        rgb = cvtColor(img, COLOR_BGR2RGB)
    elif img.ndim == 2:
        rgb = cvtColor(img, COLOR_GRAY2RGB)
    else:
        raise Exception("Unstatistified image data format!")
    qimage = QImage(rgb.flatten(), width, height, QImage.Format_RGB888)
    return qimage


def SetGCPsToGeoTransform(cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat):
    ''' Make Geotranform from pixel to lon lat coordinates '''
    gcps = []

    global gcornerPointUL
    gcornerPointUL = cornerPointUL
    global gcornerPointUR
    gcornerPointUR = cornerPointUR
    global gcornerPointLR
    gcornerPointLR = cornerPointLR
    global gcornerPointLL
    gcornerPointLL = cornerPointLL
    global gframeCenterLat
    gframeCenterLat = frameCenterLat
    global gframeCenterLon
    gframeCenterLon = frameCenterLon

    global geotransform
    geotransform = gdal.GCPsToGeoTransform(gcps)

    src = np.float64(np.array([[0.0, 0.0], [xSize, 0.0], [xSize, ySize], [0.0, ySize]]))
    dst = np.float64(np.array([cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]))
    geotransform = from_points(src, dst)
    
    if geotransform is None:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", 'Unable to extract a geotransform.'), onlyLog=True)

    return


def GetGCPGeoTransform():
    ''' Return Geotransform '''
    return geotransform


def SetImageSize(w, h):
    ''' Set Image Size '''
    global xSize
    global ySize
    xSize = w
    ySize = h
    return

def GetImageWidth():
    global xSize
    return xSize

def GetImageHeight():
    global ySize
    return ySize

def _check_output(cmds, type="ffmpeg"):
    ''' Check Output Commands in Python '''

    if type is "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    return check_output(cmds, shell=True, close_fds=(not windows))


def _spawn(cmds, type="ffmpeg"):
    ''' Subprocess and Shell Commands in Python '''

    if type is "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    return Popen(cmds, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE, bufsize=0,
                 close_fds=(not windows))


def install_pip_requirements():
    ''' Install Requeriments from pip '''
    try:
        import pip
    except ImportError:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Import Pip! : "), str(e), onlyLog=True)
        raise

    package_dir = QgsApplication.qgisSettingsDirPath() + 'python/plugins/QGIS_FMV/'
    requirements_file = os.path.join(package_dir, 'requirements.txt')
    if not os.path.isfile(requirements_file):
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", 'No requirements file found in {}'.format(requirements_file)), str(e), onlyLog=True)
        raise
    try:
        pip.main(['install', '-r', requirements_file])
    except:
        raise
    return


def install_requirements_copy(lib="all"):
    ''' Install Requeriments from ext-libs '''
    ext_libs_dir = QgsApplication.qgisSettingsDirPath(
    ) + 'python/plugins/QGIS_FMV/ext-libs/'

    site_packages = os.path.dirname(
        QgsApplication.prefixPath()) + '/Python36/lib/site-packages/'
    try:
        if lib == "cv2":
            copytree(ext_libs_dir + "cv2", site_packages + "cv2")
        else:
            try:  # TODO: permissions denied
                copytree(os.path.join(ext_libs_dir, "matplotlib"),
                         os.path.join(site_packages, "matplotlib"))
                copytree(os.path.join(ext_libs_dir, "cv2"),
                         os.path.join(site_packages, "cv2"))
            except:
                return

        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", 'Libraries copied satisfactorily'), onlyLog=True)
    # Directories are the same
    except shutil.Error as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", 'Library not copied.Directories are the same'), str(e), onlyLog=True)
    # Any error saying that the directory doesn't exist
    except OSError as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", 'Library not copied'), str(e), onlyLog=True)
    return


def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)


def rad2deg(radians):
    ''' Radians to Degrees '''
    degrees = 180 * radians / pi
    return degrees


def deg2rad(degrees):
    ''' Degrees to Radians '''
    radians = pi * degrees / 180
    return radians


def UpdateLayers(packet, parent=None, mosaic=False):
    ''' Update Layers Values '''
    UpdatePlatformData(packet)

    OffsetLat1 = packet.GetOffsetCornerLatitudePoint1()
    LatitudePoint1Full = packet.GetCornerLatitudePoint1Full()

    if OffsetLat1 is not None and LatitudePoint1Full is None:
        CornerEstimationWithOffsets(packet)
        if mosaic:
            georeferencingVideo(parent)
        return

    if OffsetLat1 is None and LatitudePoint1Full is None:
        CornerEstimationWithoutOffsets(packet)
        if mosaic:
            georeferencingVideo(parent)
        return

    cornerPointUL = [packet.GetCornerLatitudePoint1Full(
    ), packet.GetCornerLongitudePoint1Full()]

    cornerPointUR = [packet.GetCornerLatitudePoint2Full(
    ), packet.GetCornerLongitudePoint2Full()]

    cornerPointLR = [packet.GetCornerLatitudePoint3Full(
    ), packet.GetCornerLongitudePoint3Full()]

    cornerPointLL = [packet.GetCornerLatitudePoint4Full(
    ), packet.GetCornerLongitudePoint4Full()]

    UpdateFootPrintData(
        cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL)

    UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                    cornerPointLR, cornerPointLL)

    frameCenterLat = packet.GetFrameCenterLatitude()
    frameCenterLon = packet.GetFrameCenterLongitude()

    SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                          cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat)

    if mosaic:
        georeferencingVideo(parent)
    return


def georeferencingVideo(parent):
    """ Extract Current Frame Thread """
    # only works on custom video surface
    image = parent.videoWidget.GetCurrentFrame()
    root, ext = os.path.splitext(os.path.basename(parent.fileName))
    out = os.path.join(os.path.expanduser("~"), "QGIS_FMV", root)
    GeoreferenceFrame(image, out, parent)
    return


def GeoreferenceFrame(image, output, parent):
    ''' Save Current Image '''

    # TODO : Add in a custom group?Remove when close dialog?Create memory
    # raster?

    p = str(parent.player.position())
    if p == "0":
        return

    ext = ".tiff"

    t = "out_" + p + ext
    name = "g_" + p
    f_g = name + ext

    src_file = os.path.join(output, t)

    image.save(src_file)

    dst_filename = os.path.join(os.path.dirname(src_file), f_g)

    # Opens source dataset
    src_ds = gdal.Open(src_file)
    driver = gdal.GetDriverByName("GTiff")

    # Open destination dataset
    dst_ds = driver.CreateCopy(dst_filename, src_ds, 0)

    # Get raster projection
    epsg = 4326
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg)

    # Set projection
    dst_ds.SetProjection(srs.ExportToWkt())

    # Set location
    dst_ds.SetGeoTransform(geotransform)
    dst_ds.GetRasterBand(1).SetNoDataValue(0)

    # Close files
    dst_ds = None
    src_ds = None

    try:
        os.remove(src_file)
    except OSError:
        pass
    # Add Layer to canvas
    layer = QgsRasterLayer(dst_filename, name)
    addLayerNoCrsDialog(layer, False, frames_g)
    QApplication.processEvents()
    return


def CommonLayer(value):
    ''' Common comands Layers '''
    value.commitChanges()
    value.updateExtents()
    value.triggerRepaint()


def UpdateBeamsData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL):
    ''' Update Beams Values '''
    lat = packet.GetSensorLatitude()
    lon = packet.GetSensorLongitude()
    alt = packet.GetSensorTrueAltitude()

    beamsLyr = qgsu.selectLayerByName(Beams_lyr)

    try:
        if beamsLyr is not None:
            beamsLyr.startEditing()
            if beamsLyr.featureCount() == 0:

                # UL
                featureUL = QgsFeature()
                featureUL.setAttributes(
                    [lon, lat, alt, cornerPointUL[1], cornerPointUL[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointUL[1], cornerPointUL[0])])
                featureUL.setGeometry(surface)
                beamsLyr.addFeatures([featureUL])
                # UR
                featureUR = QgsFeature()
                featureUR.setAttributes(
                    [lon, lat, alt, cornerPointUR[1], cornerPointUR[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointUR[1], cornerPointUR[0])])
                featureUR.setGeometry(surface)
                beamsLyr.addFeatures([featureUR])
                # LR
                featureLR = QgsFeature()
                featureLR.setAttributes(
                    [lon, lat, alt, cornerPointLR[1], cornerPointLR[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointLR[1], cornerPointLR[0])])
                featureLR.setGeometry(surface)
                beamsLyr.addFeatures([featureLR])
                # LL
                featureLL = QgsFeature()
                featureLL.setAttributes(
                    [lon, lat, alt, cornerPointLL[1], cornerPointLL[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointLL[1], cornerPointLL[0])])
                featureLL.setGeometry(surface)
                beamsLyr.addFeatures([featureLL])

            else:
                beamsLyr.beginEditCommand(
                    "ChangeGeometry + ChangeAttribute")
                # UL
                fetId = 1
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointUL[1], 4: cornerPointUL[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([QgsPointXY(lon, lat), QgsPointXY(cornerPointUL[1], cornerPointUL[0])])})
                # UR
                fetId = 2
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointUR[1], 4: cornerPointUR[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([QgsPointXY(lon, lat), QgsPointXY(cornerPointUR[1], cornerPointUR[0])])})
                # LR
                fetId = 3
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointLR[1], 4: cornerPointLR[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([QgsPointXY(lon, lat), QgsPointXY(cornerPointLR[1], cornerPointLR[0])])})
                # LL
                fetId = 4
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointLL[1], 4: cornerPointLL[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([QgsPointXY(lon, lat), QgsPointXY(cornerPointLL[1], cornerPointLL[0])])})

                beamsLyr.endEditCommand()

            CommonLayer(beamsLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Beams Layer! : "), str(e))
    return


def UpdateFootPrintData(cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL):
    ''' Update Footprint Values '''
    footprintLyr = qgsu.selectLayerByName(Footprint_lyr)

    try:
        if footprintLyr is not None:
            footprintLyr.startEditing()
            if footprintLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([cornerPointUL[1], cornerPointUL[0], cornerPointUR[1], cornerPointUR[0],
                                       cornerPointLR[1], cornerPointLR[0], cornerPointLL[1], cornerPointLL[0]])
                surface = QgsGeometry.fromPolygonXY([[QgsPointXY(cornerPointUL[1], cornerPointUL[0]),
                                                      QgsPointXY(
                    cornerPointUR[1], cornerPointUR[0]),
                    QgsPointXY(
                    cornerPointLR[1], cornerPointLR[0]),
                    QgsPointXY(
                    cornerPointLL[1], cornerPointLL[0]),
                    QgsPointXY(cornerPointUL[1], cornerPointUL[0])]])
                feature.setGeometry(surface)
                footprintLyr.addFeatures([feature])
            else:
                footprintLyr.beginEditCommand(
                    "ChangeGeometry + ChangeAttribute")
                fetId = 1
                attrib = {0: cornerPointUL[1], 1: cornerPointUL[0], 2: cornerPointUR[1], 3: cornerPointUR[0],
                          4: cornerPointLR[1], 5: cornerPointLR[0], 6: cornerPointLL[1], 7: cornerPointLL[0]}

                footprintLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})

                footprintLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolygonXY([[QgsPointXY(cornerPointUL[1],
                                                                   cornerPointUL[0]),
                                                        QgsPointXY(
                        cornerPointUR[1], cornerPointUR[0]),
                        QgsPointXY(
                        cornerPointLR[1], cornerPointLR[0]),
                        QgsPointXY(
                        cornerPointLL[1], cornerPointLL[0]),
                        QgsPointXY(cornerPointUL[1], cornerPointUL[0])]])})
            footprintLyr.endEditCommand()

            CommonLayer(footprintLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update FootPrint Layer! : "), str(e))
    return


def UpdatePlatformData(packet):
    ''' Update PlatForm Values '''
    lat = packet.GetSensorLatitude()
    lon = packet.GetSensorLongitude()
    alt = packet.GetSensorTrueAltitude()
    PlatformHeading = packet.GetPlatformHeadingAngle()
    platformLyr = qgsu.selectLayerByName(Platform_lyr)

    try:
        if all(v is not None for v in [platformLyr, lat, lon, alt, PlatformHeading]):
            platformLyr.startEditing()
            platformLyr.renderer().symbol().setAngle(float(PlatformHeading))

            if platformLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([lon, lat, alt])
                p = QgsPointXY()
                p.set(lon, lat)
                geom = QgsGeometry.fromPointXY(p)
                feature.setGeometry(geom)
                platformLyr.addFeatures([feature])

            else:
                platformLyr.beginEditCommand(
                    "ChangeGeometry + ChangeAttribute")
                fetId = 1
                attrib = {0: lon, 1: lat, 2: alt}
                platformLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})

                platformLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry.fromPointXY(QgsPointXY(lon, lat))})
                platformLyr.endEditCommand()

            CommonLayer(platformLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Platform Layer! : "), str(e))

    return


def CornerEstimationWithOffsets(packet):
    ''' Corner estimation using Offsets '''
    try:

        OffsetLat1 = packet.GetOffsetCornerLatitudePoint1()
        OffsetLon1 = packet.GetOffsetCornerLongitudePoint1()
        OffsetLat2 = packet.GetOffsetCornerLatitudePoint2()
        OffsetLon2 = packet.GetOffsetCornerLongitudePoint2()
        OffsetLat3 = packet.GetOffsetCornerLatitudePoint3()
        OffsetLon3 = packet.GetOffsetCornerLongitudePoint3()
        OffsetLat4 = packet.GetOffsetCornerLatitudePoint4()
        OffsetLon4 = packet.GetOffsetCornerLongitudePoint4()
        frameCenterLat = packet.GetFrameCenterLatitude()
        frameCenterLon = packet.GetFrameCenterLongitude()

        # Lat,Lon
        cornerPointUL = (OffsetLat1 + frameCenterLat,
                         OffsetLon1 + frameCenterLon)
        cornerPointUR = (OffsetLat2 + frameCenterLat,
                         OffsetLon2 + frameCenterLon)
        cornerPointLR = (OffsetLat3 + frameCenterLat,
                         OffsetLon3 + frameCenterLon)
        cornerPointLL = (OffsetLat4 + frameCenterLat,
                         OffsetLon4 + frameCenterLon)

        UpdateFootPrintData(
            cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL)

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL)

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat)

    except:
        return False

    return True


def CornerEstimationWithoutOffsets(packet):
    ''' Corner estimation without Offsets '''
    try:
        sensorLatitude = packet.GetSensorLatitude()
        sensorLongitude = packet.GetSensorLongitude()
        sensorTrueAltitude = packet.GetSensorTrueAltitude()
        frameCenterLat = packet.GetFrameCenterLatitude()
        frameCenterLon = packet.GetFrameCenterLongitude()
        sensorVerticalFOV = packet.GetSensorVerticalFieldOfView()
        sensorHorizontalFOV = packet.GetSensorHorizontalFieldOfView()
        headingAngle = packet.GetPlatformHeadingAngle()
        sensorRelativeAzimut = packet.GetSensorRelativeAzimuthAngle()
        targetWidth = packet.GettargetWidth()

        if sensorLatitude == 0:
            return False

        initialPoint = (sensorLongitude, sensorLatitude)
        destPoint = (frameCenterLon, frameCenterLat)

        distance = sphere.distance(initialPoint, destPoint)
        if distance == 0:
            return False

        if sensorVerticalFOV > 0 and sensorHorizontalFOV > sensorVerticalFOV:
            aspectRatio = sensorVerticalFOV / sensorHorizontalFOV

        else:
            aspectRatio = 0.75

        value2 = (headingAngle + sensorRelativeAzimut) % 360.0  # Heading
        value3 = targetWidth / 2.0

        value5 = sqrt(pow(distance, 2.0) + pow(sensorTrueAltitude, 2.0))
        value6 = targetWidth * aspectRatio / 2.0

        degrees = rad2deg(atan(value3 / distance))

        value8 = rad2deg(atan(distance / sensorTrueAltitude))
        value9 = rad2deg(atan(value6 / value5))
        value10 = value8 + value9
        value11 = sensorTrueAltitude * tan(radians(value10))
        value12 = value8 - value9
        value13 = sensorTrueAltitude * tan(radians(value12))
        value14 = distance - value13
        value15 = value11 - distance
        value16 = value3 - value14 * tan(radians(degrees))
        value17 = value3 + value15 * tan(radians(degrees))
        distance2 = sqrt(pow(value14, 2.0) + pow(value16, 2.0))
        value19 = sqrt(pow(value15, 2.0) + pow(value17, 2.0))
        value20 = rad2deg(atan(value16 / value14))
        value21 = rad2deg(atan(value17 / value15))

        # CP Up Left
        bearing = (value2 + 360.0 - value21) % 360.0
        cornerPointUL = sphere.destination(destPoint, value19, bearing)

        # TODO: Use Geopy?
#         from geopy import Point
#         from geopy.distance import distance, VincentyDistance
#
#         # given: lat1, lon1, bearing, distMiles
#         lat2, lon2 = VincentyDistance(kilometers=value19).destination(Point(destPoint[1], destPoint[0]), bearing)

        # CP Up Right
        bearing = (value2 + value21) % 360.0
        cornerPointUR = sphere.destination(destPoint, value19, bearing)

        # CP Low Right
        bearing = (value2 + 180.0 - value20) % 360.0
        cornerPointLR = sphere.destination(destPoint, distance2, bearing)

        # CP Low Left
        bearing = (value2 + 180.0 + value20) % 360.0
        cornerPointLL = sphere.destination(destPoint, distance2, bearing)

        UpdateFootPrintData(
            cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL)

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL)

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat)
    except:
        return False

    return True


def _convert_timestamp(ts):
    '''Translates the values from a regex match for two timestamps of the
    form 00:12:34,567 into seconds.'''
    start = int(ts.group(1)) * 3600 + int(ts.group(2)) * 60
    start += int(ts.group(3))
    start += float(ts.group(4)) / 10 ** len(ts.group(4))
    end = int(ts.group(5)) * 3600 + int(ts.group(6)) * 60
    end += int(ts.group(7))
    end += float(ts.group(8)) / 10 ** len(ts.group(8))
    return start, end


def _seconds_to_time(sec):
    '''Returns a string representation of the length of time provided.
    For example, 3675.14 -> '01:01:15' '''
    hours = int(sec / 3600)
    sec -= hours * 3600
    minutes = int(sec / 60)
    sec -= minutes * 60
    return '%02d:%02d:%02d' % (hours, minutes, sec)


def _seconds_to_time_frac(sec, comma=False):
    '''Returns a string representation of the length of time provided,
    including partial seconds.
    For example, 3675.14 -> '01:01:15.140000' '''
    hours = int(sec / 3600)
    sec -= hours * 3600
    minutes = int(sec / 60)
    sec -= minutes * 60
    if comma:
        frac = int(round(sec % 1.0 * 1000))
        return '%02d:%02d:%02d,%03d' % (hours, minutes, sec, frac)
    else:
        return '%02d:%02d:%07.4f' % (hours, minutes, sec)
