# -*- coding: utf-8 -*-
"""Record button blink animation and background video-segment recording."""

import os.path
import subprocess

from qgis.PyQt.QtCore import QCoreApplication, QTimer
from qgis.PyQt.QtGui import QIcon, QMovie
from qgis.core import QgsTask

from QGISFMV.utils.core.QgsFmvUtils import (
    _seconds_to_time,
    _spawn,
    askForFiles,
    buildRecordFfmpegArgs,
    recordSaveExtensions,
)
from QGISFMV.utils.ui.QgsFmvResources import ICON_RECORD, RECORD_GIF


class RecordController:
    """Manage the record-button blink animation and ffmpeg segment recording."""

    def __init__(self, player):
        self.player = player
        self.startRecord = "00:00:00"
        self.endRecord = "00:00:00"
        self.RecGIF = QMovie(RECORD_GIF)
        # Parent must be a QObject (player is QDockWidget); the timer follows it.
        self._recordBlinkTimer = QTimer(player)
        self._recordBlinkTimer.setInterval(450)
        self._recordBlinkTimer.timeout.connect(self._updateRecordButtonBlink)
        self._recordBlinkOn = False
        self._recordBtnIdleStyle = (
            "QPushButton, QPushButton:checked, QPushButton:flat, "
            "QPushButton:flat:checked {"
            " background-color: transparent; border: none; padding: 0px; }"
        )
        self._setRecordIdle()

    def stop(self):
        """Stop the blink timer (idempotent teardown helper)."""
        self._recordBlinkTimer.stop()

    def _updateRecordButtonBlink(self):
        """Pulse the record button background while capture is active."""
        if not self._recordBlinkTimer.isActive():
            return
        self._recordBlinkOn = not self._recordBlinkOn
        if self._recordBlinkOn:
            self.player.btn_Rec.setStyleSheet(
                "QPushButton { background-color: rgba(220, 38, 38, 200);"
                " border-radius: 4px; border: 1px solid rgba(255, 80, 80, 220); }"
            )
        else:
            self.player.btn_Rec.setStyleSheet(
                "QPushButton { background-color: rgba(220, 38, 38, 70);"
                " border-radius: 4px; border: 1px solid rgba(220, 38, 38, 120); }"
            )

    def _setRecordIdle(self):
        """Idle record control: static red dot only."""
        self._recordBlinkTimer.stop()
        try:
            self.RecGIF.frameChanged.disconnect(self.ReciconUpdate)
        except (TypeError, RuntimeError):
            pass
        self.RecGIF.stop()
        self._recordBlinkOn = False
        btn = self.player.btn_Rec
        btn.blockSignals(True)
        btn.setChecked(False)
        btn.blockSignals(False)
        btn.setIcon(QIcon(ICON_RECORD))
        btn.setStyleSheet(self._recordBtnIdleStyle)
        btn.update()

    def _setRecordActive(self):
        """Recording: blinking icon and pulsing button chrome."""
        btn = self.player.btn_Rec
        btn.setChecked(True)
        btn.setIcon(QIcon(self.RecGIF.currentPixmap()))
        self.RecGIF.frameChanged.connect(self.ReciconUpdate)
        self.RecGIF.start()
        self._recordBlinkOn = False
        self._updateRecordButtonBlink()
        self._recordBlinkTimer.start()

    def ReciconUpdate(self, _):
        """Record Button Icon Effect"""
        self.player.btn_Rec.setIcon(QIcon(self.RecGIF.currentPixmap()))

    def StopRecordAnimation(self):
        """Stop record blink animation and restore idle icon."""
        self._setRecordIdle()

    def RecordVideo(self, value):
        """Cut Video
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        currentTime = _seconds_to_time(player.currentInfo)

        if value is False:
            self.endRecord = currentTime
            self._setRecordIdle()

            out, _ = askForFiles(
                player._dialog_parent(),
                QCoreApplication.translate("QgsFmvPlayer", "Save video record"),
                isSave=True,
                exts=recordSaveExtensions(player.fileName),
            )

            if not out:
                self.StopRecordAnimation()
                return

            player._add_background_task(
                QgsTask.fromFunction(
                    "Record Video Task",
                    self.RecordVideoTask,
                    infile=player.fileName,
                    startRecord=self.startRecord,
                    endRecord=self.endRecord,
                    out=out,
                    on_finished=player.taskResults.finishedTask,
                    flags=QgsTask.Flag.CanCancel,
                )
            )

        else:
            self.startRecord = currentTime
            self._setRecordActive()
        return

    def RecordVideoTask(self, task, infile, startRecord, endRecord, out):
        """Record a video segment by stream-copying between timestamps."""
        p = _spawn(buildRecordFfmpegArgs(infile, startRecord, endRecord, out))
        try:
            _, stderr_data = p.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            p.kill()
            return {
                "task": task.description(),
                "error": QCoreApplication.translate(
                    "QgsFmvPlayer", "Record timed out after 10 minutes."
                ),
            }
        if task.isCanceled():
            return None

        if p.returncode != 0 or not os.path.exists(out) or os.path.getsize(out) == 0:
            err_msg = (
                stderr_data.decode("utf-8", errors="replace").strip()
                if stderr_data
                else "unknown error"
            )
            return {
                "task": task.description(),
                "error": QCoreApplication.translate("QgsFmvPlayer", "Record failed: ")
                + err_msg,
                "stop_record_animation": True,
            }

        return {"task": task.description(), "stop_record_animation": True}
