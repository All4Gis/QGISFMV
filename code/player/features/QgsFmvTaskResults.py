# -*- coding: utf-8 -*-
"""Common QgsTask on_finished handling shared by every player background task."""

import os.path

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import Qgis as QGis, QgsProject, QgsRasterLayer

from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsPlot import ShowPlot
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


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
            elif isinstance(result, dict):
                if result.get("stop_record_animation"):
                    player.recordController.StopRecordAnimation()
                if result.get("error"):
                    qgsu.showUserAndLogMessage(
                        result["error"], level=QGis.MessageLevel.Warning
                    )
                    return
                task_name = result.get("task", "")
                if "Georeferencing" in task_name:
                    return
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "QgsFmvPlayer", "Successfully " + task_name + "!"
                    )
                )
                if "Bitrate" in task_name:
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
                if task_name == "Show Video Info Task":
                    if result.get("json"):
                        player.exportController.showVideoInfoDialog(result.get("json"))
                    else:
                        qgsu.showUserAndLogMessage(
                            QCoreApplication.translate(
                                "QgsFmvPlayer", "Could not read video information."
                            ),
                            level=QGis.MessageLevel.Warning,
                        )
                if task_name == "Save Current Georeferenced Frame Task":
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
