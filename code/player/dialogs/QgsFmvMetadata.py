# -*- coding: utf-8 -*-
import csv
import os
import platform

from qgis.core import Qgis as QGis
from qgis.core import QgsApplication, QgsTask
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QDockWidget

from QGISFMV.gui.ui_FmvMetadata import Ui_FmvMetadata
from QGISFMV.player.dialogs.QgsFmvReportGenerator import ReportGenerator
from QGISFMV.player.dialogs.QgsFmvReportMetadata import (
    _group_metadata_fields,
    _metadata_dict_from_table,
)
from QGISFMV.utils.core.QgsFmvUtils import (
    BurnDrawingsImage,
    _seconds_to_time,
    askForFiles,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

# Metadata-formatting helpers live in QgsFmvReportMetadata.py; PDF rendering
# lives in ReportGenerator.


# ---------------------------------------------------------------------------
# QgsFmvMetadata — dock widget (public API unchanged)
# ---------------------------------------------------------------------------


class QgsFmvMetadata(QDockWidget, Ui_FmvMetadata):
    """Metadata Class Reports"""

    def __init__(self, player=None):
        """Contructor"""
        super().__init__()
        self.setupUi(self)
        if platform.system() == "Darwin":
            self.menubarwidget.setNativeMenuBar(False)
        self.player = player
        self._background_tasks = []

    def _dialog_parent(self):
        if self.player is not None and hasattr(self.player, "_dialog_parent"):
            return self.player._dialog_parent()
        if self.player is not None and getattr(self.player, "iface", None) is not None:
            return self.player.iface.mainWindow()
        return self

    def _add_background_task(self, task):
        self._background_tasks = [t for t in self._background_tasks if t is not None]
        self._background_tasks.append(task)
        QgsApplication.taskManager().addTask(task)
        return task

    def finishedTask(self, e, result=None):
        """Common finish task function"""
        if e is None:
            if result is None:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "QgsFmvMetadata",
                        "Completed with no exception and no result "
                        "(probably manually canceled by the user)",
                    ),
                    level=QGis.MessageLevel.Warning,
                )
            else:
                if result.get("error"):
                    qgsu.showUserAndLogMessage(
                        result["error"], level=QGis.MessageLevel.Warning
                    )
                    return
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "QgsFmvMetadata", "Succesfully " + result["task"] + "!"
                    )
                )
        else:
            task_name = (result or {}).get("task", "task")
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvMetadata", "Failed " + task_name + "!"
                ),
                level=QGis.MessageLevel.Warning,
            )
            from QGISFMV.utils.logging import log

            log.error("Task failed (%s): %s", task_name, e)

    def _report_metadata(self):
        """Metadata dict for exports, falling back to the visible table."""
        data = {}
        if self.player is not None:
            packet_data = self.player.GetPacketData()
            if packet_data:
                data = dict(packet_data)
        table_data = _metadata_dict_from_table(self.VManager)
        if table_data:
            if not data:
                data = table_data
            else:
                for key, entry in table_data.items():
                    if key not in data:
                        data[key] = entry
                        continue
                    current = data.get(key)
                    if (
                        current
                        and len(current) > 1
                        and str(current[1]).strip() in ("", "None")
                        and len(entry) > 1
                        and str(entry[1]).strip() not in ("", "None")
                    ):
                        data[key] = entry
        return data

    def SaveAsPDF(self):
        """Save Table as pdf
        The drawings are saved by default
        """
        if self.player is None:
            return

        timestamp = _seconds_to_time(self.player.currentInfo)

        # Clean frame (no drawings) + annotated frame (drawings burned in).
        # Force a paint so grab() sees the current overlays/drawings.
        vw = self.player.videoWidget
        try:
            vw.UpdateSurface()
            vw.repaint()
        except Exception as exc:
            log.debug("PDF frame refresh before capture failed: %s", exc)

        frame_clean = vw.currentFrame()
        if frame_clean is not None and not frame_clean.isNull():
            frame_clean = frame_clean.copy()
        else:
            frame_clean = None

        video_rect = vw.surface.videoRect()
        if video_rect is None or video_rect.isEmpty():
            video_rect = vw.rect()
        overlay = vw.grab(video_rect).toImage()
        if overlay is not None and not overlay.isNull():
            overlay = overlay.copy()
        else:
            overlay = None

        if frame_clean is not None and overlay is not None:
            frame_annotated = BurnDrawingsImage(frame_clean, overlay)
        elif overlay is not None:
            frame_annotated = overlay
        else:
            frame_annotated = frame_clean

        if frame_annotated is not None and not frame_annotated.isNull():
            log.info(
                "PDF frames captured: clean=%sx%s annotated=%sx%s",
                frame_clean.width() if frame_clean is not None else 0,
                frame_clean.height() if frame_clean is not None else 0,
                frame_annotated.width(),
                frame_annotated.height(),
            )
        else:
            log.warning("PDF report: no video frame available to embed")

        data = self._report_metadata()
        rows = self.VManager.rowCount()
        columns = self.VManager.columnCount()
        fileName = self.player.fileName

        out, _ = askForFiles(
            self._dialog_parent(),
            QCoreApplication.translate("QgsFmvMetadata", "Save PDF"),
            isSave=True,
            exts="pdf",
        )
        if not out:
            return

        try:
            self.CreatePDF(
                None,
                out=out,
                timestamp=timestamp,
                data=data,
                frame=frame_annotated,
                frame_clean=frame_clean,
                rows=rows,
                columns=columns,
                fileName=fileName,
                VManager=self.VManager,
            )
            self.finishedTask(None, {"task": "Save PDF Report Task"})
        except Exception as exc:
            log.error("Save PDF failed: %s", exc, exc_info=True)
            self.finishedTask(exc, {"task": "Save PDF Report Task"})
        return

    def CreatePDF(
        self,
        task,
        out,
        timestamp,
        data,
        frame,
        rows,
        columns,
        fileName,
        VManager,
        frame_clean=None,
    ):
        """Create a professional multi-section FMV analysis PDF report."""
        generator = ReportGenerator(player=self.player)
        return generator.generate(
            task=task,
            out=out,
            timestamp=timestamp,
            data=data,
            frame=frame,
            rows=rows,
            columns=columns,
            fileName=fileName,
            VManager=VManager,
            frame_clean=frame_clean,
        )

    def SaveACSV(self):
        """Save Table as CSV"""
        if self.player is None:
            return

        data = self.player.GetPacketData()
        out, _ = askForFiles(
            self._dialog_parent(),
            QCoreApplication.translate("QgsFmvMetadata", "Save CSV"),
            isSave=True,
            exts="csv",
        )
        if not out:
            return

        # Snapshot Qt/player state on the main thread — CreateCSV runs in a worker.
        headers = []
        for column in range(self.VManager.columnCount()):
            headers.append(
                self.VManager.model().headerData(column, Qt.Orientation.Horizontal)
            )
        video_name = ""
        timestamp = ""
        if self.player is not None:
            video_name = (
                os.path.basename(self.player.fileName) if self.player.fileName else ""
            )
            timestamp = _seconds_to_time(self.player.currentInfo)

        self._add_background_task(
            QgsTask.fromFunction(
                "Save CSV Report Task",
                self.CreateCSV,
                out=out,
                data=data,
                headers=headers,
                video_name=video_name,
                timestamp=timestamp,
                on_finished=self.finishedTask,
                flags=QgsTask.Flag.CanCancel,
            )
        )
        return

    def CreateCSV(self, task, out, data, headers=None, video_name="", timestamp=""):
        """Create CSV QgsTask — grouped metadata with BOM for Excel."""
        try:
            from datetime import datetime

            # Build grouped data
            groups = _group_metadata_fields(data)
            if headers is None:
                headers = ["Key", "Name", "Value"]

            with open(out, "w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.writer(stream, delimiter=";", quoting=csv.QUOTE_MINIMAL)

                # Header block
                writer.writerow(["FMV Metadata Report"])
                writer.writerow(["Video", video_name])
                writer.writerow(["Timestamp", timestamp])
                writer.writerow(
                    ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                )
                writer.writerow([])
                writer.writerow(headers)

                # Grouped rows
                for group_name, keys in groups:
                    writer.writerow([])
                    writer.writerow([f"--- {group_name} ---"])
                    for key in keys:
                        entry = data.get(key, ["", ""])
                        label = entry[0] if len(entry) > 0 else ""
                        value = entry[1] if len(entry) > 1 else ""
                        writer.writerow([key, label, value])

            if task.isCanceled():
                return None
            return {"task": task.description()}
        except Exception as exc:
            return {"task": task.description(), "error": str(exc)}

    def closeEvent(self, _):
        """Close Dock Event"""
        self.hide()
