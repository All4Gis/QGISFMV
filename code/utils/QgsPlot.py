# Original Code : https://github.com/zeroepoch/plotbitrate
# Modificated for work in QGIS FMV Plugin

from PyQt5.QtCore import QObject, QCoreApplication
from QGIS_FMV.utils.QgsFmvUtils import _spawn

try:
    from pydevd import *
except ImportError:
    None

import xml.etree.cElementTree as etree

try:
    import numpy
    import matplotlib.pyplot as matplot
except ImportError:
    None


def ShowPlot(bitrate_data, frame_count, fileName, output=None):
    ''' Show plot,because show not work using threading '''
    matplot.figure().canvas.set_window_title(fileName)
    matplot.title(QCoreApplication.translate(
        "QgsFmvPlayer", "Stream Bitrate vs Time"))
    matplot.xlabel(QCoreApplication.translate(
        "QgsFmvPlayer", "Time (sec)"))
    matplot.ylabel(QCoreApplication.translate(
        "QgsFmvPlayer", "Frame Bitrate (kbit/s)"))
    matplot.grid(True)
    # map frame type to color
    frame_type_color = {
        # audio
        'A': 'yellow',
        # video
        'I': 'red',
        'P': 'green',
        'B': 'blue'
    }

    global_peak_bitrate = 0.0
    global_mean_bitrate = 0.0

    # render charts in order of expected decreasing size
    for frame_type in ['I', 'P', 'B', 'A']:

        # skip frame type if missing
        if frame_type not in bitrate_data:
            continue

        # convert list of tuples to numpy 2d array
        frame_list = bitrate_data[frame_type]
        frame_array = numpy.array(frame_list)

        # update global peak bitrate
        peak_bitrate = frame_array.max(0)[1]
        if peak_bitrate > global_peak_bitrate:
            global_peak_bitrate = peak_bitrate

        # update global mean bitrate (using piecewise mean)
        mean_bitrate = frame_array.mean(0)[1]
        global_mean_bitrate += mean_bitrate * \
            (len(frame_list) / frame_count)

        # plot chart using gnuplot-like impulses
        matplot.vlines(
            frame_array[:, 0], [0], frame_array[:, 1],
            color=frame_type_color[frame_type],
            label="{} Frames".format(frame_type))

    # calculate peak line position (left 15%, above line)
    peak_text_x = matplot.xlim()[1] * 0.15
    peak_text_y = global_peak_bitrate + \
        ((matplot.ylim()[1] - matplot.ylim()[0]) * 0.015)
    peak_text = "peak ({:.0f})".format(global_peak_bitrate)

    # draw peak as think black line w/ text
    matplot.axhline(global_peak_bitrate, linewidth=2, color='black')
    matplot.text(peak_text_x, peak_text_y, peak_text,
                 horizontalalignment='center', fontweight='bold', color='black')

    # calculate mean line position (right 85%, above line)
    mean_text_x = matplot.xlim()[1] * 0.85
    mean_text_y = global_mean_bitrate + \
        ((matplot.ylim()[1] - matplot.ylim()[0]) * 0.015)
    mean_text = "mean ({:.0f})".format(global_mean_bitrate)

    # draw mean as think black line w/ text
    matplot.axhline(global_mean_bitrate, linewidth=2, color='black')
    matplot.text(mean_text_x, mean_text_y, mean_text,
                 horizontalalignment='center', fontweight='bold',
                 color='black')

    matplot.legend()
    if output is not None:
        matplot.savefig(output)
    else:
        matplot.show()
    return matplot


class CreatePlotsBitrate(QObject):
    """ Create Plot Bitrate """

    def __init__(self):
        """ Constructor """
        self.bitrate_data = {}
        self.frame_count = 0
        self.output = None

    def CreatePlot(self, task, fileName, output, t):
        """ Create Plot Bitrate Slot"""
        try:
            task.setProgress(10)
            frame_rate = None
            frame_time = 0.0

            # set ffprobe stream specifier
            if t == 'audio':
                stream_spec = 'a'
            elif t == 'video':
                stream_spec = 'V'
            else:
                task.cancel()
                return None

            # get frame data for the selected stream
            cmds = ["-show_entries", "frame",
                    "-select_streams", stream_spec,
                    "-print_format", "xml",
                    fileName]
            try:
                with _spawn(cmds, t="probe") as proc_frame:
                    # process xml elements as they close
                    for event in etree.iterparse(proc_frame.stdout):
                        # skip non-frame elements
                        node = event[1]
                        if node.tag != 'frame':
                            continue

                        # count number of frames
                        self.frame_count += 1

                        # get type of frame
                        if t == 'audio':
                            frame_type = 'A'  # pseudo frame type
                        else:
                            frame_type = node.get('pict_type')

                        # get frame rate only once
                        if frame_rate is None:
                            # audio frame rate, 1 / frame duration
                            if t == 'audio':
                                frame_rate = 1.0 / \
                                    float(node.get('pkt_duration_time'))

                            # video frame rate, read stream header
                            else:
                                cmds = ["-show_entries", "stream",
                                        "-select_streams", "V",
                                        "-print_format", "xml",
                                        fileName
                                        ]
                                with _spawn(cmds, t="probe") as proc_stream:

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
                        try:
                            frame_time = float(
                                node.get('best_effort_timestamp_time'))
                        except Exception:
                            try:
                                frame_time = float(node.get('pkt_pts_time'))
                            except Exception:
                                if self.frame_count > 1:
                                    frame_time += float(node.get('pkt_duration_time'))

                        frame_bitrate = (float(node.get('pkt_size'))
                                         * 8 / 1000) * frame_rate
                        frame = (frame_time, frame_bitrate)

                        # create new frame list if new type
                        if frame_type not in self.bitrate_data:
                            self.bitrate_data[frame_type] = []

                        # append frame to list by type
                        self.bitrate_data[frame_type].append(frame)

                        task.setProgress(45)

                    # check if ffprobe was successful
                    if self.frame_count == 0:
                        task.cancel()
                        return None
            except Exception:
                task.cancel()
                return None
            # end frame subprocess
            task.setProgress(80)
            self.output = output
            if task.isCanceled():
                return None
            return {'task': task.description()}

        except Exception:
            task.cancel()
            return None
