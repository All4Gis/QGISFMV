# Original Code : https://github.com/zeroepoch/plotbitrate
# Modificated for work in QGIS FMV Plugin

import os
import shutil
import traceback

from PyQt5.QtCore import QCoreApplication, QObject, pyqtSignal, pyqtSlot
from QGIS_FMV.utils.QgsFmvLog import log
from QGIS_FMV.utils.QgsFmvUtils import _spawn
from qgis.gui import QgsMessageBar


try:
    from pydevd import *
except ImportError:
    None

try:
    import xml.etree.cElementTree as etree
except ImportError:
    import xml.etree.ElementTree as etree


# TODO : Disabled if video not have audio stream
class CreatePlotsBitrate(QObject):
    """ Create Plot Bitrate """
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str, Exception, basestring)
    progress = pyqtSignal(float)
    return_fig = pyqtSignal(dict, int, str)

    @pyqtSlot(str, str, str)
    def CreatePlot(self, file, output, type):
        """ Create Plot Bitrate Slot"""
        try:
            self.progress.emit(10)

            bitrate_data = {}
            frame_count = 0
            frame_rate = None
            frame_time = 0.0

            # set ffprobe stream specifier
            if type == 'audio':
                stream_spec = 'a'
            elif type == 'video':
                stream_spec = 'V'
            else:
                self.error.emit(
                    "CreatePlotsBitrate", "Invalid stream type", traceback.format_exc())
                return

            # get frame data for the selected stream
            cmds = ["-show_entries", "frame",
                    "-select_streams", stream_spec,
                    "-print_format", "xml",
                    file]
            self.progress.emit(20)
            try:
                with _spawn(cmds, type="probe") as proc_frame:
                    self.progress.emit(22)
                    # process xml elements as they close
                    for event in etree.iterparse(proc_frame.stdout):
                        self.progress.emit(25)
                        # skip non-frame elements
                        node = event[1]
                        if node.tag != 'frame':
                            continue

                        # count number of frames
                        frame_count += 1

                        # get type of frame
                        if type == 'audio':
                            frame_type = 'A'  # pseudo frame type
                        else:
                            frame_type = node.get('pict_type')

                        # get frame rate only once (assumes non-variable
                        # framerate)
                        self.progress.emit(30)
                        if frame_rate is None:

                            # audio frame rate, 1 / frame duration
                            if type == 'audio':
                                frame_rate = 1.0 / \
                                    float(node.get('pkt_duration_time'))

                            # video frame rate, read stream header
                            else:
                                cmds = ["-show_entries", "stream",
                                        "-select_streams", "V",
                                        "-print_format", "xml",
                                        file
                                        ]
                                with _spawn(cmds, type="probe") as proc_stream:

                                    # parse stream header xml
                                    stream_data = etree.parse(
                                        proc_stream.stdout)
                                    stream_elem = stream_data.find('.//stream')

                                    # compute frame rate from ratio
                                    frame_rate_ratio = stream_elem.get(
                                        'avg_frame_rate')
                                    (dividend, divisor) = frame_rate_ratio.split('/')
                                    frame_rate = float(
                                        dividend) / float(divisor)

                        # collect frame data
                        self.progress.emit(35)
                        try:
                            frame_time = float(
                                node.get('best_effort_timestamp_time'))
                        except:
                            try:
                                frame_time = float(node.get('pkt_pts_time'))
                            except:
                                if frame_count > 1:
                                    frame_time += float(node.get('pkt_duration_time'))

                        self.progress.emit(40)

                        frame_bitrate = (float(node.get('pkt_size'))
                                         * 8 / 1000) * frame_rate
                        frame = (frame_time, frame_bitrate)

                        # create new frame list if new type
                        if frame_type not in bitrate_data:
                            bitrate_data[frame_type] = []

                        # append frame to list by type
                        bitrate_data[frame_type].append(frame)

                        self.progress.emit(45)

                    # check if ffprobe was successful
                    if frame_count == 0:
                        self.error.emit(
                            "CreatePlotsBitrate", "Error: No frame data, failed to execute ffprobe", traceback.format_exc())
                        return
            except:
                self.error.emit(
                    "CreatePlotsBitrate", "Error: No frame data, failed to execute ffprobe", traceback.format_exc())
                return
            # end frame subprocess
            # Start MatPlot Setup new figure
            self.progress.emit(80)

            self.return_fig.emit(bitrate_data, frame_count, output)
            self.finished.emit("CreatePlotsBitrate",
                               "Bitrate correct Finished!")
            return

        except Exception as e:
            self.error.emit("CreatePlotsBitrate", e, traceback.format_exc())
            return
