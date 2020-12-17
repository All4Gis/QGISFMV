# -*- coding: utf-8 -*-
import os.path
from qgis.PyQt.QtCore import (QUrl,
                              QPoint,
                              QCoreApplication,
                              Qt,
                              QTimer)
from qgis.PyQt.QtGui import QIcon, QMovie
from qgis.PyQt.QtWidgets import (QToolTip,
                                 QMessageBox,
                                 QAbstractSlider,
                                 QHeaderView,
                                 QStyleOptionSlider,
                                 QTreeView,
                                 QVBoxLayout,
                                 QDialog,
                                 QMainWindow,
                                 QFileDialog,
                                 QMenu,
                                 QApplication,
                                 QTableWidgetItem,
                                 QToolBar)
from qgis.core import Qgis as QGis, QgsTask, QgsApplication, QgsRasterLayer, QgsProject, QgsLayerTreeGroup

from PyQt5.QtMultimedia import QMediaPlayer, QMediaPlaylist, QMediaContent

from QGIS_FMV.converter.Converter import Converter
from QGIS_FMV.gui.ui_FmvPlayer import Ui_PlayerWindow
from QGIS_FMV.player.QgsFmvOptions import FmvOptions
from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.streamparser import StreamParser
from QGIS_FMV.player.QgsFmvMetadata import QgsFmvMetadata
from QGIS_FMV.utils.QgsFmvLayers import (CreateVideoLayers,
                                         CreateGroupByName,
                                         RemoveGroupByName)
from QGIS_FMV.utils.QgsFmvUtils import (callBackMetadataThread,
                                        ResetData,
                                        getVideoFolder,
                                        BurnDrawingsImage,
                                        _spawn,
                                        UpdateLayers,
                                        hasElevationModel,
                                        _seconds_to_time,
                                        _seconds_to_time_frac,
                                        askForFiles,
                                        askForFolder,
                                        setCenterMode,
                                        GetGeotransform_affine)
from QGIS_FMV.utils.QgsJsonModel import QJsonModel
from QGIS_FMV.utils.QgsPlot import CreatePlotsBitrate, ShowPlot
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.video.QgsColor import ColorDialog

try:
    from pydevd import *
except ImportError:
    None
try:
    from osgeo import gdal, osr
except ImportError:
    import gdal
try:
    import cv2
except Exception as e:
    qgsu.showUserAndLogMessage(QCoreApplication.translate(
        "VideoProcessor", "Error: Missing OpenCV packages"))


class QgsFmvPlayer(QMainWindow, Ui_PlayerWindow):
    """ Video Player Class """

    def __init__(self, iface, path, parent=None, meta_reader=None, pass_time=None, islocal=False, klv_folder=None):
        """ Constructor """

        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface
        self.fileName = path
        self.meta_reader = meta_reader
        self.isStreaming = False
        self.islocal = islocal
        self.klv_folder = klv_folder
        self.createingMosaic = False
        self.currentInfo = 0.0
        self.data = None
        self.staticDraw = False
        self.playbackRateSlow = 0.7

        # Create Draw Toolbar
        self.DrawToolBar.addAction(self.actionMagnifying_glass)
        self.DrawToolBar.addSeparator()

        # Draw Polygon QToolButton
        self.toolBtn_DPolygon.setDefaultAction(self.actionDraw_Polygon)
        self.DrawToolBar.addWidget(self.toolBtn_DPolygon)

        # Draw Point QToolButton
        self.toolBtn_DPoint.setDefaultAction(self.actionDraw_Pinpoint)
        self.DrawToolBar.addWidget(self.toolBtn_DPoint)

        # Draw Line QToolButton
        self.toolBtn_DLine.setDefaultAction(self.actionDraw_Line)
        self.DrawToolBar.addWidget(self.toolBtn_DLine)

#         self.DrawToolBar.addSeparator()
#         self.DrawToolBar.addAction(self.actionHandDraw)
        self.DrawToolBar.addSeparator()

        # Measure QToolButton
        self.toolBtn_Measure.setDefaultAction(self.actionMeasureDistance)
        self.DrawToolBar.addWidget(self.toolBtn_Measure)
        self.DrawToolBar.addSeparator()

        # Censure QToolButton
        self.toolBtn_Cesure.setDefaultAction(self.actionCensure)
        self.DrawToolBar.addWidget(self.toolBtn_Cesure)
        self.DrawToolBar.addSeparator()

        # Stamp
        self.DrawToolBar.addAction(self.actionStamp)
        self.DrawToolBar.addSeparator()

        # Object Tracking
        self.DrawToolBar.addAction(self.actionObject_Tracking)

        # Hide Color Button
        self.btn_Color.hide()

        self.RecGIF = QMovie(":/imgFMV/images/record.gif")
        self.playIcon = QIcon(":/imgFMV/images/play-arrow.png")
        self.pauseIcon = QIcon(":/imgFMV/images/pause.png")

        self.videoWidget.customContextMenuRequested[QPoint].connect(
            self.contextMenuRequested)

        self.menubarwidget.customContextMenuRequested[QPoint].connect(
            self.contextMenuBarRequested)

        self.duration = 0
        self.playerMuted = False
        self.HasFileAudio = False

        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.pass_time = pass_time
        self.player.setNotifyInterval(250)  # Player update interval
        self.playlist = QMediaPlaylist()

        self.player.setVideoOutput(
            self.videoWidget.videoSurface())  # Abstract Surface

        self.player.durationChanged.connect(self.durationChanged)
        self.player.positionChanged.connect(self.positionChanged)
        self.player.mediaStatusChanged.connect(self.statusChanged)
        self.player.playbackRateChanged.connect(self.rateChanged)

        self.player.stateChanged.connect(self.setCurrentState)

        self.playerState = QMediaPlayer.LoadingMedia
        self.playFile(path, self.islocal, self.klv_folder)

        self.sliderDuration.setRange(0, self.player.duration() / 1000)

        self.volumeSlider.setValue(self.player.volume())
        self.volumeSlider.enterEvent = self.showVolumeTip

        self.metadataDlg = QgsFmvMetadata(player=self)
        self.addDockWidget(Qt.RightDockWidgetArea, self.metadataDlg)
        self.metadataDlg.setMinimumWidth(500)
        self.metadataDlg.hide()

        self.converter = Converter()
        self.BitratePlot = CreatePlotsBitrate()

        if self.actionCenter_on_Platform.isChecked():
            setCenterMode(1, self.iface)
        elif self.actionCenter_on_Footprint.isChecked():
            setCenterMode(2, self.iface)
        elif self.actionCenter_Target.isChecked():
            setCenterMode(3, self.iface)

        # Defalut WGS 84/ World Mercator (3D)
        # QgsProject.instance().setCrs(QgsCoordinateReferenceSystem(3395))

    def setMetaReader(self, meta_reader):
        self.meta_reader = meta_reader
        
    def centerMapPlatform(self, checked):
        ''' Center map on Platform
        @param checked: Boolean if button is checked
        '''
        if checked:
            self.actionCenter_on_Footprint.setChecked(False)
            self.actionCenter_Target.setChecked(False)
            setCenterMode(1, self.iface)
        else:
            setCenterMode(0, self.iface)

    def centerMapFootprint(self, checked):
        '''Center Map on Footprint
        @param checked: Boolean if button is checked
        '''
        if checked:
            self.actionCenter_on_Platform.setChecked(False)
            self.actionCenter_Target.setChecked(False)
            setCenterMode(2, self.iface)
        else:
            setCenterMode(0, self.iface)

    def centerMapTarget(self, checked):
        '''Center Map on Target
        @param checked: Boolean if button is checked
        '''
        if checked:
            self.actionCenter_on_Platform.setChecked(False)
            self.actionCenter_on_Footprint.setChecked(False)
            setCenterMode(3, self.iface)
        else:
            setCenterMode(0, self.iface)

    def MouseLocationCoordinates(self, idx):
        '''Set Cursor Video Coordinates , WGS84/MGRS
        @type idx: int
        @param idx: QComboBox index
        '''
        if idx == 1:
            self.videoWidget.SetMGRS(True)
        else:
            self.videoWidget.SetMGRS(False)

    def HasAudio(self, videoPath):
        """Check if video have Metadata or not
        @type videoPath: String
        @param videoPath: Video file path
        """
        try:
            p = _spawn(['-i', videoPath,
                        '-show_streams', '-select_streams', 'a',
                        '-loglevel', 'error'], t="probe")

            stdout_data, _ = p.communicate()

            if stdout_data == b'':
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvPlayer", "This video doesn't have Audio ! "))
                self.actionAudio.setEnabled(False)
                self.actionSave_Audio.setEnabled(False)
                return False

            return True
        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Audio check Failed! : "), str(e))
            self.actionAudio.setEnabled(False)
            self.actionSave_Audio.setEnabled(False)

    def get_metadata_from_buffer(self, currentTime=None):
        """Metadata CallBack
        @type currentTime: String
        @param currentTime: Current video timestamp
        """
        try:

            # There is no way to spawn a thread and call after join() without blocking the video UI thread.
            # callBackMetadata can be as fast as possible, it will always create a small video lag every time meta are read.
            # To get rid of this, we fill a buffer (BufferedMetaReader) in the QManager with some Metadata in advance,
            # and hope they'll be ready to read here in a totaly non-blocking
            # way (increase the buffer size if needed in QManager).
            if not self.islocal:
                stdout_data = self.meta_reader.get(currentTime)
                # debug
                qgsu.showUserAndLogMessage("", "Buffer size:" + str(self.meta_reader.getSize()), onlyLog=True)
            else:
                stdout_data = b'\x15'
            # qgsu.showUserAndLogMessage(
            #    "", "stdout_data: " + str(stdout_data) + " currentTime: " + str(currentTime), onlyLog=True)
            if stdout_data == 'NOT_READY':
                qgsu.showUserAndLogMessage("", "Buffer value read but is not ready, increase buffer size:" + str(self.meta_reader.getSize()), onlyLog=True)
                return
            # Values need to be read, pause the video a short while
            elif stdout_data == 'BUFFERING':
                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvPlayer", "Buffering metadata..."), duration=4, level=QGis.Info)
                self.player.pause()
                QTimer.singleShot(2500, lambda: self.player.play())
                return
            elif stdout_data is None:
                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvPlayer", "No metadata to show, buffer size:" + str(self.meta_reader.getSize())), level=QGis.Info)
                # qgsu.showUserAndLogMessage("No metadata to show.", "Buffer returned None Type, check pass_time. : ", onlyLog=True)
                return
            elif stdout_data == b'' or len(stdout_data) == 0:
                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvPlayer", "No metadata to show, buffer size:" + str(self.meta_reader.getSize())), level=QGis.Info)
                # qgsu.showUserAndLogMessage("No metadata to show.", "Buffer returned empty metadata, check pass_time. : ", onlyLog=True)
                return

            self.packetStreamParser(stdout_data)

        except Exception as inst:
            qgsu.showUserAndLogMessage("", "Metadata Buffer Failed! : " + str(inst), onlyLog=True)
            # qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvPlayer", "Metadata Buffer Failed! : "), str(inst))

    def packetStreamParser(self, stdout_data):
        '''Common packet process
        @type stdout_data: String
        @param stdout_data: Binary data
        '''
        for packet in StreamParser(stdout_data):
            try:
                if isinstance(packet, UnknownElement):
                    qgsu.showUserAndLogMessage(
                        "Error interpreting klv data, metadata cannot be read.", "the parser did not recognize KLV data", level=QGis.Warning, onlyLog=True)
                    continue
                data = packet.MetadataList()
                self.data = data
                if self.metadataDlg.isVisible():  # Only add metadata to table if this QDockWidget is visible (speed plugin)
                    self.addMetadata(data)
                try:
                    UpdateLayers(packet, parent=self,
                                 mosaic=self.createingMosaic, group=self.fileName)
                except Exception:
                    None
                QApplication.processEvents()
                return
            except Exception as e:
                qgsu.showUserAndLogMessage("", "QgsFmvPlayer packetStreamParser failed! : " + str(e), onlyLog=True)

    def callBackMetadata(self, currentTime, nextTime):
        '''Metadata CallBack Streaming
        @type currentTime: String
        @param currentTime: Current timestamp

        @type nextTime: String
        @param nextTime: Next timestamp
        '''
        try:

            port = int(self.fileName.split(':')[2])
            t = callBackMetadataThread(cmds=['-i', self.fileName.replace(str(port), str(port + 1)),
                                             '-ss', currentTime,
                                             '-to', nextTime,
                                             '-map', '0:d',
                                             '-preset', 'ultrafast',
                                             '-f', 'data', '-'])
            t.start()
            t.join(1)
            if t.is_alive():
                t.p.terminate()
                t.join()

            if t.stdout == b'':
                return

            self.packetStreamParser(t.stdout)

        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Metadata Callback Failed! : "), str(e))

    def readLocal(self, currentInfo):
        ''' Read Local Metadata ,klv files'''
        try:
            dataFile = os.path.join(self.klv_folder, str(round(currentInfo, 1)) + ".klv")
            f = open(dataFile, 'rb')
            stdout_data = f.read()
        except Exception:
            return

        if stdout_data == b'':
            return

        self.packetStreamParser(stdout_data)

        return

    def GetPacketData(self):
        ''' Return Current Packet data '''
        return self.data

    def addMetadata(self, packet):
        '''Add Metadata to List
        @param packet: Metadata packet
        '''
        self.clearMetadata()
        row = 0
        if packet is None:
            return
        for key in sorted(packet.keys()):
            self.metadataDlg.VManager.insertRow(row)
            self.metadataDlg.VManager.setItem(
                row, 0, QTableWidgetItem(str(key)))
            self.metadataDlg.VManager.setItem(
                row, 1, QTableWidgetItem(str(packet[key][0])))
            self.metadataDlg.VManager.setItem(
                row, 2, QTableWidgetItem(str(packet[key][1])))
            row += 1
        self.metadataDlg.VManager.setVisible(False)
        self.metadataDlg.VManager.resizeColumnsToContents()
        self.metadataDlg.VManager.setVisible(True)
        self.metadataDlg.VManager.verticalScrollBar().setSliderPosition(self.sliderPosition)

    def clearMetadata(self):
        ''' Clear Metadata List '''
        try:
            self.sliderPosition = self.metadataDlg.VManager.verticalScrollBar().sliderPosition()
            self.metadataDlg.VManager.setRowCount(0)
        except Exception:
            None

    def saveInfoToJson(self):
        """ Save video Info to json """
        out_json, _ = askForFiles(self, QCoreApplication.translate(
            "QgsFmvPlayer", "Save Json"),
            isSave=True,
            exts="json")

        if not out_json:
            return

        taskSaveInfoToJson = QgsTask.fromFunction('Save Video Info to Json Task',
                                                  self.converter.probeToJson,
                                                  fname=self.fileName, output=out_json,
                                                  on_finished=self.finishedTask,
                                                  flags=QgsTask.CanCancel)

        QgsApplication.taskManager().addTask(taskSaveInfoToJson)
        return

    def showVideoInfo(self):
        ''' Show default probe info '''
        taskSaveInfoToJson = QgsTask.fromFunction('Show Video Info Task',
                                                  self.converter.probeShow,
                                                  fname=self.fileName,
                                                  on_finished=self.finishedTask,
                                                  flags=QgsTask.CanCancel)

        QgsApplication.taskManager().addTask(taskSaveInfoToJson)
        return

    def state(self):
        ''' Return Current State '''
        return self.playerState

    def setCurrentState(self, state):
        '''Set Current State
        @type state: QMediaPlayer::State
        @param state: Current video state (play/pause ...)
        '''
        if state != self.playerState:
            self.playerState = state
            if state == QMediaPlayer.StoppedState:
                self.btn_play.setIcon(self.playIcon)

        return

    def showColorDialog(self):
        ''' Show Color dialog '''
        self.ColorDialog = ColorDialog(parent=self)
        self.ColorDialog.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        # Fail if not uncheked
        self.actionMagnifying_glass.setChecked(False)
        self.ColorDialog.exec_()
        QApplication.processEvents()
        self.ColorDialog.contrastSlider.setValue(80)
        self.ColorDialog.contrastSlider.triggerAction(
            QAbstractSlider.SliderMove)
        return

    def createMosaic(self, value):
        ''' Function for create Video Mosaic '''
        folder = getVideoFolder(self.fileName)
        qgsu.createFolderByName(folder, "mosaic")

        self.createingMosaic = value
        # Create Group
        CreateGroupByName()
        return

    def contextMenuBarRequested(self, point):
        ''' Context Menu Bar for toggle visibility of Menu Bar'''
        menu = QMenu('ToolBars')
        toolbars = self.findChildren(QToolBar)
        for toolbar in toolbars:
            action = menu.addAction(toolbar.windowTitle())
            action.setCheckable(True)
            action.setChecked(toolbar.isVisible())
            action.setObjectName(toolbar.windowTitle())
            action.triggered.connect(lambda _: self.ToggleQToolBar())
        menu.exec_(self.mapToGlobal(point))
        return

    def ToggleQToolBar(self):
        ''' Toggle ToolBar '''
        toolbars = self.findChildren(QToolBar)
        for toolbar in toolbars:
            if self.sender().objectName() == toolbar.windowTitle():
                toolbar.toggleViewAction().trigger()

    def contextMenuRequested(self, point):
        ''' Context Menu Video '''
        menu = QMenu('Video')

#         actionColors = menu.addAction(
#             QCoreApplication.translate("QgsFmvPlayer", "Color Options"))
#         actionColors.triggered.connect(self.showColorDialog)

        actionMute = menu.addAction(QIcon(":/imgFMV/images/volume_up.png"),
                                    QCoreApplication.translate("QgsFmvPlayer", "Mute/Unmute"))
        actionMute.triggered.connect(self.setMuted)

        menu.addSeparator()
        actionAllFrames = menu.addAction(QIcon(":/imgFMV/images/capture_all_frames.png"),
                                         QCoreApplication.translate("QgsFmvPlayer", "Extract All Frames"))

        actionAllFrames.triggered.connect(self.ExtractAllFrames)

        actionCurrentFrames = menu.addAction(QIcon(":/imgFMV/images/screenshot.png"),
                                             QCoreApplication.translate("QgsFmvPlayer",
                                                                        "Extract Current Frame"))
        actionCurrentFrames.triggered.connect(self.ExtractCurrentFrame)

        menu.addSeparator()
        actionShowMetadata = menu.addAction(QIcon(":/imgFMV/images/show-metadata.png"),
                                            QCoreApplication.translate("QgsFmvPlayer", "Show Metadata"))
        actionShowMetadata.triggered.connect(self.OpenQgsFmvMetadata)

        menu.addSeparator()
        actionOptions = menu.addAction(QIcon(":/imgFMV/images/custom-options.png"),
                                       QCoreApplication.translate("QgsFmvPlayer", "Options"))
        actionOptions.triggered.connect(self.OpenOptions)

        menu.exec_(self.mapToGlobal(point))

    def rateChanged(self, qreal):   
        '''Signals the playbackRate has changed to rate.
        @type value: qreal
        @param value: rate value
        '''
        self.player.setPosition(self.sdv)
        QApplication.processEvents()
        return
    
    def grayFilter(self, value):
        '''Gray Video Filter
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetGray(value)

        if value and self.player.playbackRate() == self.playbackRateSlow:
            self.sdv = self.player.position()
            self.player.setPlaybackRate(1.0)
            return

        self.videoWidget.UpdateSurface()
        return

    def MirrorHorizontalFilter(self, value):
        '''Mirror Horizontal Video Filter
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetMirrorH(value)

        if value and self.player.playbackRate() == self.playbackRateSlow:
            self.sdv = self.player.position()
            self.player.setPlaybackRate(1.0)
            return

        self.videoWidget.UpdateSurface()
        return

    def NDVIFilter(self, value):
        '''NDVI Video Filter
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetNDVI(value)

        # TODO : Temporarily we lower in rate. Player in other thread?
        if value and self.player.playbackRate() != self.playbackRateSlow:
            self.sdv = self.player.position()
            self.player.setPlaybackRate(self.playbackRateSlow)
            return

        # QApplication.processEvents()
        self.videoWidget.UpdateSurface()
        return

    def edgeFilter(self, value):
        '''Edge Detection Video Filter
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetEdgeDetection(value)

        # TODO : Temporarily we lower in rate. Player in other thread?
        if value and self.player.playbackRate() != self.playbackRateSlow:
            self.sdv = self.player.position()
            self.player.setPlaybackRate(self.playbackRateSlow)
            return
        # QApplication.processEvents()
        self.videoWidget.UpdateSurface()
        return

    def invertColorFilter(self, value):
        '''Invert Color Video Filter
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetInvertColor(value)

        if value and self.player.playbackRate() == self.playbackRateSlow:
            self.sdv = self.player.position()
            self.player.setPlaybackRate(1.0)
            return

        # QApplication.processEvents()
        self.videoWidget.UpdateSurface()
        return

    def autoContrastFilter(self, value):
        '''Auto Contrast Video Filter
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetAutoContrastFilter(value)
        # TODO : Temporarily we lower in rate. Player in other thread?
        if value and self.player.playbackRate() != self.playbackRateSlow:
            self.sdv = self.player.position()
            self.player.setPlaybackRate(self.playbackRateSlow)
            return

        # QApplication.processEvents()
        self.videoWidget.UpdateSurface()
        return

    def monoFilter(self, value):
        '''Filter Mono Video
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetMonoFilter(value)

        if value and self.player.playbackRate() == self.playbackRateSlow:
            self.sdv = self.player.position()
            self.player.setPlaybackRate(1.0)
            return

        # QApplication.processEvents()
        self.videoWidget.UpdateSurface()
        return

    def magnifier(self, value):
        '''Magnifier Glass Utils
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetMagnifier(value)
        self.videoWidget.UpdateSurface()
        return

    def stamp(self, value):
        '''Stamp Utils
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetStamp(value)
        self.videoWidget.UpdateSurface()
        return

    def pointDrawer(self, value):
        '''Draw Point
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetPointDrawer(value)
        self.videoWidget.UpdateSurface()

    def lineDrawer(self, value):
        '''Draw Line
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetLineDrawer(value)
        self.videoWidget.UpdateSurface()

    def polygonDrawer(self, value):
        '''Draw Polygon
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetPolygonDrawer(value)
        self.videoWidget.UpdateSurface()

    def ojectTracking(self, value):
        '''Object Tracking
        @type value: bool
        @param value: Button checked state
        '''
        # Remove tracking if is unchecked
        # if not value:
        self.videoWidget.Track_Canvas_RubberBand.reset()

        self.UncheckUtils(self.sender(), value)
        # TODO : Temporarily we lower in rate. Player in other thread?
        if value and self.player.playbackRate() != self.playbackRateSlow: 
            self.sdv = self.player.position()
            self.player.setPlaybackRate(self.playbackRateSlow)
            
        QApplication.processEvents()
        self.videoWidget.SetObjectTracking(value)
        self.videoWidget.UpdateSurface()

    def VideoMeasureDistance(self, value):
        '''Video Measure Distance
        @type value: bool
        @param value: Button checked state
        '''
        self.CommonPauseTool(value)
        self.videoWidget.UpdateSurface()

        self.toolBtn_Measure.setDefaultAction(self.actionMeasureDistance)
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetMeasureDistance(value)
        if not value:
            self.videoWidget.ResetDrawMeasureDistance()

        self.staticDraw = value

    def VideoMeasureArea(self, value):
        '''Video Measure Area
        @type value: bool
        @param value: Button checked state
        '''
        self.CommonPauseTool(value)
        self.videoWidget.UpdateSurface()

        self.toolBtn_Measure.setDefaultAction(self.actionMeasureArea)
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetMeasureArea(value)
        if not value:
            self.videoWidget.ResetDrawMeasureArea()

        self.staticDraw = value

    # TODO : Make draw hand tool
    def VideoHandDraw(self, value):
        '''Video Free Hand Draw
        @type value: bool
        @param value: Button checked state
        '''
        self.videoWidget.SetHandDraw(value)
        self.CommonPauseTool(value)
        self.videoWidget.UpdateSurface()

    def CommonPauseTool(self, value):
        '''Static draw common function
        @type value: bool
        @param value: Button checked state
        '''
        if value:
            if self.playerState == QMediaPlayer.PlayingState:
                self.player.pause()
                self.btn_play.setIcon(self.playIcon)
        else:
            if self.playerState in (QMediaPlayer.StoppedState,
                                    QMediaPlayer.PausedState):
                self.player.play()
                self.btn_play.setIcon(self.pauseIcon)
        QApplication.processEvents()

    def VideoCensure(self, value):
        '''Censure Video Parts
        @type value: bool
        @param value: Button checked state
        '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetCensure(value)
        self.videoWidget.UpdateSurface()
        return

    def UncheckUtils(self, sender, value):
        ''' Uncheck Utils Video
        @type value: bool
        @param value: Button checked state
        '''
        self.actionMagnifying_glass.setChecked(False)
        self.actionDraw_Pinpoint.setChecked(False)
        self.actionDraw_Line.setChecked(False)
        self.actionDraw_Polygon.setChecked(False)
        self.actionObject_Tracking.setChecked(False)
        self.actionMeasureDistance.setChecked(False)
        self.actionMeasureArea.setChecked(False)
        self.actionCensure.setChecked(False)
        self.actionStamp.setChecked(False)

        self.videoWidget.RestoreDrawer()

        if not value and self.player.playbackRate() == self.playbackRateSlow and sender.objectName() == "actionObject_Tracking" and not self.videoWidget._filterSatate.hasFiltersSlow():
            self.sdv = self.player.position()
            self.player.setPlaybackRate(1.0)
            

        QApplication.processEvents()
        sender.setChecked(value)
        QApplication.processEvents()
        return

    def UncheckFilters(self, sender, value):
        ''' Uncheck Filters Video '''
        self.actionGray.setChecked(False)
        self.actionInvert_Color.setChecked(False)
        self.actionMono_Filter.setChecked(False)
        self.actionCanny_edge_detection.setChecked(False)
        self.actionAuto_Contrast_Filter.setChecked(False)
        self.actionMirroredH.setChecked(False)
        self.actionNDVI.setChecked(False)

        self.videoWidget.RestoreFilters()

        if not value and self.player.playbackRate() == self.playbackRateSlow and not self.actionObject_Tracking.isChecked():
            self.sdv = self.player.position()
            self.player.setPlaybackRate(1.0)

        QApplication.processEvents()
        sender.setChecked(value)
        QApplication.processEvents()
        return

    def isMuted(self):
        ''' Is muted video property'''
        return self.playerMuted

    def setMuted(self):
        ''' Muted video '''
        if self.player.isMuted():
            self.btn_volume.setIcon(QIcon(":/imgFMV/images/volume_up.png"))
            self.player.setMuted(False)
            self.volumeSlider.setEnabled(True)
        else:
            self.btn_volume.setIcon(QIcon(":/imgFMV/images/volume_off.png"))
            self.player.setMuted(True)
            self.volumeSlider.setEnabled(False)
        return

    def stop(self):
        ''' Stop video'''
        # Prevent Error in a Video Utils.Disable Magnifier
        if self.actionMagnifying_glass.isChecked():
            self.actionMagnifying_glass.trigger()
        # Stop Video
        self.fakeStop()
        return

    def volume(self):
        ''' Volume Slider '''
        return self.volumeSlider.value()

    def setVolume(self, volume):
        '''Tooltip and set Volume value and icon
        @type volume: qreal
        @param volume: QSlider value
        '''
        self.player.setVolume(volume)
        self.showVolumeTip(None)
        if 0 < volume <= 30:
            self.btn_volume.setIcon(QIcon(":/imgFMV/images/volume_30.png"))
        elif 30 < volume <= 60:
            self.btn_volume.setIcon(QIcon(":/imgFMV/images/volume_60.png"))
        elif 60 < volume <= 100:
            self.btn_volume.setIcon(QIcon(":/imgFMV/images/volume_up.png"))
        elif volume == 0:
            self.btn_volume.setIcon(QIcon(":/imgFMV/images/volume_off.png"))

    def EndMedia(self):
        ''' Button end video position '''
        if self.player.isVideoAvailable():
            self.player.setPosition(self.player.duration())
            self.videoWidget.update()
        return

    def StartMedia(self):
        ''' Button start video position '''
        if self.player.isVideoAvailable():
            self.player.setPosition(0)
            self.videoWidget.update()
        return

    def forwardMedia(self):
        ''' Button forward Video '''
        forwardTime = int(self.player.position()) + 10 * 1000
        if forwardTime > int(self.player.duration()):
            forwardTime = int(self.player.duration())
        self.player.setPosition(forwardTime)

    def rewindMedia(self):
        ''' Button rewind Video '''
        rewindTime = int(self.player.position()) - 10 * 1000
        if rewindTime < 0:
            rewindTime = 0
        self.player.setPosition(rewindTime)

    def AutoRepeat(self, checked):
        '''Button AutoRepeat Video
        @param checked: Button checked state
        '''
        if checked:
            self.playlist.setPlaybackMode(QMediaPlaylist.Loop)
        else:
            self.playlist.setPlaybackMode(QMediaPlaylist.Sequential)
        return

    def showVolumeTip(self, _):
        '''Volume Slider Tooltip Trick
        @type _: QEvent
        @param _: Enter Event
        '''
        self.style = self.volumeSlider.style()
        self.opt = QStyleOptionSlider()
        self.volumeSlider.initStyleOption(self.opt)
        rectHandle = self.style.subControlRect(
            self.style.CC_Slider, self.opt, self.style.SC_SliderHandle)
        self.tip_offset = QPoint(5, 15)
        pos_local = rectHandle.topLeft() + self.tip_offset
        pos_global = self.volumeSlider.mapToGlobal(pos_local)
        QToolTip.showText(pos_global, str(
            self.volumeSlider.value()) + " %", self)

    def showMoveTip(self, currentInfo):
        '''Player Silder Move Tooptip Trick
        @type currentInfo: String
        @param currentInfo: Current time value
        '''
        self.style = self.sliderDuration.style()
        self.opt = QStyleOptionSlider()
        self.sliderDuration.initStyleOption(self.opt)
        rectHandle = self.style.subControlRect(
            self.style.CC_Slider, self.opt, self.style.SC_SliderHandle)
        self.tip_offset = QPoint(5, 15)
        pos_local = rectHandle.topLeft() + self.tip_offset
        pos_global = self.sliderDuration.mapToGlobal(pos_local)

        tStr = _seconds_to_time(currentInfo)

        QToolTip.showText(pos_global, tStr, self)

    def durationChanged(self, duration):
        '''Duration video change signal
        @type duration: int
        @param duration: Video duration
        '''
        duration /= 1000
        self.duration = duration
        self.sliderDuration.setMaximum(duration)

    def positionChanged(self, progress):
        '''Current Video position change
        @type progress: qint64
        @param progress: Slide video duration current value
        '''
        progress /= 1000
        # Remove measure if slider position change
        if self.staticDraw:
            self.RemoveMeasures()

        if not self.sliderDuration.isSliderDown():
            self.sliderDuration.setValue(progress)

        self.updateDurationInfo(progress)

    def updateDurationInfo(self, currentInfo):
        '''Update labels duration Info and CallBack Metadata
        @type currentInfo: String
        @param currentInfo: Current time value
        '''
        duration = self.duration
        self.currentInfo = currentInfo
        if currentInfo or duration:

            totalTime = _seconds_to_time(duration)
            currentTime = _seconds_to_time(currentInfo)
            tStr = currentTime + " / " + totalTime
            currentTimeInfo = _seconds_to_time_frac(currentInfo)

            if self.isStreaming:
                # get last metadata available
                self.get_metadata_from_buffer()
                # qgsu.showUserAndLogMessage("", "Streaming on ", onlyLog=True)
                # nextTime = currentInfo + self.pass_time / 1000
                # nextTimeInfo = _seconds_to_time_frac(nextTime)
                # self.callBackMetadata(currentTimeInfo, nextTimeInfo)
            elif self.islocal:
                self.readLocal(currentInfo)
            else:
                # Get Metadata from buffer
                self.get_metadata_from_buffer(currentTimeInfo)

        else:
            tStr = ""

        self.labelDuration.setText(tStr)

    def handleCursor(self, status):
        '''Change cursor
        @type status: QMediaPlayer::MediaStatus
        @param status: Video status
        '''
        if status in (QMediaPlayer.LoadingMedia,
                      QMediaPlayer.BufferingMedia,
                      QMediaPlayer.StalledMedia):
            self.setCursor(Qt.BusyCursor)
        else:
            self.unsetCursor()

    def statusChanged(self, status):
        '''Signal Status video change
        @type status: QMediaPlayer::MediaStatus
        @param status: Video status
        '''
        self.handleCursor(status)
        if status is QMediaPlayer.LoadingMedia or status is QMediaPlayer.StalledMedia or status is QMediaPlayer.InvalidMedia:
            self.videoAvailableChanged(False)
        elif status == QMediaPlayer.InvalidMedia:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", self.player.errorString()), level=QGis.Warning)
            self.videoAvailableChanged(False)
        else:
            self.videoAvailableChanged(True)

    def playFile(self, videoPath, islocal=False, klv_folder=None):
        ''' Play file from path
        @param videoPath: Video file path
        @param islocal: Check if video is local,created using multiplexor or is MISB
        @param klv_folder: klv folder if video is created using multiplexor
        '''
        self.islocal = islocal
        self.klv_folder = klv_folder
        try:
            # Remove All Data
            self.RemoveAllData()
            self.clearMetadata()
            QApplication.processEvents()

            # Create Group
            root = QgsProject.instance().layerTreeRoot()
            node_group = QgsLayerTreeGroup(videoPath)
            #If you have a loaded project, insert the group
            #on top of it.
            root.insertChildNode(0, node_group)

            self.fileName = videoPath
            self.playlist = QMediaPlaylist()

            self.isStreaming = False
            if "://" in self.fileName:
                self.isStreaming = True

            if self.isStreaming:
                # show video from splitter (port +1)
                oldPort = videoPath.split(":")[2]
                newPort = str(int(oldPort) + 10)                
                proto = videoPath.split(":")[0]
                url = QUrl(proto + "://127.0.0.1:" + newPort)
            else:
                url = QUrl.fromLocalFile(videoPath)
            qgsu.showUserAndLogMessage("", "Added: " + str(url), onlyLog=True)

            self.playlist.addMedia(QMediaContent(url))
            self.player.setPlaylist(self.playlist)

            self.setWindowTitle(QCoreApplication.translate(
                "QgsFmvPlayer", 'Playing : ') + os.path.basename(videoPath))

            CreateVideoLayers(hasElevationModel(), videoPath)

            self.HasFileAudio = True
            if not self.HasAudio(videoPath):
                self.actionAudio.setEnabled(False)
                self.actionSave_Audio.setEnabled(False)
                self.HasFileAudio = False

            self.playClicked(True)

        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", 'Open Video File : '), str(e), level=QGis.Warning)

    def ReciconUpdate(self, _):
        ''' Record Button Icon Effect '''
        self.btn_Rec.setIcon(QIcon(self.RecGIF.currentPixmap()))

    def StopRecordAnimation(self):
        '''Stop record gif animation'''
        self.RecGIF.frameChanged.disconnect(self.ReciconUpdate)
        self.RecGIF.stop()
        self.btn_Rec.setIcon(QIcon(":/imgFMV/images/record.png"))

    def RecordVideo(self, value):
        '''Cut Video
        @type value: bool
        @param value: Button checked state
        '''
        currentTime = _seconds_to_time(self.currentInfo)

        if value is False:
            self.endRecord = currentTime
            _, file_extension = os.path.splitext(self.fileName)

            out, _ = askForFiles(self, QCoreApplication.translate(
                "QgsFmvPlayer", "Save video record"),
                isSave=True,
                exts=file_extension[1:])

            if not out:
                self.StopRecordAnimation()
                return

            taskRecordVideo = QgsTask.fromFunction('Record Video Task',
                                                   self.RecordVideoTask,
                                                   infile=self.fileName,
                                                   startRecord=self.startRecord,
                                                   endRecord=self.endRecord,
                                                   out=out,
                                                   on_finished=self.finishedTask,
                                                   flags=QgsTask.CanCancel)

            QgsApplication.taskManager().addTask(taskRecordVideo)

        else:
            self.startRecord = currentTime
            self.RecGIF.frameChanged.connect(self.ReciconUpdate)
            self.RecGIF.start()
        return

    def RecordVideoTask(self, task, infile, startRecord, endRecord, out):
        ''' Record Video Task '''
        p = _spawn(['-i', infile,
                    '-ss', startRecord,
                    '-to', endRecord,
                    '-c', 'copy',
                    '-map', '0',
                    out])
        p.communicate()
        self.StopRecordAnimation()
        if task.isCanceled():
            return None
        return {'task': task.description()}

    def videoAvailableChanged(self, available):
        '''Buttons for video available
        @type available: bool
        '''
        # self.btn_Color.setEnabled(available)
        self.btn_CaptureFrame.setEnabled(available)
        self.gb_PlayerControls.setEnabled(available)
        return

    def toggleGroup(self, state):
        '''Toggle GroupBox
        @type state: bool
        @param state: Expand/collapse QGroupBox
        '''
        sender = self.sender()
        if state:
            sender.setFixedHeight(sender.sizeHint().height())
        else:
            sender.setFixedHeight(15)

    def fakeStop(self):
        '''self.player.stop() make a black screen and not reproduce it again'''
        self.player.pause()
        self.StartMedia()
        self.btn_play.setIcon(self.playIcon)

    def RemoveMeasures(self):
        ''' Remove video measurements '''
        # Remove Measure when video is playing
        # Uncheck Measure Distance
        self.videoWidget.ResetDrawMeasureDistance()
        self.actionMeasureDistance.setChecked(False)
        self.videoWidget.SetMeasureDistance(False)
        # Uncheck Measure Area
        self.videoWidget.ResetDrawMeasureArea()
        self.actionMeasureArea.setChecked(False)
        self.videoWidget.SetMeasureArea(False)

        self.staticDraw = False

    def playClicked(self, _):
        ''' Stop and Play video '''
        if self.playerState in (QMediaPlayer.StoppedState,
                                QMediaPlayer.PausedState):
            self.btn_play.setIcon(self.pauseIcon)

            if self.staticDraw:
                self.RemoveMeasures()

            # Play Video
            self.player.play()
        elif self.playerState == QMediaPlayer.PlayingState:
            self.btn_play.setIcon(self.playIcon)
            self.player.pause()
        QApplication.processEvents()

    def seek(self, seconds):
        '''
        Slider Move
        @type seconds:  String
        '''
        self.player.setPosition(seconds * 1000)
        self.showMoveTip(seconds)

    def convertVideo(self):
        '''Convert Video To Other Format '''
        out, _ = askForFiles(self, QCoreApplication.translate(
            "QgsFmvPlayer", "Save Video as..."),
            isSave=True,
            exts=["mp4", "ogg", "avi", "mkv", "webm", "flv", "mov", "mpg", "mp3"])

        if not out:
            return

        # TODO : Make Correct format Conversion and embebed metadata
        info = self.converter.probeInfo(self.fileName)
        if info is not None:
            if self.HasFileAudio:
                audio_codec = info.audio.codec
                audio_samplerate = info.audio.audio_samplerate
                audio_channels = info.audio.audio_channels

            video_codec = info.video.codec
            video_width = info.video.video_width
            video_height = info.video.video_height
            video_fps = info.video.video_fps

        _, out_ext = os.path.splitext(out)

        if self.HasFileAudio:
            options = {
                'format': out_ext[1:],
                'audio': {
                    'codec': audio_codec,
                    'samplerate': audio_samplerate,
                    'channels': audio_channels
                },
                'video': {
                    'codec': video_codec,
                    'width': video_width,
                    'height': video_height,
                    'fps': video_fps
                }}
        else:
            options = {
                'format': out_ext[1:],
                'video': {
                    'codec': video_codec,
                    'width': video_width,
                    'height': video_height,
                    'fps': video_fps
                }}

        taskConvertVideo = QgsTask.fromFunction('Converting Video Task',
                                                self.converter.convert,
                                                infile=self.fileName, outfile=out, options=options, twopass=False,
                                                on_finished=self.finishedTask,
                                                flags=QgsTask.CanCancel)

        QgsApplication.taskManager().addTask(taskConvertVideo)

    def CreateBitratePlot(self):
        ''' Create video Plot Bitrate Thread '''
        sender = self.sender().objectName()

        if sender == "actionAudio":
            taskactionAudio = QgsTask.fromFunction('Show Audio Bitrate',
                                                   self.BitratePlot.CreatePlot,
                                                   fileName=self.fileName, output=None, t='audio',
                                                   on_finished=self.finishedTask,
                                                   flags=QgsTask.CanCancel)

            QgsApplication.taskManager().addTask(taskactionAudio)

        elif sender == "actionVideo":
            taskactionVideo = QgsTask.fromFunction('Show Video Bitrate',
                                                   self.BitratePlot.CreatePlot,
                                                   fileName=self.fileName, output=None, t='video',
                                                   on_finished=self.finishedTask,
                                                   flags=QgsTask.CanCancel)

            QgsApplication.taskManager().addTask(taskactionVideo)

        elif sender == "actionSave_Audio":
            fileaudio, _ = askForFiles(self, QCoreApplication.translate(
                "QgsFmvPlayer", "Save Audio Bitrate Plot"),
                isSave=True,
                exts=["png", "pdf", "pgf", "eps", "ps", "raw", "rgba", "svg", "svgz"])

            if not fileaudio:
                return

            taskactionSave_Audio = QgsTask.fromFunction('Save Action Audio Bitrate',
                                                        self.BitratePlot.CreatePlot,
                                                        fileName=self.fileName, output=fileaudio, t='audio',
                                                        on_finished=self.finishedTask,
                                                        flags=QgsTask.CanCancel)

            QgsApplication.taskManager().addTask(taskactionSave_Audio)

        elif sender == "actionSave_Video":
            filevideo, _ = askForFiles(self, QCoreApplication.translate(
                "QgsFmvPlayer", "Save Video Bitrate Plot"),
                isSave=True,
                exts=["png", "pdf", "pgf", "eps", "ps", "raw", "rgba", "svg", "svgz"])

            if not filevideo:
                return

            taskactionSave_Video = QgsTask.fromFunction('Save Action Video Bitrate',
                                                        self.BitratePlot.CreatePlot,
                                                        fileName=self.fileName, output=filevideo, t='video',
                                                        on_finished=self.finishedTask,
                                                        flags=QgsTask.CanCancel)

            QgsApplication.taskManager().addTask(taskactionSave_Video)

    def finishedTask(self, e, result=None):
        """ Common finish task function """
        if e is None:
            if result is None:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvPlayer", 'Completed with no exception and no result '
                    '(probably manually canceled by the user)'), level=QGis.Warning)
            else:
                if "Georeferencing" in result['task']:
                    return
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvPlayer", "Succesfully " + result['task'] + "!"))
                if "Bitrate" in result['task']:
                    self.matplot = ShowPlot(self.BitratePlot.bitrate_data, self.BitratePlot.frame_count, self.fileName, self.BitratePlot.output)
                if result['task'] == 'Show Video Info Task':
                    self.showVideoInfoDialog(self.converter.bytes_value)
                if result['task'] == 'Save Current Georeferenced Frame Task':
                    buttonReply = qgsu.CustomMessage(
                        QCoreApplication.translate("QgsFmvPlayer", "Information"),
                        QCoreApplication.translate("QgsFmvPlayer", "Do you want to load the layer?"),
                        icon="Information")
                    if buttonReply == QMessageBox.Yes:
                        file = result['file']
                        root, _ = os.path.splitext(file)
                        layer = QgsRasterLayer(file, root)
                        QgsProject.instance().addMapLayer(layer)
                    return
        else:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Failed " + result['task'] + "!"), level=QGis.Warning)
            raise e

    def ExtractAllFrames(self):
        """ Extract All Video Frames Task """
        directory = askForFolder(self, QCoreApplication.translate(
            "QgsFmvPlayer", "Save all Frames"),
            options=QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly)

        if directory:
            taskExtractAllFrames = QgsTask.fromFunction('Save All Frames Task',
                                                        self.SaveAllFrames,
                                                        fileName=self.fileName, directory=directory,
                                                        on_finished=self.finishedTask,
                                                        flags=QgsTask.CanCancel)

            QgsApplication.taskManager().addTask(taskExtractAllFrames)
        return

    def SaveAllFrames(self, task, fileName, directory):
        ''' Extract and save all video frames into directory '''
        vidcap = cv2.VideoCapture(fileName)
        length = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
        count = 0
        while not task.isCanceled():
            _, image = vidcap.read()
            cv2.imwrite(directory + "\\frame_%d.jpg" %
                        count, image)  # save frame as JPEG file
            task.setProgress(count * 100 / length)
            count += 1
        vidcap.release()
        cv2.destroyAllWindows()
        if task.isCanceled():
            return None
        return {'task': task.description()}

    def ExtractCurrentFrame(self):
        """ Extract Current Frame Task
            The drawings are saved by default
        """
        # image = self.videoWidget.currentFrame()   # without drawings
        image = BurnDrawingsImage(self.videoWidget.currentFrame(), self.videoWidget.grab(self.videoWidget.surface.videoRect()).toImage())

        output, _ = askForFiles(self, QCoreApplication.translate(
            "QgsFmvPlayer", "Save Current Frame"),
            isSave=True,
            exts=["png", "jpg", "bmp", "tiff"])

        if not output:
            return

        taskCurrentFrame = QgsTask.fromFunction('Save Current Frame Task',
                                                self.SaveCapture,
                                                image=image, output=output,
                                                on_finished=self.finishedTask,
                                                flags=QgsTask.CanCancel)

        QgsApplication.taskManager().addTask(taskCurrentFrame)
        return

    def SaveCapture(self, task, image, output):
        ''' Save Current Frame '''
        image.save(output)
        if task.isCanceled():
            return None
        return {'task': task.description()}

    def ExtractCurrentGeoFrame(self):
        """ Extract Current GeoReferenced Frame Task """
        image = BurnDrawingsImage(self.videoWidget.currentFrame(), self.videoWidget.grab(self.videoWidget.surface.videoRect()).toImage())

        geotransform = GetGeotransform_affine()
        position = str(self.player.position())
        directory = askForFolder(self, QCoreApplication.translate(
            "QgsFmvPlayer", "Save Current Georeferenced Frame"),
            options=QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly)

        if not directory:
            return

        taskCurrentGeoFrame = QgsTask.fromFunction('Save Current Georeferenced Frame Task',
                                                   self.SaveGeoCapture,
                                                   image=image, output=directory, p=position, geotransform=geotransform,
                                                   on_finished=self.finishedTask,
                                                   flags=QgsTask.CanCancel)

        QgsApplication.taskManager().addTask(taskCurrentGeoFrame)
        return

    def SaveGeoCapture(self, task, image, output, p, geotransform):
        ''' Save Current GeoReferenced Frame '''
        ext = ".tiff"
        t = "out_" + p + ext
        name = "g_" + p
        src_file = os.path.join(output, t)

        image.save(src_file)

        # Opens source dataset
        src_ds = gdal.OpenEx(src_file, gdal.OF_RASTER |
                             gdal.OF_READONLY, open_options=['NUM_THREADS=ALL_CPUS'])

        # Open destination dataset
        dst_filename = os.path.join(output, name + ext)
        dst_ds = gdal.GetDriverByName("GTiff").CreateCopy(dst_filename, src_ds, 0,
                                                          options=['TILED=NO', 'BIGTIFF=NO', 'COMPRESS_OVERVIEW=DEFLATE', 'COMPRESS=LZW', 'NUM_THREADS=ALL_CPUS', 'predictor=2'])
        src_ds = None
        # Get raster projection
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)

        # Set projection
        dst_ds.SetProjection(srs.ExportToWkt())

        # Set location
        dst_ds.SetGeoTransform(geotransform)
        dst_ds.GetRasterBand(1).SetNoDataValue(0)
        dst_ds.FlushCache()
        # Close files
        dst_ds = None
        os.remove(src_file)
        if task.isCanceled():
            return None
        return {'task': task.description(),
                'file': dst_filename}

    def OpenQgsFmvMetadata(self):
        """ Open Metadata Dock """
        if self.metadataDlg is None:
            self.metadataDlg = QgsFmvMetadata(player=self)
            self.addDockWidget(Qt.RightDockWidgetArea, self.metadataDlg)
            self.metadataDlg.show()
        else:
            self.metadataDlg.show()

        self.addMetadata(self.data)
        return

    def OpenOptions(self):
        """ Open Options Dialog """
        self.Options = FmvOptions()
        self.Options.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.Options.show()

    def showVideoInfoDialog(self, outjson):
        """Show Video Information Dialog
        @type outjson: QByteArray
        @param outjson: Json file data
        """
        view = QTreeView()
        model = QJsonModel()
        view.setModel(model)
        model.loadJsonFromConsole(outjson)

        self.VideoInfoDialog = QDialog(self, Qt.Window | Qt.WindowCloseButtonHint)
        self.VideoInfoDialog.setWindowTitle(QCoreApplication.translate(
            "QgsFmvPlayer", "Video Information : ") + self.fileName)
        self.VideoInfoDialog.setWindowIcon(
            QIcon(":/imgFMV/images/video-info.png"))

        self.verticalLayout = QVBoxLayout(self.VideoInfoDialog)
        self.verticalLayout.addWidget(view)
        view.expandAll()
        view.header().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.VideoInfoDialog.resize(500, 400)
        self.VideoInfoDialog.show()

    def RemoveAllData(self):
        ''' Remove All TOC/Canvas Data '''
        # Remove group
        RemoveGroupByName(self.fileName)
        # Reset internal variables
        ResetData()
        # Remove Canvas RubberBands
        self.videoWidget.RemoveCanvasRubberbands()
        # Remove Video objects
        self.videoWidget.RemoveVideoDrawings()

    def closeEvent(self, event):
        """ Close Event """
        # Ask when the player is closed
        buttonReply = qgsu.CustomMessage("QGIS FMV",
                                         QCoreApplication.translate("QgsFmvPlayer", "If you close or reopen the video all the information will be erased."),
                                         QCoreApplication.translate("QgsFmvPlayer", "Do you want to close or reopen it?"),
                                         icon="Information")
        if buttonReply == QMessageBox.No:
            event.ignore()
            return

        # Stop Video
        self.stop()

        # Close splitter
        # If we don't close it and open a new video, the metadata shown are the old.
        # TODO: NOT WORK
        try:
            self.meta_reader.dispose()
        except Exception:
            None
        # Toggle Active flag in metadata dock
        self.parent.ToggleActiveFromTitle()

        # Remove All Data
        self.RemoveAllData()

        # We close metadata dock if it's open
        try:
            self.metadataDlg.hide()
        except Exception:
            None

        # We close matplot graphics if it's open
        try:
            self.matplot.close()
        except Exception:
            None

        # We close Video info json if it's open
        try:
            self.VideoInfoDialog.hide()
        except Exception:
            None

        # We close Options dialog if it's open
        try:
            self.Options.hide()
        except Exception:
            None

        # Restore Filters State
        self.videoWidget.RestoreFilters()
