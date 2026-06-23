# -*- coding: utf-8 -*-
"""
Video Multiplexer dialog.

Generates a MISB / STANAG 4609 MPEG-TS video (video + audio + timed KLV
metadata channel) from a DJI video and its telemetry CSV, using the
self-contained generator under ``QGIS_FMV.misb``.

This replaces the old per-frame ``.klv`` folder approach: the result is a single
``.ts`` file with the KLV embedded (stream_type 0x15, "KLVA"), ready to be opened
directly in QGISFMV like any other MISB video.
"""
import os

from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QDialog, QApplication

from qgis.core import Qgis as QGis

from QGIS_FMV.gui.ui_FmvMultiplexer import Ui_VideoMultiplexer
from QGIS_FMV.utils.QgsFmvUtils import askForFiles, ffmpeg_path
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu

import QGIS_FMV.misb.misb_common as misb_common
from QGIS_FMV.misb.misb_ffmpeg import mux_with_ffmpeg


class Multiplexor(QDialog, Ui_VideoMultiplexer):
    """ MISB video generator dialog """

    def __init__(self, iface, parent=None, Exts=None):
        """ Constructor """
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.parent = parent

        self.video_file = None
        self.csv_file = None
        self.Exts = Exts

    def OpenVideoFile(self):
        ''' Open input video File '''
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "Multiplexor", "Open video file"),
            exts=self.Exts)
        if filename:
            self.video_file = filename
            self.ln_inputVideo.setText(self.video_file)
        return

    def OpenCsvFile(self):
        ''' Open telemetry CSV File '''
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "Multiplexor", "Open telemetry CSV"),
            exts="csv")
        if filename:
            self.csv_file = filename
            self.ln_inputMeta.setText(self.csv_file)
        return

    def CreateMISB(self):
        ''' Create the MISB MPEG-TS video (video + audio + KLV) '''
        input_video = self.ln_inputVideo.text()
        input_csv = self.ln_inputMeta.text()

        if not input_video or not input_csv:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "Multiplexor", "You must select both the video and the telemetry CSV."),
                level=QGis.MessageLevel.Warning)
            return

        if not os.path.isfile(input_video):
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "Multiplexor", "Video file does not exist."),
                level=QGis.MessageLevel.Warning)
            return

        if not os.path.isfile(input_csv):
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "Multiplexor", "Telemetry CSV does not exist."),
                level=QGis.MessageLevel.Warning)
            return

        # Apply the field of view from the dialog to the encoder
        misb_common.HFOV_DEG = float(self.sp_hfov.value())
        misb_common.VFOV_DEG = float(self.sp_vfov.value())

        only_recording = not self.chk_allRows.isChecked()
        out_ts = misb_common.default_output(input_video)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            packets = misb_common.build_klv_packets(input_csv, only_recording=only_recording)
            mux_with_ffmpeg(input_video, packets, out_ts, ffmpeg_bin=ffmpeg_path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "Multiplexor", "MISB video creation failed: "), str(e),
                level=QGis.MessageLevel.Critical)
            return
        finally:
            QApplication.restoreOverrideCursor()
            QApplication.processEvents()

        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "Multiplexor", "MISB video created: ") + out_ts,
            level=QGis.MessageLevel.Success)

        # Add the new MISB video to the manager (KLV is embedded in the .ts)
        _, name = os.path.split(out_ts)
        self.parent.AddFileRowToManager(name, out_ts)

        self.close()
        return
