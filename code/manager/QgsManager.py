# -*- coding: utf-8 -*-
import ast
from configparser import ConfigParser
import os
from os.path import dirname, abspath
from qgis.PyQt.Qt  import QSettings, pyqtSlot, QEvent, Qt, QCoreApplication, QPoint
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QUrl, QTimer
from qgis.PyQt.QtWidgets import (QDockWidget,
                                 QTableWidgetItem,
                                 QAction,
                                 QMenu,
                                 QProgressBar,
                                 QVBoxLayout,
                                 QWidget)
import qgis.utils

from PyQt5.QtGui import QColor

from QGIS_FMV.player.QgsFmvDrawToolBar import DrawToolBar as draw
from QGIS_FMV.converter.ffmpeg import FFMpeg
from QGIS_FMV.gui.ui_FmvManager import Ui_ManagerWindow
from QGIS_FMV.manager.QgsMultiplexor import Multiplexor
from QGIS_FMV.manager.QgsFmvOpenStream import OpenStream
from QGIS_FMV.player.QgsFmvPlayer import QgsFmvPlayer, QMediaContent
from QGIS_FMV.utils.QgsFmvUtils import (askForFiles,
                                        BufferedMetaReader,
                                        StreamMetaReader,
                                        initElevationModel,
                                        AddVideoToSettings,
                                        RemoveVideoToSettings,
                                        RemoveVideoFolder,
                                        getVideoFolder,
                                        getVideoManagerList,
                                        getNameSpace,
                                        getKlvStreamIndex,                  
                                        getVideoLocationInfo)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.core import QgsPointXY, QgsCoordinateReferenceSystem, QgsProject, QgsCoordinateTransform, Qgis as QGis
from PyQt5.QtMultimedia import QMediaPlaylist

try:
    from pydevd import *
except ImportError:
    None

s = QSettings()
parser = ConfigParser()
parser.read(os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini'))

class FmvManager(QWidget, Ui_ManagerWindow):
    ''' Video Manager '''

    def __init__(self, iface, action, actionShowHide, parent=None):
        super().__init__(parent)
        self.setupUi(self)
                                                                           
        self.mCloseButton.clicked.connect( action.toggle )
        
        self.mLowerButton.setDefaultAction(actionShowHide )
        
        self.parent = parent
        self.iface = iface
        self._PlayerDlg = None

        self.meta_reader = []
        self.initialPt = []
        self.pass_time = 250
        
        self.loading = False
        self.playlist = QMediaPlaylist()
        self.VManager.viewport().installEventFilter(self)

        # Context Menu
        self.VManager.customContextMenuRequested.connect(self.__context_menu)
        self.removeAct = QAction(QIcon(":/imgFMV/images/mActionDeleteSelected.svg"),
                                 QCoreApplication.translate("ManagerDock", "Remove from list"), self,
                                 triggered=self.remove)

        self.VManager.setColumnWidth(1, 150)
        self.VManager.setColumnWidth(2, 140)
        self.VManager.setColumnWidth(3, 250)
        self.VManager.setColumnWidth(4, 150)
        self.VManager.setColumnWidth(5, 130)                                    
        self.VManager.verticalHeader().setDefaultAlignment(Qt.AlignHCenter)
        self.VManager.hideColumn(0)

        self.videoPlayable = []
        self.videoIsStreaming = []
        self.dtm_path = parser['GENERAL']['DTM_file']
        draw.setValues()
        self.setAcceptDrops(True)
    
    def loadVideosFromSettings(self):
        
        # Get Video Manager List
        VideoList = getVideoManagerList()
        for load_id in VideoList:
            filename = s.value(getNameSpace() + "/Manager_List/" + load_id)
            _, name = os.path.split(filename)

            folder = getVideoFolder(filename)
            klv_folder = os.path.join(folder, "klv")
            exist = os.path.exists(klv_folder)
                        
            if exist:
                self.AddFileRowToManager(name, filename, load_id, exist, klv_folder)
            else:
                if os.path.isfile(filename):
                    self.AddFileRowToManager(name, filename, load_id)
    
    def eventFilter(self, source, event):
        ''' Event Filter '''
        if (event.type() == QEvent.MouseButtonPress and source is self.VManager.viewport() and self.VManager.itemAt(event.pos()) is None):
            self.VManager.clearSelection()
        return QDockWidget.eventFilter(self, source, event)

    @pyqtSlot(QPoint)
    def __context_menu(self, position):
        ''' Context Menu Manager Rows '''
        if self.VManager.itemAt(position) is None:
            return
        menu = QMenu()
        menu.addAction(self.removeAct)
        menu.exec_(self.VManager.mapToGlobal(position))

    def remove(self):
        ''' Remove current row '''         
        for cr in self.VManager.selectedItems():
            idx = 0
            #we browse cells but we need lines, so ignore already deleted rows
            try:
                idx = cr.row()
            except:
                continue
            
            row_id = self.VManager.item(idx, 0).text()
            row_text = self.VManager.item(idx, 1).text()
            
            self.VManager.removeRow(idx)
            
            self.videoPlayable.pop(idx)
            self.videoIsStreaming.pop(idx)
            self.initialPt.pop(idx)
            self.playlist.removeMedia(idx)
            
            # Remove video to Settings List
            RemoveVideoToSettings(row_id)
            # Remove folder if is local
            RemoveVideoFolder(row_text)

            if self.meta_reader[idx] != None:
                self.meta_reader[idx].dispose()
            
            self.meta_reader.pop(idx)
            
            if self.playlist.isEmpty() and self._PlayerDlg is not None:
                self._PlayerDlg.close()
                
                    
    def CloseFMV(self):
        ''' Close FMV '''
        try:
            self._PlayerDlg.close()
        except Exception:
            None
        self.close()
        return
    

    def openStreamDialog(self):
        ''' Open Stream Dialog '''
        self.OpenStream = OpenStream(self.iface, parent=self)
        self.OpenStream.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.OpenStream.exec_()
        return

    def openMuiltiplexorDialog(self):
        ''' Open Multiplexor Dialog '''
        self.Muiltiplexor = Multiplexor(self.iface, parent=self, Exts=ast.literal_eval(parser.get("FILES", "Exts")))
        self.Muiltiplexor.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.Muiltiplexor.exec_()
        return

    def AddFileRowToManager(self, name, filename, load_id=None, islocal=False, klv_folder=None):
        ''' Add file Video to new Row '''
        # We limit the number of videos due to the buffer
        self.loading = True
        if self.VManager.rowCount() > 5:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "ManagerDock", "You must delete some video from the list before adding a new one"), level=QGis.Warning)
            self.loading = False
            return

        self.islocal = islocal
        self.klv_folder = klv_folder
        self.isStreaming = False
        w = QWidget()
        layout = QVBoxLayout()
        pbar = QProgressBar()
        layout.addWidget(pbar)
        w.setLayout(layout)
        rowPosition = self.VManager.rowCount()               
        self.videoPlayable.append(False)
        
        pbar.setGeometry(0, 0, 300, 30)
        pbar.setValue(0)
        pbar.setMaximumHeight(30)

        if load_id is None:
            row_id = 0
            if rowPosition != 0:
                row_id = int(self.VManager.item(rowPosition - 1, 0).text()) + 1
        else:
            row_id = load_id

        self.VManager.insertRow(rowPosition)

        self.VManager.setItem(
            rowPosition, 0, QTableWidgetItem(str(row_id)))

        self.VManager.setItem(rowPosition, 1, QTableWidgetItem(name))
        self.VManager.setItem(rowPosition, 2, QTableWidgetItem(QCoreApplication.translate(
            "ManagerDock", "Loading")))
        self.VManager.setItem(rowPosition, 3, QTableWidgetItem(filename))
        self.VManager.setItem(rowPosition, 4, QTableWidgetItem("-"))
        self.VManager.setCellWidget(rowPosition, 5, w)

        self.VManager.setVisible(False)
        self.VManager.horizontalHeader().setStretchLastSection(True)
        self.VManager.setVisible(True)

        # resolve if it is a stream
        if "://" in filename:
            self.videoIsStreaming.append(True)
        else:
            self.videoIsStreaming.append(False)
                
        if not self.videoIsStreaming[-1]:
            # Disable row if not exist video file
            if not os.path.exists(filename):
                self.ToggleActiveRow(rowPosition, value="Missing source file")
                for j in range(self.VManager.columnCount()):
                    try:
                        self.VManager.item(rowPosition, j).setFlags(Qt.NoItemFlags | Qt.ItemIsEnabled)
                        self.VManager.item(rowPosition, j).setBackground(QColor(211, 211, 211))
                    except Exception:
                        self.VManager.cellWidget(rowPosition, j).setStyleSheet("background-color:rgb(211,211,211);")
                        pass
                self.loading = False
                return

            pbar.setValue(30)
            info = FFMpeg().probe(filename)
            if info is None:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "ManagerDock", "Failed loading FFMPEG ! "))
            
            klvIdx = getKlvStreamIndex(filename, islocal)
                        
            # init non-blocking metadata buffered reader
            self.meta_reader.append(BufferedMetaReader(filename, klv_index=klvIdx, pass_time=self.pass_time))
                                        
            pbar.setValue(60)
            try:
                # init point we can center the video on
                self.initialPt.append(getVideoLocationInfo(filename, islocal, klv_folder))
                if not self.initialPt[rowPosition]:
                    self.VManager.setItem(rowPosition, 4, QTableWidgetItem(
                        QCoreApplication.translate(
                            "ManagerDock", "Start location not available.")))
                    self.ToggleActiveRow(rowPosition, value="Video not applicable")
                    pbar.setValue(100)
                    
                else:
                    self.VManager.setItem(rowPosition, 4, QTableWidgetItem(
                        self.initialPt[rowPosition][2]))
                    pbar.setValue(90)
                    self.videoPlayable[rowPosition] = True
            except Exception:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "ManagerDock", "This video doesn't have Metadata ! "))
                pbar.setValue(100)
                self.ToggleActiveRow(rowPosition, value="Video not applicable")
                
        else:
            self.meta_reader.append(StreamMetaReader(filename))
            qgsu.showUserAndLogMessage("", "StreamMetaReader initialized.", onlyLog=True)
            self.initialPt.append(None)
            self.videoPlayable[rowPosition] = True
        
        url = ""
        if self.videoIsStreaming[-1]:
            # show video from splitter (port +1)
            oldPort = filename.split(":")[2]
            newPort = str(int(oldPort) + 10)                
            proto = filename.split(":")[0]
            url = QUrl(proto + "://127.0.0.1:" + newPort)
        else:
            url = QUrl.fromLocalFile(filename)
        
        self.playlist.addMedia(QMediaContent(url))
        
        if self.videoPlayable[rowPosition]:
            pbar.setValue(100)
            if islocal:
                self.ToggleActiveRow(rowPosition, value="Ready Local")
            else:
                self.ToggleActiveRow(rowPosition, value="Ready")
            # Add video to settings list
            AddVideoToSettings(str(row_id), filename)
        
        self.loading = False
            
    def openVideoFileDialog(self):
        ''' Open video file dialog '''
        if self.loading:
            return
        
        Exts = ast.literal_eval(parser.get("FILES", "Exts"))
                        
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "ManagerDock", "Open video"),
            exts=Exts)

        if filename:
            if not self.isFileInPlaylist(filename):
                _, name = os.path.split(filename)
                self.AddFileRowToManager(name, filename)
            else:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "ManagerDock", "File is already loaded in playlist: " + filename))
        
        return
    
    
    def isFileInPlaylist(self, filename):
        mcount = self.playlist.mediaCount()
        for x in range(mcount):
            if filename in self.playlist.media(x).canonicalUrl().toString():
                return True
        return False
    
    def PlayVideoFromManager(self, model):
        ''' Play video from manager dock.
            Manager row double clicked
        '''
        # Don't enable Play if video doesn't have metadata
        if not self.videoPlayable[model.row()]:
            return
        
        try:
            if self._PlayerDlg.isVisible():
                self._PlayerDlg.close()
        except Exception:
            None

        path = self.VManager.item(model.row(), 3).text()
        text = self.VManager.item(model.row(), 1).text()
        
        folder = getVideoFolder(text)
        klv_folder = os.path.join(folder, "klv")
        exist = os.path.exists(klv_folder)
        
        # First time we open the player
        if self._PlayerDlg is None:
            if exist:
                self.CreatePlayer(path, model.row(), islocal=True, klv_folder=klv_folder)
            else:
                self.CreatePlayer(path, model.row())  
        
        if exist:
            self._PlayerDlg.playFile(path, islocal=True, klv_folder=klv_folder)
        else:
            self._PlayerDlg.playFile(path)              
        
        
        self.SetupPlayer(model.row())
    
    
    def SetupPlayer(self, row):
        ''' Play video from manager dock.
            Manager row double clicked
        '''       
        self.ToggleActiveRow(row)
        
        self.playlist.setCurrentIndex(row)
        
        #qgsu.CustomMessage("QGIS FMV", path, self._PlayerDlg.fileName, icon="Information")
        #if path != self._PlayerDlg.fileName:
        self._PlayerDlg.setMetaReader(self.meta_reader[row])
        self.ToggleActiveFromTitle()
        self._PlayerDlg.show()
        self._PlayerDlg.activateWindow()
                    
        #zoom to map zone     
        curAuthId =  self.iface.mapCanvas().mapSettings().destinationCrs().authid()
        
        map_pos = QgsPointXY(self.initialPt[row][1], self.initialPt[row][0])
        if curAuthId != "EPSG:4326":
            trgCode=int(curAuthId.split(":")[1])
            xform = QgsCoordinateTransform(QgsCoordinateReferenceSystem(4326), QgsCoordinateReferenceSystem(trgCode), QgsProject().instance())
            map_pos = xform.transform(map_pos)
            
        self.iface.mapCanvas().setCenter(map_pos)
        self.iface.mapCanvas().zoomScale(50000)
            

    def CreatePlayer(self, path, row, islocal=False, klv_folder=None):
        ''' Create Player '''
        self._PlayerDlg = QgsFmvPlayer(self.iface, path, parent=self, meta_reader=self.meta_reader[
            row], pass_time=self.pass_time, islocal=islocal, klv_folder=klv_folder)
                    
        self._PlayerDlg.player.setPlaylist(self.playlist)
        self._PlayerDlg.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self._PlayerDlg.show()
        self._PlayerDlg.activateWindow()

    def ToggleActiveFromTitle(self):
        ''' Toggle Active video status '''
        column = 2
        for row in range(self.VManager.rowCount()):
            if self.VManager.item(row, column) is not None:
                v = self.VManager.item(row, column).text()
                text = self.VManager.item(row, 1).text()
                if v == "Playing":
                    folder = getVideoFolder(text)
                    klv_folder = os.path.join(folder, "klv")
                    exist = os.path.exists(klv_folder)
                    if exist:
                        self.ToggleActiveRow(row, value="Ready Local")
                    else:
                        self.ToggleActiveRow(row, value="Ready")
                    return

    def ToggleActiveRow(self, row, value="Playing"):
        ''' Toggle Active row manager video status '''
        self.VManager.setItem(row, 2, QTableWidgetItem(QCoreApplication.translate(
            "ManagerDock", value)))
        return

    def closeEvent(self, _):
        ''' Close Manager Event '''
        FmvDock = qgis.utils.plugins[getNameSpace()]
        FmvDock._FMVManager = None
        try:
            if self._PlayerDlg.isVisible():
                self._PlayerDlg.close()
        except Exception:
            None
        return
    
    def dragEnterEvent(self, e):
        check = True
        Exts = ast.literal_eval(parser.get("FILES", "Exts"))
        if e.mimeData().hasUrls():
            for url in e.mimeData().urls():
                fileIsOk = False
                for ext in Exts:
                    if url.fileName().lower().endswith(ext):
                       fileIsOk = True
                       break
                if not fileIsOk:
                    check = False
                    break
        
        #Only accept if all files match a required extension       
        if check:    
            e.acceptProposedAction()
        #Ignore and stop propagation
        else:
            e.setDropAction(Qt.IgnoreAction)
            e.accept()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            #local files
            if "file:///" in url.toString():
                if not self.isFileInPlaylist(url.toString()[8:]):
                    self.AddFileRowToManager(url.fileName(), url.toString()[8:])
            #network drives
            else:
                if not self.isFileInPlaylist(url.toString()[5:]):
                    self.AddFileRowToManager(url.fileName(), url.toString()[5:])
