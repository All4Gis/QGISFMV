# -*- coding: utf-8 -*-
"""Shutdown/teardown orchestration: session cleanup, task cancellation, dock removal."""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsApplication

from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class CloseController:
    """Confirm shutdown, tear down playback/telemetry, and remove map layers."""

    def __init__(self, player):
        self._player = player

    @staticmethod
    def _safe_call(fn, label=""):
        """Call *fn* catching and logging any exception — idempotent cleanup helper."""
        try:
            fn()
        except Exception as e:
            log.debug("%s failed: %s", label, e)

    def _isAppClosing(self):
        """True while QGIS/Qt is quitting (skip confirm dialogs)."""
        app = QgsApplication.instance()
        return app is not None and app.closingDown()

    def _cancelBackgroundTasks(self):
        """Cancel pending QgsTasks so finished callbacks do not run after teardown."""
        player = self._player
        for task in list(getattr(player, "_background_tasks", [])):
            if task is None:
                continue
            try:
                task.cancel()
            except Exception as e:
                log.debug("closeEvent: task.cancel failed: %s", e)
        player._background_tasks = []

    def _clearVideoSession(self, video_path=None):
        """Stop playback and clear map layers/drawings for one video."""
        player = self._player
        player._creatingMosaic = False
        player.mosaic.reset()
        player._syncMosaicUi(False)
        player.filterManager.resetState()
        player._closeBCDialog()
        player.recordController.StopRecordAnimation()
        player.autoSnapshot.stop()
        player.timeline.clearEvents()

        try:
            player.playbackController.fakeStop()
        except Exception as e:
            log.debug("prepareSwitchVideo: fakeStop failed: %s", e)

        player.RemoveAllData(video_path)
        player.filterManager.restoreFilters()
        player.filterManager.resetState()

        player.metadataPipeline.resetStreamState()
        player.data = None
        player._lastMetadataPacket = None
        player.PrecisionTimeStamp = ""
        player.clearMetadata()

    def requestClose(self, force=False):
        """Confirm shutdown, stop playback, and remove map layers."""
        player = self._player
        if player.closing:
            return True

        if not force and not self._isAppClosing():
            buttonReply = qgsu.CustomMessage(
                "QGIS FMV",
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "If you close or reopen the video all the information will be erased.",
                ),
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Do you want to close or reopen it?"
                ),
                icon="Information",
            )
            if buttonReply == QMessageBox.StandardButton.No:
                return False

        self._performCloseCleanup()
        return True

    def _performCloseCleanup(self):
        """Tear down playback, telemetry workers, and map layers."""
        player = self._player
        if player.closing:
            return

        player._saveToolBarState()
        player.closing = True
        self._clearVideoSession(player.fileName)

        # Session telemetry was already reset by RemoveAllData/ResetData above,
        # while self.session was still the active session; release it now.
        player.session.deactivate()

        player.playbackController._disconnectPlaybackSignals()
        self._cancelBackgroundTasks()

        # Stop UI timers before tearing down decode/filter threads.
        self._safe_call(player.recordController.stop, "recordController stop")
        self._safe_call(player.autoSnapshot.stop, "autoSnapshot stop")

        def _stop_video_widget_timers():
            vw = getattr(player, "videoWidget", None)
            if vw is not None:
                for timer_name in (
                    "_track_timer",
                    "_display_refresh_timer",
                    "_toolHintTimer",
                ):
                    timer = getattr(vw, timer_name, None)
                    if timer is not None:
                        timer.stop()

        self._safe_call(_stop_video_widget_timers, "videoWidget timer stop")

        player.metadataPipeline.shutdown()

        self._safe_call(player.player.shutdown, "player shutdown")
        self._safe_call(player.videoWidget.surface.dispose, "surface.dispose")

        # Manager owns readers for reopen; dispose only when QGIS/plugin is exiting.
        reader = player.metaReader
        player.metaReader = None
        parent_shutting_down = bool(getattr(player.parent, "_shutting_down", False))
        if reader is not None and (self._isAppClosing() or parent_shutting_down):
            self._safe_call(reader.dispose, "metaReader.dispose")

        self._safe_call(player.stop, "stop")

        if player.parent is not None:
            self._safe_call(
                player.parent.ToggleActiveFromTitle, "ToggleActiveFromTitle"
            )

        def _cleanup_metadata_dock():
            player.metadataDlg.hide()
            player.iface.removeDockWidget(player.metadataDlg)

        self._safe_call(_cleanup_metadata_dock, "metadataDlg cleanup")

        def _close_matplot():
            m = getattr(player, "matplot", None)
            if m is not None:
                m.close()

        self._safe_call(_close_matplot, "matplot.close")

        def _hide_video_info():
            dlg = getattr(player, "VideoInfoDialog", None)
            if dlg is not None:
                dlg.hide()

        self._safe_call(_hide_video_info, "VideoInfoDialog.hide")

        player.filterManager.restoreFilters()

        try:
            if player.iface is not None:
                player.iface.removeDockWidget(player)
        except Exception as e:
            log.debug("closeEvent: removeDockWidget failed: %s", e)
        if player.parent is not None:
            player.parent._PlayerDlg = None
            player.parent._PlayerDock = None
