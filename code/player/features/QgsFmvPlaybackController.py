# -*- coding: utf-8 -*-
"""Playback transport, media-status handling, and slider/duration synchronization."""

import os.path

from qgis.core import Qgis as QGis
from qgis.core import QgsTask
from qgis.PyQt.QtCore import QCoreApplication, Qt, QTimer, QUrl
from qgis.PyQt.QtWidgets import QApplication

from QGISFMV.utils.core.QgsFmvUtils import _seconds_to_time, hasElevationModel
from QGISFMV.utils.layers.QgsFmvLayers import CreateVideoLayers
from QGISFMV.utils.logging import log
from QGISFMV.utils.media.QgsFmvKlvReader import StreamMetaReader
from QGISFMV.utils.media.QgsFmvMultimedia import (
    BufferingMedia,
    EndOfMedia,
    InvalidMedia,
    LoadedMedia,
    LoadingMedia,
    PausedState,
    PlayingState,
    PlaylistLoop,
    PlaylistSequential,
    StalledMedia,
    StoppedState,
    getPlaylist,
    hasVideo,
)
from QGISFMV.utils.media.QgsFmvStreamUtils import isStreamUri, streamDisplayName
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class PlaybackController:
    """Owns the play/pause/seek transport and QMediaPlayer signal handlers."""

    def __init__(self, player):
        self._player = player

    def _disconnectPlaybackSignals(self):
        """Stop frame/telemetry callbacks once the player is shutting down."""
        player = self._player
        qmp = getattr(player, "player", None)
        if qmp is None:
            return
        for signal_name, slot in (
            ("frameDisplayed", player.onFrameDisplayed),
            ("positionChanged", self.positionChanged),
            ("durationChanged", self.durationChanged),
            ("mediaStatusChanged", self.statusChanged),
            ("playbackRateChanged", self.rateChanged),
        ):
            signal = getattr(qmp, signal_name, None)
            if signal is None:
                continue
            try:
                signal.disconnect(slot)
            except Exception as exc:
                log.debug("Playback signal %s disconnect: %s", signal_name, exc)

    def _configureOpenCvAudioUi(self):
        """Disable in-player audio controls only for the OpenCV backend."""
        player = self._player
        if player.audioOutput is not None:
            player.btn_volume.setEnabled(True)
            player.volumeSlider.setEnabled(True)
            player.btn_volume.setToolTip("")
            player.volumeSlider.setToolTip("")
            return
        tip = QCoreApplication.translate(
            "QgsFmvPlayer",
            "In-player volume is not available with this playback backend. "
            "Use the Audio menu to export or plot audio with FFmpeg.",
        )
        player.btn_volume.setEnabled(False)
        player.btn_volume.setToolTip(tip)
        player.volumeSlider.setEnabled(False)
        player.volumeSlider.setToolTip(tip)

    def setCurrentState(self, state):
        """Set Current State
        @type state: QMediaPlayer::State
        @param state: Current video state (play/pause ...)
        """
        player = self._player
        if state != player.playerState:
            player.playerState = state
            if state == StoppedState:
                player.btn_play.setIcon(player.playIcon)
                player.btn_stop.setEnabled(False)
            elif state == PlayingState:
                player.btn_play.setIcon(player.pauseIcon)
                player.btn_stop.setEnabled(True)
            elif state == PausedState:
                player.btn_play.setIcon(player.playIcon)
                player.btn_stop.setEnabled(True)
                position = player.player.position() / 1000
                self.updateDurationInfo(position, True)

    def rateChanged(self, _qreal):
        """Signals the playbackRate has changed to rate."""
        player = self._player
        player.player.setPosition(player.sdv)

    def handleCursor(self, status):
        """Change cursor
        @type status: QMediaPlayer::MediaStatus
        @param status: Video status
        """
        player = self._player
        if status in (LoadingMedia, BufferingMedia, StalledMedia):
            player.setCursor(Qt.CursorShape.BusyCursor)
        else:
            player.unsetCursor()

    def statusChanged(self, status):
        """Signal Status video change
        @type status: QMediaPlayer::MediaStatus
        @param status: Video status
        """
        player = self._player
        self.handleCursor(status)
        if status in (LoadingMedia, StalledMedia):
            self.videoAvailableChanged(False)
        elif status == InvalidMedia:
            if len(player.player.errorString()) > 0:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "QgsFmvPlayer", "Player error: " + player.player.errorString()
                    ),
                    level=QGis.MessageLevel.Warning,
                )
            qgsu.showUserAndLogMessage("", "invalid media", onlyLog=True)
            self.videoAvailableChanged(False)
            if player.metaReader is not None:
                QTimer.singleShot(300, player.metadataPipeline.syncInitialMetadata)
        elif status == EndOfMedia and player.parent.playlist.nextIndex() == -1:
            player.btn_play.setIcon(player.playIcon)
            player.btn_stop.setEnabled(True)
            self.videoAvailableChanged(True)
        elif status == EndOfMedia:
            player.metadataPipeline.resetPlaybackCycleState()
        elif status == LoadedMedia:
            self.videoAvailableChanged(True)
            player.metadataPipeline.syncInitialMetadata()
            if player._pendingPlayOnLoad:
                player._pendingPlayOnLoad = False
                self.playClicked(True)
        else:
            self.videoAvailableChanged(True)

    def playFile(self, videoPath):
        """Play file from path"""
        player = self._player
        previous_path = player.fileName
        player.fileName = videoPath
        player.closing = False
        player.metadataPipeline.resetStreamState()
        player.metadataPipeline.resetFramePosition()
        # Drop mosaic session before teardown so a finishing task cannot reattach.
        player._creatingMosaic = False
        player.mosaic.reset()
        player._syncMosaicUi(False)
        player.session.activate()
        try:
            # Remove All Data
            player.RemoveAllData(previous_path)
            player.clearMetadata()
            QApplication.processEvents()

            titleName = (
                streamDisplayName(videoPath)
                if isStreamUri(videoPath)
                else os.path.basename(videoPath)
            )
            player.setWindowTitle(
                QCoreApplication.translate("QgsFmvPlayer", "Playing : ") + titleName
            )

            CreateVideoLayers(hasElevationModel(), titleName)
            player.miniMapOverlay.set_group(player._videoGroupName())

            player.hasFileAudio = False
            player.actionAudio.setEnabled(False)
            player.actionSave_Audio.setEnabled(False)
            if not isStreamUri(videoPath):
                player._add_background_task(
                    QgsTask.fromFunction(
                        QCoreApplication.translate("QgsFmvPlayer", "Audio Check Task"),
                        player.exportController.checkAudioTask,
                        videoPath=videoPath,
                        on_finished=player.exportController.audioCheckFinished,
                        flags=QgsTask.Flag.CanCancel,
                    )
                )

            media_url = (
                QUrl(videoPath)
                if isStreamUri(videoPath)
                else QUrl.fromLocalFile(videoPath)
            )
            log.info("Opening video: %s (%s)", videoPath, type(player.player).__name__)
            if player._loadedMediaPath != videoPath:
                player._loadedMediaPath = videoPath
                player._pendingPlayOnLoad = True
                player.player.setSource(media_url)
            else:
                player.metadataPipeline.syncInitialMetadata()
                self.playClicked(True)

        except Exception as e:
            log.error("playFile failed: %s", e)
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "Open Video File : "),
                str(e),
                level=QGis.MessageLevel.Warning,
            )

    def videoAvailableChanged(self, available):
        """Buttons for video available
        @type available: bool
        """
        player = self._player
        player.btn_CaptureFrame.setEnabled(available)
        player.gb_PlayerControls.setEnabled(available)
        return

    def pauseAt(self, pos):
        """Seek to *pos* (ms) and pause playback."""
        player = self._player
        player.player.setPosition(pos)
        player.player.pause()
        player.btn_play.setIcon(player.playIcon)

        player.btn_stop.setEnabled(False)
        player.videoWidget.refreshDisplay()
        player.videoWidget.refreshCursorRubberBand()

    def fakeStop(self):
        """self.player.stop() make a black screen and not reproduce it again"""
        player = self._player
        if player.playerState == PausedState:
            player.player.play()
            player.btn_play.setIcon(player.pauseIcon)

        self.pauseAt(0)

    def playClicked(self, _):
        """Stop and Play video"""
        player = self._player
        if player.playerState in (StoppedState, PausedState):
            player.btn_play.setIcon(player.pauseIcon)
            player.btn_stop.setEnabled(True)

            if player.staticDraw:
                player.RemoveMeasures()

            if isinstance(player.metaReader, StreamMetaReader):
                player.metaReader.markPlaybackStart()
            player.metadataPipeline.resetStreamState()

            # Play Video
            player.player.play()
        elif player.playerState == PlayingState:
            player.btn_play.setIcon(player.playIcon)
            self.pauseAt(player.player.position())

    def seek(self, seconds):
        """
        Slider Move
        @type seconds:  String
        """
        player = self._player
        player.metadataPipeline.resetAppliedLayerSeq()
        player.player.setPosition(int(seconds * 1000))
        player.showMoveTip(seconds)

    def EndMedia(self):
        """Button end video position"""
        player = self._player
        if hasVideo(player.player):
            player.player.setPosition(player.player.duration())
            player.videoWidget.update()
        return

    def StartMedia(self):
        """Button start video position"""
        player = self._player
        if hasVideo(player.player):
            player.player.setPosition(0)
            player.videoWidget.update()
        return

    def forwardMedia(self):
        """Button forward Video"""
        from QGISFMV.utils.constants import SKIP_INTERVAL_MS

        player = self._player
        pos = player.player.position()
        duration = player.player.duration()
        player.player.setPosition(min(pos + SKIP_INTERVAL_MS, duration))

    def rewindMedia(self):
        """Button rewind Video"""
        from QGISFMV.utils.constants import SKIP_INTERVAL_MS

        player = self._player
        player.player.setPosition(max(player.player.position() - SKIP_INTERVAL_MS, 0))

    def AutoRepeat(self, checked):
        """Button AutoRepeat Video
        @param checked: Button checked state
        """
        player = self._player
        pl = getPlaylist(player.player)
        if pl is not None:
            pl.setPlaybackMode(PlaylistLoop if checked else PlaylistSequential)
        return

    def durationChanged(self, duration):
        """Duration video change signal
        @type duration: int
        @param duration: Video duration
        """
        player = self._player
        duration /= 1000
        player.duration = duration
        player.sliderDuration.setMaximum(int(duration))
        player.timeline.setDuration(duration)

    def positionChanged(self, progress):
        """Current Video position change
        @type progress: qint64
        @param progress: Slide video duration current value
        """
        player = self._player
        progress /= 1000

        # Remove measure if slider position change
        if player.staticDraw:
            player.RemoveMeasures()

        if not player.sliderDuration.isSliderDown():
            player.sliderDuration.setValue(int(progress))

        if isStreamUri(player.fileName):
            return

        if not player.closing and not player.sliderDuration.isSliderDown():
            player.currentInfo = progress
            player.metadataPipeline.syncMetadataForPosition(progress)

    def sliderDurationReleased(self):
        """Seek to the slider position when the user releases the duration slider."""
        player = self._player
        value = player.sliderDuration.value()
        player.metadataPipeline.resetStreamState()
        self.seek(value)

    def updateDurationInfo(self, currentInfo, isPrecise=False):
        """Update labels duration Info (legacy callers; metadata uses onFrameDisplayed)."""
        player = self._player
        duration = player.duration
        player.currentInfo = currentInfo

        if isStreamUri(player.fileName):
            tStr = _seconds_to_time(currentInfo) + " / LIVE"
        elif currentInfo or duration:
            tStr = _seconds_to_time(currentInfo) + " / " + _seconds_to_time(duration)
        else:
            tStr = ""

        if player.PrecisionTimeStamp != "":
            player.lb_prec_ts.setText(player.PrecisionTimeStamp)

        player.videoWidget.mouseMoveEvent(None, True)
        player.labelDuration.setText(tStr)
