# Original Code : https://github.com/zeroepoch/plotbitrate
# Modificated for work in QGIS FMV Plugin
# -*- coding: utf-8 -*-
from io import BytesIO

from qgis.PyQt.QtCore import QObject, QCoreApplication
from QGISFMV.utils.core.QgsFmvUtils import _spawn
from QGISFMV.utils.logging import log

import xml.etree.ElementTree as etree

numpy = None
matplot = None
_plot_ok = None  # None = untested, True/False = cached


def _ensure_plot_deps():
    """Import matplotlib/numpy on first use; retries after fresh install."""
    global numpy, matplot, _plot_ok
    if _plot_ok:
        return True
    try:
        import numpy as _np
        import matplotlib.pyplot as _mp

        numpy = _np
        matplot = _mp
        _plot_ok = True
        return True
    except ImportError:
        numpy = None
        matplot = None
        _plot_ok = False
        return False


def _probeFrameRate(fileName, streamSpec, mediaType):
    """Return average frame rate for the selected stream."""
    proc = _spawn(
        [
            "-show_entries",
            "stream=avg_frame_rate,r_frame_rate",
            "-select_streams",
            streamSpec,
            "-v",
            "quiet",
            "-print_format",
            "xml",
            fileName,
        ],
        t="probe",
    )
    out, _ = proc.communicate(timeout=30)
    if proc.returncode != 0 or not out:
        return None

    streamElem = etree.parse(BytesIO(out)).find(".//stream")
    if streamElem is None:
        return None

    if mediaType == "audio":
        procFrame = _spawn(
            [
                "-show_entries",
                "frame=pkt_duration_time",
                "-select_streams",
                streamSpec,
                "-read_intervals",
                "%+#1",
                "-v",
                "quiet",
                "-print_format",
                "xml",
                fileName,
            ],
            t="probe",
        )
        frameOut, _ = procFrame.communicate(timeout=15)
        if procFrame.returncode == 0 and frameOut:
            frameElem = etree.parse(BytesIO(frameOut)).find(".//frame")
            duration = (
                frameElem.get("pkt_duration_time") if frameElem is not None else None
            )
            if duration:
                return 1.0 / float(duration)
        return None

    for attr in ("avg_frame_rate", "r_frame_rate"):
        ratio = streamElem.get(attr) or ""
        if ratio and ratio != "0/0" and "/" in ratio:
            dividend, divisor = ratio.split("/", 1)
            if float(divisor):
                return float(dividend) / float(divisor)
    return None


def _probeFrameXml(fileName, streamSpec):
    """Read all frame metadata XML for a stream (single ffprobe call)."""
    proc = _spawn(
        [
            "-show_entries",
            "frame=pict_type,pkt_size,best_effort_timestamp_time,pkt_pts_time,pkt_duration_time",
            "-select_streams",
            streamSpec,
            "-v",
            "quiet",
            "-print_format",
            "xml",
            fileName,
        ],
        t="probe",
    )
    out, _ = proc.communicate(timeout=30)
    if proc.returncode != 0 or not out:
        return None
    return out


def ShowPlot(bitrate_data, frame_count, fileName, output=None):
    """Show plot,because show not work using threading"""
    if not _ensure_plot_deps():
        raise ImportError("matplotlib and numpy are required for bitrate plots")

    fig = matplot.figure()
    try:
        fig.canvas.manager.set_window_title(fileName)
    except Exception as exc:
        from QGISFMV.utils.logging import log
        log.debug("matplotlib window title failed: %s", exc)
    matplot.title(QCoreApplication.translate("QgsFmvPlayer", "Stream Bitrate vs Time"))
    matplot.xlabel(QCoreApplication.translate("QgsFmvPlayer", "Time (sec)"))
    matplot.ylabel(QCoreApplication.translate("QgsFmvPlayer", "Frame Bitrate (kbit/s)"))
    matplot.grid(True)
    frame_type_color = {
        "A": "yellow",
        "I": "red",
        "P": "green",
        "B": "blue",
    }

    global_peak_bitrate = 0.0
    global_mean_bitrate = 0.0

    for frame_type in ["I", "P", "B", "A"]:
        if frame_type not in bitrate_data:
            continue

        frame_list = bitrate_data[frame_type]
        frame_array = numpy.array(frame_list)

        peak_bitrate = frame_array.max(0)[1]
        if peak_bitrate > global_peak_bitrate:
            global_peak_bitrate = peak_bitrate

        mean_bitrate = frame_array.mean(0)[1]
        global_mean_bitrate += mean_bitrate * (len(frame_list) / frame_count)

        matplot.vlines(
            frame_array[:, 0],
            [0],
            frame_array[:, 1],
            color=frame_type_color[frame_type],
            label="{} Frames".format(frame_type),
        )

    peak_text_x = matplot.xlim()[1] * 0.15
    peak_text_y = global_peak_bitrate + (
        (matplot.ylim()[1] - matplot.ylim()[0]) * 0.015
    )
    peak_text = "peak ({:.0f})".format(global_peak_bitrate)

    matplot.axhline(global_peak_bitrate, linewidth=2, color="black")
    matplot.text(
        peak_text_x,
        peak_text_y,
        peak_text,
        horizontalalignment="center",
        fontweight="bold",
        color="black",
    )

    mean_text_x = matplot.xlim()[1] * 0.85
    mean_text_y = global_mean_bitrate + (
        (matplot.ylim()[1] - matplot.ylim()[0]) * 0.015
    )
    mean_text = "mean ({:.0f})".format(global_mean_bitrate)

    matplot.axhline(global_mean_bitrate, linewidth=2, color="black")
    matplot.text(
        mean_text_x,
        mean_text_y,
        mean_text,
        horizontalalignment="center",
        fontweight="bold",
        color="black",
    )

    matplot.legend()
    if output is not None:
        matplot.savefig(output)
    else:
        matplot.show()
    return matplot


class CreatePlotsBitrate(QObject):
    """Compute and display bitrate plots for video/audio streams."""

    def __init__(self):
        super().__init__()
        self.bitrate_data = {}
        self.frame_count = 0
        self.output = None

    def CreatePlot(self, task, fileName, output, t):
        """Extract frame bitrates via ffprobe and store them for plotting."""
        if not _ensure_plot_deps():
            return {
                "task": task.description(),
                "error": "matplotlib/numpy not installed",
            }

        try:
            task.setProgress(10)
            self.bitrate_data = {}
            self.frame_count = 0
            self.output = output

            if t == "audio":
                streamSpec = "a"
            elif t == "video":
                streamSpec = "V"
            else:
                return None

            frameRate = _probeFrameRate(fileName, streamSpec, t)
            if frameRate is None or frameRate <= 0:
                return None

            task.setProgress(25)
            rawXml = _probeFrameXml(fileName, streamSpec)
            if not rawXml:
                return None

            root = etree.parse(BytesIO(rawXml))
            frameTime = 0.0
            for node in root.findall(".//frame"):
                self.frame_count += 1

                if t == "audio":
                    frameType = "A"
                else:
                    frameType = node.get("pict_type") or "P"

                try:
                    frameTime = float(node.get("best_effort_timestamp_time"))
                except (TypeError, ValueError):
                    try:
                        frameTime = float(node.get("pkt_pts_time"))
                    except (TypeError, ValueError):
                        duration = node.get("pkt_duration_time")
                        if duration and self.frame_count > 1:
                            frameTime += float(duration)

                try:
                    pktSize = float(node.get("pkt_size"))
                except (TypeError, ValueError):
                    continue

                frameBitrate = (pktSize * 8 / 1000) * frameRate
                self.bitrate_data.setdefault(frameType, []).append(
                    (frameTime, frameBitrate)
                )

                if self.frame_count % 100 == 0:
                    task.setProgress(
                        min(
                            75,
                            25
                            + int(
                                50
                                * self.frame_count
                                / max(len(root.findall(".//frame")), 1)
                            ),
                        )
                    )

            if self.frame_count == 0:
                return None

            task.setProgress(80)
            if task.isCanceled():
                return None
            return {"task": task.description()}

        except Exception as _exc:
            log.debug("bitrate plot creation failed: %s", _exc)
            return None
