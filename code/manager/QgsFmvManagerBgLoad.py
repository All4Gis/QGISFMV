"""Background media/telemetry probing for the Manager: worker/thread lifecycle
and completion handling that turns a probe result into row state + UI updates.
"""

import os

from qgis.core import Qgis as QGis
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QObject,
    Qt,
    QThread,
    QUrl,
    pyqtSignal,
    pyqtSlot,
)
from qgis.PyQt.QtWidgets import QTableWidgetItem
from QGIS_FMV.utils.core.QgsFmvUtils import (
    AddVideoToSettings,
    _coordsFromKlvStream,
    _pymisb_klv,
    getKlvStreamIndex,
)
from QGIS_FMV.utils.logging import log
from QGIS_FMV.utils.media.QgsFfmpegProbe import is_valid_media, is_valid_stream
from QGIS_FMV.utils.media.QgsFmvKlvReader import LocalFileMetaReader, StreamMetaReader
from QGIS_FMV.utils.media.QgsFmvMultimedia import mediaUrlToContent
from QGIS_FMV.utils.media.QgsFmvStreamUtils import isStreamUri
from QGIS_FMV.utils.ui.QgsUtils import QgsUtils as qgsu


def _format_location(location):
    """Prefer a reverse-geocode label, otherwise decimal coordinates."""
    if not location:
        return ""
    label = location[2] if len(location) > 2 and location[2] else ""
    if label and label != "-":
        return label
    if len(location) >= 2 and location[0] is not None and location[1] is not None:
        try:
            return f"{float(location[0]):.6f}, {float(location[1]):.6f}"
        except (TypeError, ValueError):
            return "-"
    return "-"


def _ffmpeg_binaries_ready():
    """True when both ffmpeg and ffprobe resolve to real files."""
    try:
        from QGIS_FMV.utils.settings.QgsFmvSettings import ffmpeg_binary, ffprobe_binary

        ff = ffmpeg_binary()
        fp = ffprobe_binary()
    except Exception as exc:
        log.debug("ffmpeg binary check failed: %s", exc)
        return False
    return bool(ff and os.path.isfile(ff) and fp and os.path.isfile(fp))


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

    @pyqtSlot()
    def run(self):
        media_ok = False
        klvIdx = 0
        coords = []
        location = []
        metaReader = None
        telemetry_found = False
        error = ""
        try:
            if self._is_stream:
                try:
                    metaReader = StreamMetaReader(self._filename)
                except Exception as exc:
                    from QGIS_FMV.utils.logging import log

                    log.error("StreamMetaReader failed: %s", exc)
                    metaReader = None
                try:
                    media_ok = is_valid_stream(self._filename)
                except Exception as exc:
                    from QGIS_FMV.utils.logging import log

                    log.error("is_valid_stream failed: %s", exc)
                    media_ok = False
                if metaReader is not None and metaReader.hasTelemetry():
                    firstPacket = metaReader.firstPacket()
                    if isinstance(firstPacket, (bytes, bytearray)) and firstPacket:
                        telemetry_found = True
                        coords = _coordsFromKlvStream(firstPacket)
            else:
                # Register ST0601 parsers before any packet parse. Plugin
                # startup leaves this import until the first video open.
                _pymisb_klv()
                media_ok = is_valid_media(self._filename)
                klvIdx = getKlvStreamIndex(self._filename, quiet=True)
                if media_ok or os.path.isfile(self._filename):
                    # Finish the full KLV read before deciding. A short peek
                    # often returns nothing and was reported as "no telemetry".
                    metaReader = LocalFileMetaReader(
                        self._filename, klvIdx, preload=False
                    )
                    if metaReader.hasTelemetry():
                        telemetry_found = True
                        firstPacket = metaReader.firstPacket()
                        if isinstance(firstPacket, (bytes, bytearray)) and firstPacket:
                            coords = _coordsFromKlvStream(firstPacket)
            if coords:
                from QGIS_FMV.utils.core.QgsFmvUtils import fetchReverseGeocodeLabel

                lat, lon = coords[0], coords[1]
                loc = fetchReverseGeocodeLabel(lat, lon)
                location = [lat, lon, loc]
        except Exception as exc:
            error = str(exc)
            from QGIS_FMV.utils.logging import log

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
                "telemetry_found": telemetry_found,
                "pbar": self._pbar,
                "error": error,
            }
        )


class ManagerBgLoadController(QObject):
    """Owns the background probe worker/thread lifecycle and result handling.

    ``on_done`` is a real slot so the table update runs on the GUI thread.
    """

    def __init__(self, manager):
        super().__init__(manager)
        self._m = manager

    def start(self, is_stream, filename, rowPosition, row_id, pbar):
        """Create and start the background worker/thread for one manager row."""
        manager = self._m
        worker = _BgWorker(is_stream, filename, rowPosition, row_id, pbar)
        # Unparented QThread — parenting to the dock crashes Qt on quit if still running.
        thread = QThread()
        worker.moveToThread(thread)
        # Queue both ways: on_done must touch widgets on the GUI thread, and
        # run() must start from the worker event loop so thread.quit() is not
        # a no-op (QThread::started is emitted before exec()).
        worker.done.connect(self.on_done, Qt.ConnectionType.QueuedConnection)
        worker.done.connect(thread.quit)
        thread.started.connect(worker.run, Qt.ConnectionType.QueuedConnection)

        job = {"thread": thread, "worker": worker}

        def _forget_job():
            try:
                manager._bg_jobs.remove(job)
            except ValueError:
                log.debug("forget_job failed: %s", job)

        thread.finished.connect(_forget_job)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        manager._bg_jobs.append(job)
        manager._bg_worker = worker
        manager._bg_thread = thread
        thread.start()

    def stop(self):
        """Stop background telemetry indexing if still running."""
        from QGIS_FMV.utils.core.QgsFmvThreads import stop_qthread

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

    def _onTelemetryReady(
        self, row_id, rowPosition, metaReader, pbar, media_ok, telemetry_found=False
    ):
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
            index_ready = (
                metaReader.isReady()
                if callable(getattr(metaReader, "isReady", None))
                else True
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
            elif not index_ready:
                qgsu.showUserAndLogMessage(
                    "", "Telemetry index running in the background.", onlyLog=True
                )
            elif metaReader.hasTelemetry() or telemetry_found:
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
        if not location:
            existing = list(row_entry.get("initialPt") or [])
            if len(existing) >= 2:
                location = existing

        row_entry["initialPt"] = location
        hasTelemetry = bool(r.get("telemetry_found")) or (
            metaReader is not None and metaReader.hasTelemetry()
        )
        index_pending = (
            metaReader is not None
            and callable(getattr(metaReader, "isReady", None))
            and not metaReader.isReady()
        )
        is_stream = bool(r.get("is_stream"))

        # Build display text for the Start Location column.
        loc_text = _format_location(location)
        if not loc_text:
            if hasTelemetry or media_ok or is_stream or index_pending:
                loc_text = "-"
            else:
                loc_text = QCoreApplication.translate(
                    "ManagerDock", "Start location not available."
                )

        manager.VManager.setItem(rowPosition, 4, QTableWidgetItem(loc_text))

        # The full index may still be running. A short peek often misses KLV,
        # so "no packet yet" is not "no data".
        if (
            not is_stream
            and not location
            and not hasTelemetry
            and not media_ok
            and not index_pending
        ):
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

    @pyqtSlot(object)
    def on_done(self, r):
        """Called on the GUI thread after background video loading finishes."""
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

            reader_pending = (
                metaReader is not None
                and callable(getattr(metaReader, "isReady", None))
                and not metaReader.isReady()
            )
            # Only blame FFmpeg when the binary itself is missing. A probe
            # that returns no streams is a media problem, not a missing tool.
            if (
                not media_ok
                and not reader_pending
                and not r.get("telemetry_found")
                and not (metaReader is not None and metaReader.hasTelemetry())
                and not _ffmpeg_binaries_ready()
            ):
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "ManagerDock", "Failed loading FFMPEG ! "
                    ),
                    level=QGis.MessageLevel.Warning,
                )

            row_entry = self._onTelemetryReady(
                row_id,
                rowPosition,
                metaReader,
                pbar,
                media_ok,
                r.get("telemetry_found"),
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
            # Keep a file that already has a reader or a successful probe.
            # The index callback will correct the status if KLV is absent.
            if r.get("telemetry_found") or media_ok or metaReader is not None:
                row_entry = manager._row_data.setdefault(
                    row_id,
                    {"playable": False, "initialPt": [], "metaReader": metaReader},
                )
                row_entry["playable"] = True
                if metaReader is not None:
                    row_entry["metaReader"] = metaReader
                manager.ToggleActiveRow(rowPosition, value="Ready")
            else:
                manager.ToggleActiveRow(rowPosition, value="Video not applicable")
            if pbar is not None:
                pbar.setValue(100)
        finally:
            manager.loading = False
            manager._start_next_settings_load()
