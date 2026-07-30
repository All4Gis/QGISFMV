# -*- coding: utf-8 -*-
"""Video Multiplexer dialog — build MISB STANAG 4609 videos with pymisb."""

import os

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QDialog
from qgis.core import Qgis as QGis, QgsApplication, QgsTask

from QGISFMV.gui.ui_FmvMultiplexer import Ui_VideoMultiplexer
from QGISFMV.utils.core.QgsFmvUtils import askForFiles, _ensureFfmpegPaths
import QGISFMV.utils.core.QgsFmvUtils as _fmv_utils
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class Multiplexor(QDialog, Ui_VideoMultiplexer):
    """Create a MISB multiplexed video from source video + telemetry."""

    def __init__(self, iface, parent=None, Exts=None):
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self._manager = parent
        self.Exts = Exts
        self.chk_addManager.setChecked(True)
        self._background_tasks = []

    def OpenVideoFile(self):
        """Open a file dialog to select the input video file."""
        filename, _ = askForFiles(
            self,
            QCoreApplication.translate("Multiplexor", "Open video file"),
            exts=self.Exts,
        )
        if filename:
            self.ln_inputVideo.setText(filename)
            if not self.ln_outputVideo.text().strip():
                from pymisb.common import default_output

                self.ln_outputVideo.setText(default_output(filename))

    def OpenTelemetryFile(self):
        """Open a file dialog to select the input telemetry/KLV file."""
        filename, _ = askForFiles(
            self,
            QCoreApplication.translate("Multiplexor", "Open telemetry file"),
            exts=["csv", "txt", "log"],
        )
        if filename:
            self.ln_inputMeta.setText(filename)

    def OpenOutputFile(self):
        """Open a save dialog for the multiplexed output .ts file."""
        filename, _ = askForFiles(
            self,
            QCoreApplication.translate("Multiplexor", "Save multiplexed video as..."),
            isSave=True,
            exts=["ts"],
        )
        if filename:
            if not filename.lower().endswith(".ts"):
                filename += ".ts"
            self.ln_outputVideo.setText(filename)

    def CreateMISB(self):
        """Validate inputs and start the MISB multiplexing task."""
        inputVideo = self.ln_inputVideo.text().strip()
        telemetryFile = self.ln_inputMeta.text().strip()
        outputVideo = self.ln_outputVideo.text().strip()

        if not inputVideo or not telemetryFile or not outputVideo:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "Multiplexor",
                    "Select the source video, telemetry file, and output path.",
                ),
                level=QGis.MessageLevel.Warning,
            )
            return

        if not os.path.isfile(inputVideo):
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("Multiplexor", "Video file does not exist."),
                level=QGis.MessageLevel.Warning,
            )
            return

        if not os.path.isfile(telemetryFile):
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "Multiplexor", "Telemetry file does not exist."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return

        ext = os.path.splitext(telemetryFile)[1].lower()
        if ext not in (".csv", ".txt", ".log"):
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "Multiplexor", "Telemetry must be a .csv, .txt, or .log file."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return

        outputDir = os.path.dirname(os.path.abspath(outputVideo))
        if outputDir and not os.path.isdir(outputDir):
            try:
                os.makedirs(outputDir, exist_ok=True)
            except OSError as exc:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "Multiplexor", "Cannot create output folder: "
                    ),
                    str(exc),
                    level=QGis.MessageLevel.Critical,
                )
                return

        addManager = self.chk_addManager.isChecked()

        task = QgsTask.fromFunction(
            QCoreApplication.translate("Multiplexor", "MISB Multiplex Task"),
            self.muxTask,
            inputVideo=inputVideo,
            telemetryFile=telemetryFile,
            outputVideo=outputVideo,
            ext=ext,
            addManager=addManager,
            on_finished=self.muxFinished,
            flags=QgsTask.Flag.CanCancel,
        )
        self._background_tasks = [t for t in self._background_tasks if t is not None]
        self._background_tasks.append(task)
        QgsApplication.taskManager().addTask(task)
        self.accept()

    def _runMuxWithFfmpeg(self, task, inputVideo, packets, outputVideo):
        """Call pymisb mux, supporting both old and new engine signatures."""
        import inspect

        from pymisb.mux.engine import mux_with_ffmpeg

        _ensureFfmpegPaths()
        kwargs = {}
        params = inspect.signature(mux_with_ffmpeg).parameters
        if "ffmpeg_path" in params:
            kwargs["ffmpeg_path"] = _fmv_utils.ffmpeg_path
        if "task" in params:
            kwargs["task"] = task

        task.setProgress(10)
        if task.isCanceled():
            return
        mux_with_ffmpeg(inputVideo, packets, outputVideo, **kwargs)
        if task.isCanceled():
            return
        if not os.path.isfile(outputVideo) or os.path.getsize(outputVideo) == 0:
            raise RuntimeError("Mux completed but the output file is missing or empty.")
        task.setProgress(100)

    def muxTask(self, task, inputVideo, telemetryFile, outputVideo, ext, addManager):
        """Background task: multiplex KLV telemetry into the video stream."""
        from pymisb.common import build_klv_packets, build_klv_packets_from_txt

        if ext == ".csv":
            packets = build_klv_packets(telemetryFile)
        else:
            packets = build_klv_packets_from_txt(telemetryFile)

        if not packets:
            raise ValueError("No telemetry packets were generated.")
        if task.isCanceled():
            return None

        task.setProgress(5)
        self._runMuxWithFfmpeg(task, inputVideo, packets, outputVideo)
        if task.isCanceled():
            return None

        return {
            "task": QCoreApplication.translate("Multiplexor", "MISB Multiplex Task"),
            "output": outputVideo,
            "addManager": addManager,
        }

    def muxFinished(self, e, result=None):
        """Slot: handle MISB multiplex task completion."""
        if e is None and result:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("Multiplexor", "MISB video created: ")
                + result["output"],
                level=QGis.MessageLevel.Success,
            )
            if result.get("addManager") and self._manager is not None:
                _, name = os.path.split(result["output"])
                self._manager.AddFileRowToManager(name, result["output"])
            return

        taskName = (result or {}).get("task", "MISB Multiplex Task")
        detail = str(e) if e else ""
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate("Multiplexor", "MISB video creation failed: ")
            + taskName,
            detail,
            level=QGis.MessageLevel.Critical,
        )
