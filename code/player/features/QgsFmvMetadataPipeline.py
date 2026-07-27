# -*- coding: utf-8 -*-
"""KLV telemetry ingestion pipeline: worker-thread wiring, packet dedup, and layer sync."""

from qgis.PyQt.QtCore import QCoreApplication, QThread, QTimer, Qt
from qgis.PyQt.QtWidgets import QDockWidget, QTableWidgetItem
from qgis.core import Qgis as QGis

from QGISFMV.player.dialogs.QgsFmvMetadata import QgsFmvMetadata
from QGISFMV.utils.core.QgsFmvThreads import stop_qthread
from QGISFMV.utils.core.QgsFmvUtils import UpdateLayers
from QGISFMV.utils.layers.QgsFmvLayers import beginNewTrajectorySegment
from QGISFMV.utils.logging import log
from QGISFMV.utils.media.QgsFmvKlvReader import LocalFileMetaReader, StreamMetaReader
from QGISFMV.utils.media.QgsFmvMetadataWorker import MetadataParseWorker
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class MetadataPipelineController:
    """Owns the KLV parse worker thread and applies parsed packets to layers/UI."""

    def __init__(self, player):
        self.player = player
        self._lastStreamPacket = None
        self._lastStreamSeq = -1
        self._lastAppliedLayerSeq = -1
        self._lastFramePositionSec = None
        self._playbackCycle = 0
        self._sliderPosition = 0

        self._metadataWorker = MetadataParseWorker()
        # Do NOT parent QThreads to the dock widget — Qt qFatal if destroyed while running.
        self._metadataThread = QThread()
        self._metadataWorker.moveToThread(self._metadataThread)
        self._metadataWorker.packetReady.connect(self._onParsedMetadataPacket)
        self._metadataWorker.parseFailed.connect(self._onMetadataParseFailed)
        self._metadataThread.start()

    def clearMetadata(self):
        """Clear the metadata dock table."""
        player = self.player
        try:
            table = player.metadataDlg.VManager
            self._sliderPosition = table.verticalScrollBar().sliderPosition()
            table.setRowCount(0)
        except Exception as exc:
            log.debug("clearMetadata failed: %s", exc)

    def addMetadata(self, packet):
        """Update the metadata table from a parsed KLV packet dict."""
        player = self.player
        table = player.metadataDlg.VManager
        if packet is None:
            self.clearMetadata()
            return

        keys = sorted(packet.keys(), key=str)
        n = len(keys)
        if n == 0:
            self.clearMetadata()
            return

        table.setUpdatesEnabled(False)
        try:
            if table.rowCount() == n:
                for row, key in enumerate(keys):
                    val0 = str(packet[key][0])
                    val1 = str(packet[key][1])
                    item0 = table.item(row, 1)
                    item1 = table.item(row, 2)
                    if item0 is None or item0.text() != val0:
                        table.setItem(row, 1, QTableWidgetItem(val0))
                    if item1 is None or item1.text() != val1:
                        table.setItem(row, 2, QTableWidgetItem(val1))
            else:
                self.clearMetadata()
                for row, key in enumerate(keys):
                    table.insertRow(row)
                    table.setItem(row, 0, QTableWidgetItem(str(key)))
                    table.setItem(row, 1, QTableWidgetItem(str(packet[key][0])))
                    table.setItem(row, 2, QTableWidgetItem(str(packet[key][1])))
                table.setVisible(False)
                table.resizeColumnsToContents()
                table.setVisible(True)
            table.verticalScrollBar().setSliderPosition(self._sliderPosition)
        finally:
            table.setUpdatesEnabled(True)

    def _placeMetadataDockTopLeft(self):
        """Pin the metadata panel to the top of the left dock column."""
        player = self.player
        dock = player.metadataDlg
        area = Qt.DockWidgetArea.LeftDockWidgetArea
        main_window = player.iface.mainWindow()

        if dock.parent() is None:
            player.iface.addDockWidget(area, dock)

        for other in main_window.findChildren(QDockWidget):
            if other is dock:
                continue
            if main_window.dockWidgetArea(other) != area:
                continue
            main_window.splitDockWidget(dock, other, Qt.Orientation.Vertical)
            break

        dock.show()
        dock.raise_()

    def OpenQgsFmvMetadata(self):
        """Open the metadata dock and refresh the table from current packet data."""
        player = self.player
        if player.metadataDlg is None:
            player.metadataDlg = QgsFmvMetadata(player=player)
        self._placeMetadataDockTopLeft()
        self.addMetadata(player.data)

    def shutdown(self):
        """Disconnect and stop the metadata worker thread (idempotent)."""
        worker = self._metadataWorker
        if worker is not None:
            try:
                worker.clearPending()
            except Exception as exc:
                log.debug("Metadata clearPending: %s", exc)
            try:
                worker.packetReady.disconnect(self._onParsedMetadataPacket)
            except Exception as exc:
                log.debug("Metadata packetReady disconnect: %s", exc)
            try:
                worker.parseFailed.disconnect(self._onMetadataParseFailed)
            except Exception as exc:
                log.debug("Metadata parseFailed disconnect: %s", exc)
        thread = self._metadataThread
        self._metadataThread = None
        self._metadataWorker = None
        stop_qthread(thread)

    def resetStreamState(self):
        """Reset stream packet caching state (call on file switch, loop, or close)."""
        self._lastStreamPacket = None
        self._lastStreamSeq = -1
        self._lastAppliedLayerSeq = -1

    def resetFramePosition(self):
        """Reset frame-position/loop tracking (call on playFile)."""
        self._lastFramePositionSec = None
        self._playbackCycle = 0

    def resetAppliedLayerSeq(self):
        """Force the next packet to be applied even if its sequence repeats (seek)."""
        self._lastAppliedLayerSeq = -1

    def resetPlaybackCycleState(self):
        """Reset telemetry dedup and start a new trajectory segment after a loop."""
        player = self.player
        self._playbackCycle += 1
        self.resetStreamState()
        if self._metadataWorker is not None:
            self._metadataWorker.clearPending()
        beginNewTrajectorySegment(player._videoGroupName())

    def syncInitialMetadata(self):
        """Draw platform/footprint for the first telemetry packet on player open."""
        player = self.player
        if player.closing:
            return
        if player.metaReader is None:
            return
        if isinstance(player.metaReader, (LocalFileMetaReader, StreamMetaReader)):
            if not player.metaReader.isReady():
                QTimer.singleShot(200, self.syncInitialMetadata)
                return
        if isinstance(player.metaReader, StreamMetaReader):
            seq, stdout_data = player.metaReader.getLatestSnapshot()
            if stdout_data not in (None, b""):
                self._applyStreamPacket(stdout_data, seq=seq)
            return
        idx, stdout_data = player.metaReader.getSnapshot(0)
        if stdout_data in (None, b""):
            stdout_data = player.metaReader.firstPacket()
            idx = 0
        if stdout_data not in (None, "BUFFERING", "NOT_READY", b""):
            self._applyStreamPacket(stdout_data, seq=idx)

    def _applyStreamPacket(self, stdout_data, seq=None):
        """Queue KLV parsing when the telemetry packet changes."""
        player = self.player
        if player.closing:
            return
        if not stdout_data or stdout_data in ("BUFFERING", "NOT_READY"):
            return
        if seq is not None:
            if seq == self._lastStreamSeq:
                return
            self._lastStreamSeq = seq
        elif stdout_data == self._lastStreamPacket:
            return
        self._lastStreamPacket = stdout_data
        self._metadataWorker.parseRequested.emit(
            stdout_data,
            seq if seq is not None else self._lastStreamSeq,
            self._playbackCycle,
        )

    def syncMetadataForPosition(self, currentInfoSec):
        """Queue telemetry parsing for the video position (seconds from start)."""
        player = self.player
        if player.closing:
            return
        if player.metaReader is None or not player.metaReader.isReady():
            return

        if isinstance(player.metaReader, StreamMetaReader):
            if player.fileName.lower().startswith("udp://"):
                seq, packet = player.metaReader.getLatestSnapshot()
            else:
                seq, packet = player.metaReader.getSnapshot(currentInfoSec)
            if not packet:
                return
            self._applyStreamPacket(packet, seq=seq)
        elif isinstance(player.metaReader, LocalFileMetaReader):
            idx, packet = player.metaReader.getSnapshot(currentInfoSec)
            if not packet:
                return
            self._applyStreamPacket(packet, seq=idx)

    def onFrameDisplayed(self, currentInfoSec):
        """Detect loop restarts and sync telemetry for the current frame position."""
        prev = self._lastFramePositionSec
        if prev is not None and currentInfoSec + 1.0 < prev:
            self.resetPlaybackCycleState()
        self._lastFramePositionSec = currentInfoSec
        self.syncMetadataForPosition(currentInfoSec)

    def _onMetadataParseFailed(self, message):
        qgsu.showUserAndLogMessage(
            "", "Metadata parse failed: " + message, onlyLog=True
        )

    def _onParsedMetadataPacket(self, packet):
        player = self.player
        if player.closing:
            return
        if getattr(packet, "_fmvCycle", -1) != self._playbackCycle:
            return
        seq = getattr(packet, "_fmvSeq", None)
        if seq is not None and self._lastAppliedLayerSeq >= 0:
            if seq == self._lastAppliedLayerSeq:
                return
            if seq < self._lastAppliedLayerSeq:
                self.resetPlaybackCycleState()
        if seq is not None:
            self._lastAppliedLayerSeq = seq
        try:
            self._applyParsedMetadataPacket(packet)
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Metadata layer update failed"
                ),
                str(exc),
                level=QGis.MessageLevel.Warning,
                onlyLog=False,
            )

    def _applyParsedMetadataPacket(self, packet):
        """Update metadata table and map layers from a parsed KLV packet."""
        player = self.player
        if player.closing:
            return False
        data = packet.MetadataList()
        player.data = data
        player._lastMetadataPacket = packet
        if not player.metadataDlg.isHidden():
            self.addMetadata(data)
        res = UpdateLayers(
            packet,
            parent=player,
            mosaic=player.creatingMosaic,
            group=player._videoGroupName(),
        )
        player.videoWidget.refreshCursorRubberBand()
        if not res:
            return False
        for key in sorted(data.keys(), key=str):
            if str(data[key][0]) == "Precision Time Stamp":
                player.PrecisionTimeStamp = str(data[key][1].split(".")[0])

        # Update HUD overlay
        if player.hudOverlay._visible:
            player.hudOverlay.updateFromState(player.session)
            player.hudOverlay.setTimestamp(player.PrecisionTimeStamp)

        if getattr(player.miniMapOverlay, "_visible", False):
            player.miniMapOverlay.update_from_state(player.session)

        # Check alert rules + spatial geofences
        player.alertManager.checkMetadata(data)
        geofence = getattr(player, "geofenceController", None)
        if geofence is not None:
            geofence.checkMetadata(data)

        # Live place label (reverse geocode → HUD)
        place = getattr(player, "placeLabelController", None)
        if place is not None and place.isEnabled():
            try:
                from QGISFMV.geo.QgsFmvSpatial import metadata_lat_lon

                pos = metadata_lat_lon(data, prefer_frame_center=True)
                if pos is not None:
                    place.onFrameCenter(pos[0], pos[1])
            except Exception:
                pass

        # Target pin cue (range / bearing / FOV enter)
        target_pin = getattr(player, "targetPinController", None)
        if target_pin is not None and target_pin.hasPin():
            try:
                target_pin.updateFromMetadata(data)
            except Exception:
                pass

        # Build click-to-seek geo/time index
        map_seek = getattr(player, "mapSeekController", None)
        if map_seek is not None:
            map_seek.recordFromMetadata(
                data, time_sec=getattr(player, "currentInfo", None)
            )

        # Update C2 overlays
        if player.sensorConeOverlay.isVisible:
            player.sensorConeOverlay.update(packet, player._videoGroupName())
        if player.distanceRingsOverlay.isVisible:
            player.distanceRingsOverlay.update(packet, player._videoGroupName())

        return True