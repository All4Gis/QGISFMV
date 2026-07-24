# -*- coding: utf-8 -*-
"""Player attach/playback orchestration: create or reuse the FMV player dock
for the video selected in the Manager, and center the map on its start point.
"""
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
    QgsProject,
)

from QGISFMV.utils.media.QgsFmvMultimedia import attachPlaylist
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class ManagerPlaylistController:
    """Create/reuse the FMV player dock and wire it to the selected manager row."""

    def __init__(self, manager):
        self._m = manager

    def play(self, model):
        """Play video from manager dock.
        Manager row double clicked
        """
        manager = self._m
        # Don't enable Play if video doesn't have metadata
        if not manager._is_playable(model.row()):
            return

        row = model.row()
        path = manager.VManager.item(row, 3).text()

        if manager._PlayerDlg is not None:
            current_path = getattr(manager._PlayerDlg, "fileName", None)
            if current_path == path:
                self.setup_player(row)
                if manager._PlayerDock is not None:
                    manager._PlayerDock.show()
                    manager._PlayerDock.raise_()
                return
            if not manager._PlayerDlg.prepareSwitchVideo():
                return
        else:
            self.create_player(path, row)

        self.setup_player(row)
        manager._PlayerDlg.playFile(path)
        if manager._PlayerDock is not None:
            manager._PlayerDock.show()
            manager._PlayerDock.raise_()

    def setup_player(self, row):
        """Play video from manager dock.
        Manager row double clicked
        """
        manager = self._m
        manager.ToggleActiveRow(row)

        manager.playlist.setCurrentIndex(row)

        row_entry = manager._row_entry(row)
        meta_reader = row_entry.get("metaReader")
        if meta_reader is not None:
            manager._PlayerDlg.setMetaReader(meta_reader)
        manager.ToggleActiveFromTitle()
        if manager._PlayerDock is not None:
            manager._PlayerDock.show()
            manager._PlayerDock.raise_()

        # zoom to map zone
        try:
            pt = manager._row_entry(row).get("initialPt") or []
            if len(pt) >= 2 and pt[0] is not None and pt[1] is not None:
                curAuthId = (
                    manager.iface.mapCanvas().mapSettings().destinationCrs().authid()
                )
                map_pos = QgsPointXY(pt[1], pt[0])
                if curAuthId != "EPSG:4326":
                    trgCode = int(curAuthId.split(":")[1])
                    xform = QgsCoordinateTransform(
                        QgsCoordinateReferenceSystem(4326),
                        QgsCoordinateReferenceSystem(trgCode),
                        QgsProject().instance(),
                    )
                    map_pos = xform.transform(map_pos)
                manager.iface.mapCanvas().setCenter(map_pos)
                manager.iface.mapCanvas().zoomScale(50000)
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                "", "Map zoom skipped: " + str(exc), onlyLog=True
            )

    def create_player(self, path, row):
        """Create Player"""
        from QGISFMV.player.QgsFmvPlayer import QgsFmvPlayer

        manager = self._m
        manager._PlayerDlg = QgsFmvPlayer(
            manager.iface,
            path,
            parent=manager,
            metaReader=manager._row_entry(row).get("metaReader"),
        )
        # Player is itself a QDockWidget (same pattern as this Manager).
        manager._PlayerDock = manager._PlayerDlg
        manager.iface.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, manager._PlayerDock
        )
        attachPlaylist(manager._PlayerDlg.player, manager.playlist)
        manager._PlayerDock.show()
        manager._PlayerDock.raise_()
