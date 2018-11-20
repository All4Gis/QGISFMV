# Original Code : https://github.com/zeroepoch/plotbitrate
# Modificated for work in QGIS FMV Plugin

from PyQt5.QtCore import QObject
from QGIS_FMV.utils.QgsFmvUtils import _spawn

try:
    from pydevd import *
except ImportError:
    None

try:
    import xml.etree.cElementTree as etree
except ImportError:
    import xml.etree.ElementTree as etree


class CreatePlotsBitrate(QObject):
    """ Create Plot Bitrate """

    def __init__(self):
        """ Constructor """
        self.bitrate_data = None
        self.frame_count = None
        self.output = None

    def CreatePlot(self, task, fileName, output, t):
        """ Create Plot Bitrate Slot"""
        try:
            task.setProgress(10)

            bitrate_data = {}
            frame_count = 0
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
                    "-print_format", "xml", "-preset", "ultrafast",
                    fileName]
            try:
                with _spawn(cmds, t="probe") as proc_frame:
                    task.setProgress(22)
                    # process xml elements as they close
                    for event in etree.iterparse(proc_frame.stdout):
                        task.setProgress(40)
                        # skip non-frame elements
                        node = event[1]
                        if node.tag != 'frame':
                            continue

                        # count number of frames
                        frame_count += 1

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
                                        "-print_format", "xml", "-preset", "ultrafast",
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
                                if frame_count > 1:
                                    frame_time += float(node.get('pkt_duration_time'))

                        frame_bitrate = (float(node.get('pkt_size'))
                                         * 8 / 1000) * frame_rate
                        frame = (frame_time, frame_bitrate)

                        # create new frame list if new type
                        if frame_type not in bitrate_data:
                            bitrate_data[frame_type] = []

                        # append frame to list by type
                        bitrate_data[frame_type].append(frame)

                        task.setProgress(45)

                    # check if ffprobe was successful
                    if frame_count == 0:
                        task.cancel()
                        return None
            except Exception:
                task.cancel()
                return None
            # end frame subprocess
            task.setProgress(80)
            self.bitrate_data = bitrate_data
            self.frame_count = frame_count
            self.output = output
            if task.isCanceled():
                return None
            return {'task': task.description()}

        except Exception:
            task.cancel()
            return None
