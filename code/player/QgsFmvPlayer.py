# -*- coding: utf-8 -*-
import os.path

from qgis.PyQt.QtCore import QPoint, QCoreApplication, QSettings, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QToolTip,
    QMessageBox,
    QStyle,
    QStyleOptionSlider,
    QDockWidget,
    QDialog,
)
from qgis.core import Qgis as QGis, QgsApplication

from QGISFMV.utils.media.QgsFmvMultimedia import (
    createMediaPlayer,
    setVideoOutput,
    connectStateChanged,
    setVolume,
    getVolume,
    PausedState,
    StoppedState,
)

from QGISFMV.gui.ui_FmvPlayer import Ui_PlayerWindow
from QGISFMV.player.dialogs.QgsFmvSettings import open_fmv_settings

from QGISFMV.utils.media.QgsFmvStreamUtils import isStreamUri, streamDisplayName
from QGISFMV.player.dialogs.QgsFmvMetadata import QgsFmvMetadata
from QGISFMV.player.features.QgsFmvMosaicController import MosaicController
from QGISFMV.player.features.QgsFmvRecordController import RecordController
from QGISFMV.player.features.QgsFmvMetadataPipeline import MetadataPipelineController
from QGISFMV.player.features.QgsFmvMapCenterController import MapCenterController
from QGISFMV.player.features.QgsFmvPlaybackController import PlaybackController
from QGISFMV.player.features.QgsFmvCloseController import CloseController
from QGISFMV.player.features.QgsFmvTaskResults import TaskResultsController
from QGISFMV.player.features.QgsFmvExportController import ExportController
from QGISFMV.player.features.QgsFmvContextMenus import ContextMenuController
from QGISFMV.player.features.QgsFmvDrawToolsController import DrawToolsController
from QGISFMV.utils.layers.QgsFmvLayers import RemoveGroupByName
from QGISFMV.utils.core.QgsFmvUtils import (
    ResetData,
    _seconds_to_time,
    getNameSpace,
)
from QGISFMV.utils.core.QgsFmvVideoSession import VideoSession
from QGISFMV.utils.ui.QgsPlot import CreatePlotsBitrate
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.ui.QgsFmvResources import ICON_PAUSE, ICON_PLAY
from QGISFMV.player.filters.FilterManager import FilterManager

# New features
from QGISFMV.player.overlays.QgsFmvHud import HudOverlay
from QGISFMV.player.features.QgsFmvSnapshots import AutoSnapshot
from QGISFMV.player.features.QgsFmvAlerts import AlertManager
from QGISFMV.player.overlays.QgsFmvSensorCone import SensorConeOverlay
from QGISFMV.player.overlays.QgsFmvDistanceRings import DistanceRingsOverlay

from QGISFMV.utils.vision.QgsObjectTracker import cv2_available, has_object_tracking


class QgsFmvPlayer(QDockWidget, Ui_PlayerWindow):
    """Video player dock (same pattern as FmvManager)."""

    def __init__(self, iface, path, parent=None, metaReader=None):
        """Constructor"""
        super().__init__(parent)
        import platform

        self.setupUi(self)
        self.setObjectName("QgsFmvPlayerDock")
        # PyQt6: set dock features here — pyuic6 emits invalid Qt.DockWidgetClosable.
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        if platform.system() == "Darwin":
            self.menubarwidget.setNativeMenuBar(False)

        self.parent = parent
        self.iface = iface
        # Player owns the per-video telemetry/georeferencing session.
        self.session = VideoSession(self.iface)
        self.session.activate()
        self.fileName = path
        self.metaReader = metaReader
        self._background_tasks = []
        self.videoWidget.setPlayerWindow(self)
        self._creatingMosaic = False
        self.mosaic = MosaicController(self)
        self.currentInfo = 0.0
        self.data = None
        self._lastMetadataPacket = None
        self.staticDraw = False
        self.playbackRateSlow = 0.7
        self.sdv = 0
        self.closing = False
        self._pendingPlayOnLoad = False
        self._loadedMediaPath = None
        self.metadataPipeline = MetadataPipelineController(self)
        self.playbackController = PlaybackController(self)
        self.closeController = CloseController(self)
        self.taskResults = TaskResultsController(self)
        self.exportController = ExportController(self)
        self.drawTools = DrawToolsController(self)

        self._setupDrawToolBar()
        self._setupPlaybackUi()

    def _setupDrawToolBar(self):
        """Configure drawing toolbar defaults (layout lives in ui_FmvPlayer.ui)."""
        self.btn_stop.setEnabled(False)
        self.PrecisionTimeStamp = ""

        self.toolBtn_DPolygon.setDefaultAction(self.actionDraw_Polygon)
        self.toolBtn_DPoint.setDefaultAction(self.actionDraw_Pinpoint)
        self.toolBtn_DLine.setDefaultAction(self.actionDraw_Line)
        self.toolBtn_Measure.setDefaultAction(self.actionMeasureDistance)
        self.toolBtn_Cesure.setDefaultAction(self.actionCensure)

        self.drawTools._setupMilitarySymbolTool()

        if not has_object_tracking():
            self.actionObject_Tracking.setEnabled(False)
            self.actionObject_Tracking.setToolTip(
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Object Tracking is unavailable (numpy is required).",
                )
            )
        elif not cv2_available():
            self.actionObject_Tracking.setToolTip(
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Object Tracking (numpy MOSSE fallback).",
                )
            )

    def _setupPlaybackUi(self):
        """Wire media player, metadata dock, toolbar, and overlays."""
        self.recordController = RecordController(self)
        self.contextMenuController = ContextMenuController(self)
        self.playIcon = QIcon(ICON_PLAY)
        self.pauseIcon = QIcon(ICON_PAUSE)

        self.videoWidget.customContextMenuRequested[QPoint].connect(
            self.contextMenuController.contextMenuRequested
        )

        self.menubarwidget.customContextMenuRequested[QPoint].connect(
            self.contextMenuController.contextMenuBarRequested
        )

        self.duration = 0
        self.playerMuted = False
        self.hasFileAudio = False

        self.player, self.audioOutput = createMediaPlayer(None)

        setVideoOutput(self.player, self.videoWidget)  # Surface / sink
        self.player.durationChanged.connect(self.playbackController.durationChanged)
        self.player.positionChanged.connect(self.playbackController.positionChanged)
        self.player.frameDisplayed.connect(self.onFrameDisplayed)
        if hasattr(self.player, "playbackLooped"):
            self.player.playbackLooped.connect(
                self.metadataPipeline.resetPlaybackCycleState
            )
        self.player.mediaStatusChanged.connect(self.playbackController.statusChanged)
        self.player.playbackRateChanged.connect(self.playbackController.rateChanged)

        connectStateChanged(self.player, self.playbackController.setCurrentState)

        self.playerState = StoppedState

        self.sliderDuration.setRange(0, int(self.player.duration() / 1000))

        try:
            self.sliderDuration.sliderMoved.disconnect(self.seek)
        except (TypeError, RuntimeError):
            pass
        self.sliderDuration.sliderMoved.connect(self.showMoveTip)
        self.sliderDuration.sliderReleased.connect(
            self.playbackController.sliderDurationReleased
        )

        self.volumeSlider.setValue(getVolume(self.player, self.audioOutput))
        self.volumeSlider.enterEvent = self.showVolumeTip
        self.playbackController._configureOpenCvAudioUi()

        self.metadataDlg = QgsFmvMetadata(player=self)
        self.metadataDlg.hide()

        self.BitratePlot = CreatePlotsBitrate()

        self.mapCenter = MapCenterController(self)
        self.mapCenter.setup()

        # disable context menu
        self.menubarwidget.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        # Inner QMainWindow hosts the Draw toolbar so it stays movable/floatable.
        self.DrawToolBar.setFloatable(True)
        self.DrawToolBar.setMovable(True)
        self.DrawToolBar.setAllowedAreas(
            Qt.ToolBarArea.TopToolBarArea
            | Qt.ToolBarArea.BottomToolBarArea
            | Qt.ToolBarArea.LeftToolBarArea
            | Qt.ToolBarArea.RightToolBarArea
        )
        self._restoreToolBarState()

        self._initOverlayFeatures()

    def _initOverlayFeatures(self):
        """Initialize HUD, MiniMap, Timeline, Snapshots, Alerts, Sync, and C2 overlays."""
        self.hudOverlay = HudOverlay(self.videoWidget)
        self.videoWidget._hudRef = self.hudOverlay

        from QGISFMV.player.overlays.QgsFmvMiniMap import MiniMapOverlay

        self.miniMapOverlay = MiniMapOverlay(self.videoWidget, self.iface)
        self.miniMapOverlay.hide()
        self.videoWidget._miniMapRef = self.miniMapOverlay

        # TimelineWidget is declared in ui_FmvPlayer.ui (self.timeline).
        self.timeline.seekRequested.connect(self._onTimelineSeek)

        self.autoSnapshot = AutoSnapshot(self)
        self.alertManager = AlertManager(self)

        # C2 / Geo-Intelligence overlays
        self.sensorConeOverlay = SensorConeOverlay()
        self.distanceRingsOverlay = DistanceRingsOverlay()

        self.filterManager = FilterManager(self)

    def setMetaReader(self, metaReader):
        """Set the KLV metadata reader for this video."""
        self.metaReader = metaReader
        self.metadataPipeline.resetStreamState()

    def applyRuntimeSettings(self):
        """Pick up settings.ini changes while the player stays open."""
        from QGISFMV.utils.settings.QgsFmvSettings import reloadRuntime

        reloadRuntime()
        from QGISFMV.utils.core.QgsFmvUtils import _ensureFfmpegPaths

        _ensureFfmpegPaths()
        self.mosaic.apply_runtime_settings()

    @property
    def creatingMosaic(self):
        """Preferred spelling for createingMosaic."""
        return self._creatingMosaic

    @creatingMosaic.setter
    def creatingMosaic(self, value):
        """Enable or disable mosaic creation mode."""
        self._creatingMosaic = value

    def _dialog_parent(self):
        """Parent widget for file/message dialogs."""
        return self.iface.mainWindow() if self.iface is not None else self

    def _probe_media_path(self):
        """Return the current media path if ffprobe can use it."""
        path = self.fileName
        if not path:
            return None
        if isStreamUri(path):
            return path
        if os.path.isfile(path):
            return path
        return None

    def _add_background_task(self, task):
        """Keep a reference so QgsTask on_finished callbacks still fire."""
        self._background_tasks.append(task)
        QgsApplication.taskManager().addTask(task)
        return task

    def centerMapPlatform(self, checked):
        """Center map on Platform (Qt Designer slot - delegates to MapCenterController)."""
        self.mapCenter.centerMapPlatform(checked)

    def centerMapFootprint(self, checked):
        """Center Map on Footprint (Qt Designer slot - delegates to MapCenterController)."""
        self.mapCenter.centerMapFootprint(checked)

    def centerMapTarget(self, checked):
        """Center Map on Target (Qt Designer slot - delegates to MapCenterController)."""
        self.mapCenter.centerMapTarget(checked)

    def MouseLocationCoordinates(self, idx):
        """Set Cursor Video Coordinates , WGS84/MGRS
        @type idx: int
        @param idx: QComboBox index
        """
        if idx == 1:
            self.videoWidget.SetMGRS(True)
        else:
            self.videoWidget.SetMGRS(False)

    def onFrameDisplayed(self, positionMs):
        """Refresh telemetry (map, table, layers) on each decoded video frame."""
        if self.closing:
            return
        current = positionMs / 1000.0
        self.currentInfo = current

        if isStreamUri(self.fileName):
            tStr = _seconds_to_time(self.currentInfo) + " / LIVE"
        elif self.currentInfo or self.duration:
            tStr = (
                _seconds_to_time(self.currentInfo)
                + " / "
                + _seconds_to_time(self.duration)
            )
        else:
            tStr = ""

        self.labelDuration.setText(tStr)
        if self.PrecisionTimeStamp != "":
            self.lb_prec_ts.setText(self.PrecisionTimeStamp)
        if not self.sliderDuration.isSliderDown():
            self.sliderDuration.setValue(int(self.currentInfo))
        self.videoWidget.mouseMoveEvent(None, True)

        # Update timeline position
        self.timeline.setPosition(self.currentInfo)

        self.metadataPipeline.onFrameDisplayed(self.currentInfo)

    def GetPacketData(self):
        """Return Current Packet data"""
        return self.data

    def addMetadata(self, packet):
        """Update metadata table (delegates to MetadataPipelineController)."""
        self.metadataPipeline.addMetadata(packet)

    def clearMetadata(self):
        """Clear Metadata List (delegates to MetadataPipelineController)."""
        self.metadataPipeline.clearMetadata()

    def saveInfoToJson(self):
        """Save video Info to json (Qt Designer slot - delegates to ExportController)."""
        self.exportController.saveInfoToJson()

    def showVideoInfo(self, checked=False):
        """Show default probe info (Qt Designer slot - delegates to ExportController)."""
        self.exportController.showVideoInfo(checked)

    def createMosaic(self, value):
        """Toggle live Video Mosaic creation."""
        self.mosaic.set_enabled(value)
        self._syncMosaicUi(value)

    def _syncMosaicUi(self, checked):
        """Keep toolbar button and menu action in sync without re-entrancy."""
        for widget_name in ("actionCreate_Mosaic", "btn_GeoReferencing"):
            widget = getattr(self, widget_name, None)
            if widget is None or not hasattr(widget, "setChecked"):
                continue
            widget.blockSignals(True)
            try:
                widget.setChecked(bool(checked))
            finally:
                widget.blockSignals(False)

    def onMosaicFrameAdded(self, frame_path):
        """Called after each georeferenced frame is written."""
        self.mosaic.on_frame_added(frame_path)

    def exportMosaic(self):
        """Export the current live mosaic GeoTIFF."""
        self.mosaic.export_mosaic(parent=self._dialog_parent())

    def _saveToolBarState(self):
        """Save toolbar geometry and visibility to QSettings."""
        settings = QSettings()
        ns = getNameSpace()
        settings.setValue(f"{ns}/Player/ToolBar/visible", self.DrawToolBar.isVisible())
        settings.setValue(f"{ns}/Player/ToolBar/geometry", self.DrawToolBar.saveGeometry())

    def _restoreToolBarState(self):
        """Restore toolbar geometry and visibility from QSettings."""
        settings = QSettings()
        ns = getNameSpace()
        visible = settings.value(f"{ns}/Player/ToolBar/visible", True, type=bool)
        geometry = settings.value(f"{ns}/Player/ToolBar/geometry")
        if geometry:
            self.DrawToolBar.restoreGeometry(geometry)
        self.DrawToolBar.setVisible(visible)

    # --- Filter delegation (compact dispatch) ---
    # All one-liner filter methods that simply forward to self.filterManager.
    # Method names MUST remain callable as instance attributes because they
    # are connected to Qt signals in ui_FmvPlayer.ui.
    _FILTER_DELEGATES = frozenset({
        # Basic image filters
        "grayFilter", "MirrorHorizontalFilter", "edgeFilter",
        "invertColorFilter", "autoContrastFilter", "monoFilter",
        "brightnessContrastFilter",
        # Enhancement filters
        "claheFilter", "sharpenFilter", "sobelFilter", "roadEnhanceFilter",
        # Motion / detection filters
        "motionDetectionFilter", "backgroundSubtractionFilter", "hotspotFilter",
        # Vegetation / spectral index filters
        "falseColorFilter", "exgFilter", "exrFilter", "variFilter",
        "dehazeFilter", "nrviFilter",
        # Segmentation filters
        "buildingDetectionFilter", "roadSegmentationFilter",
        "vehicleSegmentationFilter", "personSegmentationFilter",
        # Fire / smoke / flood filters
        "fireDetectionFilter", "smokeDetectionFilter", "floodDetectionFilter",
        # Brightness / contrast helpers
        "setBrightness", "setContrastLevel",
        # Brightness–contrast dialog lifecycle
        "_onBCDialogClosed", "_closeBCDialog",
    })

    def __getattr__(self, name):
        if name in self._FILTER_DELEGATES:
            # Deferred lookup: self.filterManager may not exist yet during
            # __init__ (setupUi runs before _initOverlayFeatures), but the
            # returned closure won't be called until a signal fires.
            def _delegate(*args, **kwargs):
                # Capture the Qt sender so FilterManager can check/uncheck actions.
                sender = self.sender()
                self._sender = sender
                return getattr(self.filterManager, name)(*args, **kwargs)
            return _delegate
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def magnifier(self, value):
        """Magnifier Glass Utils (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.magnifier(value)

    def stamp(self, value):
        """Stamp Utils (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.stamp(value)

    def pointDrawer(self, value):
        """Draw Point (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.pointDrawer(value)

    def militarySymbolDrawer(self, value):
        """Place military symbols (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.militarySymbolDrawer(value)

    def _refreshMilSymbolPlacedCount(self):
        """Refresh placed-count label (called from video widget)."""
        self.drawTools._refreshMilSymbolPlacedCount()

    def lineDrawer(self, value):
        """Draw Line (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.lineDrawer(value)

    def polygonDrawer(self, value):
        """Draw Polygon (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.polygonDrawer(value)

    def ensurePlaying(self):
        """Start playback and sync transport button state."""
        if self.playerState in (StoppedState, PausedState):
            self.player.play()
            self.btn_play.setIcon(self.pauseIcon)
            self.btn_stop.setEnabled(True)

    def objectTracking(self, value):
        """Object Tracking (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.objectTracking(value)

    def VideoMeasureDistance(self, value):
        """Video Measure Distance (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.VideoMeasureDistance(value)

    def VideoMeasureArea(self, value):
        """Video Measure Area (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.VideoMeasureArea(value)

    def removeLastMeasureDistance(self):
        """Remove last distance measurement point (Qt Designer slot)."""
        self.drawTools.removeLastMeasureDistance()

    def removeAllMeasureDistance(self):
        """Remove all distance measurements (Qt Designer slot)."""
        self.drawTools.removeAllMeasureDistance()

    def removeLastMeasureArea(self):
        """Remove last area measurement point (Qt Designer slot)."""
        self.drawTools.removeLastMeasureArea()

    def removeAllMeasureArea(self):
        """Remove all area measurements (Qt Designer slot)."""
        self.drawTools.removeAllMeasureArea()

    def VideoHandDraw(self, value):
        """Video Free Hand Draw (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.VideoHandDraw(value)

    def CommonPauseTool(self, value):
        """Static draw common function (delegates to DrawToolsController)."""
        self.drawTools.CommonPauseTool(value)

    def VideoCensure(self, value):
        """Censure Video Parts (Qt Designer slot - delegates to DrawToolsController)."""
        self.drawTools.VideoCensure(value)

    def UncheckUtils(self, sender, value):
        """Uncheck Utils Video (delegates to DrawToolsController)."""
        self.drawTools.UncheckUtils(sender, value)

    def UncheckFilters(self, sender, value):
        """Uncheck Filters Video (delegates to DrawToolsController)."""
        self.drawTools.UncheckFilters(sender, value)

    def setMuted(self):
        """Toggle audio mute state."""
        if self.audioOutput is not None:
            self.playerMuted = not self.playerMuted
            self.player.setMuted(self.playerMuted)
        return

    def stop(self):
        """Stop video"""
        # Prevent Error in a Video Utils.Disable Magnifier
        if self.actionMagnifying_glass.isChecked():
            self.actionMagnifying_glass.trigger()

        # Stop Video
        self.playbackController.fakeStop()

        return

    def setVolume(self, volume):
        """Set the audio volume (0-100)."""
        if self.audioOutput is not None:
            setVolume(self.player, self.audioOutput, volume)
            return
        self.playbackController._configureOpenCvAudioUi()

    def EndMedia(self):
        """Button end video position (Qt Designer slot - delegates to PlaybackController)."""
        self.playbackController.EndMedia()

    def StartMedia(self):
        """Button start video position (Qt Designer slot - delegates to PlaybackController)."""
        self.playbackController.StartMedia()

    def forwardMedia(self):
        """Button forward Video (Qt Designer slot - delegates to PlaybackController)."""
        self.playbackController.forwardMedia()

    def rewindMedia(self):
        """Button rewind Video (Qt Designer slot - delegates to PlaybackController)."""
        self.playbackController.rewindMedia()

    def AutoRepeat(self, checked):
        """Button AutoRepeat Video (Qt Designer slot - delegates to PlaybackController)
        @param checked: Button checked state
        """
        self.playbackController.AutoRepeat(checked)

    def showVolumeTip(self, _):
        """Volume Slider Tooltip Trick
        @type _: QEvent
        @param _: Enter Event
        """
        style = self.volumeSlider.style()
        opt = QStyleOptionSlider()
        self.volumeSlider.initStyleOption(opt)
        rectHandle = style.subControlRect(
            QStyle.ComplexControl.CC_Slider,
            opt,
            QStyle.SubControl.SC_SliderHandle,
            self.volumeSlider,
        )
        tip_offset = QPoint(5, 15)
        pos_local = rectHandle.topLeft() + tip_offset
        pos_global = self.volumeSlider.mapToGlobal(pos_local)
        QToolTip.showText(pos_global, str(self.volumeSlider.value()) + " %", self)

    def showMoveTip(self, currentInfo):
        """Player Silder Move Tooptip Trick
        @type currentInfo: String
        @param currentInfo: Current time value
        """
        style = self.sliderDuration.style()
        opt = QStyleOptionSlider()
        self.sliderDuration.initStyleOption(opt)
        rectHandle = style.subControlRect(
            QStyle.ComplexControl.CC_Slider,
            opt,
            QStyle.SubControl.SC_SliderHandle,
            self.sliderDuration,
        )
        tip_offset = QPoint(5, 15)
        pos_local = rectHandle.topLeft() + tip_offset
        pos_global = self.sliderDuration.mapToGlobal(pos_local)

        tStr = _seconds_to_time(currentInfo)

        QToolTip.showText(pos_global, tStr, self)

    def playFile(self, videoPath):
        """Play file from path (external entrypoint - delegates to PlaybackController)."""
        self.playbackController.playFile(videoPath)

    def RecordVideo(self, value):
        """Cut Video (Qt Designer slot - delegates to RecordController)
        @type value: bool
        @param value: Button checked state
        """
        self.recordController.RecordVideo(value)

    def toggleGroup(self, state):
        """Toggle GroupBox
        @type state: bool
        @param state: Expand/collapse QGroupBox
        """
        sender = self.sender()
        if state:
            sender.setFixedHeight(sender.sizeHint().height())
        else:
            sender.setFixedHeight(15)

    def RemoveMeasures(self):
        """Remove video measurements (delegates to DrawToolsController)."""
        self.drawTools.RemoveMeasures()

    def playClicked(self, _):
        """Stop and Play video (Qt Designer slot - delegates to PlaybackController)."""
        self.playbackController.playClicked(_)

    def seek(self, seconds):
        """Slider Move (Qt Designer slot - delegates to PlaybackController)
        @type seconds:  String
        """
        self.playbackController.seek(seconds)

    def convertVideo(self):
        """Convert Video To Other Format (Qt Designer slot - delegates to ExportController)."""
        self.exportController.convertVideo()

    def CreateBitratePlot(self, checked=False):
        """Create video Plot Bitrate Thread (Qt Designer slot - delegates to ExportController)."""
        self.exportController.CreateBitratePlot(checked)

    def ExtractAllFrames(self):
        """Extract All Video Frames Task (Qt Designer slot - delegates to ExportController)."""
        self.exportController.ExtractAllFrames()

    def ExtractCurrentFrame(self):
        """Extract Current Frame Task (Qt Designer slot - delegates to ExportController)."""
        self.exportController.ExtractCurrentFrame()

    def ExtractCurrentGeoFrame(self):
        """Extract Current GeoReferenced Frame Task (Qt Designer slot - delegates to ExportController)."""
        self.exportController.ExtractCurrentGeoFrame()

    def OpenQgsFmvMetadata(self):
        """Open Metadata Dock (Qt Designer slot - delegates to MetadataPipelineController)."""
        self.metadataPipeline.OpenQgsFmvMetadata()

    def openFmvSettings(self):
        """Open unified FMV settings dialog."""
        if (
            open_fmv_settings(self._dialog_parent(), player=self)
            == QDialog.DialogCode.Accepted
        ):
            self.applyRuntimeSettings()

    def _videoGroupName(self, video_path=None):
        path = video_path if video_path is not None else self.fileName
        if not path:
            return None
        return (
            streamDisplayName(path) if isStreamUri(path) else os.path.basename(path)
        )

    def prepareSwitchVideo(self):
        """Confirm and reset the current session when switching manager videos."""
        if self.closing:
            return True

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

        self._resetSessionForSwitch()
        return True

    def _resetSessionForSwitch(self):
        """Reset the current session when switching manager videos."""
        previous_path = self.fileName
        self.closeController._clearVideoSession(previous_path)
        self._loadedMediaPath = None
        self._pendingPlayOnLoad = False
        self.closing = False

    def RemoveAllData(self, video_path=None):
        """Remove All TOC/Canvas Data"""
        groupName = self._videoGroupName(video_path)
        # Overlays remove their own layers; do this before tearing down the group.
        if hasattr(self, "sensorConeOverlay"):
            self.sensorConeOverlay.setVisible(False)
        if hasattr(self, "distanceRingsOverlay"):
            self.distanceRingsOverlay.setVisible(False)
        if groupName:
            RemoveGroupByName(groupName)
        # Reset internal variables / per-group feature caches
        ResetData(groupName)
        # Remove Canvas RubberBands
        self.videoWidget.RemoveCanvasRubberbands()
        # Remove Video objects
        self.videoWidget.RemoveVideoDrawings()

    def forceClose(self):
        """Close without confirmation (plugin unload / QGIS quit)."""
        self.requestClose(force=True)
        try:
            self.hide()
        except Exception as e:
            log.debug("forceClose: hide failed: %s", e)

    def requestClose(self, force=False):
        """Confirm shutdown, stop playback, and remove map layers
        (external entrypoint - delegates to CloseController).
        """
        return self.closeController.requestClose(force=force)

    # --- Feature 1: Export KML/GPX ---
    def exportToKML(self):
        """Export the current video layers to KML (Qt Designer slot - delegates to ExportController)."""
        self.exportController.exportToKML()

    def exportToGPX(self):
        """Export the current video layers to GPX (Qt Designer slot - delegates to ExportController)."""
        self.exportController.exportToGPX()

    def exportObjectTrack(self):
        """Export the object track layer to KML (delegates to ExportController)."""
        self.exportController.exportObjectTrack()

    def clearObjectTrack(self):
        """Clear the object track rubber band and persistent layer."""
        if hasattr(self.videoWidget, "clearObjectTrack"):
            self.videoWidget.clearObjectTrack()

    # --- Feature 2: HUD Overlay ---
    def toggleHUD(self):
        """Toggle the HUD overlay on/off."""
        on = self.hudOverlay.toggle()
        if on:
            try:
                from QGISFMV.utils.core.QgsFmvUtils import gv
                self.hudOverlay.updateFromState(gv)
            except Exception as exc:
                log.debug("HUD overlay update failed: %s", exc)
            self.hudOverlay.setTimestamp(self.PrecisionTimeStamp)

    def toggleMiniMap(self, checked):
        """Toggle the mini-map overlay on/off."""
        if checked != self.miniMapOverlay._visible:
            self.miniMapOverlay.toggle()
        if checked:
            self.miniMapOverlay.set_group(self._videoGroupName())
            from QGISFMV.utils.core.QgsFmvUtils import gv
            self.miniMapOverlay.update_from_state(gv)
        return checked

    # --- C2 / Geo-Intelligence overlays ---
    def _toggleSensorCone(self, checked):
        """Toggle the sensor coverage cone overlay on the map."""
        self.sensorConeOverlay.setVisible(checked)
        if checked and self._lastMetadataPacket is not None:
            self.sensorConeOverlay.update(
                self._lastMetadataPacket, self._videoGroupName()
            )

    def _toggleDistanceRings(self, checked):
        """Toggle the distance rings overlay on the map."""
        self.distanceRingsOverlay.setVisible(checked)
        if checked and self._lastMetadataPacket is not None:
            self.distanceRingsOverlay.update(
                self._lastMetadataPacket, self._videoGroupName()
            )

    # --- Feature 3: Timeline ---
    def _onTimelineSeek(self, seconds):
        ms = int(seconds * 1000)
        self.player.setPosition(ms)

    # --- Feature 5: Auto Snapshots ---
    def toggleAutoSnapshots(self):
        """Toggle automatic frame snapshots on/off."""
        return self.autoSnapshot.toggle()

    # --- Feature 6: Alerts ---
    def toggleAlerts(self):
        """Toggle alert monitoring on/off."""
        return self.alertManager.toggle()

    def addAlertRule(self):
        """Open the dialog to add a new alert rule."""
        self.alertManager.addRuleDialog()

    def clearAlerts(self):
        """Remove all alert rules after user confirmation."""
        count = len(self.alertManager.rules())
        if count == 0:
            qgsu.showUserAndLogMessage(
                "", "No alert rules to clear.",
                level=QGis.MessageLevel.Warning,
            )
            return
        reply = qgsu.CustomMessage(
            "QGIS FMV",
            QCoreApplication.translate(
                "QgsFmvPlayer",
                f"Delete all {count} alert rule(s)?",
            ),
            "",
            icon="Warning",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.alertManager.clearRules()
            self.actionToggle_Alerts.setChecked(False)

    def closeEvent(self, event):
        """Close Event"""
        if self.requestClose():
            event.accept()
        else:
            event.ignore()
