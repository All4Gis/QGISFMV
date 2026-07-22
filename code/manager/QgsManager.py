# -*- coding: utf-8 -*-
import ast
import os
import platform
from QGISFMV.utils.settings.QgsFmvSettings import get, load
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import (
    QUrl,
    pyqtSlot,
    QCoreApplication,
    QEvent,
    QPoint,
    QSettings,
    Qt,
    QThread,
    pyqtSignal,
    QObject,
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
from QGISFMV.utils.media.QgsFfmpegProbe import is_valid_media, is_valid_stream
from QGISFMV.gui.ui_FmvManager import Ui_ManagerWindow
from QGISFMV.utils.core.QgsFmvUtils import (
    askForFiles,
    AddVideoToSettings,
    RemoveVideoToSettings,
    RemoveVideoFolder,
    getVideoManagerList,
    getNameSpace,
    getKlvStreamIndex,
    _coordsFromKlvStream,
    qmouse_pos,
)
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.ui.QgsFmvResources import ICON_DELETE
from qgis.core import (
    QgsApplication,
    QgsPointXY,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsCoordinateTransform,
    Qgis as QGis,
)
from QGISFMV.utils.media.QgsFmvMultimedia import (
    createPlaylist,
    attachPlaylist,
    mediaUrlToContent,
)
from QGISFMV.utils.media.QgsFmvKlvReader import LocalFileMetaReader, StreamMetaReader
from QGISFMV.utils.media.QgsFmvStreamUtils import isStreamUri

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


class _BgWorker(QObject):
    """Background worker that probes media and KLV telemetry off the main thread."""

    done = pyqtSignal(object)

    def __init__(self, is_stream, filename, rowPosition, row_id, pbar, parent=None):
        super().__init__(parent)
        self._is_stream = is_stream
        self._filename = filename
        self._rowPosition = rowPosition
        self._row_id = row_id
        self._pbar = pbar

    def run(self):
        media_ok = False
        klvIdx = 0
        coords = []
        location = []
        metaReader = None
        error = ""
        try:
            if self._is_stream:
                try:
                    metaReader = StreamMetaReader(self._filename)
                except Exception as exc:
                    from QGISFMV.utils.logging import log
                    log.error("StreamMetaReader failed: %s", exc)
                    metaReader = None
                try:
                    media_ok = is_valid_stream(self._filename)
                except Exception as exc:
                    from QGISFMV.utils.logging import log
                    log.error("is_valid_stream failed: %s", exc)
                    media_ok = False
                if metaReader is not None and metaReader.hasTelemetry():
                    firstPacket = metaReader.firstPacket()
                    if (
                        isinstance(firstPacket, (bytes, bytearray))
                        and firstPacket
                    ):
                        coords = _coordsFromKlvStream(firstPacket)
            else:
                media_ok = is_valid_media(self._filename)
                klvIdx = getKlvStreamIndex(self._filename, quiet=True)
                if media_ok or os.path.isfile(self._filename):
                    metaReader = LocalFileMetaReader(
                        self._filename, klvIdx, preload=False
                    )
                if metaReader is not None and metaReader.hasTelemetry():
                    firstPacket = metaReader.firstPacket()
                    if (
                        isinstance(firstPacket, (bytes, bytearray))
                        and firstPacket
                    ):
                        coords = _coordsFromKlvStream(firstPacket)
            if coords:
                from QGISFMV.utils.core.QgsFmvUtils import fetchReverseGeocodeLabel

                lat, lon = coords[0], coords[1]
                loc = fetchReverseGeocodeLabel(lat, lon)
                location = [lat, lon, loc]
        except Exception as exc:
            error = str(exc)
            from QGISFMV.utils.logging import log

            log.error("Background load failed: " + error)
        self.done.emit(
            {
                "rowPosition": self._rowPosition,
                "row_id": self._row_id,
                "filename": self._filename,
                "media_ok": media_ok,
                "is_stream": self._is_stream,
                "klvIdx": klvIdx,
                "coords": coords,
                "location": location,
                "metaReader": metaReader,
                "pbar": self._pbar,
                "error": error,
            }
        )


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
        try:
            return int(row_id)
        except (TypeError, ValueError):
            return row_id

    def _row_id_at(self, row_index):
        """Return the integer row ID stored in column 0 at *row_index*."""
        item = self.VManager.item(row_index, 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None

    def _row_entry(self, row_index, create=False):
        """Return the metadata dict for the row, optionally creating it."""
        row_id = self._row_id_at(row_index)
        if row_id is None:
            return {}
        row_id = self._normalize_row_id(row_id)
        if create:
            return self._row_data.setdefault(
                row_id,
                {"playable": False, "initialPt": [], "metaReader": None},
            )
        entry = self._row_data.get(row_id)
        if entry is None:
            legacy = self._row_data.get(str(row_id))
            if legacy is not None:
                self._row_data[row_id] = legacy
                del self._row_data[str(row_id)]
                entry = legacy
        return entry or {}

    def _is_playable(self, row_index):
        """True when the row at *row_index* has been verified as playable."""
        return bool(self._row_entry(row_index).get("playable"))

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

        worker = _BgWorker(is_stream, filename, rowPosition, row_id, pbar)
        # Unparented QThread — parenting to the dock crashes Qt on quit if still running.
        thread = QThread()
        worker.moveToThread(thread)
        worker.done.connect(self._on_bg_load_done)
        worker.done.connect(thread.quit)
        thread.started.connect(worker.run)

        job = {"thread": thread, "worker": worker}

        def _forget_job():
            try:
                self._bg_jobs.remove(job)
            except ValueError:
                pass

        thread.finished.connect(_forget_job)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

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
        self._bg_jobs.append(job)
        self._bg_worker = worker
        self._bg_thread = thread
        thread.start()

    def _onTelemetryReady(self, row_id, rowPosition, metaReader, pbar, media_ok):
        """Store the metadata reader, log diagnostics, and advance the progress bar."""
        row_entry = self._row_data.setdefault(
            row_id,
            {"playable": False, "initialPt": [], "metaReader": None},
        )
        if metaReader is not None:
            row_entry["metaReader"] = metaReader
            load_err = metaReader.loadError() if callable(getattr(metaReader, "loadError", None)) else None
            if load_err:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate("ManagerDock", "Telemetry index failed"),
                    load_err,
                    level=QGis.MessageLevel.Warning,
                )
            elif isinstance(metaReader, StreamMetaReader):
                qgsu.showUserAndLogMessage(
                    "", "Live telemetry reader started.", onlyLog=True
                )
            elif metaReader.hasTelemetry():
                qgsu.showUserAndLogMessage(
                    "",
                    f"Telemetry cache ready ({metaReader.packetCount()} packets).",
                    onlyLog=True,
                )
            else:
                qgsu.showUserAndLogMessage(
                    "", "No KLV telemetry stream found.", onlyLog=True
                )
        else:
            row_entry["metaReader"] = None
            qgsu.showUserAndLogMessage(
                "", "Telemetry index unavailable for this file.", onlyLog=True
            )
        pbar.setValue(60)
        return row_entry

    def _onLocationReady(self, row_id, rowPosition, r, row_entry, pbar, metaReader, media_ok):
        """Resolve start location, update the table row, and mark playability."""
        location = list(r.get("location") or [])
        if not location:
            coords = r.get("coords") or []
            if coords:
                location = [coords[0], coords[1], "-"]

        row_entry["initialPt"] = location
        hasTelemetry = metaReader is not None and metaReader.hasTelemetry()
        is_stream = bool(r.get("is_stream"))

        # Build display text for the Start Location column.
        if location:
            # Prefer the reverse-geocode label (index 2); fall back to coords.
            label = location[2] if len(location) > 2 and location[2] else "-"
            if label == "-" and len(location) >= 2:
                label = f"{location[0]:.6f}, {location[1]:.6f}"
            loc_text = label
        elif hasTelemetry or media_ok or is_stream:
            loc_text = "-"
        else:
            loc_text = QCoreApplication.translate(
                "ManagerDock", "Start location not available."
            )

        self.VManager.setItem(rowPosition, 4, QTableWidgetItem(loc_text))

        if not location and not hasTelemetry and not media_ok:
            self.ToggleActiveRow(rowPosition, value="Video not applicable")
            pbar.setValue(100)
        else:
            pbar.setValue(90)
            row_entry["playable"] = True

        return row_entry

    def _onPlaylistReady(self, row_id, rowPosition, filename, row_entry, pbar):
        """Add the video to the media playlist and persist to settings if playable."""
        if isStreamUri(filename):
            url = QUrl(filename)
        else:
            url = QUrl.fromLocalFile(filename)
        self.playlist.addMedia(mediaUrlToContent(url))

        if row_entry.get("playable"):
            pbar.setValue(100)
            self.ToggleActiveRow(rowPosition, value="Ready")
            AddVideoToSettings(str(row_id), filename)

    def _on_bg_load_done(self, r):
        """Called on main thread after background video loading finishes."""
        metaReader = r.get("metaReader")
        if self._shutting_down:
            if metaReader is not None:
                try:
                    metaReader.dispose()
                except Exception as exc:
                    from QGISFMV.utils.logging import log
                    log.debug("_on_bg_load_done dispose during shutdown: %s", exc)
            self.loading = False
            self._start_next_settings_load()
            return

        rowPosition = r["rowPosition"]
        row_id = self._normalize_row_id(r["row_id"])
        filename = r["filename"]
        media_ok = r["media_ok"]
        pbar = r["pbar"]
        error = r.get("error") or ""

        try:
            if error:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate("ManagerDock", "Video load failed"),
                    error,
                    level=QGis.MessageLevel.Warning,
                )

            if not media_ok:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate("ManagerDock", "Failed loading FFMPEG ! ")
                )

            row_entry = self._onTelemetryReady(row_id, rowPosition, metaReader, pbar, media_ok)
            row_entry = self._onLocationReady(row_id, rowPosition, r, row_entry, pbar, metaReader, media_ok)
            self._onPlaylistReady(row_id, rowPosition, filename, row_entry, pbar)
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("ManagerDock", "Video load failed"),
                str(exc),
                level=QGis.MessageLevel.Warning,
            )
            self.ToggleActiveRow(rowPosition, value="Video not applicable")
            pbar.setValue(100)
        finally:
            self.loading = False
            self._start_next_settings_load()

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
        # Don't enable Play if video doesn't have metadata
        if not self._is_playable(model.row()):
            return

        row = model.row()
        path = self.VManager.item(row, 3).text()

        if self._PlayerDlg is not None:
            current_path = getattr(self._PlayerDlg, "fileName", None)
            if current_path == path:
                self.SetupPlayer(row)
                if self._PlayerDock is not None:
                    self._PlayerDock.show()
                    self._PlayerDock.raise_()
                return
            if not self._PlayerDlg.prepareSwitchVideo():
                return
        else:
            self.CreatePlayer(path, row)

        self.SetupPlayer(row)
        self._PlayerDlg.playFile(path)
        if self._PlayerDock is not None:
            self._PlayerDock.show()
            self._PlayerDock.raise_()

    def SetupPlayer(self, row):
        """Play video from manager dock.
        Manager row double clicked
        """
        self.ToggleActiveRow(row)

        self.playlist.setCurrentIndex(row)

        row_entry = self._row_entry(row)
        meta_reader = row_entry.get("metaReader")
        if meta_reader is not None:
            self._PlayerDlg.setMetaReader(meta_reader)
        self.ToggleActiveFromTitle()
        if self._PlayerDock is not None:
            self._PlayerDock.show()
            self._PlayerDock.raise_()

        # zoom to map zone
        try:
            pt = self._row_entry(row).get("initialPt") or []
            if len(pt) >= 2 and pt[0] is not None and pt[1] is not None:
                curAuthId = (
                    self.iface.mapCanvas().mapSettings().destinationCrs().authid()
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
                self.iface.mapCanvas().setCenter(map_pos)
                self.iface.mapCanvas().zoomScale(50000)
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                "", "Map zoom skipped: " + str(exc), onlyLog=True
            )

    def CreatePlayer(self, path, row):
        """Create Player"""
        from QGISFMV.player.QgsFmvPlayer import QgsFmvPlayer

        self._PlayerDlg = QgsFmvPlayer(
            self.iface,
            path,
            parent=self,
            metaReader=self._row_entry(row).get("metaReader"),
        )
        # Player is itself a QDockWidget (same pattern as this Manager).
        self._PlayerDock = self._PlayerDlg
        self.iface.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._PlayerDock
        )
        attachPlaylist(self._PlayerDlg.player, self.playlist)
        self._PlayerDock.show()
        self._PlayerDock.raise_()

    def ToggleActiveFromTitle(self):
        """Toggle Active video status"""
        column = 2
        for row in range(self.VManager.rowCount()):
            if self.VManager.item(row, column) is not None:
                v = self.VManager.item(row, column).text()
                if v == "Playing":
                    self.ToggleActiveRow(row, value="Ready")
                    return

    def ToggleActiveRow(self, row, value="Playing"):
        """Toggle Active row manager video status"""
        self.VManager.setItem(
            row, 2, QTableWidgetItem(QCoreApplication.translate("ManagerDock", value))
        )

    def _is_app_closing(self):
        """True when the QGIS application is shutting down."""
        app = QgsApplication.instance()
        return app is not None and app.closingDown()

    def _stop_bg_load(self):
        """Stop background telemetry indexing if still running."""
        from QGISFMV.utils.core.QgsFmvThreads import stop_qthread

        jobs = list(getattr(self, "_bg_jobs", []))
        self._bg_jobs = []
        self._bg_worker = None
        self._bg_thread = None
        for job in jobs:
            worker = job.get("worker")
            if worker is not None:
                try:
                    worker.done.disconnect(self._on_bg_load_done)
                except Exception as exc:
                    log.debug("signal disconnect failed during bg cleanup: %s", exc)
            stop_qthread(job.get("thread"))

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
        self._stop_bg_load()
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
        self._stop_bg_load()
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
