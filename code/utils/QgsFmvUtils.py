# -*- coding: utf-8 -*-
import inspect
from math import atan, tan, sqrt, radians, pi
import os
from os.path import dirname, abspath
import platform
import json
from datetime import datetime
from subprocess import Popen, PIPE, check_output
import threading

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QFileDialog
from QGIS_FMV.klvdata.streamparser import StreamParser
from QGIS_FMV.klvdata.element import UnknownElement
from configparser import SafeConfigParser

parser = SafeConfigParser()
parser.read(os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini'))

frames_g = parser['LAYERS']['frames_g']
Reverse_geocoding_url = parser['GENERAL']['Reverse_geocoding_url']
min_buffer_size = int(parser['GENERAL']['min_buffer_size'])
Platform_lyr = parser['LAYERS']['Platform_lyr']
Footprint_lyr = parser['LAYERS']['Footprint_lyr']
FrameCenter_lyr = parser['LAYERS']['FrameCenter_lyr']
dtm_buffer = int(parser['GENERAL']['DTM_buffer_size'])
ffmpegConf = parser['GENERAL']['ffmpeg']

from QGIS_FMV.geo import sphere as sphere
from QGIS_FMV.utils.QgsFmvLayers import (addLayerNoCrsDialog,
                                         ExpandLayer,
                                         UpdateFootPrintData,
                                         UpdateTrajectoryData,
                                         UpdateBeamsData,
                                         UpdatePlatformData,
                                         UpdateFrameCenterData,
                                         UpdateFrameAxisData,
                                         SetcrtSensorSrc,
                                         SetcrtPltTailNum)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtCore import (QSettings,
                              QUrl,
                              QEventLoop)
from qgis.core import (QgsApplication,
                       QgsNetworkAccessManager,
                       QgsTask,
                       QgsRasterLayer,
                       Qgis as QGis)
from osgeo import gdal, osr

try:
    from homography import from_points
except ImportError:
    None

try:
    from cv2 import (COLOR_BGR2RGB,
                     cvtColor,
                     COLOR_GRAY2RGB)
    import numpy as np
except ImportError:
    None

try:
    from pydevd import *
except ImportError:
    None

settings = QSettings()
tm = QgsApplication.taskManager()

windows = platform.system() == 'Windows'

xSize = 0
ySize = 0

defaultTargetWidth = 200.0

iface, \
geotransform , \
geotransform_affine, \
gcornerPointUL, \
gcornerPointUR, \
gcornerPointLR, \
gcornerPointLL, \
gframeCenterLon, \
gframeCenterLat, \
frameCenterElevation, \
sensorLatitude, \
sensorLongitude, \
sensorTrueAltitude = [None] * 13

centerMode = 0

dtm_data = []
dtm_transform = None
dtm_colLowerBound = 0
dtm_rowLowerBound = 0

tLastLon = 0.0
tLastLat = 0.0

_settings = {}

if windows:
    ffmpeg_path = os.path.join(ffmpegConf, 'ffmpeg.exe')
    ffprobe_path = os.path.join(ffmpegConf, 'ffprobe.exe')
else:
    ffmpeg_path = os.path.join(ffmpegConf, 'ffmpeg')
    ffprobe_path = os.path.join(ffmpegConf, 'ffprobe')


class BufferedMetaReader():
    ''' Non-Blocking metadata reader with buffer  '''

    def __init__(self, video_path, pass_time=250, intervall=500):
        # don't go too low with pass_time or we won't catch any metadata at
        # all.
        # 8 x 500 = 4000ms buffer time
        # min_buffer_size x buffer_intervall = Miliseconds buffer time
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
        start_milisec = int(start_sec * 1000)

        for k in range(start_milisec, start_milisec + (size * self.intervall), self.intervall):
            cTime = k / 1000.0
            nTime = (k + self.pass_time) / 1000.0
            new_key = _seconds_to_time_frac(cTime)
            if new_key not in self._meta:
                # qgsu.showUserAndLogMessage("QgsFmvUtils", 'buffering: ' + _seconds_to_time_frac(cTime) + " to " + _seconds_to_time_frac(nTime), onlyLog=True)
                self._meta[new_key] = callBackMetadataThread(cmds=['-i', self.video_path,
                                                                   '-ss', new_key,
                                                                   '-to', _seconds_to_time_frac(
                                                                       nTime),
                                                                   '-map', 'data-re',
                                                                   '-f', 'data', '-'])
                self._meta[new_key].start()

    def get(self, t):
        ''' read a value and check the buffer '''
        value = b''
        # get the closest value for this time from the buffer
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
            qgsu.showUserAndLogMessage(
                "", "wrong value for time, need . decimal" + t, onlyLog=True)
        try:
            # after skip, buffer may not have been initialized
            if new_t not in self._meta:
                qgsu.showUserAndLogMessage(
                    "", "Meta reader -> get: " + t + " cache: " + new_t + " values have not been init yet.", onlyLog=True)
                self._check_buffer(new_t)
                value = 'BUFFERING'
            elif self._meta[new_t].p is None:
                value = 'NOT_READY'
                qgsu.showUserAndLogMessage(
                    "", "Meta reader -> get: " + t + " cache: " + new_t + " values not ready yet.", onlyLog=True)
            elif self._meta[new_t].p.returncode is None:
                value = 'NOT_READY'
                qgsu.showUserAndLogMessage(
                    "", "Meta reader -> get: " + t + " cache: " + new_t + " values not ready yet.", onlyLog=True)
            elif self._meta[new_t].stdout:
                value = self._meta[new_t].stdout
            else:
                qgsu.showUserAndLogMessage(
                    "", "Meta reader -> get: " + t + " cache: " + new_t + " values ready but empty.", onlyLog=True)

            self._check_buffer(new_t)
        except Exception as e:
            qgsu.showUserAndLogMessage(
                "", "No value found for: " + t + " rounded: " + new_t + " e:" + str(e), onlyLog=True)

        # qgsu.showUserAndLogMessage("QgsFmvUtils", "meta_reader -> get: " + t + " return code: "+ str(self._meta[new_t].p.returncode), onlyLog=True)
        # qgsu.showUserAndLogMessage("QgsFmvUtils", "meta_reader -> get: " + t + " cache: "+ new_t +" len: " + str(len(value)), onlyLog=True)

        return value


class callBackMetadataThread(threading.Thread):
    ''' CallBack metadata in other thread  '''

    def __init__(self, cmds):
        self.cmds = cmds
        self.p = None
        threading.Thread.__init__(self)

    def run(self):
        # qgsu.showUserAndLogMessage("", "callBackMetadataThread run: commands:" + str(self.cmds), onlyLog=True)
        self.p = _spawn(self.cmds)
        self.stdout, _ = self.p.communicate()


def setCenterMode(mode, interface):
    global centerMode, iface
    centerMode = mode
    iface = interface

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
            if isinstance(packet, UnknownElement):
                qgsu.showUserAndLogMessage(
                    "Error interpreting klv data, metadata cannot be read.", "the parser did not recognize KLV data", level=QGis.Warning)
                continue
            packet.MetadataList()
            frameCenterLat = packet.FrameCenterLatitude
            frameCenterLon = packet.FrameCenterLongitude
            loc = "-"

            if Reverse_geocoding_url != "":
                try:
                    url = QUrl(Reverse_geocoding_url.format(
                        str(frameCenterLat), str(frameCenterLon)))
                    request = QNetworkRequest(url)
                    reply = QgsNetworkAccessManager.instance().get(request)
                    loop = QEventLoop()
                    reply.finished.connect(loop.quit)
                    loop.exec_()
                    reply.finished.disconnect(loop.quit)
                    loop = None
                    result = reply.readAll()
                    data = json.loads(result.data())

                    if "village" in data["address"] and "state" in data["address"]:
                        loc = data["address"]["village"] + \
                            ", " + data["address"]["state"]
                    elif "town" in data["address"] and "state" in data["address"]:
                        loc = data["address"]["town"] + \
                            ", " + data["address"]["state"]
                    else:
                        loc = data["display_name"]

                except Exception:
                    qgsu.showUserAndLogMessage(
                        "", "getVideoLocationInfo: failed to get address from reverse geocoding service.", onlyLog=True)

            location = [frameCenterLat, frameCenterLon, loc]

            qgsu.showUserAndLogMessage("", "Got Location: lon: " + str(frameCenterLon) + 
                                       " lat: " + str(frameCenterLat) + " location: " + str(loc), onlyLog=True)

            break
        else:

            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "This video doesn't have Metadata ! : "))

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Video info callback failed! : "), str(e))

    return location


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
        if t == "bool":
            return bool
        elif t == "number":
            return float
        else:
            return unicode

    namespace = namespace or _callerName().split(".")[0]
    full_name = namespace + "/" + name
    if settings.contains(full_name):
        if typ is None:
            typ = _type_map(_find_in_cache(name, 'type'))
        v = settings.value(full_name, None, type=typ)
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
    ''' dialog for save or load files '''
    msg = msg or 'Select file'
    caller = _callerName().split(".")
    name = "/".join(["LAST_PATH", caller[-1]])
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
                parent, msg, path, extString) or None
            if ret[0] != "":
                name, ext = os.path.splitext(ret[0])
                if ext == "":
                    ret[0] += "." + exts[0]  # Default extension
        else:
            ret = QFileDialog.getOpenFileName(
                parent, msg, path, extString) or None
        f = ret

    if f is not None:
        setPluginSetting(name, os.path.dirname(f[0]), namespace)

    return ret


def setPluginSetting(name, value, namespace=None):
    namespace = namespace or _callerName().split(".")[0]
    settings.setValue(namespace + "/" + name, value)


def askForFolder(parent, msg=None, options=QFileDialog.ShowDirsOnly):
    msg = msg or 'Select folder'
    caller = _callerName().split(".")
    name = "/".join(["LAST_PATH", caller[-1]])
    namespace = caller[0]
    path = pluginSetting(name, namespace)
    folder = QFileDialog.getExistingDirectory(parent, msg, path, options)
    if folder:
        setPluginSetting(name, folder, namespace)
    return folder


def convertQImageToMat(img):
    '''  Converts a QImage into an opencv MAT format  '''
    img = img.convertToFormat(QImage.Format_RGB888)
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    return np.array(ptr).reshape(img.height(), img.width(), 3)


def convertMatToQImage(img):
    '''  Converts an opencv MAT image to a QImage  '''
    height, width = img.shape[:2]
    if img.ndim == 3:
        rgb = cvtColor(img, COLOR_BGR2RGB)
    elif img.ndim == 2:
        rgb = cvtColor(img, COLOR_GRAY2RGB)
    else:
        raise Exception("Unstatistified image data format!")
    return QImage(rgb, width, height, QImage.Format_RGB888)


def SetGCPsToGeoTransform(cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat):
    ''' Make Geotranform from pixel to lon lat coordinates '''
    gcps = []

    global gcornerPointUL, gcornerPointUR, gcornerPointLR, gcornerPointLL, gframeCenterLat, gframeCenterLon, geotransform_affine, geotransform

    gcornerPointUL = cornerPointUL
    gcornerPointUR = cornerPointUR
    gcornerPointLR = cornerPointLR
    gcornerPointLL = cornerPointLL
    gframeCenterLat = frameCenterLat
    gframeCenterLon = frameCenterLon

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
        qgsu.showUserAndLogMessage(
            "", "Unable to extract a geotransform.", onlyLog=True)

    return


def GetSensor():
    return [sensorLatitude, sensorLongitude, sensorTrueAltitude]


def GetFrameCenter():
    global sensorTrueAltitude
    global frameCenterElevation
    global gframeCenterLat
    global gframeCenterLon
    # Todo if sensor height is null, compute it from sensor altitude.
    if(frameCenterElevation == None):
        frameCenterElevation = sensorTrueAltitude - 500    
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
    if dtm_data is not None and len(dtm_data) > 0:
        return True
    else:
        return False


def SetImageSize(w, h):
    ''' Set Image Size '''
    global xSize, ySize
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

    cmds.insert(3, '-preset')
    cmds.insert(4, 'ultrafast')

    return Popen(cmds, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                 bufsize=0,
                 close_fds=(not windows))


def install_pip_requirements():
    ''' Install Requeriments from pip >= 10.0.1'''
    package_dir = QgsApplication.qgisSettingsDirPath() + 'python/plugins/QGIS_FMV/'
    requirements_file = os.path.join(package_dir, 'requirements.txt')
    if not os.path.isfile(requirements_file):
        qgsu.showUserAndLogMessage("", 'No requirements file found in {}'.format(
            requirements_file), "", onlyLog=True)
        raise
    try:
        process = Popen(["pip", "install", '-r', requirements_file],
                        shell=True,
                        stdout=PIPE,
                        stderr=PIPE)
        process.wait()
    except Exception:
        raise
    return


def rad2deg(radians):
    ''' Radians to Degrees '''
    degrees = 180 * radians / pi
    return degrees


def deg2rad(degrees):
    ''' Degrees to Radians '''
    radians = pi * degrees / 180
    return radians


def ResetData():
    global dtm_data, tLastLon, tLastLat

    SetcrtSensorSrc()
    SetcrtPltTailNum()

    dtm_data = []
    tLastLon = 0.0
    tLastLat = 0.0


def initElevationModel(frameCenterLat, frameCenterLon, dtm_path):
    global dtm_data, dtm_transform, dtm_colLowerBound, dtm_rowLowerBound

    # Initialize the dtm once, based on a zone arouind the target
    qgsu.showUserAndLogMessage("", "Initializing DTM.", onlyLog=True)
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
    cIndex = int((frameCenterLon - xOrigin) / pixelWidth)
    rIndex = int((frameCenterLat - yOrigin) / (-pixelHeight))
    dtm_colLowerBound = cIndex - dtm_buffer
    dtm_rowLowerBound = rIndex - dtm_buffer
    if dtm_colLowerBound < 0 or dtm_rowLowerBound < 0:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "There is no DTM for theses bounds. Check/increase DTM_buffer_size in settings.ini"), level=QGis.Warning)
    else:
        # qgsu.showUserAndLogMessage("UpdateLayers: ", " dtm_colLowerBound:"+str(dtm_colLowerBound)+" dtm_rowLowerBound:"+str(dtm_rowLowerBound)+" dtm_buffer:"+str(dtm_buffer), onlyLog=True)

        dtm_data = band.ReadAsArray(
            dtm_colLowerBound, dtm_rowLowerBound, 2 * dtm_buffer, 2 * dtm_buffer)
        if dtm_data is not None:
            qgsu.showUserAndLogMessage(
                "", "DTM successfully initialized, len: " + str(len(dtm_data)), onlyLog=True)


def UpdateLayers(packet, parent=None, mosaic=False):
    ''' Update Layers Values '''

    global frameCenterElevation, sensorLatitude, sensorLongitude, sensorTrueAltitude

    frameCenterLat = packet.FrameCenterLatitude
    frameCenterLon = packet.FrameCenterLongitude
    frameCenterElevation = packet.FrameCenterElevation
    sensorLatitude = packet.SensorLatitude
    sensorLongitude = packet.SensorLongitude
    sensorTrueAltitude = packet.SensorTrueAltitude
    OffsetLat1 = packet.OffsetCornerLatitudePoint1
    LatitudePoint1Full = packet.CornerLatitudePoint1Full

    UpdatePlatformData(packet, hasElevationModel())
    UpdateTrajectoryData(packet, hasElevationModel())
    UpdateFrameCenterData(packet, hasElevationModel())
    UpdateFrameAxisData(packet, hasElevationModel())

    if OffsetLat1 is not None and LatitudePoint1Full is None:
        CornerEstimationWithOffsets(packet)
        if mosaic:
            georeferencingVideo(parent)

    elif OffsetLat1 is None and LatitudePoint1Full is None:
        CornerEstimationWithoutOffsets(packet)
        if mosaic:
            georeferencingVideo(parent)

    else:
        cornerPointUL = [packet.CornerLatitudePoint1Full,
                         packet.CornerLongitudePoint1Full]
        if None in cornerPointUL:
            return

        cornerPointUR = [packet.CornerLatitudePoint2Full,
                         packet.CornerLongitudePoint2Full]
        if None in cornerPointUR:
            return

        cornerPointLR = [packet.CornerLatitudePoint3Full,
                         packet.CornerLongitudePoint3Full]

        if None in cornerPointLR:
            return

        cornerPointLL = [packet.CornerLatitudePoint4Full,
                         packet.CornerLongitudePoint4Full]

        if None in cornerPointLL:
            return
        UpdateFootPrintData(
            packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, hasElevationModel())

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL, hasElevationModel())

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat)

        if mosaic:
            georeferencingVideo(parent)

    # recenter map on platform
    if centerMode == 1:
        lyr = qgsu.selectLayerByName(Platform_lyr)
        iface.mapCanvas().setExtent(lyr.extent())
    # recenter map on footprint
    elif centerMode == 2:
        lyr = qgsu.selectLayerByName(Footprint_lyr)
        iface.mapCanvas().setExtent(lyr.extent())
    # recenter map on target
    elif centerMode == 3:
        lyr = qgsu.selectLayerByName(FrameCenter_lyr)
        iface.mapCanvas().setExtent(lyr.extent())

    iface.mapCanvas().refresh()
    return


def georeferencingVideo(parent):
    """ Extract Current Frame Thread """
    image = parent.videoWidget.GetCurrentFrame()
    root, _ = os.path.splitext(os.path.basename(parent.fileName))
    out = os.path.join(os.path.expanduser("~"), "QGIS_FMV", root)
    position = str(parent.player.position())

    taskGeoreferencingVideo = QgsTask.fromFunction('Georeferencing Current Frame Task',
                                                   GeoreferenceFrame,
                                                   image=image, output=out, p=position,
                                                   on_finished=parent.finishedTask,
                                                   flags=QgsTask.CanCancel)

    QgsApplication.taskManager().addTask(taskGeoreferencingVideo)
    return


def GeoreferenceFrame(task, image, output, p):
    ''' Save Current Image '''
    ext = ".tiff"
    t = "out_" + p + ext
    name = "g_" + p

    src_file = os.path.join(output, t)

    image.save(src_file)

    # Opens source dataset
    src_ds = gdal.OpenEx(src_file, gdal.OF_RASTER | 
                         gdal.OF_READONLY, open_options=['NUM_THREADS=ALL_CPUS'])

    # Open destination dataset
    dst_filename = os.path.join(output, name + ext)
    dst_ds = gdal.GetDriverByName("GTiff").CreateCopy(dst_filename, src_ds, 0,
                                                      options=['TILED=NO', 'BIGTIFF=NO', 'COMPRESS_OVERVIEW=DEFLATE', 'COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS', 'predictor=2'])
    src_ds = None
    # Get raster projection
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Set projection
    dst_ds.SetProjection(srs.ExportToWkt())

    # Set location
    # TODO : CHECK GEOTRANSFORM
    dst_ds.SetGeoTransform(geotransform_affine)
    dst_ds.GetRasterBand(1).SetNoDataValue(0)
    dst_ds.FlushCache()
    # Close files
    dst_ds = None

    # Add Layer to canvas
    layer = QgsRasterLayer(dst_filename, name)
    addLayerNoCrsDialog(layer, False, frames_g)
    ExpandLayer(layer, False)
    if task.isCanceled():
        return None
    return {'task': task.description()}


def GetGeotransform_affine():
    return geotransform_affine


def CornerEstimationWithOffsets(packet):
    ''' Corner estimation using Offsets '''
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
        cornerPointUL = (OffsetLat1 + frameCenterLat,
                         OffsetLon1 + frameCenterLon)
        cornerPointUR = (OffsetLat2 + frameCenterLat,
                         OffsetLon2 + frameCenterLon)
        cornerPointLR = (OffsetLat3 + frameCenterLat,
                         OffsetLon3 + frameCenterLon)
        cornerPointLL = (OffsetLat4 + frameCenterLat,
                         OffsetLon4 + frameCenterLon)

        if hasElevationModel():
            pCornerPointUL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUL)
            pCornerPointUR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUR)
            pCornerPointLR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLR)
            pCornerPointLL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLL)

            UpdateFootPrintData(packet,
                                pCornerPointUL, pCornerPointUR, pCornerPointLR, pCornerPointLL, hasElevationModel())

            UpdateBeamsData(packet, pCornerPointUL, pCornerPointUR,
                            pCornerPointLR, pCornerPointLL, hasElevationModel())
        else:

            UpdateFootPrintData(packet,
                                cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, hasElevationModel())

            UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                            cornerPointLR, cornerPointLL, hasElevationModel())

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat)

    except Exception:
        return False

    return True


def CornerEstimationWithoutOffsets(packet):
    ''' Corner estimation without Offsets '''
    try:
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
        targetWidth = packet.targetWidth
        slantRange = packet.SlantRange

        # If target width = 0 (occurs on some platforms), compute it with the slate range.
        # Otherwise it leaves the footprint as a point.
        # In some case targetWidth don't have value then equal to 0
        if targetWidth is None:
            targetWidth = 0
        if targetWidth == 0 and slantRange != 0:
            targetWidth = 2.0 * slantRange * \
                tan(radians(sensorHorizontalFOV / 2.0))
        elif targetWidth == 0 and slantRange == 0:
            # default target width to not leave footprint as a point.
            targetWidth = defaultTargetWidth
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "Target width unknown, defaults to: " + str(targetWidth) + "m."))

        # compute distance to ground
        if frameCenterElevation != 0:
            sensorGroundAltitude = sensorTrueAltitude - frameCenterElevation
        else:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvUtils", "Sensor ground elevation narrowed to true altitude: " + str(sensorTrueAltitude) + "m."))
            sensorGroundAltitude = sensorTrueAltitude

        if sensorLatitude == 0:
            return False

        if sensorLongitude is None or sensorLatitude is None:
            return False

        initialPoint = (sensorLongitude, sensorLatitude)

        if frameCenterLon is None or frameCenterLat is None:
            return False

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

        if hasElevationModel():
            pCornerPointUL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUL)
            pCornerPointUR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUR)
            pCornerPointLR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLR)
            pCornerPointLL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLL)

            UpdateFootPrintData(packet,
                                pCornerPointUL, pCornerPointUR, pCornerPointLR, pCornerPointLL, hasElevationModel())

            UpdateBeamsData(packet, pCornerPointUL, pCornerPointUR,
                            pCornerPointLR, pCornerPointLL, hasElevationModel())

        else:
            UpdateFootPrintData(packet,
                                cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, hasElevationModel())

            UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                            cornerPointLR, cornerPointLL, hasElevationModel())

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL,
                              frameCenterLon, frameCenterLat)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "CornerEstimationWithoutOffsets failed! : "), str(e))
        return False

    return True


def GetLine3DIntersectionWithDEM(sensorPt, targetPt):
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
    distance = sqrt(distance ** 2 + (targetAlt - sensorAlt) ** 2)
    dLat = (targetLat - sensorLat) / distance
    dLon = (targetLon - sensorLon) / distance
    dAlt = (targetAlt - sensorAlt) / distance

    xOrigin = dtm_transform[0]
    yOrigin = dtm_transform[3]
    pixelWidth = dtm_transform[1]
    pixelHeight = -dtm_transform[5]

    pixelWidthMeter = pixelWidth * (pi / 180.0) * 6378137.0

    # start at k = sensor point, then test every pixel a point on the 3D line
    # until we cross the dtm (diffAlt >= 0).

    diffAlt = -1
    for k in range(0, int(dtm_buffer * pixelWidthMeter), int(pixelWidthMeter)):
        point = [sensorLon + k * dLon, sensorLat + 
                 k * dLat, sensorAlt + k * dAlt]

        col = int((point[0] - xOrigin) / pixelWidth)
        row = int((yOrigin - point[1]) / pixelHeight)
        try:
            diffAlt = point[2] - dtm_data[row - 
                                          dtm_rowLowerBound][col - dtm_colLowerBound]

        except Exception:
            qgsu.showUserAndLogMessage(
                "", "DEM point not found after all iterations.", onlyLog=True)

            break
        if diffAlt <= 0:
            pt = [point[1], point[0], point[2]]
            break

    if not pt:
        qgsu.showUserAndLogMessage(
            "", "DEM point not found, last computed delta high: " + str(diffAlt), onlyLog=True)

    return pt


def GetLine3DIntersectionWithPlane(sensorPt, demPt, planeHeight):
    ''' Get Altitude from DEM '''
    sensorLat = sensorPt[0]
    sensorLon = sensorPt[1]
    sensorAlt = sensorPt[2]
    demPtLat = demPt[1]
    demPtLon = demPt[0]
    demPtAlt = demPt[2]

    distance = sphere.distance([sensorLat, sensorLon], [demPtLat, demPtLon])
    distance = sqrt(distance ** 2 + (demPtAlt - demPtAlt) ** 2)
    dLat = (demPtLat - sensorLat) / distance
    dLon = (demPtLon - sensorLon) / distance
    dAlt = (demPtAlt - sensorAlt) / distance

    k = ((demPtAlt - planeHeight) / (sensorAlt - demPtAlt)) * distance
    pt = [sensorLon + (distance + k) * dLon, sensorLat + 
          (distance + k) * dLat, sensorAlt + (distance + k) * dAlt]

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
    ''' Seconds to time'''
    secs = timeval.hour * 3600 + timeval.minute * 60 + timeval.second
    secs += secs_to_add
    return _seconds_to_time(secs)


def _time_to_seconds(dateStr):
    '''Time to seconds'''
    timeval = datetime.strptime(dateStr, '%H:%M:%S.%f')
    secs = timeval.hour * 3600 + timeval.minute * 60 + \
        timeval.second + timeval.microsecond / 1000000

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
