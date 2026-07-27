# -*- coding: utf-8 -*-
"""Storyboard — silent georeferenced frame captures at bookmarks / alerts."""

from __future__ import annotations

import os

from qgis.core import QgsTask

from QGISFMV.utils.core.QgsFmvUtils import (
    BurnDrawingsImage,
    GetGeotransform_affine,
    getVideoFolder,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class StoryboardController:
    """Auto-capture georeferenced frames into ``<video>/storyboard/``."""

    def __init__(self, player):
        self.player = player
        self._enabled = False
        self._paths = []  # captured geotiff paths this session

    def setEnabled(self, value):
        self._enabled = bool(value)
        return self._enabled

    def isEnabled(self):
        return self._enabled

    def paths(self):
        return list(self._paths)

    def clearSession(self):
        self._paths.clear()

    def onAlert(self, message=""):
        """Slot: capture a storyboard frame when an alert fires."""
        if not self._enabled:
            return None
        label = "alert"
        if message:
            label = "sentinel" if "SENTINEL" in message else "alert"
        return self.capture(tag=label)

    def onBookmark(self):
        """Capture after a manual bookmark (optional hook)."""
        if not self._enabled:
            return None
        return self.capture(tag="bookmark")

    def capture(self, tag="frame"):
        """Silently write a georeferenced GeoTIFF under the video storyboard folder."""
        player = self.player
        try:
            vw = getattr(player, "videoWidget", None)
            if vw is None or player.fileName is None:
                return None
            frame = vw.currentFrame()
            if frame is None or frame.isNull():
                return None
            image = BurnDrawingsImage(
                frame,
                vw.grab(vw.surface.videoRect()).toImage(),
            )
            geotransform = GetGeotransform_affine()
            if geotransform is None:
                qgsu.showUserAndLogMessage(
                    "",
                    "Storyboard: no geotransform yet — play until georeferenced.",
                    onlyLog=True,
                )
                return None
            folder = os.path.join(getVideoFolder(player.fileName), "storyboard")
            os.makedirs(folder, exist_ok=True)
            position = str(int(player.player.position()))
            export = player.exportController
            task = QgsTask.fromFunction(
                "Storyboard Capture",
                export.SaveGeoCapture,
                image=image,
                output=folder,
                p=f"{tag}_{position}",
                geotransform=geotransform,
                on_finished=self._on_finished,
                flags=QgsTask.Flag.CanCancel,
            )
            player._add_background_task(task)
            return folder
        except Exception as exc:
            log.debug("storyboard capture failed: %s", exc)
            return None

    def _on_finished(self, error, result=None):
        if error is not None or not result:
            return
        path = result.get("file")
        if path:
            self._paths.append(path)
            qgsu.showUserAndLogMessage(
                "",
                f"Storyboard saved: {os.path.basename(path)}",
                onlyLog=True,
            )
