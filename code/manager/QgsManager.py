# -*- coding: utf-8 -*-
import ast
import os
import platform
from QGISFMV.utils.settings.QgsFmvSettings import get, load
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import (
    pyqtSlot,
    QCoreApplication,
    QEvent,
    QPoint,
    QSettings,
    Qt,
)

settings = QSettings()
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QTableWidgetItem,
    QMenu,
)
import qgis.utils

from qgis.PyQt.QtGui import QColor, QAction

from QGISFMV.utils.logging import log

from QGISFMV.player.drawing.QgsFmvDrawToolBar import DrawToolBar as draw
from QGISFMV.gui.ui_FmvManager import Ui_ManagerWindow
from QGISFMV.utils.core.QgsFmvUtils import (
    askForFiles,
    RemoveVideoToSettings,
    RemoveVideoFolder,
    getVideoManagerList,
    getNameSpace,
    qmouse_pos,
)
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.ui.QgsFmvResources import ICON_DELETE
from qgis.core import (
    QgsApplication,
    Qgis as QGis,
)
from QGISFMV.utils.media.QgsFmvMultimedia import createPlaylist
from QGISFMV.utils.media.QgsFmvStreamUtils import isStreamUri

from QGISFMV.manager.QgsFmvManagerBgLoad import ManagerBgLoadController
from QGISFMV.manager.QgsFmvManagerPlaylistController import ManagerPlaylistController
from QGISFMV.manager.QgsFmvManagerRows import ManagerRowStore

load()

_DEFAULT_EXTS = ["ts", "mpeg4", "mp4", "avi", "mpg", "H264", "mov", "mpeg"]


def _parse_extensions():
    """Parse [FILES] exts from settings.ini, falling back to defaults."""
    try:
        return ast.literal_eval(get("FILES", "exts"))
    except (SyntaxError, ValueError):
        from QGISFMV.utils.logging import log
        log.warning("Failed to parse [FILES] exts, using defaults")
        return _DEFAULT_EXTS


class FmvManager(QDockWidget, Ui_ManagerWindow):
    """Video Manager"""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        if platform.system() == "Darwin":
            self.menubarwidget.setNativeMenuBar(False)

        self.parent = parent
        self.iface = iface
        self._PlayerDlg = None
        self._PlayerDock = None
        self._row_data = {}
        self.loading = False
        self._shutting_down = False
        self._bg_worker = None
        self._bg_thread = None
        # Keep strong refs to unparented QThreads until they finish — replacing
        # self._bg_thread while a load is running would destroy a live QThread
        # and abort Qt (seen when restoring multiple videos from settings).
        self._bg_jobs = []

        # Focused controllers — this class stays the thin QDockWidget façade;
        # UI Designer slot names below are preserved and mostly delegate.
        self.bgLoad = ManagerBgLoadController(self)
        self.playlistController = ManagerPlaylistController(self)
        self.rows = ManagerRowStore(self)

        self.playlist = createPlaylist()
        self.VManager.viewport().installEventFilter(self)

        # Context Menu
        self.VManager.customContextMenuRequested.connect(self.__context_menu)
        self.removeAct = QAction(
            QIcon(ICON_DELETE),
            QCoreApplication.translate("ManagerDock", "Remove from list"),
            self,
        )
        self.removeAct.triggered.connect(self.remove)

        # Per-column widths are not expressible in .ui for QTableWidget.
        self.VManager.setColumnWidth(1, 250)
        self.VManager.setColumnWidth(2, 140)
        self.VManager.setColumnWidth(3, 600)
        self.VManager.setColumnWidth(4, 600)
        self.VManager.setColumnWidth(5, 130)
        self.VManager.hideColumn(0)

        draw.setValues()
        self.setAcceptDrops(True)

        # Load previously saved videos
        self.loadVideosFromSettings()

    def _normalize_row_id(self, row_id):
        """Coerce *row_id* to int, returning the original value on failure."""
        return self.rows.normalize_row_id(row_id)

    def _row_id_at(self, row_index):
        """Return the integer row ID stored in column 0 at *row_index*."""
        return self.rows.row_id_at(row_index)

    def _row_entry(self, row_index, create=False):
        """Return the metadata dict for the row, optionally creating it."""
        return self.rows.row_entry(row_index, create=create)

    def _is_playable(self, row_index):
        """True when the row at *row_index* has been verified as playable."""
        return self.rows.is_playable(row_index)

    def applyRuntimeSettings(self):
        """Refresh manager fields that mirror settings.ini after a save."""
        if self._PlayerDlg is not None:
            try:
                self._PlayerDlg.applyRuntimeSettings()
            except Exception as exc:
                from QGISFMV.utils.logging import log
                log.debug("applyRuntimeSettings failed: %s", exc)

    def loadVideosFromSettings(self):
        """Load persisted video list, skipping files that no longer exist.

        Queue rows and start them one-by-one so we never spawn parallel
        unparented QThreads that overwrite each other's Python refs.
        """
        VideoList = getVideoManagerList()
        self._pending_settings_loads = []
        for load_id in VideoList:
            filename = settings.value(getNameSpace() + "/Manager_List/" + load_id)
            if not filename:
                continue
            # Skip videos that no longer exist on disk
            if not filename.startswith(("udp://", "rtp://", "rtsp://", "tcp://")):
                if not os.path.isfile(filename):
                    RemoveVideoToSettings(load_id)
                    continue
            _, name = os.path.split(filename)
            self._pending_settings_loads.append((name, filename, load_id))
        self._start_next_settings_load()

    def _start_next_settings_load(self):
        """Start the next queued settings video when the previous load finished."""
        pending = getattr(self, "_pending_settings_loads", None)
        if not pending:
            return
        if self.loading or self._shutting_down:
            return
        name, filename, load_id = pending.pop(0)
        self.AddFileRowToManager(name, filename, load_id)

    def eventFilter(self, source, event):
        """Event Filter"""
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and source is self.VManager.viewport()
            and self.VManager.itemAt(qmouse_pos(event)) is None
        ):
            self.VManager.clearSelection()
        return QDockWidget.eventFilter(self, source, event)

    @pyqtSlot(QPoint)
    def __context_menu(self, position):
        """Context Menu Manager Rows"""
        if self.VManager.itemAt(position) is None:
            return
        menu = QMenu()
        menu.addAction(self.removeAct)
        menu.exec(self.VManager.mapToGlobal(position))

    def remove(self):
        """Remove current row"""
        if self.loading:
            return

        # close video player (safer because it changes playlist internals)
        if self._PlayerDlg is not None:
            self._PlayerDlg.close()
        for cr in self.VManager.selectedItems():
            idx = 0
            # we browse cells but we need lines, so ignore already deleted rows
            try:
                idx = cr.row()
            except Exception as _exc:
                log.debug("Failed to get row index from table item: %s", _exc)
                continue

            row_id = int(self.VManager.item(idx, 0).text())
            row_text = self.VManager.item(idx, 1).text()

            self.VManager.removeRow(idx)

            row_data = self._row_data.pop(row_id, None)
            if row_data and row_data.get("metaReader") is not None:
                row_data["metaReader"].dispose()

            # Remove video to Settings List
            RemoveVideoToSettings(str(row_id))
            # Remove folder if is local
            RemoveVideoFolder(row_text)

            # remove from playlist
            self.playlist.removeMedia(idx)

    def closeFMV(self):
        """Close FMV"""
        self.close()

    def openMuiltiplexorDialog(self):
        """Open multiplexor dialog (legacy name kept for UI slots)."""
        self.openMultiplexorDialog()

    def openMultiplexorDialog(self):
        """Open Multiplexor Dialog"""
        from QGISFMV.manager.QgsMultiplexor import Multiplexor

        self.Muiltiplexor = Multiplexor(
            self.iface, parent=self, Exts=_parse_extensions()
        )
        self.Muiltiplexor.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
        )
        self.Muiltiplexor.exec()

    def openStreamDialog(self):
        """Open live stream dialog (UDP/TCP/RTP/RTSP)."""
        if self.loading:
            return
        from QGISFMV.manager.QgsFmvOpenStream import OpenStream

        dlg = OpenStream(self.iface, parent=self)
        dlg.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        dlg.exec()

    def AddFileRowToManager(self, name, filename, load_id=None):
        """Add file Video to new Row"""
        self.loading = True
        from QGISFMV.utils.constants import MAX_VIDEOS_IN_MANAGER
        if self.VManager.rowCount() > MAX_VIDEOS_IN_MANAGER:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "ManagerDock",
                    "You must delete some video from the list before adding a new one",
                ),
                level=QGis.MessageLevel.Warning,
            )
            self.loading = False
            self._start_next_settings_load()
            return

        if "://" in filename and not isStreamUri(filename):
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "ManagerDock", "Unsupported stream URL scheme."
                ),
                level=QGis.MessageLevel.Warning,
            )
            self.loading = False
            self._start_next_settings_load()
            return

        is_stream = isStreamUri(filename)
        from QGISFMV.utils.ui.QgsFmvTableProgress import create_table_progress_widget

        w = create_table_progress_widget(self)
        pbar = w.pbar
        rowPosition = self.VManager.rowCount()

        # Geometry / max height come from ui_FmvTableProgress.ui
        pbar.setValue(0)

        if load_id is None:
            row_id = 0
            if rowPosition != 0:
                row_id = int(self.VManager.item(rowPosition - 1, 0).text()) + 1
        else:
            row_id = self._normalize_row_id(load_id)

        self._row_data[row_id] = {
            "playable": False,
            "initialPt": [],
            "metaReader": None,
        }

        self.VManager.insertRow(rowPosition)

        self.VManager.setItem(rowPosition, 0, QTableWidgetItem(str(row_id)))

        self.VManager.setItem(rowPosition, 1, QTableWidgetItem(name))
        self.VManager.setItem(
            rowPosition,
            2,
            QTableWidgetItem(QCoreApplication.translate("ManagerDock", "Loading")),
        )
        self.VManager.setItem(rowPosition, 3, QTableWidgetItem(filename))
        self.VManager.setItem(rowPosition, 4, QTableWidgetItem("-"))
        self.VManager.setCellWidget(rowPosition, 5, w)

        self.VManager.setVisible(False)
        self.VManager.horizontalHeader().setStretchLastSection(True)
        self.VManager.setVisible(True)

        if not is_stream and not os.path.exists(filename):
            self.ToggleActiveRow(rowPosition, value="Missing source file")
            for j in range(self.VManager.columnCount()):
                try:
                    self.VManager.item(rowPosition, j).setFlags(
                        Qt.ItemFlag.NoItemFlags | Qt.ItemFlag.ItemIsEnabled
                    )
                    self.VManager.item(rowPosition, j).setBackground(
                        QColor(211, 211, 211)
                    )
                except Exception as _exc:
                    log.debug("Styling missing-file row cell (%s): %s", j, _exc)
                    self.VManager.cellWidget(rowPosition, j).setStyleSheet(
                        "background-color:rgb(211,211,211);"
                    )
            self.loading = False
            self._start_next_settings_load()
            return

        pbar.setValue(30)

        self.VManager.setItem(
            rowPosition,
            2,
            QTableWidgetItem(
                QCoreApplication.translate(
                    "ManagerDock",
                    "Connecting stream" if is_stream else "Indexing telemetry",
                )
            ),
        )
        pbar.setValue(40)
        self.bgLoad.start(is_stream, filename, rowPosition, row_id, pbar)

    def openVideoFileDialog(self):
        """Open video file dialog"""
        if self.loading:
            return

        Exts = _parse_extensions()

        filename, _ = askForFiles(
            self, QCoreApplication.translate("ManagerDock", "Open video"), exts=Exts
        )

        if filename:
            if not self.isFileInPlaylist(filename):
                _, name = os.path.split(filename)
                self.AddFileRowToManager(name, filename)
            else:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "ManagerDock", "File is already loaded in playlist: " + filename
                    )
                )

    def isFileInPlaylist(self, filename):
        """Return True if *filename* is already in the media playlist."""
        mcount = self.playlist.mediaCount()
        for x in range(mcount):
            if filename in self.playlist.media(x).canonicalUrl().toString():
                return True
        return False

    def PlayVideoFromManager(self, model):
        """Play video from manager dock.
        Manager row double clicked
        """
        self.playlistController.play(model)

    def SetupPlayer(self, row):
        """Play video from manager dock.
        Manager row double clicked
        """
        self.playlistController.setup_player(row)

    def CreatePlayer(self, path, row):
        """Create Player"""
        self.playlistController.create_player(path, row)

    def ToggleActiveFromTitle(self):
        """Toggle Active video status"""
        self.rows.toggle_active_from_title()

    def ToggleActiveRow(self, row, value="Playing"):
        """Toggle Active row manager video status"""
        self.rows.toggle_active_row(row, value=value)

    def _is_app_closing(self):
        """True when the QGIS application is shutting down."""
        app = QgsApplication.instance()
        return app is not None and app.closingDown()

    def _dispose_all_meta_readers(self):
        """Dispose every cached KLV reader (idempotent)."""
        for row_id, row_data in list(self._row_data.items()):
            reader = (row_data or {}).get("metaReader")
            if reader is None:
                continue
            try:
                reader.dispose()
            except Exception as exc:
                from QGISFMV.utils.logging import log
                log.debug("dispose metaReader row %s failed: %s", row_id, exc)
            row_data["metaReader"] = None
        self._row_data.clear()

    def _clear_plugin_manager_ref(self):
        """Remove the plugin's back-reference to this manager instance."""
        try:
            plugin = qgis.utils.plugins.get(getNameSpace())
            if plugin is not None and getattr(plugin, "_FMVManager", None) is self:
                plugin._FMVManager = None
        except Exception as exc:
            from QGISFMV.utils.logging import log
            log.debug("clear plugin manager ref failed: %s", exc)

    def shutdown(self):
        """Force-close player, stop workers, and dispose KLV/ffmpeg readers."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self.bgLoad.stop()
        player = self._PlayerDlg
        self._PlayerDlg = None
        self._PlayerDock = None
        if player is not None:
            try:
                player.forceClose()
            except Exception as exc:
                from QGISFMV.utils.logging import log
                log.debug("shutdown player.forceClose failed: %s", exc)
            try:
                self.iface.removeDockWidget(player)
            except Exception as exc:
                log.debug("removeDockWidget failed during shutdown: %s", exc)
        self._dispose_all_meta_readers()
        self._clear_plugin_manager_ref()

    def closeEvent(self, event):
        """Close Manager Event"""
        if self._shutting_down or self._is_app_closing():
            self.shutdown()
            event.accept()
            return

        # Interactive close: keep the confirm dialog when a player is open.
        if self._PlayerDlg is not None:
            if not self._PlayerDlg.requestClose():
                event.ignore()
                return
            self._PlayerDlg = None
            self._PlayerDock = None

        self._shutting_down = True
        self.bgLoad.stop()
        self._dispose_all_meta_readers()
        self._clear_plugin_manager_ref()
        event.accept()

    def dragEnterEvent(self, e):
        """Accept drag events containing video file URLs."""
        if not e.mimeData().hasUrls():
            e.setDropAction(Qt.DropAction.IgnoreAction)
            e.accept()
            return

        exts = _parse_extensions()
        for url in e.mimeData().urls():
            fname = url.fileName().lower()
            if not any(fname.endswith(ext) for ext in exts):
                e.setDropAction(Qt.DropAction.IgnoreAction)
                e.accept()
                return

        e.acceptProposedAction()

    def dropEvent(self, e):
        """Handle file drops — add dropped video files to the manager."""
        for url in e.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if not self.isFileInPlaylist(path):
                    self.AddFileRowToManager(url.fileName(), path)
            else:
                uri = url.toString()
                if not self.isFileInPlaylist(uri):
                    self.AddFileRowToManager(url.fileName(), uri)
