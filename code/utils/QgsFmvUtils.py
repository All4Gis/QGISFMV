# -*- coding: utf-8 -*-
import inspect
from math import atan, tan, sqrt, radians, pi
import os
import platform
import shutil
from datetime import datetime
from subprocess import Popen, PIPE, check_output
import threading

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QFileDialog
from QGIS_FMV.klvdata.streamparser import StreamParser
from QGIS_FMV.fmvConfig import (Platform_lyr,
                                Beams_lyr,
                                Footprint_lyr,
                                Trajectory_lyr,
                                frames_g,
                                DTM_buffer_size as dtm_buffer)
from QGIS_FMV.fmvConfig import ffmpeg as ffmpeg_path
from QGIS_FMV.fmvConfig import ffprobe as ffprobe_path
from QGIS_FMV.geo import sphere as sphere
from QGIS_FMV.utils.QgsFmvLayers import (addLayerNoCrsDialog,
                                         ExpandLayer,
                                         SetDefaultFootprintStyle,
                                         SetDefaultPlatformStyle)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.PyQt.QtCore import QSettings
from qgis.core import (QgsApplication,
                       QgsFeature,
                       QgsGeometry,
                       QgsPointXY,
                       QgsRasterLayer,
                       Qgis as QGis)
from qgis.gui import *
try:
    from homography import from_points
except ImportError:
    None
from qgis.utils import iface


settings = QSettings()

try:
    from cv2 import (COLOR_BGR2RGB,
                     cvtColor,
                     COLOR_GRAY2RGB)
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
geotransform_affine = None
defaultTargetWidth = 200.0

gcornerPointUL = None
gcornerPointUR = None
gcornerPointLR = None
gcornerPointLL = None
gframeCenterLon = None
gframeCenterLat = None
frameCenterElevation = None
sensorLatitude = None
sensorLongitude = None
sensorTrueAltitude = None

crtSensorSrc = 'DEFAULT'
crtPltTailNum = 'DEFAULT'

dtm_data = []
dtm_transform = None
dtm_colLowerBound = 0
dtm_rowLowerBound = 0

tLastLon = 0.0
tLastLat = 0.0

if windows:
    ffmpeg_path = ffmpeg_path + '\\ffmpeg.exe'
    ffprobe_path = ffprobe_path + '\\ffprobe.exe'
else:
    ffmpeg_path = ffmpeg_path + '\\ffmpeg'
    ffprobe_path = ffprobe_path + '\\ffprobe'


class BufferedMetaReader():
    '''  Test : Non-Blocking metadata reader with buffer  '''

    def __init__(self, video_path, pass_time=100, intervall=200, min_buffer_size=10):
        self.video_path = video_path
        self.pass_time = pass_time
        self.intervall = intervall
        self._meta = {}
        self._min_buffer_size = min_buffer_size
        self._initialize('00:00:00.0000', self._min_buffer_size)

    def _initialize(self, start, size):
        self.bufferParalell(start, size)

    def _check_buffer(self, start):
        self.bufferParalell(start, self._min_buffer_size)

    def getSize(self):
        return len(self._meta)

    def bufferParalell(self, start, size):
        start_sec = _time_to_seconds(start)
        start_milisec = int(start_sec*1000)
        for k in range(start_milisec, start_milisec + (size * self.intervall), self.intervall):
            cTime = k / 1000.0
            nTime = (k + self.pass_time) / 1000.0
            new_key = _seconds_to_time_frac(cTime)
            if new_key not in self._meta:
                #qgsu.showUserAndLogMessage("QgsFmvUtils", 'buffering: ' + _seconds_to_time_frac(cTime) + " to " + _seconds_to_time_frac(nTime), onlyLog=True)
                self._meta[new_key] = callBackMetadataThread(cmds=['-i', self.video_path,
                                                                   '-ss', _seconds_to_time_frac(cTime),
                                                                   '-to', _seconds_to_time_frac(nTime),
                                                                   '-map', 'data-re',
                                                                   '-f', 'data', '-'])
                self._meta[new_key].start()

    # read a value and check the buffer
    def get(self, t):
        value = b''
        #get the closest value for this time from the buffer
        s = t.split(".")
        new_t = ''
        try:
            milis = int(s[1][:-1])
            r_milis = round(milis / self.intervall) * self.intervall
            if r_milis != 1000:
                if r_milis < 1000:
                    new_t = s[0] + "." + str(r_milis) + "0"
                if r_milis < 100:
                    new_t = s[0] + ".0" + str(r_milis) + "0"
                if r_milis < 10:
                    new_t = s[0] + ".00" + str(r_milis) + "0"
            else:
                date = datetime.strptime(s[0], '%H:%M:%S')
                new_t = _add_secs_to_time(date, 1) + ".0000"
        except Exception:
            qgsu.showUserAndLogMessage("", "wrong value for time, need . decimal" + t, onlyLog=True)
        try:
            if self._meta[new_t].p.returncode is None:
                value = 'NOT_READY'
                qgsu.showUserAndLogMessage("", "Meta reader -> get: " + t + " cache: "+ new_t +" values not ready yet.", onlyLog=True)      
            elif self._meta[new_t].stdout:
                value = self._meta[new_t].stdout
            else:
                qgsu.showUserAndLogMessage("", "Meta reader -> get: " + t + " cache: "+ new_t +" values ready but empty.", onlyLog=True)

            self._check_buffer(new_t)
        except Exception:
            qgsu.showUserAndLogMessage("", "No value found for: " + t + " rounded: " + new_t, onlyLog=True)

        #qgsu.showUserAndLogMessage("QgsFmvUtils", "meta_reader -> get: " + t + " cache: "+ new_t +" len: " + str(len(value)), onlyLog=True)

        return value


class callBackMetadataThread(threading.Thread):
    '''  Test : CallBack metadata in other thread  '''

    def __init__(self, cmds, t="ffmpeg"):
        self.stdout = None
        self.stderr = None
        self.cmds = cmds
        self.type = t
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


def getVideoLocationInfo(videoPath): 
        """ Get basic location info about the video """
        location = []

        try:
            p = _spawn(['-i', videoPath,
                        '-ss', '00:00:00',
                        '-to', '00:00:01',
                        '-map', 'data-re',
                        '-f', 'data', '-'])

            stdout_data, _ = p.communicate()

            if stdout_data == b'':
                return

            for packet in StreamParser(stdout_data):
                packet.MetadataList()
                frameCenterLat = packet.GetFrameCenterLatitude()
                frameCenterLon = packet.GetFrameCenterLongitude()
                location = [frameCenterLat, frameCenterLon]
                qgsu.showUserAndLogMessage("", "Got Location: lon: "+str(frameCenterLon) + " lat: "+str(frameCenterLat), onlyLog=True)
                break
            else:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvUtils", "This video doesn't have Metadata ! : "), level=QGis.Info)

        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "Video info callback failed! : "), str(e), level=QGis.Info)

        return location


LAST_PATH = "LAST_PATH"
BOOL = "bool"
NUMBER = "number"
_settings = {}
try:
    from qgis.PyQt.QtCore import QPyNullVariant
except Exception:
    pass


def pluginSetting(name, namespace=None, typ=None):
    def _find_in_cache(name, key):
        try:
            for setting in _settings[namespace]:
                if setting["name"] == name:
                    return setting[key]
        except Exception:
            return None
        return None

    def _type_map(t):
        """Return setting python type"""
        if t == BOOL:
            return bool
        elif t == NUMBER:
            return float
        else:
            return unicode

    namespace = namespace or _callerName().split(".")[0]
    full_name = namespace + "/" + name
    if settings.contains(full_name):
        if typ is None:
            typ = _type_map(_find_in_cache(name, 'type'))
        v = settings.value(full_name, None, type=typ)
        try:
            if isinstance(v, QPyNullVariant):
                v = None
        except Exception:
            pass
        return v
    else:
        return _find_in_cache(name, 'default')


def _callerName():
    stack = inspect.stack()
    parentframe = stack[2][0]
    name = []
    module = inspect.getmodule(parentframe)
    name.append(module.__name__)
    if 'self' in parentframe.f_locals:
        name.append(parentframe.f_locals['self'].__class__.__name__)
    codename = parentframe.f_code.co_name
    if codename != '<module>':
        name.append(codename)
    del parentframe
    return ".".join(name)


def askForFiles(parent, msg=None, isSave=False, allowMultiple=False, exts="*"):
    msg = msg or 'Select file'
    caller = _callerName().split(".")
    name = "/".join([LAST_PATH, caller[-1]])
    namespace = caller[0]
    path = pluginSetting(name, namespace)
    f = None
    if not isinstance(exts, list):
        exts = [exts]
    extString = ";; ".join([" %s files (*.%s)" % (e.upper(), e)
                            if e != "*" else "All files (*.*)" for e in exts])
    if allowMultiple:
        ret = QFileDialog.getOpenFileNames(parent, msg, path, '*.' + extString)
        if ret:
            f = ret[0]
        else:
            f = ret = None
    else:
        if isSave:
            ret = QFileDialog.getSaveFileName(
                parent, msg, path, '*.' + extString) or None
            if ret is not None and not ret.endswith(exts[0]):
                ret += "." + exts[0]
        else:
            ret = QFileDialog.getOpenFileName(
                parent, msg, path, '*.' + extString) or None
        f = ret

    if f is not None:
        setPluginSetting(name, os.path.dirname(f[0]), namespace)

    return ret


def setPluginSetting(name, value, namespace=None):
    namespace = namespace or _callerName().split(".")[0]
    settings.setValue(namespace + "/" + name, value)


def askForFolder(parent, msg=None):
    msg = msg or 'Select folder'
    caller = _callerName().split(".")
    name = "/".join([LAST_PATH, caller[-1]])
    namespace = caller[0]
    path = pluginSetting(name, namespace)
    folder = QFileDialog.getExistingDirectory(parent, msg, path)
    if folder:
        setPluginSetting(name, folder, namespace)
    return folder


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
    global geotransform_affine

    Height = GetFrameCenter()[2]
    gcp = gdal.GCP(cornerPointUL[1], cornerPointUL[0], 
                   Height, 0, 0, "Corner Upper Left", "1") 
    gcps.append(gcp) 
    gcp = gdal.GCP(cornerPointUR[1], cornerPointUR[0], 
                   Height, xSize, 0, "Corner Upper Right", "2") 
    gcps.append(gcp) 
    gcp = gdal.GCP(cornerPointLR[1], cornerPointLR[0], 
                   Height, xSize, ySize, "Corner Lower Right", "3") 
    gcps.append(gcp) 
    gcp = gdal.GCP(cornerPointLL[1], cornerPointLL[0], 
                   Height, 0, ySize, "Corner Lower Left", "4") 
    gcps.append(gcp) 
    gcp = gdal.GCP(frameCenterLon, frameCenterLat, Height, 
                   xSize / 2, ySize / 2, "Center", "5") 
    gcps.append(gcp) 

    geotransform_affine = gdal.GCPsToGeoTransform(gcps) 

    src = np.float64(
        np.array([[0.0, 0.0], [xSize, 0.0], [xSize, ySize], [0.0, ySize]]))
    dst = np.float64(
        np.array([cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]))
    geotransform = from_points(src, dst)

    if geotransform is None:
        qgsu.showUserAndLogMessage("", "Unable to extract a geotransform.", onlyLog=True)

    return


def GetSensor():
    return [sensorLatitude, sensorLongitude, sensorTrueAltitude]


def GetFrameCenter():
    return [gframeCenterLat, gframeCenterLon, frameCenterElevation]


def GetcornerPointUL():
    return gcornerPointUL


def GetcornerPointUR():
    return gcornerPointUR


def GetcornerPointLR():
    return gcornerPointLR


def GetcornerPointLL():
    return gcornerPointLL


def GetGCPGeoTransform():
    ''' Return Geotransform '''
    return geotransform


def hasElevationModel():
    if len(dtm_data) > 0:
        return True
    else:
        return False


def SetImageSize(w, h):
    ''' Set Image Size '''
    global xSize
    global ySize
    xSize = w
    ySize = h
    return


def GetImageWidth():
    return xSize


def GetImageHeight():
    return ySize


def _check_output(cmds, t="ffmpeg"):
    ''' Check Output Commands in Python '''

    if t is "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    return check_output(cmds, shell=True, close_fds=(not windows))


def _spawn(cmds, t="ffmpeg"):
    ''' Subprocess and Shell Commands in Python '''

    if t is "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    return Popen(cmds, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                 bufsize=0,
                 close_fds=(not windows))


def install_pip_requirements():
    ''' Install Requeriments from pip '''
    try:
        import pip
    except ImportError:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Import Pip! : "), "", onlyLog=True)
        raise

    package_dir = QgsApplication.qgisSettingsDirPath() + 'python/plugins/QGIS_FMV/'
    requirements_file = os.path.join(package_dir, 'requirements.txt')
    if not os.path.isfile(requirements_file):
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", 'No requirements file found in {}'.format(requirements_file)), "", onlyLog=True)
        raise
    try:
        version_num = pip.__version__[:pip.__version__.find('.')]
        if int(version_num) <= 10:
            pip.main(['install', '-r', requirements_file])
        else:
            from pip._internal import main
            main(['install', '-r', requirements_file])
    except Exception:
        raise
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


def ResetData():
    global dtm_data
    global crtSensorSrc
    global crtPltTailNum
    global tLastLon
    global tLastLat

    dtm_data = []
    crtSensorSrc = 'DEFAULT'
    crtPltTailNum = 'DEFAULT'
    tLastLon = 0.0
    tLastLat = 0.0


def initElevationModel(frameCenterLat, frameCenterLon, dtm_path):
    global dtm_data
    global dtm_transform
    global dtm_colLowerBound
    global dtm_rowLowerBound

    #Initialize the dtm once, based on a zone arouind the target
    qgsu.showUserAndLogMessage("", "Initializing DTM." , onlyLog=True)
    dataset = gdal.Open(dtm_path)
    if dataset is None:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "Failed to read DTM file. "), level=QGis.Warning)
        return
    band = dataset.GetRasterBand(1)
    dtm_transform = dataset.GetGeoTransform()
    xOrigin = dtm_transform[0]
    yOrigin = dtm_transform[3]
    pixelWidth = dtm_transform[1]
    pixelHeight = -dtm_transform[5]
    cIndex = int((frameCenterLon-xOrigin)/pixelWidth)
    rIndex = int((frameCenterLat-yOrigin)/(-pixelHeight))
    dtm_colLowerBound = cIndex-dtm_buffer
    dtm_rowLowerBound = rIndex-dtm_buffer
    if dtm_colLowerBound < 0 or dtm_rowLowerBound < 0:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "There is no DTM for theses bounds. Check/increase DTM_buffer_size in fmvConfig.py"), level=QGis.Warning)
    else:
        #qgsu.showUserAndLogMessage("UpdateLayers: ", " dtm_colLowerBound:"+str(dtm_colLowerBound)+" dtm_rowLowerBound:"+str(dtm_rowLowerBound)+" dtm_buffer:"+str(dtm_buffer), onlyLog=True)
        dtm_data = band.ReadAsArray(dtm_colLowerBound, dtm_rowLowerBound, 2 * dtm_buffer, 2 * dtm_buffer)
        if dtm_data is not None:
            qgsu.showUserAndLogMessage("", "DTM successfully initialized, len: " + str(len(dtm_data)), onlyLog=True)


def UpdateLayers(packet, parent=None, mosaic=False):
    ''' Update Layers Values '''
    global frameCenterElevation
    global sensorLatitude
    global sensorLongitude
    global sensorTrueAltitude

    frameCenterLat = packet.GetFrameCenterLatitude()
    frameCenterLon = packet.GetFrameCenterLongitude()
    frameCenterElevation = packet.GetFrameCenterElevation()    
    sensorLatitude = packet.GetSensorLatitude()
    sensorLongitude = packet.GetSensorLongitude()
    sensorTrueAltitude = packet.GetSensorTrueAltitude()

    UpdatePlatformData(packet)
    UpdateTrajectoryData(packet)

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
        packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL)

    UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                    cornerPointLR, cornerPointLL)



    SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                          cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat)

    if mosaic:
        georeferencingVideo(parent)
    return


def georeferencingVideo(parent):
    """ Extract Current Frame Thread """
    # only works on custom video surface
    image = parent.videoWidget.GetCurrentFrame()
    root, _ = os.path.splitext(os.path.basename(parent.fileName))
    out = os.path.join(os.path.expanduser("~"), "QGIS_FMV", root)
    GeoreferenceFrame(image, out, parent)
    return


def GeoreferenceFrame(image, output, parent):
    ''' Save Current Image '''

    # TODO : Create memory raster?

    p = str(parent.player.position())
    if p == "0":
        return

    ext = ".tiff"

    t = "out_" + p + ext
    name = "g_" + p

    src_file = os.path.join(output, t)

    image.save(src_file)

    # Opens source dataset
    src_ds = gdal.Open(src_file)
    driver = gdal.GetDriverByName("GTiff")

    # Open destination dataset
    dst_filename = os.path.join(output, name + ext)
    dst_ds = driver.CreateCopy(dst_filename, src_ds, \
        options = ['BLOCKYSIZE=16', 'COMPRESS=DEFLATE', 'NUM_THREADS=ALL_CPUS'])

    # Get raster projection
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Set projection
    dst_ds.SetProjection(srs.ExportToWkt())

    # Set location
    dst_ds.SetGeoTransform(geotransform_affine)
    dst_ds.GetRasterBand(1).SetNoDataValue(0)

    # Close files
    dst_ds = None
    src_ds = None

    # Add Layer to canvas
    layer = QgsRasterLayer(dst_filename, name)
    addLayerNoCrsDialog(layer, False, frames_g)
    ExpandLayer(layer, False)
    iface.mapCanvas().refresh()
    try:
        os.remove(src_file)
    except OSError:
        pass

    return


def CommonLayer(value):
    ''' Common commands Layers '''
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
                    {fetId: QgsGeometry.fromPolylineXY([
                        QgsPointXY(lon, lat),
                        QgsPointXY(cornerPointUR[1], cornerPointUR[0])])})
                # LR
                fetId = 3
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointLR[1], 4: cornerPointLR[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([
                        QgsPointXY(lon, lat),
                        QgsPointXY(cornerPointLR[1], cornerPointLR[0])])})
                # LL
                fetId = 4
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointLL[1], 4: cornerPointLL[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([
                        QgsPointXY(lon, lat),
                        QgsPointXY(cornerPointLL[1],
                                   cornerPointLL[0])])})

                beamsLyr.endEditCommand()

            CommonLayer(beamsLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Beams Layer! : "), str(e))
    return


def UpdateFootPrintData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL):
    ''' Update Footprint Values '''
    global crtSensorSrc
    imgSS = packet.GetImageSourceSensor()
    footprintLyr = qgsu.selectLayerByName(Footprint_lyr)

    try:
        if footprintLyr is not None:

            if(imgSS != crtSensorSrc):
                SetDefaultFootprintStyle(footprintLyr, imgSS)
                crtSensorSrc = imgSS

            footprintLyr.startEditing()
            if footprintLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([cornerPointUL[1], cornerPointUL[0],
                                       cornerPointUR[1], cornerPointUR[0],
                                       cornerPointLR[1], cornerPointLR[0],
                                       cornerPointLL[1], cornerPointLL[0]])
                surface = QgsGeometry.fromPolygonXY([[
                    QgsPointXY(cornerPointUL[1],
                               cornerPointUL[0]),
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
                attrib = {0: cornerPointUL[1],
                          1: cornerPointUL[0],
                          2: cornerPointUR[1],
                          3: cornerPointUR[0],
                          4: cornerPointLR[1],
                          5: cornerPointLR[0],
                          6: cornerPointLL[1],
                          7: cornerPointLL[0]}

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


def UpdateTrajectoryData(packet):
    ''' Update Trajectory Values '''
    global tLastLon
    global tLastLat

    lat = packet.GetSensorLatitude()
    lon = packet.GetSensorLongitude()
    alt = packet.GetSensorTrueAltitude()

    try:
        if tLastLon == 0.0 and tLastLat == 0.0:
            tLastLon = lon
            tLastLat = lat
        else:
            #little check to see if telemetry data are plausible before drawing.
            distance = sphere.distance((tLastLon, tLastLat), (lon, lat))
            if distance > 1000: # 1 km is the best value for prevent draw trajectory when start video again
                return
    except Exception:
        None

    tLastLon = lon
    tLastLat = lat
    trajectoryLyr = qgsu.selectLayerByName(Trajectory_lyr)

    try:
        if trajectoryLyr is not None:
            trajectoryLyr.startEditing()
            f = QgsFeature()
            if trajectoryLyr.featureCount() == 0:
                f.setAttributes(
                    [lon, lat, alt])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(lon, lat)])
                f.setGeometry(surface)
                trajectoryLyr.addFeatures([f])

            else:
                f_last = trajectoryLyr.getFeature(trajectoryLyr.featureCount())
                f.setAttributes(
                    [lon, lat, alt])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat),
                     QgsPointXY(f_last.attribute(0), f_last.attribute(1))])
                f.setGeometry(surface)
                trajectoryLyr.addFeatures([f])

            CommonLayer(trajectoryLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Trajectory Layer! : "), str(e))
    return


def UpdatePlatformData(packet):
    ''' Update PlatForm Values '''
    global crtPltTailNum
    lat = packet.GetSensorLatitude()
    lon = packet.GetSensorLongitude()
    alt = packet.GetSensorTrueAltitude()
    PlatformHeading = packet.GetPlatformHeadingAngle()
    platformTailNumber = packet.GetPlatformTailNumber()
    platformLyr = qgsu.selectLayerByName(Platform_lyr)

    try:
        if all(v is not None for v in [platformLyr, lat, lon, alt, PlatformHeading]):
            if platformTailNumber != crtPltTailNum:
                SetDefaultPlatformStyle(platformLyr, platformTailNumber)
                crtPltTailNum = platformTailNumber

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

        UpdateFootPrintData(packet,
            cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL)

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL)

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat)

    except Exception:
        return False

    return True


def CornerEstimationWithoutOffsets(packet):
    ''' Corner estimation without Offsets '''
    global defaultTargetWidth

    try:
        sensorLatitude = packet.GetSensorLatitude()
        sensorLongitude = packet.GetSensorLongitude()
        sensorTrueAltitude = packet.GetSensorTrueAltitude()
        frameCenterLat = packet.GetFrameCenterLatitude()
        frameCenterLon = packet.GetFrameCenterLongitude()
        frameCenterElevation = packet.GetFrameCenterElevation()
        sensorVerticalFOV = packet.GetSensorVerticalFieldOfView()
        sensorHorizontalFOV = packet.GetSensorHorizontalFieldOfView()
        headingAngle = packet.GetPlatformHeadingAngle()
        sensorRelativeAzimut = packet.GetSensorRelativeAzimuthAngle()
        targetWidth = packet.GettargetWidth()
        slantRange = packet.GetSlantRange()

        # If target width = 0 (occurs on some platforms), compute it with the slate range.
        # Otherwise it leaves the footprint as a point.
        if targetWidth == 0 and slantRange != 0:
            targetWidth = 2.0 * slantRange * \
                tan(radians(sensorHorizontalFOV / 2.0))
        elif targetWidth == 0 and slantRange == 0:
            # default target width to not leave footprint as a point.
            targetWidth = defaultTargetWidth
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "Target width unknown, defaults to: " + str(targetWidth) + "m."), level=QGis.Info)

        # compute distance to ground
        if frameCenterElevation != 0:
            sensorGroundAltitude = sensorTrueAltitude - frameCenterElevation
        else:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "Sensor ground elevation narrowed to true altitude: " + str(sensorTrueAltitude) + "m."), level=QGis.Info)
            sensorGroundAltitude = sensorTrueAltitude

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

        value5 = sqrt(pow(distance, 2.0) + pow(sensorGroundAltitude, 2.0))
        value6 = targetWidth * aspectRatio / 2.0

        degrees = rad2deg(atan(value3 / distance))

        value8 = rad2deg(atan(distance / sensorGroundAltitude))
        value9 = rad2deg(atan(value6 / value5))
        value10 = value8 + value9
        value11 = sensorGroundAltitude * tan(radians(value10))
        value12 = value8 - value9
        value13 = sensorGroundAltitude * tan(radians(value12))
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
        cornerPointUL = list(
            reversed(sphere.destination(destPoint, value19, bearing)))

        # CP Up Right
        bearing = (value2 + value21) % 360.0
        cornerPointUR = list(
            reversed(sphere.destination(destPoint, value19, bearing)))

        # CP Low Right
        bearing = (value2 + 180.0 - value20) % 360.0
        cornerPointLR = list(
            reversed(sphere.destination(destPoint, distance2, bearing)))

        # CP Low Left
        bearing = (value2 + 180.0 + value20) % 360.0
        cornerPointLL = list(
            reversed(sphere.destination(destPoint, distance2, bearing)))

        UpdateFootPrintData(packet,
            cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL)

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL)

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL,
                              frameCenterLon, frameCenterLat)
    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "CornerEstimationWithoutOffsets failed! : "), str(e), level=QGis.Info)
        return False

    return True


def GetLine3DIntersectionWithDEM(sensorPt, targetPt):
    global dtm_data 
    global dtm_transform
    global dtm_colLowerBound
    global dtm_rowLowerBound

    pt = []

    sensorLat = sensorPt[0]
    sensorLon = sensorPt[1]
    sensorAlt = sensorPt[2]
    targetLat = targetPt[0]
    targetLon = targetPt[1]
    try:
        targetAlt = targetPt[2]
    except Exception:
        targetAlt = GetFrameCenter()[2]

    distance = sphere.distance([sensorLat, sensorLon], [targetLat, targetLon])
    distance = sqrt(distance ** 2 + (targetAlt-sensorAlt) ** 2)
    dLat = (targetLat-sensorLat)/distance
    dLon = (targetLon-sensorLon)/distance
    dAlt = (targetAlt-sensorAlt)/distance

    xOrigin = dtm_transform[0]
    yOrigin = dtm_transform[3]
    pixelWidth = dtm_transform[1]
    pixelHeight = -dtm_transform[5]

    pixelWidthMeter = pixelWidth * (pi/180.0)*6378137.0

    #start at k = sensor point, then test every pixel a point on the 3D line until we cross the dtm (diffAlt >= 0).
    diffAlt = -1
    for k in range(0, int(dtm_buffer * pixelWidthMeter), int(pixelWidthMeter)):
        point = [sensorLon + k * dLon, sensorLat + k * dLat, sensorAlt + k * dAlt]
        col = int((point[0] - xOrigin) / pixelWidth)
        row = int((yOrigin - point[1] ) / pixelHeight)
        try:
            diffAlt = point[2] - dtm_data[row - dtm_rowLowerBound][col -  dtm_colLowerBound]
        except:
            qgsu.showUserAndLogMessage("", "DEM point not found after all iterations.", onlyLog=True)
            break
        if diffAlt <= 0:
            pt = [point[1], point[0], point[2]]
            break

    if not pt:
        qgsu.showUserAndLogMessage("", "DEM point not found, last computed delta high: "+str(diffAlt), onlyLog=True)

    return pt


def GetLine3DIntersectionWithPlane(sensorPt, demPt, planeHeight):
    sensorLat = sensorPt[0]
    sensorLon = sensorPt[1]
    sensorAlt = sensorPt[2]
    demPtLat = demPt[1]
    demPtLon = demPt[0]
    demPtAlt = demPt[2]

    distance = sphere.distance([sensorLat, sensorLon], [demPtLat, demPtLon])
    distance = sqrt(distance ** 2 + (demPtAlt-demPtAlt) ** 2)
    dLat = (demPtLat-sensorLat)/distance
    dLon = (demPtLon-sensorLon)/distance
    dAlt = (demPtAlt-sensorAlt)/distance

    k = ((demPtAlt-planeHeight)/(sensorAlt-demPtAlt))*distance
    pt = [sensorLon + (distance+k)*dLon, sensorLat+(distance+k)*dLat, sensorAlt + (distance+k)*dAlt]

    return pt


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


def _add_secs_to_time(timeval, secs_to_add):
    secs = timeval.hour * 3600 + timeval.minute * 60 + timeval.second
    secs += secs_to_add
    return _seconds_to_time(secs)


def _time_to_seconds(dateStr):
    timeval = datetime.strptime(dateStr, '%H:%M:%S.%f')
    secs = timeval.hour * 3600 + timeval.minute * 60 + timeval.second + timeval.microsecond/1000000
    return secs


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
