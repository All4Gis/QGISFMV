# -*- coding: utf-8 -*-
from configparser import ConfigParser
from datetime import datetime
import inspect
import json
from math import atan, tan, sqrt, radians, pi, degrees
import os
from os.path import dirname, abspath
import platform
import shutil
from qgis.PyQt.QtCore import (QSettings,
                              QUrl,
                              QEventLoop)
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.PyQt.QtWidgets import QFileDialog
from qgis.core import (QgsApplication,
                       QgsNetworkAccessManager,
                       QgsTask,
                       QgsRasterLayer,
                       Qgis as QGis)
# from subprocess import Popen, PIPE, STARTF_USESHOWWINDOW, STARTUPINFO, check_output, DEVNULL
import subprocess
import threading
from queue import Queue, Empty

from osgeo import gdal, osr

from QGIS_FMV.geo import sphere
from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.streamparser import StreamParser
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

parser = ConfigParser()
parser.read(os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini'))

frames_g = parser['LAYERS']['frames_g']
Reverse_geocoding_url = parser['GENERAL']['Reverse_geocoding_url']
min_buffer_size = int(parser['GENERAL']['min_buffer_size'])
Platform_lyr = parser['LAYERS']['Platform_lyr']
Footprint_lyr = parser['LAYERS']['Footprint_lyr']
FrameCenter_lyr = parser['LAYERS']['FrameCenter_lyr']
dtm_buffer = int(parser['GENERAL']['DTM_buffer_size'])
ffmpegConf = parser['GENERAL']['ffmpeg']


try:
    from cv2 import (COLOR_BGR2RGB,
                     cvtColor,
                     COLOR_GRAY2RGB,
                     findHomography)
    import numpy as np
except ImportError:
    None

try:
    from pydevd import *
except ImportError:
    None

settings = QSettings()
tm = QgsApplication.taskManager()
groupName = None
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


class NonBlockingStreamReader:

    def __init__(self, process):
        self._p = process
        self._q = Queue()
        self.stopped = False

        def _populateQueue(process, queue):
            '''
            Collect lines from metadata stream and put them in 'queue'.
            '''
            packetsPerQueueElement = 1
            metaFound = 0
            data = b''
            while self._p.poll() is None and not self.stopped:
                line = process.stdout.read(16)
                if line:
                    # find starting block for misb0601 or misbeg0104
                    if line == b'\x06\x0e+4\x02\x0b\x01\x01\x0e\x01\x03\x01\x01\x00\x00\x00' or line == b'\x06\x0e+4\x02\x01\x01\x01\x0e\x01\x01\x02\x01\x01\x00\x00':
                        #qgsu.showUserAndLogMessage("", "metaFound" + str(metaFound), onlyLog=True)
                        metaFound = metaFound + 1

                    # feed the current packet
                    if metaFound <= packetsPerQueueElement:
                        #qgsu.showUserAndLogMessage("", "feeding packet" + str(metaFound), onlyLog=True)
                        data = data + line
                    # add to queue and start a new one
                    else:
                        #qgsu.showUserAndLogMessage("", "Put to queue and start over" + repr(data), onlyLog=True)
                        queue.put(data)
                        data = line
                        metaFound = 1

                # End of stream
                else:
                    qgsu.showUserAndLogMessage("", "reader got end of stream.", onlyLog=True)
                    break

            if self.stopped:
                qgsu.showUserAndLogMessage("", "NonBlockingStreamReader ended because stop signal received.", onlyLog=True)

        self._t = threading.Thread(target=_populateQueue, args=(self._p, self._q))
        self._t.daemon = True
        self._t.start()  # start collecting lines from the stream

    def readline(self, timeout=None):
        try:
            return self._q.get(block=timeout is not None,
                               timeout=timeout)
        except Empty:
            return None
            # return "---"


# Splitter class for streaming.
# Reads input stream and split AV to Port: (src + 10), and reads metadata from stdout to a Queue,
# later passed to the metadata decoder.
class Splitter(threading.Thread):

    def __init__(self, cmds, _type="ffmpeg"):
        self.stdout = None
        self.stderr = None
        self.cmds = cmds
        self.type = _type
        self.p = None
        threading.Thread.__init__(self)

    def run(self):
        if self.type is "ffmpeg":
            self.cmds.insert(0, ffmpeg_path)
        else:
            self.cmds.insert(0, ffprobe_path)

        qgsu.showUserAndLogMessage("", "starting Splitter on thread:" + str(threading.current_thread().ident), onlyLog=True)
        qgsu.showUserAndLogMessage("", "with args:" + ' '.join(self.cmds), onlyLog=True)

        # Hide shell windows that pops up on windows.
        if windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        self.p = subprocess.Popen(self.cmds, startupinfo=startupinfo, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
        # Dont us _spawn here as it will DeadLock, and the splitter won't work
        #self.p = _spawn(self.cmds)
        self.nbsr = NonBlockingStreamReader(self.p)
        self.nbsr._t.join()
        qgsu.showUserAndLogMessage("", "Splitter thread ended.", onlyLog=True)


class StreamMetaReader():

    def __init__(self, video_path):
        self.split = video_path.split(":")
        self.srcProtocol = self.split[0]
        self.srcHost = self.split[1]
        self.srcPort = int(self.split[2])
        self.destPort = self.srcPort + 10
        self.connection = self.srcProtocol + ':' + self.srcHost + ':' + str(self.srcPort)
        self.connectionDest = self.srcProtocol + '://127.0.0.1:' + str(self.destPort)
        self.splitter = Splitter(['-i', self.connection, '-c', 'copy', '-map', '0:v?', '-map', '0:a?', '-f', 'rtp_mpegts', self.connectionDest, '-map', '0:d?', '-f', 'data', '-'])
        self.splitter.start()
        qgsu.showUserAndLogMessage("", "Splitter started.", onlyLog=True)

    def getSize(self):
        return self.splitter.nbsr._q.qsize()

    def get(self, _):
        qgsu.showUserAndLogMessage("", "Get called on Streamreader.", onlyLog=True)
        return self.splitter.nbsr.readline()

    def dispose(self):
        qgsu.showUserAndLogMessage("", "Dispose called on StreamMetaReader.", onlyLog=True)
        self.splitter.nbsr.stopped = True
        # kill the process if open, releases source port
        try:
            self.splitter.p.kill()
            qgsu.showUserAndLogMessage("", "Splitter Popen process killed.", onlyLog=True)
        except OSError:
            # can't kill a dead proc
            pass


class BufferedMetaReader():
    ''' Non-Blocking metadata reader with buffer  '''

    # intervall = 250 is a good value, if we go higher the drawings may not be accurate.
    # if we go lower, the buffer will shrink drastically and the video may hang.
    
    def __init__(self, video_path, pass_time=250, intervall=500):
        ''' Constructor '''
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
                                                                   '-map', '0:d',
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

    def dispose(self):
        pass


class callBackMetadataThread(threading.Thread):
    ''' CallBack metadata in other thread  '''

    def __init__(self, cmds):
        self.cmds = cmds
        self.p = None
        threading.Thread.__init__(self)

    def run(self):
        # qgsu.showUserAndLogMessage("", "callBackMetadataThread run: commands:" + str(self.cmds), onlyLog=True)
        self.p = _spawn(self.cmds)
        # print (self.cmds)
        self.stdout, _ = self.p.communicate()
        # print (self.stdout)
        # print (_)


def AddVideoToSettings(row_id, path):
    ''' Add video to settings list '''
    settings.setValue(getNameSpace() + "/Manager_List/" + row_id, path)


def RemoveVideoToSettings(row_id):
    ''' Remove video in settings list '''
    settings.remove(getNameSpace() + "/Manager_List/%s" % row_id)


def getVideoManagerList():
    ''' Get Video Manager List '''
    VideoList = []
    try:
        settings.beginGroup(getNameSpace() + "/Manager_List")
        VideoList = settings.childKeys()
        settings.endGroup()
    except Exception:
        None
    return VideoList


def getVideoFolder(video_file):
    ''' Get or create Video Temporal folder '''
    home = os.path.expanduser("~")

    qgsu.createFolderByName(home, "QGIS_FMV")

    root, _ = os.path.splitext(os.path.basename(video_file))
    homefmv = os.path.join(home, "QGIS_FMV")

    qgsu.createFolderByName(homefmv, root)
    return os.path.join(homefmv, root)


def RemoveVideoFolder(filename):
    ''' Remove video temporal folder if exist '''
    f, _ = os.path.splitext(filename)
    folder = getVideoFolder(f)
    try:
        shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        None
    return


def getNameSpace():
    ''' Get plugin name space '''
    namespace = _callerName().split(".")[0]
    return namespace


def setCenterMode(mode, interface):
    ''' Set map center mode '''
    global centerMode, iface
    centerMode = mode
    iface = interface


def getVideoLocationInfo(videoPath, islocal=False, klv_folder=None):
    """ Get basic location info about the video """
    location = []
    try:
        if islocal:
            dataFile = os.path.join(klv_folder, "0.0.klv")
            f = open(dataFile, 'rb')
            stdout_data = f.read()
        else:
            p = _spawn(['-i', videoPath,
                        '-ss', '00:00:00',
                        '-to', '00:00:01',
                        '-map', '0:d',
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
        ''' Find key in QGIS settings '''
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
            return str

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
    ''' Get QGIS plugin name '''
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
    extString = ";; ".join([" %s files (*.%s *.%s)" % (e.upper(), e, e.upper())
                            if e != "*" else "All files (*.*)" for e in exts])

    dlg = QFileDialog()
    
    if allowMultiple:
        ret = dlg.getOpenFileNames(parent, msg, path, '*.' + extString)
        if ret:
            f = ret[0]
        else:
            f = ret = None
    else:
        if isSave:
            ret = dlg.getSaveFileName(
                parent, msg, path, extString) or None
            if ret[0] != "":
                name, ext = os.path.splitext(ret[0])
                if not ext:
                    ret[0] += "." + exts[0]  # Default extension
        else:
            ret = dlg.getOpenFileName(
                parent, msg, path, extString) or None
        f = ret

    if f is not None:
        setPluginSetting(name, os.path.dirname(f[0]), namespace)

    return ret


def setPluginSetting(name, value, namespace=None):
    ''' Set plugin name in QGIS settings '''
    namespace = namespace or _callerName().split(".")[0]
    settings.setValue(namespace + "/" + name, value)


def askForFolder(parent, msg=None, options=QFileDialog.ShowDirsOnly):
    ''' dialog for save or load folder '''
    msg = msg or 'Select folder'
    caller = _callerName().split(".")
    name = "/".join(["LAST_PATH", caller[-1]])
    namespace = caller[0]
    path = pluginSetting(name, namespace)
    folder = QFileDialog.getExistingDirectory(parent, msg, path, options)
    if folder:
        setPluginSetting(name, folder, namespace)
    return folder


def convertQImageToMat(img, cn=3):
    '''  Converts a QImage into an opencv MAT format  '''
    img = img.convertToFormat(QImage.Format_RGB888)
    ptr = img.bits()
    ptr.setsize(img.byteCount())
    return np.array(ptr).reshape(img.height(), img.width(), cn)


def convertMatToQImage(img, t=QImage.Format_RGB888):
    '''  Converts an opencv MAT image to a QImage  '''
    height, width = img.shape[:2]
    if img.ndim == 3:
        rgb = cvtColor(img, COLOR_BGR2RGB)
    elif img.ndim == 2:
        rgb = cvtColor(img, COLOR_GRAY2RGB)
    else:
        raise Exception("Unstatistified image data format!")
    return QImage(rgb, width, height, t)


def SetGCPsToGeoTransform(cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, frameCenterLon, frameCenterLat, ele):
    ''' Make Geotranform from pixel to lon lat coordinates '''
    gcps = []

    global gcornerPointUL, gcornerPointUR, gcornerPointLR, gcornerPointLL, gframeCenterLat, gframeCenterLon, geotransform_affine, geotransform

    # TEMP FIX : If have elevation the geotransform is wrong
    if ele:
        del cornerPointUL[-1]
        del cornerPointUR[-1]
        del cornerPointLR[-1]
        del cornerPointLL[-1]
        
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
        np.array([[0.0, 0.0], [xSize, 0.0], [xSize, ySize], [0.0, ySize], [xSize / 2.0, ySize / 2.0]]))
    dst = np.float64(
        np.array([[cornerPointUL[0], cornerPointUL[1]], [cornerPointUR[0], cornerPointUR[1]], [cornerPointLR[0], cornerPointLR[1]], [cornerPointLL[0], cornerPointLL[1]], [frameCenterLat, frameCenterLon]]))


    try:
        geotransform, _ = findHomography(src, dst)
    except Exception:
        pass

    if geotransform is None:
        qgsu.showUserAndLogMessage(
            "", "Unable to extract a geotransform.", onlyLog=True)

    return


def GetSensor():
    ''' Get Sensor values '''
    return [sensorLatitude, sensorLongitude, sensorTrueAltitude]


def GetFrameCenter():
    ''' Get Frame Center values '''
    global sensorTrueAltitude
    global frameCenterElevation
    global gframeCenterLat
    global gframeCenterLon
    # if sensor height is null, compute it from sensor altitude.
    if(frameCenterElevation is None):
        frameCenterElevation = sensorTrueAltitude - 500
    return [gframeCenterLat, gframeCenterLon, frameCenterElevation]


def GetcornerPointUL():
    ''' Get Corner upper Left values '''
    return gcornerPointUL


def GetcornerPointUR():
    ''' Get Corner upper Right values '''
    return gcornerPointUR


def GetcornerPointLR():
    ''' Get Corner lower Right values '''
    return gcornerPointLR


def GetcornerPointLL():
    ''' Get Corner lower left values '''
    return gcornerPointLL


def GetGCPGeoTransform():
    ''' Return Geotransform '''
    return geotransform


def hasElevationModel():
    ''' Check if DEM is loaded '''
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
    ''' Get Image Width '''
    return xSize


def GetImageHeight():
    ''' Get Image Height '''
    return ySize


def _check_output(cmds, t="ffmpeg"):
    ''' Check Output Commands in Python '''

    if t is "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    return subprocess.check_output(cmds, shell=True, close_fds=(not windows))


def _spawn(cmds, t="ffmpeg"):
    ''' Subprocess and Shell Commands in Python '''

    if t is "ffmpeg":
        cmds.insert(0, ffmpeg_path)
    else:
        cmds.insert(0, ffprobe_path)

    cmds.insert(3, '-preset')
    cmds.insert(4, 'ultrafast')

    return subprocess.Popen(cmds, shell=windows, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            bufsize=0,
                            close_fds=(not windows))


def ResetData():
    ''' Reset Global Data '''
    global dtm_data, tLastLon, tLastLat

    SetcrtSensorSrc()
    SetcrtPltTailNum()
    # The DTM is not associated with every video.If we reset it, you won't see it when you change videos
    # dtm_data = []
    tLastLon = 0.0
    tLastLat = 0.0


def initElevationModel(frameCenterLat, frameCenterLon, dtm_path):
    ''' Start DEM transformation and extract data for set Z value in points '''
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


def UpdateLayers(packet, parent=None, mosaic=False, group=None):
    ''' Update Layers Values '''
    global frameCenterElevation, sensorLatitude, sensorLongitude, sensorTrueAltitude, groupName

    groupName = group
    frameCenterElevation = packet.FrameCenterElevation
    sensorLatitude = packet.SensorLatitude
    sensorLongitude = packet.SensorLongitude
    sensorTrueAltitude = packet.SensorTrueAltitude
    OffsetLat1 = packet.OffsetCornerLatitudePoint1
    LatitudePoint1Full = packet.CornerLatitudePoint1Full

    UpdatePlatformData(packet, hasElevationModel())
    UpdateTrajectoryData(packet, hasElevationModel())
    
    frameCenterPoint = [packet.FrameCenterLatitude, packet.FrameCenterLongitude, packet.FrameCenterElevation]
    if hasElevationModel():
        frameCenterPoint = GetLine3DIntersectionWithDEM(GetSensor(), frameCenterPoint)
    
    UpdateFrameCenterData(frameCenterPoint, hasElevationModel())
    UpdateFrameAxisData(packet.ImageSourceSensor, GetSensor(), frameCenterPoint, hasElevationModel())

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
        
        if hasElevationModel():
            cornerPointUL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUL)
            cornerPointUR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUR)
            cornerPointLR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLR)
            cornerPointLL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLL)

        UpdateFootPrintData(
            packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, hasElevationModel())

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL, hasElevationModel())

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL, frameCenterPoint[1], frameCenterPoint[0], hasElevationModel())

        if mosaic:
            georeferencingVideo(parent)

    # recenter map on platform
    if centerMode == 1:
        lyr = qgsu.selectLayerByName(Platform_lyr, groupName)
        if lyr is not None:
            iface.mapCanvas().setExtent( iface.mapCanvas().mapSettings().layerExtentToOutputExtent(lyr, lyr.extent() ) )
    # recenter map on footprint
    elif centerMode == 2:
        lyr = qgsu.selectLayerByName(Footprint_lyr, groupName)
        if lyr is not None:
            iface.mapCanvas().setExtent( iface.mapCanvas().mapSettings().layerExtentToOutputExtent(lyr, lyr.extent() ) )
    # recenter map on target
    elif centerMode == 3:
        lyr = qgsu.selectLayerByName(FrameCenter_lyr, groupName)
        if lyr is not None:
            iface.mapCanvas().setExtent( iface.mapCanvas().mapSettings().layerExtentToOutputExtent(lyr, lyr.extent() ) )

    iface.mapCanvas().refresh()
    return


def georeferencingVideo(parent):
    """ Extract Current Frame Thread
    :param packet: Parent class
    """
    image = parent.videoWidget.currentFrame()

    folder = getVideoFolder(parent.fileName)
    qgsu.createFolderByName(folder, "mosaic")
    out = os.path.join(folder, "mosaic")

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
    global groupName
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
    dst_ds.SetGeoTransform(geotransform_affine)
    dst_ds.GetRasterBand(1).SetNoDataValue(0)
    dst_ds.FlushCache()
    # Close files
    dst_ds = None

    # Add Layer to canvas
    layer = QgsRasterLayer(dst_filename, name)
    addLayerNoCrsDialog(layer, False, frames_g, isSubGroup=True)
    ExpandLayer(layer, False)
    if task.isCanceled():
        return None
    return {'task': task.description()}


def GetGeotransform_affine():
    ''' Get current frame affine transformation '''
    return geotransform_affine


def CornerEstimationWithOffsets(packet):
    ''' Corner estimation using Offsets
    :param packet: Metada packet
    '''
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

        frameCenterPoint = [packet.FrameCenterLatitude, packet.FrameCenterLongitude, packet.FrameCenterElevation]

        if hasElevationModel():
            cornerPointUL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUL)
            cornerPointUR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUR)
            cornerPointLR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLR)
            cornerPointLL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLL)

        UpdateFootPrintData(packet,
                            cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, hasElevationModel())

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL, hasElevationModel())

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL,
                              frameCenterPoint[1], frameCenterPoint[0], hasElevationModel())

    except Exception:
        return False

    return True


def CornerEstimationWithoutOffsets(packet=None, sensor=None, frameCenter=None, FOV=None, others=None):
    ''' Corner estimation without Offsets '''
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
            targetWidth = packet.targetWidth
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

        # If target width = 0 (occurs on some platforms), compute it with the slate range.
        # Otherwise it leaves the footprint as a point.
        # In some case targetWidth don't have value then equal to 0
        if targetWidth is None:
            targetWidth = 0
        if slantRange is None:
            slantRange = 0
        if targetWidth == 0 and slantRange != 0:
            targetWidth = 2.0 * slantRange * \
                tan(radians(sensorHorizontalFOV / 2.0))
        elif targetWidth == 0 and slantRange == 0:
            # default target width to not leave footprint as a point.
            targetWidth = defaultTargetWidth
#             qgsu.showUserAndLogMessage(QCoreApplication.translate(
#                 "QgsFmvUtils", "Target width unknown, defaults to: " + str(targetWidth) + "m."))

        # compute distance to ground
        if frameCenterElevation != 0 and sensorTrueAltitude is not None and frameCenterElevation is not None:
            sensorGroundAltitude = sensorTrueAltitude - frameCenterElevation
        elif frameCenterElevation != 0 and sensorTrueAltitude is not None:
            sensorGroundAltitude = sensorTrueAltitude
        else:
            #can't compute footprint without sensorGroundAltitude
            return False                              

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

        degrees_value = degrees(atan(value3 / distance))

        value8 = degrees(atan(distance / sensorGroundAltitude))
        value9 = degrees(atan(value6 / value5))
        value10 = value8 + value9
        value11 = sensorGroundAltitude * tan(radians(value10))
        value12 = value8 - value9
        value13 = sensorGroundAltitude * tan(radians(value12))
        value14 = distance - value13
        value15 = value11 - distance
        value16 = value3 - value14 * tan(radians(degrees_value))
        value17 = value3 + value15 * tan(radians(degrees_value))
        distance2 = sqrt(pow(value14, 2.0) + pow(value16, 2.0))
        value19 = sqrt(pow(value15, 2.0) + pow(value17, 2.0))
        value20 = degrees(atan(value16 / value14))
        value21 = degrees(atan(value17 / value15))

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

        frameCenterPoint = [packet.FrameCenterLatitude, packet.FrameCenterLongitude, packet.FrameCenterElevation]

        if hasElevationModel():
            cornerPointUL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUL)
            cornerPointUR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointUR)
            cornerPointLR = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLR)
            cornerPointLL = GetLine3DIntersectionWithDEM(
                GetSensor(), cornerPointLL)

        if sensor is not None:
            return cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL

        UpdateFootPrintData(packet,
                            cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, hasElevationModel())

        UpdateBeamsData(packet, cornerPointUL, cornerPointUR,
                        cornerPointLR, cornerPointLL, hasElevationModel())

        SetGCPsToGeoTransform(cornerPointUL, cornerPointUR,
                              cornerPointLR, cornerPointLL,
                              frameCenterPoint[1], frameCenterPoint[0], hasElevationModel())

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "CornerEstimationWithoutOffsets failed! : "), str(e))
        return False

    return True


def GetLine3DIntersectionWithDEM(sensorPt, targetPt):
    ''' Obtain height for points,intersecting with DEM '''
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
        # If fail,Return original point and add target elevation
        l = list(targetPt)
        l.append(targetAlt)
        return l

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
    ''' Seconds to time '''
    secs = timeval.hour * 3600 + timeval.minute * 60 + timeval.second
    secs += secs_to_add
    return _seconds_to_time(secs)


def _time_to_seconds(dateStr):
    '''
    Time to seconds
    @type dateStr: String
    @param dateStr: Date string value
    '''
    timeval = datetime.strptime(dateStr, '%H:%M:%S.%f')
    secs = timeval.hour * 3600 + timeval.minute * 60 + \
        timeval.second + timeval.microsecond / 1000000

    return secs


def _seconds_to_time(sec):
    '''Returns a string representation of the length of time provided.
    For example, 3675.14 -> '01:01:15'
    @type sec: String
    @param sec: seconds string value
    '''
    hours = int(sec / 3600)
    sec -= hours * 3600
    minutes = int(sec / 60)
    sec -= minutes * 60
    return '%02d:%02d:%02d' % (hours, minutes, sec)


def _seconds_to_time_frac(sec, comma=False):
    '''Returns a string representation of the length of time provided,
    including partial seconds.
    For example, 3675.14 -> '01:01:15.140000'
    @type sec: String
    @param sec: seconds string value
    '''
    hours = int(sec / 3600)
    sec -= hours * 3600
    minutes = int(sec / 60)
    sec -= minutes * 60
    if comma:
        frac = int(round(sec % 1.0 * 1000))
        return '%02d:%02d:%02d,%03d' % (hours, minutes, sec, frac)
    else:
        return '%02d:%02d:%07.4f' % (hours, minutes, sec)


def BurnDrawingsImage(source, overlay):
    '''Burn drawings into image
    @type source: QImage
    @param source: Original Image

    @type overlay: QImage
    @param overlay: Drawings image
    @return: QImage
    '''
    base = source.scaled(overlay.size(), Qt.IgnoreAspectRatio)

    p = QPainter()
    p.setRenderHint(QPainter.HighQualityAntialiasing)
    p.begin(base)
    p.setCompositionMode(QPainter.CompositionMode_SourceOut)
    p.drawImage(0, 0, overlay)
    p.end()

    # Restore size
    base = base.scaled(source.size(), Qt.IgnoreAspectRatio)
    return base
