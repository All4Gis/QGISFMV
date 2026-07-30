# -*- coding: utf-8 -*-
"""Simulate FMV tool entry points without launching QGIS GUI.

This is a regression harness: it instantiates controllers with a mock player,
calls public methods, and fails on unexpected exceptions. When a tool needs
Qt/QGIS it is stubbed; pure helpers run for real.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from code.tests.support import (
    CODE,
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


def _install_common_stubs():
    ensure_qgis_fmv_package()
    keys = qgis_stub_keys(
        "qgis.PyQt.QtGui",
        "qgis.PyQt.QtWidgets",
        "qgis.core",
        "qgis.utils",
        "QGISFMV.utils.ui.QgsUtils",
        "QGISFMV.utils.ui.QgsPlot",
        "QGISFMV.utils.core.QgsFmvUtils",
        "QGISFMV.utils.layers.QgsFmvLayers",
        "QGISFMV.utils.layers.QgsFmvExport",
        "QGISFMV.utils.media.QgsFfmpegProbe",
        "QGISFMV.utils.media.QgsFmvMultimedia",
        "QGISFMV.video.playback.QgsVideoState",
        "QGISFMV.player.dialogs.QgsFmvAlertRule",
        "QGISFMV.player.dialogs.QgsFmvMilitarySymbols",
        "QGISFMV.player.dialogs.QgsFmvMetadata",
        "QGISFMV.utils.core.QgsFmvThreads",
        "QGISFMV.utils.media.QgsFmvKlvReader",
        "QGISFMV.utils.media.QgsFmvMetadataWorker",
        "QGISFMV.utils.settings.QgsFmvSettings",
        "QGISFMV.player.dialogs.QgsFmvSettings",
        "QGISFMV.player.dialogs.QgsFmvVideoInfo",
        "QGISFMV.player.overlays.QgsFmvHud",
        "QGISFMV.player.overlays.QgsFmvMiniMap",
        "QGISFMV.player.overlays.QgsFmvSensorCone",
        "QGISFMV.player.overlays.QgsFmvDistanceRings",
    )
    saved = snapshot_modules(keys)
    for name in keys:
        sys.modules.setdefault(name, types.ModuleType(name))

    qgis = sys.modules["qgis"]
    pyqt = sys.modules["qgis.PyQt"]
    qgis.PyQt = pyqt

    qtcore = sys.modules["qgis.PyQt.QtCore"]

    class QObject:
        def __init__(self, parent=None, *a, **k):
            self._parent = parent

    def pyqtSignal(*a, **k):
        class _Sig:
            def __init__(self):
                self._slot = None

            def connect(self, slot):
                self._slot = slot

            def emit(self, *aa, **kk):
                if callable(self._slot):
                    self._slot(*aa, **kk)

        return _Sig()

    # Class-body ``pyqtSignal(...)`` must yield a connectable descriptor-like object.
    # Returning a fresh instance per call is enough for our AlertManager usage.
    qtcore.QObject = QObject
    qtcore.pyqtSignal = pyqtSignal

    class _FakeTimer:
        def __init__(self, parent=None):
            self._parent = parent
            self.timeout = types.SimpleNamespace(connect=lambda *a, **k: None)

        def setInterval(self, *a, **k):
            return None

        def start(self, *a, **k):
            return None

        def stop(self, *a, **k):
            return None

        def isActive(self):
            return False

    qtcore.QTimer = _FakeTimer

    class _FakeThread:
        def __init__(self, parent=None):
            self._parent = parent

        def start(self):
            return None

        def isRunning(self):
            return False

        def quit(self):
            return None

        def wait(self, *a, **k):
            return True

    qtcore.QThread = _FakeThread
    qtcore.QUrl = MagicMock
    qtcore.QRegularExpression = MagicMock
    qtcore.QCoreApplication = types.SimpleNamespace(
        translate=lambda *a, **k: a[-1] if a else ""
    )
    qtcore.QPoint = object
    qtcore.QSettings = MagicMock
    qtcore.Qt = types.SimpleNamespace(
        ToolBarArea=types.SimpleNamespace(
            TopToolBarArea=1,
            BottomToolBarArea=2,
            LeftToolBarArea=4,
            RightToolBarArea=8,
        ),
        ContextMenuPolicy=types.SimpleNamespace(NoContextMenu=0),
        MouseButton=types.SimpleNamespace(LeftButton=1),
        PenStyle=types.SimpleNamespace(NoPen=0),
        AlignmentFlag=types.SimpleNamespace(AlignCenter=4),
        TextFormat=types.SimpleNamespace(RichText=1),
        AspectRatioMode=types.SimpleNamespace(KeepAspectRatio=1),
        TransformationMode=types.SimpleNamespace(SmoothTransformation=1),
        DockWidgetArea=types.SimpleNamespace(
            RightDockWidgetArea=2, LeftDockWidgetArea=1
        ),
        Orientation=types.SimpleNamespace(Vertical=2, Horizontal=1),
        CursorShape=types.SimpleNamespace(BusyCursor=3, ArrowCursor=0),
        CheckState=types.SimpleNamespace(Checked=2, Unchecked=0),
        ConnectionType=types.SimpleNamespace(QueuedConnection=2),
    )

    qtgui = sys.modules["qgis.PyQt.QtGui"]

    class QColor:
        def __init__(self, *a):
            self.args = a

        def darker(self, *a):
            return self

    class QIcon:
        def __init__(self, *a):
            pass

    qtgui.QColor = QColor
    qtgui.QIcon = QIcon
    qtgui.QPainter = object
    qtgui.QPen = object
    qtgui.QBrush = object
    qtgui.QFont = object
    qtgui.QPixmap = MagicMock
    qtgui.QAction = MagicMock

    class _FakeMovie:
        def __init__(self, *a, **k):
            self.frameChanged = types.SimpleNamespace(
                connect=lambda *aa, **kk: None,
                disconnect=lambda *aa, **kk: None,
            )

        def start(self, *a, **k):
            return None

        def stop(self, *a, **k):
            return None

        def currentPixmap(self):
            return MagicMock()

    qtgui.QMovie = _FakeMovie

    qtw = sys.modules["qgis.PyQt.QtWidgets"]

    class QWidget:
        def __init__(self, parent=None):
            self._parent = parent

        def setMinimumHeight(self, *a):
            return None

        def setMaximumHeight(self, *a):
            return None

        def setMouseTracking(self, *a):
            return None

        def update(self):
            return None

        def width(self):
            return 200

        def height(self):
            return 32

        def hide(self):
            return None

        def show(self):
            return None

        def mapToGlobal(self, p):
            return p

        def findChildren(self, *a):
            return []

    class QMenu:
        def __init__(self, *a, **k):
            self._actions = []

        def addAction(self, *a, **k):
            act = MagicMock()
            act.setCheckable = MagicMock()
            act.setChecked = MagicMock()
            act.setObjectName = MagicMock()
            act.setEnabled = MagicMock()
            act.triggered = MagicMock()
            act.triggered.connect = MagicMock()
            self._actions.append(act)
            return act

        def addSeparator(self):
            return None

        def addMenu(self, *a, **k):
            return QMenu()

        def exec(self, *a, **k):
            return None

    qtw.QWidget = QWidget
    qtw.QMenu = QMenu
    qtw.QToolBar = object
    qtw.QActionGroup = MagicMock
    qtw.QToolTip = types.SimpleNamespace(
        showText=lambda *a: None, hideText=lambda: None
    )
    qtw.QMessageBox = types.SimpleNamespace(
        StandardButton=types.SimpleNamespace(Yes=1, No=0)
    )
    qtw.QDialog = type("QDialog", (QWidget,), {})
    qtw.QDialog.DialogCode = types.SimpleNamespace(Accepted=1, Rejected=0)
    qtw.QFileDialog = MagicMock
    qtw.QDockWidget = QWidget
    qtw.QApplication = MagicMock
    qtw.QTableWidgetItem = MagicMock

    alert_dlg = sys.modules["QGISFMV.player.dialogs.QgsFmvAlertRule"]
    alert_dlg.FmvAlertRuleDialog = MagicMock
    mil = sys.modules["QGISFMV.player.dialogs.QgsFmvMilitarySymbols"]
    mil.MilitarySymbolDialog = MagicMock
    meta_dlg = sys.modules["QGISFMV.player.dialogs.QgsFmvMetadata"]
    meta_dlg.QgsFmvMetadata = MagicMock

    core = sys.modules["qgis.core"]
    core.Qgis = types.SimpleNamespace(
        MessageLevel=types.SimpleNamespace(Warning=1, Info=0, Success=0, Critical=2)
    )
    core.QgsProject = types.SimpleNamespace(instance=lambda: MagicMock())
    core.QgsRasterLayer = object
    core.QgsApplication = MagicMock()

    class _FakeQgsTask:
        Flag = types.SimpleNamespace(CanCancel=1)

        @staticmethod
        def fromFunction(*a, **k):
            task = MagicMock()
            task.cancel = MagicMock()
            return task

    core.QgsTask = _FakeQgsTask
    core.QgsCoordinateReferenceSystem = object
    core.QgsCoordinateTransform = object
    core.QgsWkbTypes = types.SimpleNamespace()

    utils_iface = sys.modules["qgis.utils"]
    utils_iface.iface = MagicMock()

    ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]

    class QgsUtils:
        @staticmethod
        def showUserAndLogMessage(*a, **k):
            return None

        @staticmethod
        def CustomMessage(*a, **k):
            return 0

        @staticmethod
        def createFolderByName(parent, name):
            import os

            os.makedirs(os.path.join(str(parent), str(name)), exist_ok=True)

    ui.QgsUtils = QgsUtils

    plot = sys.modules["QGISFMV.utils.ui.QgsPlot"]
    plot.ShowPlot = lambda *a, **k: None
    plot.CreatePlotsBitrate = MagicMock

    fmv_utils = sys.modules["QGISFMV.utils.core.QgsFmvUtils"]
    fmv_utils.askForFiles = lambda *a, **k: None
    fmv_utils.askForFolder = lambda *a, **k: None
    fmv_utils._seconds_to_time = lambda s: "00:00:00"
    fmv_utils.ResetData = lambda: None
    fmv_utils.getNameSpace = lambda: "QGISFMV"
    fmv_utils.hasElevationModel = lambda: False
    fmv_utils.pluginSetting = lambda *a, **k: None
    fmv_utils.setPluginSetting = lambda *a, **k: None
    fmv_utils.centerCanvasOnLayer = lambda *a, **k: None
    fmv_utils.followMapCenter = lambda *a, **k: False
    fmv_utils._spawn = MagicMock()
    fmv_utils._ensureFfmpegPaths = lambda: None
    fmv_utils.BurnDrawingsImage = lambda *a, **k: None
    fmv_utils.GetGeotransform_affine = lambda: None
    fmv_utils.buildRecordFfmpegArgs = lambda *a, **k: ["ffmpeg", "-version"]
    fmv_utils.recordSaveExtensions = lambda: ["mp4"]
    fmv_utils.getVideoFolder = lambda path: "/tmp/qgis_fmv_sim"
    fmv_utils.ExtendMosaic = MagicMock()
    fmv_utils.resetMosaicFrameCounter = lambda: None
    fmv_utils.UpdateLayers = lambda *a, **k: None
    fmv_utils.ensureGlobalState = lambda *a, **k: None

    probe = sys.modules.setdefault(
        "QGISFMV.utils.media.QgsFfmpegProbe", types.ModuleType("probe")
    )
    probe.convert_video = lambda *a, **k: None
    probe.is_valid_media = lambda *a, **k: True
    probe.save_probe_json_task = MagicMock()
    probe.show_probe_json_task = MagicMock()

    mm = sys.modules["QGISFMV.utils.media.QgsFmvMultimedia"]
    for name, value in (
        ("PlayingState", 1),
        ("PausedState", 2),
        ("StoppedState", 0),
        ("LoadingMedia", 10),
        ("LoadedMedia", 11),
        ("BufferingMedia", 12),
        ("StalledMedia", 13),
        ("InvalidMedia", 14),
        ("EndOfMedia", 15),
        ("PlaylistLoop", 20),
        ("PlaylistSequential", 21),
    ):
        setattr(mm, name, value)
    mm.hasVideo = lambda *a, **k: True
    mm.getPlaylist = MagicMock(return_value=MagicMock())

    vs = sys.modules["QGISFMV.video.playback.QgsVideoState"]
    vs.MOUSE_MOVE_EVENT = object

    threads = sys.modules["QGISFMV.utils.core.QgsFmvThreads"]
    threads.stop_qthread = lambda t: None

    class _Worker:
        def __init__(self):
            self.packetReady = types.SimpleNamespace(
                connect=lambda *a, **k: None,
                disconnect=lambda *a, **k: None,
            )
            self.parseFailed = types.SimpleNamespace(
                connect=lambda *a, **k: None,
                disconnect=lambda *a, **k: None,
            )

        def moveToThread(self, *a, **k):
            return None

        def clearPending(self):
            return None

        def submit(self, *a, **k):
            return None

    worker_mod = sys.modules["QGISFMV.utils.media.QgsFmvMetadataWorker"]
    worker_mod.MetadataParseWorker = _Worker

    klv = sys.modules["QGISFMV.utils.media.QgsFmvKlvReader"]
    klv.LocalFileMetaReader = MagicMock
    klv.StreamMetaReader = MagicMock

    settings_mod = sys.modules["QGISFMV.utils.settings.QgsFmvSettings"]
    settings_mod.get = lambda section, key, default=None: default

    layers = sys.modules["QGISFMV.utils.layers.QgsFmvLayers"]
    layers.RemoveGroupByName = lambda *a, **k: None
    layers.exportGroupToKML = lambda *a, **k: None
    layers.exportGroupToGPX = lambda *a, **k: None
    layers.CreateGroupByName = lambda *a, **k: None
    layers.addLayerNoCrsDialog = lambda *a, **k: None
    layers.beginNewTrajectorySegment = lambda *a, **k: None
    layers.CreateVideoLayers = lambda *a, **k: None
    layers.frames_g = "frames"
    layers.groupName = "sim"
    layers.Footprint_lyr = "Footprint"
    layers.FrameCenter_lyr = "Frame Center"
    layers.Platform_lyr = "Platform"

    export = sys.modules["QGISFMV.utils.layers.QgsFmvExport"]
    export.exportGroupToKML = lambda *a, **k: None
    export.exportGroupToGPX = lambda *a, **k: None
    export.exportObjectTrack = lambda *a, **k: None

    return saved


class _FakeTimeline:
    def __init__(self):
        self._events = []

    def addEvent(self, time_sec, label="", color=None, lat=None, lon=None, alt=None):
        ev = types.SimpleNamespace(
            time_sec=float(time_sec),
            label=label,
            color=color,
            lat=lat,
            lon=lon,
            alt=alt,
        )
        self._events.append(ev)
        return ev

    def clearEvents(self):
        self._events.clear()

    def eventCount(self):
        return len(self._events)

    def events(self):
        return list(self._events)

    def setDuration(self, s):
        self._duration = s

    def setPosition(self, s):
        self._position = s


def _mock_player():
    player = MagicMock()
    player.closing = False
    player.currentInfo = 5.5
    player.duration = 60.0
    player.fileName = "/tmp/sim.ts"
    player.timeline = _FakeTimeline()
    player.videoWidget = MagicMock()
    player.videoWidget.mapToGlobal = lambda p: p
    player.videoWidget.currentFrame = MagicMock(return_value=None)
    player.iface = MagicMock()
    player.recordController = MagicMock()
    player.exportController = MagicMock()
    player.BitratePlot = MagicMock(bitrate_data=[], frame_count=0, output="/tmp/x")
    player.matplot = None
    player.findChildren = MagicMock(return_value=[])
    player._saveToolBarState = MagicMock()
    player.menubarwidget = MagicMock()
    player.actionToggle_Alerts = MagicMock()
    player.session = MagicMock()
    player.creatingMosaic = False
    player.playerState = 0  # StoppedState
    player.playbackRateSlow = 0.25
    player.sdv = 0
    player.data = None
    player.metaReader = None
    player.metadataDlg = MagicMock()
    player.metadataDlg.VManager = MagicMock()
    player.metadataDlg.VManager.rowCount = MagicMock(return_value=0)
    player.metadataDlg.VManager.verticalScrollBar = MagicMock(
        return_value=MagicMock(sliderPosition=MagicMock(return_value=0))
    )
    player._videoGroupName = MagicMock(return_value="sim_group")
    player.btn_play = MagicMock()
    player.btn_stop = MagicMock()
    player.playIcon = MagicMock()
    player.pauseIcon = MagicMock()
    player.player = MagicMock()
    player.player.position = MagicMock(return_value=5500)
    player.player.playbackRate = MagicMock(return_value=1.0)
    player.player.errorString = MagicMock(return_value="")
    player.filterManager = MagicMock()
    player.playbackController = MagicMock()
    for name in (
        "actionMagnifying_glass",
        "actionDraw_Pinpoint",
        "actionDraw_Line",
        "actionDraw_Polygon",
        "actionObject_Tracking",
        "actionMeasureDistance",
        "actionMeasureArea",
        "actionCensure",
        "actionStamp",
        "actionMilitary_Symbols",
    ):
        act = MagicMock()
        act.objectName = MagicMock(return_value=name)
        setattr(player, name, act)
    return player


@pytest.fixture(scope="module")
def stubs():
    saved = _install_common_stubs()
    yield
    restore_modules(saved)


class TestSimulateBookmarksAndAlerts:
    def test_bookmark_and_alert_pipeline(self, stubs, tmp_path):
        bm = load_plugin_module(
            "player/features/QgsFmvBookmarkController.py",
            "QGISFMV.player.features.QgsFmvBookmarkController",
        )
        alerts = load_plugin_module(
            "player/features/QgsFmvAlerts.py",
            "QGISFMV.player.features.QgsFmvAlerts",
        )
        player = _mock_player()
        ctrl = bm.BookmarkController(player)
        am = alerts.AlertManager(player)
        am.alertTriggered.connect(ctrl.onAlertTriggered)

        ctrl.addBookmark()
        assert player.timeline.eventCount() == 1

        rule = alerts.AlertRule("Sensor Latitude", ">", "10")
        am.addRule(rule)
        am._enabled = True
        # metadata_dict values are (name, value) pairs as used by the player table
        meta = {0: ["Sensor Latitude", "40.5"]}
        am.checkMetadata(meta)
        assert player.timeline.eventCount() >= 2

        path = ctrl.exportBookmarks(path=str(tmp_path / "b.csv"))
        assert path and Path(path).is_file()
        ctrl.clearBookmarks()
        assert player.timeline.eventCount() == 0


class TestSimulateTaskResults:
    def test_all_result_kinds(self, stubs):
        mod = load_plugin_module(
            "player/features/QgsFmvTaskResults.py",
            "QGISFMV.player.features.QgsFmvTaskResults",
        )
        player = _mock_player()
        ctrl = mod.TaskResultsController(player)

        cases = [
            (None, None),
            (None, {"error": "x", "stop_record_animation": True}),
            (None, {"task": "Georeferencing mosaic"}),
            (None, {"task": "Bitrate Analysis"}),
            (None, {"task": "Show Video Info Task", "json": {"a": 1}}),
            (None, {"task": "Show Video Info Task"}),
            (None, {"task": "Export KML"}),
            (Exception("boom"), {"task": "Export KML", "stop_record_animation": True}),
        ]
        for err, result in cases:
            ctrl.finishedTask(err, result)


class TestSimulateStreamAndFormatting:
    def test_stream_tools(self, stubs):
        stream = load_plugin_module("utils/media/QgsFmvStreamUtils.py")
        assert stream.buildStreamUri("UDP", "127.0.0.1", "5005")
        ok, _ = stream.validateStreamEndpoint("UDP", "127.0.0.1", "5005")
        assert ok
        assert stream.vlcHintText("UDP")

    def test_formatting_tools(self, stubs):
        fmt = load_plugin_module("utils/formatting.py")
        assert fmt.seconds_to_time(65) == "00:01:05"
        assert fmt.format_length(1500).endswith("km")


class TestSimulateControllersSmoke:
    """Instantiate feature controllers and poke safe methods."""

    @pytest.mark.parametrize(
        "rel_path,cls_name,calls",
        [
            (
                "player/features/QgsFmvContextMenus.py",
                "ContextMenuController",
                [
                    ("contextMenuBarRequested", (MagicMock(),)),
                    ("contextMenuRequested", (MagicMock(),)),
                ],
            ),
            (
                "player/features/QgsFmvMapCenterController.py",
                "MapCenterController",
                [],
            ),
            (
                "player/features/QgsFmvCloseController.py",
                "CloseController",
                [],
            ),
        ],
    )
    def test_controller_smoke(self, stubs, rel_path, cls_name, calls):
        mod = load_plugin_module(rel_path, "QGISFMV." + rel_path.replace("/", ".")[:-3])
        cls = getattr(mod, cls_name)
        player = _mock_player()
        ctrl = cls(player)
        for method_name, args in calls:
            getattr(ctrl, method_name)(*args)


class TestSimulateAlertRules:
    def test_ops(self, stubs):
        alerts = load_plugin_module(
            "player/features/QgsFmvAlerts.py",
            "QGISFMV.player.features.QgsFmvAlerts",
        )
        meta = {0: ["Platform Heading Angle", "90"]}
        for op, value, expect in (
            (">", "80", True),
            ("<", "80", False),
            ("==", "90", True),
        ):
            rule = alerts.AlertRule("Heading", op, value)
            ok, actual = rule.check(meta)
            assert ok is expect


class TestSimulateDetectionAndMosaic:
    def test_iou_nms(self, stubs):
        geom = load_plugin_module(
            "video/filters/QgsFmvDetectionGeometry.py",
            "QGISFMV.video.filters.QgsFmvDetectionGeometry",
        )
        geom.reset_detection_state()
        assert geom._box_iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
        boxes, scores = geom._nms_boxes(
            [(0, 0, 10, 10), (1, 1, 11, 11)], [0.9, 0.8], iou_thresh=0.3
        )
        assert len(boxes) == 1

    def test_mosaic_helpers(self, stubs):
        mosaic = load_plugin_module(
            "utils/core/QgsFmvMosaic.py",
            "QGISFMV.utils.core.QgsFmvMosaic",
        )
        w = mosaic._mosaic_feather_weights(16, 16, feather_px=8)
        assert w.shape == (16, 16)
        mosaic.resetMosaicFrameCounter()


class TestSimulateExportAndRecordSmoke:
    def test_export_controller_methods_exist(self, stubs):
        # ExportController pulls many deps; verify module loads when stubs present.
        try:
            mod = load_plugin_module(
                "player/features/QgsFmvExportController.py",
                "QGISFMV.player.features.QgsFmvExportController",
            )
        except Exception as exc:
            pytest.skip(f"ExportController deps unavailable under stubs: {exc}")
        player = _mock_player()
        ctrl = mod.ExportController(player)
        # Safe no-op wrappers when layers are stubbed.
        ctrl.exportToKML()
        ctrl.exportToGPX()

    def test_record_idle_styles_callable(self, stubs):
        try:
            mod = load_plugin_module(
                "player/features/QgsFmvRecordController.py",
                "QGISFMV.player.features.QgsFmvRecordController",
            )
        except Exception as exc:
            pytest.skip(f"RecordController deps unavailable under stubs: {exc}")
        player = _mock_player()
        player.btn_Rec = MagicMock()
        player.btn_Rec.setStyleSheet = MagicMock()
        player.btn_Rec.setIcon = MagicMock()
        player.btn_Rec.setChecked = MagicMock()
        ctrl = mod.RecordController(player)
        # Stop animation path should not raise.
        if hasattr(ctrl, "StopRecordAnimation"):
            ctrl.StopRecordAnimation()
        ctrl.stop()


class TestSimulateConstantsAndSettings:
    def test_constants_and_settings_defaults(self, stubs):
        const = load_plugin_module("utils/constants.py")
        assert const.MOSAIC_FEATHER_PX > 0
        settings = load_plugin_module("utils/settings/QgsFmvSettings.py")
        assert callable(settings._default_ffmpeg_folder)


class TestSimulatePlayerUi:
    """Generated Player UI exposes bookmark actions wired to slots."""

    def test_player_ui_has_bookmark_actions(self):
        ui_path = CODE / "gui" / "ui_FmvPlayer.py"
        text = ui_path.read_text(encoding="utf-8")
        for token in (
            "actionAdd_Bookmark",
            "actionClear_Bookmarks",
            "actionExport_Bookmarks",
            "actionSet_Geofence",
            "actionWatch_Detections_Geofence",
            "actionClick_to_Seek",
            "actionTime_Machine",
            "actionLookback",
            "actionPublish_Detections",
            "actionDetection_Heat_Trail",
            "actionInstant_Replay",
            "actionPlace_Labels",
            "actionStoryboard",
            "actionCinematic_Follow",
            "actionPin_Target",
            "actionJump_Next_Target_FOV",
            "actionClear_Target_Pin",
            "actionExport_Mission_Package",
            "addTimelineBookmark",
            "clearTimelineBookmarks",
            "exportTimelineBookmarks",
            "setGeofenceFromFootprint",
            "toggleWatchDetectionsGeofence",
            "toggleClickToSeek",
            "toggleTimeMachine",
            "toggleLookback",
            "toggleDetectionHeatTrail",
            "toggleInstantReplay",
            "togglePlaceLabels",
            "toggleStoryboard",
            "toggleCinematicFollow",
            "togglePinTarget",
            "jumpToNextTargetFov",
            "clearTargetPin",
            "exportMissionPackage",
            'setShortcut(_translate("PlayerWindow", "B"))',
        ):
            assert token in text, f"missing {token} in compiled UI"


class TestSimulatePlayerSlotsPresent:
    def test_player_defines_bookmark_slots(self):
        src = (CODE / "player" / "QgsFmvPlayer.py").read_text(encoding="utf-8")
        for name in (
            "def addTimelineBookmark",
            "def clearTimelineBookmarks",
            "def exportTimelineBookmarks",
            "def toggleInstantReplay",
            "def toggleStoryboard",
            "def togglePlaceLabels",
            "def toggleCinematicFollow",
            "def toggleDetectionHeatTrail",
            "def togglePinTarget",
            "def jumpToNextTargetFov",
            "def clearTargetPin",
            "BookmarkController",
            "InstantReplayController",
            "StoryboardController",
            "PlaceLabelController",
            "TargetPinController",
            "alertTriggered.connect",
        ):
            assert name in src


class TestSimulateDrawTools:
    def test_draw_tool_toggles(self, stubs):
        mod = load_plugin_module(
            "player/features/QgsFmvDrawToolsController.py",
            "QGISFMV.player.features.QgsFmvDrawToolsController",
        )
        player = _mock_player()
        player.sender = MagicMock(return_value=player.actionDraw_Pinpoint)
        ctrl = mod.DrawToolsController(player)
        ctrl.pointDrawer(True)
        ctrl.lineDrawer(False)
        ctrl.polygonDrawer(True)
        ctrl.magnifier(True)
        ctrl.stamp(False)
        ctrl.VideoMeasureDistance(True)
        ctrl.VideoMeasureArea(False)
        ctrl.VideoCensure(True)
        ctrl.RemoveMeasures()
        player.videoWidget.ResetDrawMeasureDistance.assert_called()
        player.videoWidget.SetMeasureArea.assert_called_with(False)


class TestSimulateSnapshots:
    def test_auto_snapshot_toggle(self, stubs, tmp_path):
        mod = load_plugin_module(
            "player/features/QgsFmvSnapshots.py",
            "QGISFMV.player.features.QgsFmvSnapshots",
        )
        player = _mock_player()
        folder = tmp_path / "video"
        folder.mkdir()
        # Module already bound getVideoFolder at import; patch the local name.
        mod.getVideoFolder = lambda path: str(folder)
        snap = mod.AutoSnapshot(player)
        assert snap.toggle() is True
        assert snap._active is True
        assert (folder / "snapshots").is_dir()
        assert snap.toggle() is False
        assert snap._active is False


class TestSimulateMosaicController:
    def test_mosaic_enable_and_frame(self, stubs, tmp_path):
        mod = load_plugin_module(
            "player/features/QgsFmvMosaicController.py",
            "QGISFMV.player.features.QgsFmvMosaicController",
        )
        player = _mock_player()
        folder = tmp_path / "video"
        folder.mkdir()
        mod.getVideoFolder = lambda path: str(folder)
        ctrl = mod.MosaicController(player)
        ctrl.apply_runtime_settings()
        assert ctrl.refresh_every == 3
        ctrl.set_enabled(True)
        assert player.creatingMosaic is True
        assert ctrl.folder is not None
        frame = tmp_path / "g_0001.tif"
        frame.write_bytes(b"x")
        ctrl.on_frame_added(str(frame))
        assert ctrl.frame_count == 1
        ctrl.reset()
        assert ctrl.frame_count == 0


class TestSimulatePlaybackController:
    def test_state_and_seek_helpers(self, stubs):
        mod = load_plugin_module(
            "player/features/QgsFmvPlaybackController.py",
            "QGISFMV.player.features.QgsFmvPlaybackController",
        )
        player = _mock_player()
        player.playerState = 0
        ctrl = mod.PlaybackController(player)
        ctrl.setCurrentState(1)  # PlayingState
        assert player.playerState == 1
        player.btn_play.setIcon.assert_called()
        ctrl.fakeStop()
        ctrl.AutoRepeat(True)
        ctrl.seek(12.5)
        player.player.setPosition.assert_called()


class TestSimulateMetadataPipeline:
    def test_metadata_reset_and_clear(self, stubs):
        mod = load_plugin_module(
            "player/features/QgsFmvMetadataPipeline.py",
            "QGISFMV.player.features.QgsFmvMetadataPipeline",
        )
        player = _mock_player()
        ctrl = mod.MetadataPipelineController(player)
        ctrl.resetStreamState()
        ctrl.resetFramePosition()
        ctrl.resetAppliedLayerSeq()
        ctrl.clearMetadata()
        ctrl.addMetadata(
            {1: ["Sensor Latitude", "40.0"], 2: ["Sensor Longitude", "-3.0"]}
        )
        player.metadataDlg.VManager.insertRow.assert_called()
        ctrl.shutdown()
        assert ctrl._metadataWorker is None
