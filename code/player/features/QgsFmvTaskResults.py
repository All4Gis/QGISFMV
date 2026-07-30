# -*- coding: utf-8 -*-
"""Common QgsTask on_finished handling shared by every player background task."""

import os.path

from qgis.core import Qgis as QGis
from qgis.core import QgsProject, QgsRasterLayer
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox

from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsPlot import ShowPlot
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


def classify_task_result(result):
    """Pure classifier for task result dicts (unit-testable, no Qt).

    Returns a dict with boolean/string flags describing how the UI should react.
    Unknown or empty results return ``{"kind": "empty"}``.
    """
    if not isinstance(result, dict):
        return {"kind": "empty"}
    if not result:
        return {"kind": "empty"}
    if result.get("error"):
        return {
            "kind": "error",
            "error": result["error"],
            "stop_record_animation": bool(result.get("stop_record_animation")),
        }
    task_name = result.get("task", "") or ""
    kind = "success"
    if "Georeferencing" in task_name:
        kind = "georeferencing"
    elif "Bitrate" in task_name:
        kind = "bitrate"
    elif task_name == "Show Video Info Task":
        kind = "video_info"
    elif task_name == "Save Current Georeferenced Frame Task":
        kind = "save_georef_frame"
    return {
        "kind": kind,
        "task": task_name,
        "stop_record_animation": bool(result.get("stop_record_animation")),
        "has_json": bool(result.get("json")),
        "file": result.get("file"),
    }


class TaskResultsController:
    """Interpret QgsTask results/errors and route them to the right UI update."""

    def __init__(self, player):
        self._player = player

    def finishedTask(self, e, result=None):
        """Common finish task function"""
        player = self._player
        if getattr(player, "closing", False):
            return
        if e is None:
            if result is None:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "QgsFmvPlayer",
                        "Completed with no exception and no result "
                        "(probably manually canceled by the user)",
                    ),
                    level=QGis.MessageLevel.Warning,
                )
                return

            info = classify_task_result(result)
            if info.get("stop_record_animation"):
                player.recordController.StopRecordAnimation()
            if info["kind"] == "error":
                qgsu.showUserAndLogMessage(
                    info["error"], level=QGis.MessageLevel.Warning
                )
                return
            if info["kind"] == "georeferencing":
                return
            if info["kind"] == "empty":
                return

            task_name = info.get("task", "")
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Successfully " + task_name + "!"
                )
            )
            if info["kind"] == "bitrate":
                try:
                    player.matplot = ShowPlot(
                        player.BitratePlot.bitrate_data,
                        player.BitratePlot.frame_count,
                        player.fileName,
                        player.BitratePlot.output,
                    )
                except ImportError:
                    qgsu.showUserAndLogMessage(
                        QCoreApplication.translate(
                            "QgsFmvPlayer",
                            "Install matplotlib and numpy to show bitrate plots.",
                        ),
                        level=QGis.MessageLevel.Warning,
                    )
            elif info["kind"] == "video_info":
                if info.get("has_json"):
                    player.exportController.showVideoInfoDialog(result.get("json"))
                else:
                    qgsu.showUserAndLogMessage(
                        QCoreApplication.translate(
                            "QgsFmvPlayer", "Could not read video information."
                        ),
                        level=QGis.MessageLevel.Warning,
                    )
            elif info["kind"] == "save_georef_frame":
                buttonReply = qgsu.CustomMessage(
                    QCoreApplication.translate("QgsFmvPlayer", "Information"),
                    QCoreApplication.translate(
                        "QgsFmvPlayer", "Do you want to load the layer?"
                    ),
                    icon="Information",
                )
                if buttonReply == QMessageBox.StandardButton.Yes:
                    _file = result["file"]
                    root, _ = os.path.splitext(_file)
                    layer = QgsRasterLayer(_file, root)
                    QgsProject.instance().addMapLayer(layer)
                return
        else:
            if (result or {}).get("stop_record_animation"):
                player.recordController.StopRecordAnimation()
            task_name = (result or {}).get("task", "task")
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "Failed " + task_name + "!"),
                level=QGis.MessageLevel.Warning,
            )
            log.error("Task failed (%s): %s", task_name, e)
