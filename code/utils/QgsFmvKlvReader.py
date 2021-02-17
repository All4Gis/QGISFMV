# -*- coding: utf-8 -*-
from queue import Queue, Empty
import threading
import collections
import platform
import os
from configparser import ConfigParser
from os.path import dirname, abspath
import subprocess
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.utils.QgsFmvUtils import _time_to_seconds, _seconds_to_time_frac, _add_secs_to_time, _spawn
from datetime import datetime

windows = platform.system() == 'Windows'
parser = ConfigParser()
parser.read(os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini'))

min_buffer_size = int(parser['GENERAL']['min_buffer_size'])
ffmpegConf = parser['GENERAL']['ffmpeg']

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
                        # qgsu.showUserAndLogMessage("", "metaFound" + str(metaFound), onlyLog=True)
                        metaFound = metaFound + 1

                    # feed the current packet
                    if metaFound <= packetsPerQueueElement:
                        # qgsu.showUserAndLogMessage("", "feeding packet" + str(metaFound), onlyLog=True)
                        data = data + line
                    # add to queue and start a new one
                    else:
                        # qgsu.showUserAndLogMessage("", "Put to queue and start over" + repr(data), onlyLog=True)
                        queue.put(data)
                        data = line
                        metaFound = 1

                # End of stream
                else:
                    qgsu.showUserAndLogMessage(
                        "", "reader got end of stream.", onlyLog=True)
                    break

            if self.stopped:
                qgsu.showUserAndLogMessage(
                    "", "NonBlockingStreamReader ended because stop signal received.", onlyLog=True)

        self._t = threading.Thread(
            target=_populateQueue, args=(
                self._p, self._q))
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

        # qgsu.showUserAndLogMessage("", "starting Splitter on thread:" + str(threading.current_thread().ident), onlyLog=True)
        # qgsu.showUserAndLogMessage("", "with args:" + ' '.join(self.cmds), onlyLog=True)

        # Hide shell windows that pops up on windows.
        if windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        self.p = subprocess.Popen(
            self.cmds,
            startupinfo=startupinfo,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE)
        # Dont us _spawn here as it will DeadLock, and the splitter won't work
        # self.p = _spawn(self.cmds)
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
        self.connection = self.srcProtocol + ':' + \
            self.srcHost + ':' + str(self.srcPort)
        self.connectionDest = self.srcProtocol + \
            '://127.0.0.1:' + str(self.destPort)
        self.splitter = Splitter(['-i',
                                  self.connection,
                                  '-c',
                                  'copy',
                                  '-map',
                                  '0:v?',
                                  '-map',
                                  '0:a?',
                                  '-f',
                                  'rtp_mpegts',
                                  self.connectionDest,
                                  '-map',
                                  '0:d?',
                                  '-f',
                                  'data',
                                  '-'])
        self.splitter.start()
        qgsu.showUserAndLogMessage("", "Splitter started.", onlyLog=True)

    def getSize(self):
        return self.splitter.nbsr._q.qsize()

    def get(self, _):
        # qgsu.showUserAndLogMessage("", "Get called on Streamreader.", onlyLog=True)
        return self.splitter.nbsr.readline()

    def dispose(self):
        # qgsu.showUserAndLogMessage("", "Dispose called on StreamMetaReader.", onlyLog=True)
        self.splitter.nbsr.stopped = True
        # kill the process if open, releases source port
        try:
            self.splitter.p.kill()
            qgsu.showUserAndLogMessage(
                "", "Splitter Popen process killed.", onlyLog=True)
        except OSError:
            # can't kill a dead proc
            pass


class BufferedMetaReader():
    ''' Non-Blocking metadata reader with buffer  '''

    # if we go lower, the buffer will shrink drastically and the video may
    # hang.

    def __init__(self, video_path, klv_index=0, pass_time=250, interval=1000):
        ''' Constructor '''
        # don't go too low with pass_time or we won't catch any metadata at
        # all.
        # 8 x 500 = 4000ms buffer time
        # min_buffer_size x buffer_interval = Miliseconds buffer time
        self.video_path = video_path
        self.pass_time = pass_time
        self.interval = interval
        self._meta = {}
        self._min_buffer_size = min_buffer_size
        self.klv_index = klv_index
        self._initialize('00:00:00.0000', self._min_buffer_size)

    def _initialize(self, start, size):
        self.bufferParalell(start, size)

    def _check_buffer(self, start):
        self.bufferParalell(start, self._min_buffer_size)

    def getSize(self, t):
        size = 0
        s_date = datetime.strptime(t, '%H:%M:%S.%f')
        last_date = None
        # calculate buffer size ahead of supplied time (contiguous values
        # only).
        od = collections.OrderedDict(sorted(self._meta.items()))
        for ele in od.keys():
            c_date = datetime.strptime(ele, '%H:%M:%S.%f')
            if last_date is None:
                last_date = c_date
                continue

            if c_date > s_date:
                # qgsu.showUserAndLogMessage("", "Comparing: ele:" + ele + " greater than t (as date):" + t + " : yes", onlyLog=True)
                # qgsu.showUserAndLogMessage("", "c_date:" + c_date.strftime('%H:%M:%S.%f') + " last_date:" + last_date.strftime('%H:%M:%S.%f'), onlyLog=True)
                delta_millisec = (c_date - last_date).microseconds / \
                    1000 + (c_date - last_date).seconds * 1000
                # qgsu.showUserAndLogMessage("", "delta: " + str(delta_millisec), onlyLog=True)
                if delta_millisec <= self.interval:
                    size += 1
                    # qgsu.showUserAndLogMessage("", "Smaller or equal than pass_time:" + str(delta_millisec), onlyLog=True)
                else:
                    # qgsu.showUserAndLogMessage("", "Greater than pass_time:" + str(delta_millisec), onlyLog=True)
                    break

            last_date = c_date

        return size

    def bufferParalell(self, start, size):
        start_sec = _time_to_seconds(start)
        start_milisec = int(start_sec * 1000)

        for k in range(start_milisec, start_milisec +
                       (size * self.interval), self.interval):
            cTime = k / 1000.0
            nTime = (k + self.pass_time) / 1000.0
            new_key = _seconds_to_time_frac(cTime)
            if new_key not in self._meta:
                # qgsu.showUserAndLogMessage("QgsFmvUtils", 'buffering: ' + _seconds_to_time_frac(cTime) + " to " + _seconds_to_time_frac(nTime), onlyLog=True)
                self._meta[new_key] = callBackMetadataThread(
                    cmds=[
                        '-i',
                        self.video_path,
                        '-ss',
                        new_key,
                        '-to',
                        _seconds_to_time_frac(nTime),
                        '-map',
                        '0:d:' + str(
                            self.klv_index),
                        '-f',
                        'data',
                        '-'])
                self._meta[new_key].start()

    def get(self, t):
        ''' read a value and check the buffer '''
        value = b''
        # get the closest value for this time from the buffer
        s = t.split(".")
        new_t = ''
        try:
            milis = int(s[1][:-1])

            if self.interval > 1000:
                inte = 1000

            r_milis = round(milis / inte) * inte
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
                    "",
                    "Meta reader -> get: " +
                    t +
                    " cache: " +
                    new_t +
                    " values have not been init yet.",
                    onlyLog=True)
                self._check_buffer(new_t)
                value = 'BUFFERING'
            elif self._meta[new_t].p is None:
                value = 'NOT_READY'
                qgsu.showUserAndLogMessage(
                    "",
                    "Meta reader -> get: " +
                    t +
                    " cache: " +
                    new_t +
                    " values not ready yet.",
                    onlyLog=True)
            elif self._meta[new_t].p.returncode is None:
                value = 'NOT_READY'
                qgsu.showUserAndLogMessage(
                    "",
                    "Meta reader -> get: " +
                    t +
                    " cache: " +
                    new_t +
                    " values not ready yet.",
                    onlyLog=True)
            elif self._meta[new_t].stdout:
                value = self._meta[new_t].stdout
            else:
                qgsu.showUserAndLogMessage(
                    "",
                    "Meta reader -> get: " +
                    t +
                    " cache: " +
                    new_t +
                    " values ready but empty.",
                    onlyLog=True)

            self._check_buffer(new_t)
            # bSize = self.getSize(t)
            # qgsu.showUserAndLogMessage("Buffer size:" + str(bSize), "Buffer size:" + str(bSize), onlyLog=False)
        except Exception as e:
            qgsu.showUserAndLogMessage(
                "",
                "No value found for: " +
                t +
                " rounded: " +
                new_t +
                " e:" +
                str(e),
                onlyLog=True)

        # qgsu.showUserAndLogMessage("QgsFmvUtils", "meta_reader -> get: " + t + " return code: "+ str(self._meta[new_t].p.returncode), onlyLog=True)
        # qgsu.showUserAndLogMessage("QgsFmvUtils", "meta_reader -> get: " + t + " cache: "+ new_t +" len: " + str(len(value)), onlyLog=True)

        return value

    def dispose(self):
        pass


class callBackMetadataThread(threading.Thread):
    ''' CallBack metadata in other thread  '''

    def __init__(self, cmds=[]):
        self.cmds = cmds
        self.p = None
        threading.Thread.__init__(self)

    def setCmds(self, cmds):
        self.cmds = cmds

    def run(self):
        # qgsu.showUserAndLogMessage("", "callBackMetadataThread run: commands:" + str(self.cmds), onlyLog=True)
        self.p = _spawn(self.cmds)
        # print (self.cmds)
        self.stdout, _ = self.p.communicate()
        # print (self.stdout)
        # print (_)
