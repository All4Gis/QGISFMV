# -*- coding: utf-8 -*-
"""Background media/telemetry probing for the Manager: worker/thread lifecycle
and completion handling that turns a probe result into row state + UI updates.
"""

import os

from qgis.PyQt.QtCore import (
    QCoreApplication,
    QObject,
    QThread,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtWidgets import QTableWidgetItem
from qgis.core import Qgis as QGis

from QGISFMV.utils.logging import log
from QGISFMV.utils.core.QgsFmvUtils import (
    AddVideoToSettings,
    _coordsFromKlvStream,
    getKlvStreamIndex,
)
from QGISFMV.utils.media.QgsFfmpegProbe import is_valid_media, is_valid_stream
from QGISFMV.utils.media.QgsFmvKlvReader import LocalFileMetaReader, StreamMetaReader
from QGISFMV.utils.media.QgsFmvMultimedia import mediaUrlToContent
from QGISFMV.utils.media.QgsFmvStreamUtils import isStreamUri
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


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
                    if isinstance(firstPacket, (bytes, bytearray)) and firstPacket:
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
                    if isinstance(firstPacket, (bytes, bytearray)) and firstPacket:
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


class ManagerBgLoadController:
    """Owns the background probe worker/thread lifecycle and result handling.

    State (``_bg_jobs``/``_bg_worker``/``_bg_thread``) is kept on the manager
    itself, matching the rest of the manager/player controller split — this
    class only holds the behavior.
    """

    def __init__(self, manager):
        self._m = manager

    def start(self, is_stream, filename, rowPosition, row_id, pbar):
        """Create and start the background worker/thread for one manager row."""
        manager = self._m
        worker = _BgWorker(is_stream, filename, rowPosition, row_id, pbar)
        # Unparented QThread — parenting to the dock crashes Qt on quit if still running.
        thread = QThread()
        worker.moveToThread(thread)
        worker.done.connect(self.on_done)
        worker.done.connect(thread.quit)
        thread.started.connect(worker.run)

        job = {"thread": thread, "worker": worker}

        def _forget_job():
            try:
                manager._bg_jobs.remove(job)
            except ValueError:
                pass

        thread.finished.connect(_forget_job)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        manager._bg_jobs.append(job)
        manager._bg_worker = worker
        manager._bg_thread = thread
        thread.start()

    def stop(self):
        """Stop background telemetry indexing if still running."""
        from QGISFMV.utils.core.QgsFmvThreads import stop_qthread

        manager = self._m
        jobs = list(getattr(manager, "_bg_jobs", []))
        manager._bg_jobs = []
        manager._bg_worker = None
        manager._bg_thread = None
        for job in jobs:
            worker = job.get("worker")
            if worker is not None:
                try:
                    worker.done.disconnect(self.on_done)
                except Exception as exc:
                    log.debug("signal disconnect failed during bg cleanup: %s", exc)
            stop_qthread(job.get("thread"))

    def _onTelemetryReady(self, row_id, rowPosition, metaReader, pbar, media_ok):
        """Store the metadata reader, log diagnostics, and advance the progress bar."""
        manager = self._m
        row_entry = manager._row_data.setdefault(
            row_id,
            {"playable": False, "initialPt": [], "metaReader": None},
        )
        if metaReader is not None:
            row_entry["metaReader"] = metaReader
            load_err = (
                metaReader.loadError()
                if callable(getattr(metaReader, "loadError", None))
                else None
            )
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

    def _onLocationReady(
        self, row_id, rowPosition, r, row_entry, pbar, metaReader, media_ok
    ):
        """Resolve start location, update the table row, and mark playability."""
        manager = self._m
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

        manager.VManager.setItem(rowPosition, 4, QTableWidgetItem(loc_text))

        if not location and not hasTelemetry and not media_ok:
            manager.ToggleActiveRow(rowPosition, value="Video not applicable")
            pbar.setValue(100)
        else:
            pbar.setValue(90)
            row_entry["playable"] = True

        return row_entry

    def _onPlaylistReady(self, row_id, rowPosition, filename, row_entry, pbar):
        """Add the video to the media playlist and persist to settings if playable."""
        manager = self._m
        if isStreamUri(filename):
            url = QUrl(filename)
        else:
            url = QUrl.fromLocalFile(filename)
        manager.playlist.addMedia(mediaUrlToContent(url))

        if row_entry.get("playable"):
            pbar.setValue(100)
            manager.ToggleActiveRow(rowPosition, value="Ready")
            AddVideoToSettings(str(row_id), filename)

    def on_done(self, r):
        """Called on main thread after background video loading finishes."""
        manager = self._m
        metaReader = r.get("metaReader")
        if manager._shutting_down:
            if metaReader is not None:
                try:
                    metaReader.dispose()
                except Exception as exc:
                    log.debug("_on_bg_load_done dispose during shutdown: %s", exc)
            manager.loading = False
            manager._start_next_settings_load()
            return

        rowPosition = r["rowPosition"]
        row_id = manager._normalize_row_id(r["row_id"])
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
                    QCoreApplication.translate(
                        "ManagerDock", "Failed loading FFMPEG ! "
                    )
                )

            row_entry = self._onTelemetryReady(
                row_id, rowPosition, metaReader, pbar, media_ok
            )
            row_entry = self._onLocationReady(
                row_id, rowPosition, r, row_entry, pbar, metaReader, media_ok
            )
            self._onPlaylistReady(row_id, rowPosition, filename, row_entry, pbar)
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("ManagerDock", "Video load failed"),
                str(exc),
                level=QGis.MessageLevel.Warning,
            )
            manager.ToggleActiveRow(rowPosition, value="Video not applicable")
            pbar.setValue(100)
        finally:
            manager.loading = False
            manager._start_next_settings_load()
