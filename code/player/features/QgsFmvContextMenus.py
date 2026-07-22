# -*- coding: utf-8 -*-
"""Right-click context menus for the video surface and menu bar, plus toolbar toggling."""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QMenu, QToolBar

from QGISFMV.utils.ui.QgsFmvResources import (
    ICON_CAPTURE_FRAMES,
    ICON_METADATA,
    ICON_MOSAIC,
    ICON_OPTIONS,
    ICON_SCREENSHOT,
    ICON_TRACKING,
    ICON_VOLUME,
)


class ContextMenuController:
    """Build the video/menu-bar context menus and toggle toolbar visibility."""

    def __init__(self, player):
        self._player = player

    def contextMenuBarRequested(self, point):
        """Context Menu Bar for toggle visibility of Menu Bar"""
        player = self._player
        menu = QMenu("ToolBars")
        toolbars = player.findChildren(QToolBar)
        for toolbar in toolbars:
            action = menu.addAction(toolbar.windowTitle())
            action.setCheckable(True)
            action.setChecked(toolbar.isVisible())
            action.setObjectName(toolbar.windowTitle())
            action.triggered.connect(lambda _: self.ToggleQToolBar())
        menu.exec(player.mapToGlobal(point))

    def ToggleQToolBar(self):
        """Toggle ToolBar"""
        player = self._player
        toolbars = player.findChildren(QToolBar)
        sender = player.sender()
        for toolbar in toolbars:
            if sender.objectName() == toolbar.windowTitle():
                toolbar.toggleViewAction().trigger()
        player._saveToolBarState()

    def contextMenuRequested(self, point):
        """Context Menu Video"""
        player = self._player
        menu = QMenu("Video")

        actionMute = menu.addAction(
            QIcon(ICON_VOLUME),
            QCoreApplication.translate("QgsFmvPlayer", "Mute/Unmute"),
        )
        actionMute.triggered.connect(player.setMuted)

        menu.addSeparator()

        actionAllFrames = menu.addAction(
            QIcon(ICON_CAPTURE_FRAMES),
            QCoreApplication.translate("QgsFmvPlayer", "Extract All Frames"),
        )

        actionAllFrames.triggered.connect(player.ExtractAllFrames)

        actionCurrentFrames = menu.addAction(
            QIcon(ICON_SCREENSHOT),
            QCoreApplication.translate("QgsFmvPlayer", "Extract Current Frame"),
        )
        actionCurrentFrames.triggered.connect(player.ExtractCurrentFrame)

        menu.addSeparator()
        actionShowMetadata = menu.addAction(
            QIcon(ICON_METADATA),
            QCoreApplication.translate("QgsFmvPlayer", "Show Metadata"),
        )
        actionShowMetadata.triggered.connect(player.OpenQgsFmvMetadata)

        menu.addSeparator()
        actionClearTrack = menu.addAction(
            QIcon(ICON_TRACKING),
            QCoreApplication.translate("QgsFmvPlayer", "Clear Object Track"),
        )
        actionClearTrack.triggered.connect(player.clearObjectTrack)
        actionExportTrack = menu.addAction(
            QIcon(ICON_TRACKING),
            QCoreApplication.translate("QgsFmvPlayer", "Export Object Track…"),
        )
        actionExportTrack.triggered.connect(player.exportObjectTrack)
        actionExportMosaic = menu.addAction(
            QIcon(ICON_MOSAIC),
            QCoreApplication.translate("QgsFmvPlayer", "Export Mosaic…"),
        )
        actionExportMosaic.triggered.connect(player.exportMosaic)

        menu.addSeparator()
        actionSettings = menu.addAction(
            QIcon(ICON_OPTIONS),
            QCoreApplication.translate("QgsFmvPlayer", "FMV Settings"),
        )
        actionSettings.triggered.connect(player.openFmvSettings)

        # ToolBars submenu — show/hide toolbars
        menu.addSeparator()
        toolbarsMenu = menu.addMenu(
            QCoreApplication.translate("QgsFmvPlayer", "ToolBars")
        )
        for toolbar in player.findChildren(QToolBar):
            action = toolbarsMenu.addAction(toolbar.windowTitle())
            action.setCheckable(True)
            action.setChecked(toolbar.isVisible())
            action.setObjectName(toolbar.windowTitle())
            action.triggered.connect(lambda _: self.ToggleQToolBar())

        menu.exec(player.videoWidget.mapToGlobal(point))
