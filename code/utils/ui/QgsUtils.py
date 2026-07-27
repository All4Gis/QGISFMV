# -*- coding: utf-8 -*-
"""Small QGIS UI helpers used across FMV (messages, icons, folders, canvas)."""

import os

from qgis.PyQt.QtGui import QPixmap, QIcon
from qgis.PyQt.QtWidgets import QMessageBox
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsFmvResources import (
    ICON_CRITICAL,
    ICON_INFORMATION,
    ICON_PLUGIN,
    ICON_QUESTION,
    ICON_WARNING,
)
from qgis.core import QgsProject, Qgis as QGis
from qgis.utils import iface
from qgis.PyQt.QtCore import QSettings, Qt


class QgsUtils:
    """Static helpers for message boxes, icons, project folders and canvas ops."""

    @staticmethod
    def GetIcon(icon):
        """Get Icon for Custom Informative Message"""
        icons = {
            "Question": ICON_QUESTION,
            "Information": ICON_INFORMATION,
            "Warning": ICON_WARNING,
        }
        path = icons.get(icon, ICON_CRITICAL)
        i = QPixmap(path)
        return i.scaled(
            64,
            64,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    @staticmethod
    def CustomMessage(title, msg, informative="", icon="Critical"):
        """Custom Informative Message"""
        d = QMessageBox()
        d.setTextFormat(Qt.TextFormat.RichText)
        d.setWindowTitle(title)
        d.setWindowIcon(QIcon(QPixmap(ICON_PLUGIN)))
        d.setText(msg)
        d.setInformativeText(informative)
        d.setIconPixmap(QgsUtils.GetIcon(icon))
        d.addButton(QMessageBox.StandardButton.Yes)
        d.addButton(QMessageBox.StandardButton.No)
        d.setDefaultButton(QMessageBox.StandardButton.No)

        d.setMinimumWidth(350)
        d.setMaximumWidth(500)

        ret = d.exec()
        return ret

    @staticmethod
    def selectLayerByName(layerName, group=None):
        """Select a map layer by name, optionally scoped to a layer group."""
        layers = QgsProject.instance().mapLayersByName(layerName)
        if not layers:
            return None
        if group is None:
            return layers[0]

        root = QgsProject.instance().layerTreeRoot()
        video_group = root.findGroup(group)
        if video_group is None:
            return None

        for layer in layers:
            if video_group.findLayer(layer.id()) is not None:
                return layer
        return None

    @staticmethod
    def createFolderByName(path, name):
        """Create Folder by Name"""
        os.makedirs(os.path.join(path, name), exist_ok=True)

    @staticmethod
    def showUserAndLogMessage(
        before, text="", level=QGis.MessageLevel.Info, duration=3, onlyLog=False
    ):
        """Show user & log info/warning/error messages"""
        if not onlyLog:
            iface.messageBar().popWidget()
            iface.messageBar().pushMessage(before, text, level=level, duration=duration)
        if level == QGis.MessageLevel.Info:
            log.info(text)
        elif level == QGis.MessageLevel.Warning:
            log.warning(text)
        elif level == QGis.MessageLevel.Critical:
            log.error(text)
        return

    @staticmethod
    def SetShortcutForPluginFMV(text, value="Alt+F"):
        """Set DEFAULT or find user shortcut"""
        settings = QSettings()
        settings.beginGroup("shortcuts")
        # Find all saved shortcuts:
        keys = [key for key in settings.childKeys() if key == text]
        if not len(keys):
            # Nothing found in settings - fallback to default:
            shortcut = value
            settings.setValue(text, shortcut)
        elif len(keys) == 1:
            # Just one setting found, take that!
            shortcut = settings.value(keys[0])
        return shortcut
