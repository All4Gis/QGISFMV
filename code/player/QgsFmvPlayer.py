# -*- coding: utf-8 -*-
import os.path
import threading

from PyQt5.QtCore import (QUrl,
                          QThread,
                          QPoint,
                          QCoreApplication,
                          Qt,
                          QMetaObject,
                          Q_ARG)
from PyQt5.QtGui import QIcon, QMovie
from PyQt5.QtMultimedia import QMediaPlayer, QMediaPlaylist, QMediaContent
from PyQt5.QtWidgets import (QToolTip,
                             QAbstractSlider,
                             QHeaderView,
                             QStyleOptionSlider,
                             QTreeView,
                             QVBoxLayout,
                             QDialog,
                             QMainWindow,
                             QFileDialog,
                             QMessageBox,
                             QMenu,
                             QApplication,
                             QTableWidgetItem)
from QGIS_FMV.converter.Converter import Converter
from QGIS_FMV.gui.ui_FmvPlayer import Ui_PlayerWindow
from QGIS_FMV.klvdata.streamparser import StreamParser
from QGIS_FMV.player.QgsFmvMetadata import QgsFmvMetadata
from QGIS_FMV.utils.QgsFmvLayers import (CreateVideoLayers,
                                         RemoveVideoLayers,
                                         CreateGroupByName,
                                         RemoveGroupByName)
from QGIS_FMV.utils.QgsFmvUtils import (callBackMetadataThread,
                                        _spawn,
                                        UpdateLayers,
                                        _seconds_to_time,
                                        _seconds_to_time_frac)
from QGIS_FMV.utils.QgsFmvUtils import askForFiles
from QGIS_FMV.utils.QgsJsonModel import QJsonModel
from QGIS_FMV.utils.QgsPlot import CreatePlotsBitrate
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.video.QgsColor import ColorDialog
from QGIS_FMV.video.QgsVideoProcessor import ExtractFramesProcessor
from QGIS_FMV.videoStremaing.TestClient import UDPClient
from qgis.core import Qgis as QGis


try:
    from pydevd import *
except ImportError:
    None

try:
    import numpy
    import matplotlib.pyplot as matplot
except ImportError:
    None


class QgsFmvPlayer(QMainWindow, Ui_PlayerWindow):
    """ Video Player Class """

    def __init__(self, iface, path=None, parent=None):
        """ Constructor """
        super(QgsFmvPlayer, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface
        self.fileName = None
        self.metadataDlg = None
        self.createingMosaic = False
        self.currentInfo = 0.0

        self.RecGIF = QMovie(":/imgFMV/images/record.gif")

        self.videoWidget2.setVisible(False)

        self.resize(730, 350)

        self.videoWidget.customContextMenuRequested[QPoint].connect(
            self.contextMenuRequested)
#         self.videoWidget2.customContextMenuRequested[QPoint].connect(
#             self.contextMenuRequested)

        self.duration = 0
        self.playerMuted = False
        self.HasFileAudio = False

        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.player.setNotifyInterval(700)  # Metadata Callback Interval
        self.pass_time = 0.08
        self.playlist = QMediaPlaylist()

        self.player.setVideoOutput(
            self.videoWidget.videoSurface())  # Abstract Surface

#         self.player.setVideoOutput(
#             self.videoWidget2)  # Standar Surface

        self.player.durationChanged.connect(self.durationChanged)
        self.player.positionChanged.connect(self.positionChanged)
        self.player.mediaStatusChanged.connect(self.statusChanged)

        self.player.stateChanged.connect(self.setCurrentState)

        self.playerState = QMediaPlayer.StoppedState
        self.playFile(path)

        self.sliderDuration.setRange(0, self.player.duration() / 1000)

        self.volumeSlider.setValue(self.player.volume())
        self.volumeSlider.enterEvent = self.showVolumeTip

        if self.metadataDlg is None:
            self.metadataDlg = QgsFmvMetadata(parent=self, player=self)
            self.addDockWidget(Qt.RightDockWidgetArea, self.metadataDlg)
            self.metadataDlg.setMinimumWidth(500)
            self.metadataDlg.hide()

    def HasMetadata(self, videoPath):
        """ Check if video have Metadata or not """
        try:
            p = _spawn(['-i', videoPath,
                        '-map', 'data-re',
                        '-codec', 'copy',
                        '-f', 'data', '-'])

            stdout_data, _ = p.communicate()

            if stdout_data == b'':
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvPlayer", "This video don't have Metadata ! "),
                    level=QGis.Info)
                return False

            return True
        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Metadata Callback Failed! : "), str(e),
                level=QGis.Info)

    def HasAudio(self, videoPath):
        """ Check if video have Metadata or not """
        try:
            p = _spawn(['-i', videoPath,
                        '-show_streams', '-select_streams', 'a',
                        '-loglevel', 'error'], t="probe")

            stdout_data, _ = p.communicate()

            if stdout_data == b'':
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvPlayer", "This video don't have Audio ! "),
                    level=QGis.Info)
                return False

            return True
        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Audio check Failed! : "), str(e),
                level=QGis.Info)

    def callBackMetadata(self, currentTime, nextTime):
        """ Metadata CallBack """
        try:
            t = callBackMetadataThread(cmds=['-i', self.fileName,
                                             '-ss', currentTime,
                                             '-to', nextTime,
                                             '-map', 'data-re',
                                             '-f', 'data', '-'])
            t.start()
            t.join(1)
            if t.is_alive():
                t.p.terminate()
                t.join()
            if t.stdout == b'':
                return

            for packet in StreamParser(t.stdout):
                try:
                    self.addMetadata(packet.MetadataList())
                    UpdateLayers(packet, parent=self,
                                 mosaic=self.createingMosaic)
                    self.iface.mapCanvas().refresh()
                    QApplication.processEvents()
                    return
                except Exception as e:
                    None
        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Metadata Callback Failed! : "), str(e), level=QGis.Info)

    def addMetadata(self, packet):
        ''' Add Metadata to List '''
        self.clearMetadata()
        row = 0
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
        if not self.KillAllProcessors():
            return
        out_json, _ = QFileDialog.getSaveFileName(
            self, "Save File", "", "Json Files (*.json)")
        if out_json == "":
            return
        try:
            self.infoJson = Converter()
            self.infoJsonT = QThread()

            self.infoJson.moveToThread(
                self.infoJsonT)

            self.infoJson.finished.connect(
                self.QThreadFinished)

            self.infoJson.error.connect(self.QThreadError)

            self.infoJson.progress.connect(
                self.progressBarProcessor.setValue)

            self.infoJsonT.start(QThread.LowPriority)

            QMetaObject.invokeMethod(self.infoJson, 'probeToJson',
                                     Qt.QueuedConnection, Q_ARG(
                                         str, self.fileName),
                                     Q_ARG(
                                         str, out_json))

        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Error saving Json : " + str(e)))
            self.QThreadFinished("probeToJson", "Closing ProbeToJson")

    def showVideoInfo(self):
        ''' Show default probe info '''
        try:

            self.showInfo = Converter()
            self.showInfoT = QThread()

            self.showInfo.moveToThread(
                self.showInfoT)

            self.showInfo.finishedJson.connect(
                self.QThreadFinished)

            self.showInfo.error.connect(self.QThreadError)

            self.showInfo.progress.connect(
                self.progressBarProcessor.setValue)

            self.showInfoT.start(QThread.LowPriority)

            QMetaObject.invokeMethod(self.showInfo, 'probeShow',
                                     Qt.QueuedConnection, Q_ARG(
                                         str, self.fileName))

        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Error Info Show : " + str(e)))
            self.QThreadFinished("probeShow", "Closing Probe")
        return

    def state(self):
        ''' Return Current State '''
        return self.playerState

    def setCurrentState(self, state):
        ''' Set Current State '''
        if state != self.playerState:
            self.playerState = state
            if state == QMediaPlayer.StoppedState:
                self.btn_play.setIcon(QIcon(":/imgFMV/images/play-arrow.png"))

        return

    def showColorDialog(self):
        ''' Show Color dialog '''
        self.ColorDialog = ColorDialog(parent=self)
        self.ColorDialog.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        # Fail if not uncheked
        self.actionMagnifying_glass.setChecked(False)
        self.actionZoom_Rectangle.setChecked(False)
        self.toggleVideoWidget(top="standar")
        self.ColorDialog.exec_()
        QApplication.processEvents()
        self.ColorDialog.contrastSlider.setValue(80)
        self.ColorDialog.contrastSlider.triggerAction(
            QAbstractSlider.SliderMove)
        return

    def createMosaic(self, value):
        ''' Function for create Video Mosaic '''
        home = os.path.expanduser("~")

        qgsu.createFolderByName(home, "QGIS_FMV")
        homefmv = os.path.join(home, "QGIS_FMV")
        root, _ = os.path.splitext(os.path.basename(self.fileName))
        qgsu.createFolderByName(homefmv, root)
        self.createingMosaic = value
        # Create Group
        CreateGroupByName()
        return

    def contextMenuRequested(self, point):
        ''' Context Menu Video '''
        menu = QMenu()

        actionColors = menu.addAction(
            QCoreApplication.translate("QgsFmvPlayer", "Color Options"))
        actionColors.setShortcut("Ctrl+May+C")
        actionColors.triggered.connect(self.showColorDialog)

        actionMute = menu.addAction(
            QCoreApplication.translate("QgsFmvPlayer", "Mute/Unmute"))
        actionMute.setShortcut("Ctrl+May+U")
        actionMute.triggered.connect(self.setMuted)

        menu.addSeparator()
        actionAllFrames = menu.addAction(
            QCoreApplication.translate("QgsFmvPlayer", "Extract All Frames"))
        actionAllFrames.setShortcut("Ctrl+May+A")
        actionAllFrames.triggered.connect(self.ExtractAllFrames)

        actionCurrentFrames = menu.addAction(
            QCoreApplication.translate("QgsFmvPlayer",
                                       "Extract Current Frame"))
        actionCurrentFrames.setShortcut("Ctrl+May+Q")
        actionCurrentFrames.triggered.connect(self.ExtractCurrentFrame)

        menu.addSeparator()
        actionShowMetadata = menu.addAction(
            QCoreApplication.translate("QgsFmvPlayer", "Show Metadata"))
        actionShowMetadata.setShortcut("Ctrl+May+M")
        actionShowMetadata.triggered.connect(self.OpenQgsFmvMetadata)

        menu.exec_(self.mapToGlobal(point))

    # Start Snnipet FILTERS
    def grayFilter(self, value):
        ''' Gray Video Filter '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetGray(value)
        self.videoWidget.UpdateSurface()
        return

    def edgeFilter(self, value):
        ''' Edge Detection Video Filter '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetEdgeDetection(value)
        self.videoWidget.UpdateSurface()
        return

    def invertColorFilter(self, value):
        ''' Invert Color Video Filter '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetInvertColor(value)
        self.videoWidget.UpdateSurface()
        return

    def autoContrastFilter(self, value):
        ''' Auto Contrast Video Filter '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetAutoContrastFilter(value)
        self.videoWidget.UpdateSurface()
        return

    def monoFilter(self, value):
        ''' Filter Mono Video '''
        self.UncheckFilters(self.sender(), value)
        self.videoWidget.SetMonoFilter(value)
        self.videoWidget.UpdateSurface()
        return

    def magnifier(self, value):
        ''' Magnifier Glass Utils '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetMagnifier(value)
        self.videoWidget.UpdateSurface()
        return

    def zoomRect(self, value):
        ''' Zoom Rectangle Utils '''
        self.UncheckUtils(self.sender(), value)
        self.videoWidget.SetZoomRect(value)
        self.videoWidget.UpdateSurface()
        return

    def UncheckUtils(self, sender, value):
        ''' Uncheck Utils Video '''
        self.toggleVideoWidget()
        QApplication.processEvents()
        name = sender.objectName()
        self.actionMagnifying_glass.setChecked(
            True if name == "actionMagnifying_glass" else False)
        self.actionZoom_Rectangle.setChecked(
            True if name == "actionZoom_Rectangle" else False)

        sender.setChecked(value)
        return

    def UncheckFilters(self, sender, value):
        ''' Uncheck Filters Video '''
        self.toggleVideoWidget()
        name = sender.objectName()

        self.actionGray.setChecked(True if name == "actionGray" else False)
        self.actionInvert_Color.setChecked(
            True if name == "actionInvert_Color" else False)
        self.actionMono_Filter.setChecked(
            True if name == "actionMono_Filter" else False)
        self.actionCanny_edge_detection.setChecked(
            True if name == "actionCanny_edge_detection" else False)
        self.actionAuto_Contrast_Filter.setChecked(
            True if name == "actionAuto_Contrast_Filter" else False)

        self.videoWidget.SetGray(True if name == "actionGray" else False)
        self.videoWidget.SetEdgeDetection(
            True if name == "actionCanny_edge_detection" else False)
        self.videoWidget.SetInvertColor(
            True if name == "actionInvert_Color" else False)
        self.videoWidget.SetMonoFilter(
            True if name == "actionMono_Filter" else False)
        self.videoWidget.SetAutoContrastFilter(
            True if name == "actionAuto_Contrast_Filter" else False)

        sender.setChecked(value)
        return
    # End Snnipet FILTERS

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

    # TODO: SI LE DOY AL STOP LUEGO NO SE VE EL VIDEO (SE QUEDA NEGRO)
    def stop(self):
        ''' Stop video'''
        # Prevent Error in a Video Utils.Disable Magnifier and zoom
        if self.actionMagnifying_glass.isChecked():
            self.actionMagnifying_glass.trigger()
        elif self.actionZoom_Rectangle.isChecked():
            self.actionZoom_Rectangle.trigger()
        # Stop Video
        self.player.stop()
        return

    def volume(self):
        ''' Volume Slider '''
        return self.volumeSlider.value()

    def setVolume(self, volume):
        ''' Tooltip and set Volume value and icon '''
        self.player.setVolume(volume)
        self.showVolumeTip(volume)
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
        ''' Button AutoRepeat Video '''
        if checked:
            self.playlist.setPlaybackMode(QMediaPlaylist.Loop)
        else:
            self.playlist.setPlaybackMode(QMediaPlaylist.Sequential)
        return

    def showVolumeTip(self, _):
        ''' Volume Slider Tooltip Trick '''
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
        ''' Player Silder Move Tooptip Trick '''
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
        ''' Duration video change signal '''
        duration /= 1000
        self.duration = duration
        self.sliderDuration.setMaximum(duration)

    def positionChanged(self, progress):
        ''' Current Video position change '''
        progress /= 1000

        if not self.sliderDuration.isSliderDown():
            self.sliderDuration.setValue(progress)

        self.updateDurationInfo(progress)

    def updateDurationInfo(self, currentInfo):
        ''' Update labels duration Info and CallBack Metadata '''
        duration = self.duration
        self.currentInfo = currentInfo
        if currentInfo or duration:

            totalTime = _seconds_to_time(duration)
            currentTime = _seconds_to_time(currentInfo)
            tStr = currentTime + " / " + totalTime

            nextTime = currentInfo + self.pass_time
            currentTimeInfo = _seconds_to_time_frac(currentInfo)
            nextTimeInfo = _seconds_to_time_frac(nextTime)
            # Metadata CallBack
            self.callBackMetadata(currentTimeInfo, nextTimeInfo)

        else:
            tStr = ""

        self.labelDuration.setText(tStr)

    def handleCursor(self, status):
        ''' Change cursor '''
        if status in (QMediaPlayer.LoadingMedia,
                      QMediaPlayer.BufferingMedia,
                      QMediaPlayer.StalledMedia):
            self.setCursor(Qt.BusyCursor)
        else:
            self.unsetCursor()

    def statusChanged(self, status):
        ''' Signal Status video change '''
        self.handleCursor(status)
        if status is QMediaPlayer.LoadingMedia or status is QMediaPlayer.StalledMedia or status is QMediaPlayer.InvalidMedia:
            self.videoAvailableChanged(False)
        elif status == QMediaPlayer.InvalidMedia:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", self.player.errorString()), level=QGis.Warning)
            self.videoAvailableChanged(False)
        else:
            self.videoAvailableChanged(True)

    def toggleVideoWidget(self, top="custom"):
        ''' Toggle visibility video Widgets '''
        if top != "custom":
            # self.videoWidget.setVisible(False)
            # self.videoWidget2.setVisible(True)
            state = self.state
            self.player.setVideoOutput(
                self.videoWidget)  # Standar Surface
            self.resetState(state)
            self.videoWidget.setContrast(80)
            self.videoWidget.update()
            self.videoWidget.setContrast(81)
            return
        # self.videoWidget2.setVisible(False)
        # self.videoWidget.setVisible(True)
        state = self.state
        self.player.setVideoOutput(
            self.videoWidget.videoSurface())  # Abstract Surface
        self.resetState(state)
        return

    def resetState(self, state):
        ''' Reset Video State '''
        if state == QMediaPlayer.PausedState:
            self.player.play()
            self.player.pause()
        elif state == QMediaPlayer.StoppedState:
            self.player.play()
            self.player.stop()

    def playFile(self, videoPath):
        ''' Play file from path '''
        try:
            RemoveVideoLayers()
            RemoveGroupByName()
#             settrace()
#             if "udp://" in videoPath:
#                 host, port = videoPath.split("://")[1].split(":")
#                 receiver = UDPClient(host, int(port), type="udp")
#                 receiver.show()
#                 self.close()
#                 return
#             if "tcp://" in videoPath:
#                 host, port = videoPath.split("://")[1].split(":")
#                 receiver = UDPClient(host, port, type="tcp")
#                 receiver.show()
#                 self.close()
#                 return
            self.fileName = videoPath
            self.playlist = QMediaPlaylist()
            url = QUrl.fromLocalFile(videoPath)
            self.playlist.addMedia(QMediaContent(url))
            self.player.setPlaylist(self.playlist)

            self.setWindowTitle(QCoreApplication.translate(
                "QgsFmvPlayer", 'Playing : ') + os.path.basename(os.path.normpath(videoPath)))

            if self.HasMetadata(videoPath):
                CreateVideoLayers()
                self.clearMetadata()
                self.lb_cursor_coord.setText(
                    "<span style='font-size:10pt; font-weight:bold;'>Lon :</span>"
                    +
                    "<span style='font-size:9pt; font-weight:normal;'>Null</span>"
                    +
                    "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>"
                    +
                    "<span style='font-size:9pt; font-weight:normal;'>Null</span>")
            else:
                self.btn_GeoReferencing.setEnabled(False)

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

    def RecordVideo(self, value):
        ''' Cut Video '''
        currentTime = _seconds_to_time(self.currentInfo)

        if value is False:
            self.endRecord = currentTime
            _, file_extension = os.path.splitext(self.fileName)
            out, _ = QFileDialog.getSaveFileName(
                self, "Save As", "", file_extension)
            if not out:
                self.RecGIF.frameChanged.disconnect(self.ReciconUpdate)
                self.RecGIF.stop()
                self.btn_Rec.setIcon(QIcon(":/imgFMV/images/record.png"))
                return False

            lfn = out.lower()
            if not lfn.endswith((file_extension)):
                out += file_extension

            p = _spawn(['-i', self.fileName,
                        '-ss', self.startRecord,
                        '-to', self.endRecord,
                        '-c', 'copy',
                        out])
            p.communicate()
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Save file succesfully!"))

            self.RecGIF.frameChanged.disconnect(self.ReciconUpdate)
            self.RecGIF.stop()
            self.btn_Rec.setIcon(QIcon(":/imgFMV/images/record.png"))
        else:
            self.startRecord = currentTime
            self.RecGIF.frameChanged.connect(self.ReciconUpdate)
            self.RecGIF.start()
        return

    def videoAvailableChanged(self, available):
        ''' Buttons for video available '''
        # self.btn_Color.setEnabled(available)
        self.btn_CaptureFrame.setEnabled(available)
        self.gb_PlayerControls.setEnabled(available)
        return

    def toggleGroup(self, state):
        ''' Toggle GroupBox '''
        sender = self.sender()
        if state:
            sender.setFixedHeight(sender.sizeHint().height())
        else:
            sender.setFixedHeight(15)

    def playClicked(self, _):
        ''' Stop and Play video '''
        if self.playerState in (QMediaPlayer.StoppedState,
                                QMediaPlayer.PausedState):
            self.btn_play.setIcon(QIcon(":/imgFMV/images/pause.png"))
            self.player.play()
        elif self.playerState == QMediaPlayer.PlayingState:
            self.btn_play.setIcon(QIcon(":/imgFMV/images/play-arrow.png"))
            self.player.pause()

    def seek(self, seconds):
        '''Slider Move'''
        self.player.setPosition(seconds * 1000)
        self.showMoveTip(seconds)

    def convertVideo(self):
        '''Convert Video To Other Format '''
        if not self.KillAllProcessors():
            return
        sel = "mp4 Files (*.mp4)"
        out, _ = QFileDialog.getSaveFileName(
            self, "Save Video as...", None,
            "ogg files (*.ogg);;avi Files (*.avi);;mkv Files (*.mkv);;webm Files (*.webm);;flv Files (*.flv);;mov Files (*.mov);;mp4 Files (*.mp4);;mpg Files (*.mpg);;mp3 Files (*.mp3)",
            sel)

        if not out:
            return False

        lfn = out.lower()
        if not lfn.endswith((
            '.ogg',
            '.avi',
            '.mkv',
            '.webm',
            '.flv',
            '.mov',
            '.mp4',
            '.mp3',
                '.mpg')):
            # default.
            out += '.mp4'

        try:
            self.VPConverter = Converter()
            self.VPTConverter = QThread()

            self.VPConverter.moveToThread(
                self.VPTConverter)

            self.VPConverter.finished.connect(
                self.QThreadFinished)

            self.VPConverter.error.connect(self.QThreadError)

            self.VPConverter.progress.connect(
                self.progressBarProcessor.setValue)

            self.VPTConverter.start(QThread.LowPriority)

            # TODO : Make Correct format Conversion and embebed metadata
            info = self.VPConverter.probeInfo(self.fileName)
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
            QMetaObject.invokeMethod(self.VPConverter, 'convert',
                                     Qt.QueuedConnection, Q_ARG(
                                         str, self.fileName),
                                     Q_ARG(
                                         str, out),
                                     Q_ARG(
                                         dict, options),
                                     Q_ARG(
                                         bool, False))

        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Error converting video : " + str(e)))
            self.QThreadFinished("convert", "Closing convert")

    def ShowPlot(self, bitrate_data, frame_count, output=None):
        ''' Show plot,because show not work using threading '''
        matplot.figure().canvas.set_window_title(self.fileName)
        matplot.title("Stream Bitrate vs Time")
        matplot.xlabel("Time (sec)")
        matplot.ylabel("Frame Bitrate (kbit/s)")
        matplot.grid(True)
        # map frame type to color
        frame_type_color = {
            # audio
            'A': 'yellow',
            # video
            'I': 'red',
            'P': 'green',
            'B': 'blue'
        }

        global_peak_bitrate = 0.0
        global_mean_bitrate = 0.0

        # render charts in order of expected decreasing size
        for frame_type in ['I', 'P', 'B', 'A']:

            # skip frame type if missing
            if frame_type not in bitrate_data:
                continue

            # convert list of tuples to numpy 2d array
            frame_list = bitrate_data[frame_type]
            frame_array = numpy.array(frame_list)

            # update global peak bitrate
            peak_bitrate = frame_array.max(0)[1]
            if peak_bitrate > global_peak_bitrate:
                global_peak_bitrate = peak_bitrate

            # update global mean bitrate (using piecewise mean)
            mean_bitrate = frame_array.mean(0)[1]
            global_mean_bitrate += mean_bitrate * \
                (len(frame_list) / frame_count)

            # plot chart using gnuplot-like impulses
            matplot.vlines(
                frame_array[:, 0], [0], frame_array[:, 1],
                color=frame_type_color[frame_type],
                label="{} Frames".format(frame_type))

        self.progressBarProcessor.setValue(90)
        # calculate peak line position (left 15%, above line)
        peak_text_x = matplot.xlim()[1] * 0.15
        peak_text_y = global_peak_bitrate + \
            ((matplot.ylim()[1] - matplot.ylim()[0]) * 0.015)
        peak_text = "peak ({:.0f})".format(global_peak_bitrate)

        # draw peak as think black line w/ text
        matplot.axhline(global_peak_bitrate, linewidth=2, color='black')
        matplot.text(peak_text_x, peak_text_y, peak_text,
                     horizontalalignment='center', fontweight='bold', color='black')

        # calculate mean line position (right 85%, above line)
        mean_text_x = matplot.xlim()[1] * 0.85
        mean_text_y = global_mean_bitrate + \
            ((matplot.ylim()[1] - matplot.ylim()[0]) * 0.015)
        mean_text = "mean ({:.0f})".format(global_mean_bitrate)

        # draw mean as think black line w/ text
        matplot.axhline(global_mean_bitrate, linewidth=2, color='black')
        matplot.text(mean_text_x, mean_text_y, mean_text,
                     horizontalalignment='center', fontweight='bold',
                     color='black')

        matplot.legend()
        if output != "":
            matplot.savefig(output)
        else:
            matplot.show()

        self.matplot = matplot
        self.progressBarProcessor.setValue(100)

    def CreateBitratePlot(self):
        ''' Create video Plot Bitrate Thread '''
        if not self.KillAllProcessors():
            return
        try:
            self.VPBitratePlot = CreatePlotsBitrate()
            self.VPTBitratePlot = QThread()

            self.VPBitratePlot.moveToThread(
                self.VPTBitratePlot)

            self.VPBitratePlot.finished.connect(
                self.QThreadFinished)

            self.VPBitratePlot.return_fig.connect(
                self.ShowPlot)

            self.VPBitratePlot.error.connect(self.QThreadError)

            self.VPBitratePlot.progress.connect(
                self.progressBarProcessor.setValue)

            self.VPTBitratePlot.start(QThread.LowPriority)

            sender = self.sender().objectName()

            if sender == "actionAudio":
                QMetaObject.invokeMethod(self.VPBitratePlot, 'CreatePlot',
                                         Qt.QueuedConnection, Q_ARG(
                                             str, self.fileName),
                                         Q_ARG(
                                             str, None),
                                         Q_ARG(str, 'audio'))

            elif sender == "actionVideo":
                QMetaObject.invokeMethod(self.VPBitratePlot, 'CreatePlot',
                                         Qt.QueuedConnection, Q_ARG(
                                             str, self.fileName),
                                         Q_ARG(
                                             str, None),
                                         Q_ARG(str, 'video'))

            elif sender == "actionSave_Audio":
                selfilter = "Portable Network Graphics (*.png)"
                fileaudio, _ = QFileDialog.getSaveFileName(
                    self, "Save Audio Bitrate Plot", "",
                    "EPS Encapsulated Postscript (*.eps);;"
                    "PGF code for LaTex (*.pgf);;"
                    "Portable document format(*pdf);;"
                    "Portable Network Graphics (*.png);;"
                    "Postscript (*.ps);;"
                    "Raw RGBA bitmap (*.raw*.rgba);;"
                    "Scalable vector graphics (*.svg*.svgz)",
                    selfilter
                )
                if fileaudio == "":
                    return

                QMetaObject.invokeMethod(self.VPBitratePlot, 'CreatePlot',
                                         Qt.QueuedConnection, Q_ARG(
                                             str, self.fileName),
                                         Q_ARG(
                                             str, fileaudio),
                                         Q_ARG(str, 'audio'))

            elif sender == "actionSave_Video":
                selfilter = "Portable Network Graphics (*.png)"
                filevideo, _ = QFileDialog.getSaveFileName(
                    self, "Save Video Bitrate Plot", "",
                    "EPS Encapsulated Postscript (*.eps);;"
                    "PGF code for LaTex (*.pgf);;"
                    "Portable document format(*pdf);;"
                    "Portable Network Graphics (*.png);;"
                    "Postscript (*.ps);;"
                    "Raw RGBA bitmap (*.raw*.rgba);;"
                    "Scalable vector graphics (*.svg*.svgz)",
                    selfilter
                )
                if filevideo == "":
                    return

                QMetaObject.invokeMethod(self.VPBitratePlot, 'CreatePlot',
                                         Qt.QueuedConnection, Q_ARG(
                                             str, self.fileName),
                                         Q_ARG(
                                             str, filevideo),
                                         Q_ARG(str, 'video'))

        except Exception as e:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvPlayer", "Failed creating Plot Bitrate : " + str(e)))

    def ExtractAllFrames(self):
        """ Extract All Video Frames Thread """
        if not self.KillAllProcessors():
            return

        options = QFileDialog.DontResolveSymlinks | QFileDialog.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(self,
                                                     QCoreApplication.translate(
                                                         "QgsFmvPlayer",
                                                         "Save images"),
                                                     '', options=options)

        if directory:

            self.VPExtractFrames = ExtractFramesProcessor()
            self.VPTExtractAllFrames = QThread()

            self.VPExtractFrames.moveToThread(
                self.VPTExtractAllFrames)
            self.VPExtractFrames.finished.connect(
                self.QThreadFinished)
            self.VPExtractFrames.error.connect(self.QThreadError)
            self.VPExtractFrames.progress.connect(
                self.progressBarProcessor.setValue)
            self.VPTExtractAllFrames.start(QThread.LowPriority)

            QMetaObject.invokeMethod(self.VPExtractFrames, 'ExtractFrames',
                                     Qt.QueuedConnection, Q_ARG(
                                         str, directory),
                                     Q_ARG(str, self.fileName))
        return

    def ExtractCurrentFrame(self):
        """ Extract Current Frame Thread """
        image = self.videoWidget.GetCurrentFrame()
        out_image, _ = QFileDialog.getSaveFileName(
            self, "Save Current Frame", "",
            "Image File (*.png *.jpg *.bmp *.tiff)")

        if out_image == "":
            return

        if out_image:
            t = threading.Thread(target=self.SaveCapture,
                                 args=(image, out_image,))
            t.start()
        return

    def SaveCapture(self, image, output):
        ''' Save Current Image '''
        image.save(output)
        QApplication.processEvents()
        return

    def QThreadFinished(self, process, msg="", outjson=None):
        ''' Finish Threads '''
        if process == "ExtractFramesProcessor":
            self.VPExtractFrames.deleteLater()
            self.VPTExtractAllFrames.terminate()
            self.VPTExtractAllFrames.deleteLater()
        elif process == "CreatePlotsBitrate":
            self.VPBitratePlot.deleteLater()
            self.VPTBitratePlot.terminate()
            self.VPTBitratePlot.deleteLater()
        elif process == "convert":
            self.VPConverter.deleteLater()
            self.VPTConverter.terminate()
            self.VPTConverter.deleteLater()
        elif process == "probeToJson":
            self.infoJson.deleteLater()
            self.infoJsonT.terminate()
            self.infoJsonT.deleteLater()
        elif process == "probeShow":
            self.showInfo.deleteLater()
            self.showInfoT.terminate()
            self.showInfoT.deleteLater()
            self.showVideoInfoDialog(outjson)

        QApplication.processEvents()
        self.progressBarProcessor.setValue(0)
        return

    def QThreadError(self, processor, e, exception_string):
        """ Threads Errors"""
        qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvPlayer",
                                                              processor),
                                   'Failed! ' + str(e) + ' \n'.format(
            exception_string), level=QGis.Warning)

        self.QThreadFinished(processor, "Closing Processor")

        return

    def OpenQgsFmvMetadata(self):
        """ Open Metadata Dock """
        if self.metadataDlg is None:
            self.metadataDlg = QgsFmvMetadata(parent=self, player=self)
            self.addDockWidget(Qt.RightDockWidgetArea, self.metadataDlg)
            self.metadataDlg.show()
        else:
            self.metadataDlg.show()
        return

    def KillAllProcessors(self):
        """ Kill All Processors """
        """ Extract all frames Processors """
        try:
            if self.VPTExtractAllFrames.isRunning():
                ret = qgsu.CustomMessage(
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "HEY...Active background process!"),
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "Do you really want close?"))
                if ret == QMessageBox.Yes:
                    self.QThreadFinished(
                        "ExtractFramesProcessor", "Closing Extract Frames Processor")
                else:
                    return False
        except Exception:
            None

        """ Bitrates Processors"""
        try:
            if self.VPTBitratePlot.isRunning():
                ret = qgsu.CustomMessage(
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "HEY...Active background process!"),
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "Do you really want close?"))
                if ret == QMessageBox.Yes:
                    self.QThreadFinished(
                        "CreatePlotsBitrate", "Closing Plot Bitrate")
                else:
                    return False
        except Exception:
            None
        """ Converter Processors """
        try:
            if self.VPTConverter.isRunning():
                ret = qgsu.CustomMessage(
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "HEY...Active background process!"),
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "Do you really want close?"))
                if ret == QMessageBox.Yes:
                    self.QThreadFinished("convert", "Closing convert")
                else:
                    return False
        except Exception:
            None
        """ probeToJson Processors """
        try:
            if self.infoJsonT.isRunning():
                ret = qgsu.CustomMessage(
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "HEY...Active background process!"),
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "Do you really want close?"))
                if ret == QMessageBox.Yes:
                    self.QThreadFinished("probeToJson", "Closing Info to Json")
                else:
                    return False
        except Exception:
            None
        """ probeShow Processors """
        try:
            if self.showInfoT.isRunning():
                ret = qgsu.CustomMessage(
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "HEY...Active background process!"),
                    QCoreApplication.translate("QgsFmvPlayer",
                                               "Do you really want close?"))
                if ret == QMessageBox.Yes:
                    self.QThreadFinished(
                        "probeShow", "Closing Show Video Info")
                else:
                    return False
        except Exception:
            None
        return True

    def showVideoInfoDialog(self, outjson):
        """ Show Video Information Dialog """
        view = QTreeView()
        model = QJsonModel()
        view.setModel(model)
        model.loadJsonFromConsole(outjson)

        self.VideoInfoDialog = QDialog(self)
        self.VideoInfoDialog.setWindowTitle(QCoreApplication.translate(
            "QgsFmvPlayer", "Video Information : ") + self.fileName)
        self.VideoInfoDialog.setWindowIcon(
            QIcon(":/imgFMV/images/video_information.png"))

        self.verticalLayout = QVBoxLayout(self.VideoInfoDialog)
        self.verticalLayout.addWidget(view)
        view.expandAll()
        view.header().setSectionResizeMode(QHeaderView.ResizeToContents)

        self.VideoInfoDialog.setWindowFlags(
            Qt.Window | Qt.WindowCloseButtonHint)
        self.VideoInfoDialog.setObjectName("VideoInfoDialog")
        self.VideoInfoDialog.resize(500, 400)
        self.VideoInfoDialog.show()

    def closeEvent(self, evt):
        """ Close Event """
        if self.KillAllProcessors() is False:
            evt.ignore()
            return

        self.player.stop()
        self.parent._PlayerDlg = None
        self.parent.ToggleActiveFromTitle()
        RemoveVideoLayers()
        RemoveGroupByName()

        try:
            self.metadataDlg.close()
        except Exception:
            None
        try:
            self.matplot.close()
        except Exception:
            None
        # Restore Filters State
        self.videoWidget.RestoreFilters()
        del self.player
