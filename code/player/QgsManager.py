# -*- coding: utf-8 -*-
import ast
from configparser import SafeConfigParser
import os
from os.path import dirname, abspath
from qgis.PyQt.QtCore import QSettings, pyqtSlot, QEvent, Qt, QCoreApplication, QPoint
from qgis.PyQt.QtGui import QIcon
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
from QGIS_FMV.player.QgsFmvOpenStream import OpenStream
from QGIS_FMV.player.QgsFmvPlayer import QgsFmvPlayer
from QGIS_FMV.utils.QgsFmvUtils import (askForFiles,
                                        BufferedMetaReader,
                                        initElevationModel,
                                        AddVideoToSettings,
                                        RemoveVideoToSettings,
                                        getVideoManagerList,
                                        getNameSpace,
                                        getVideoLocationInfo)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu


try:
    from pydevd import *
except ImportError:
    None

s = QSettings()
parser = SafeConfigParser()
parser.read(os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini'))


class FmvManager(QDockWidget, Ui_ManagerWindow):
    ''' Video Manager '''

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface
        self._PlayerDlg = None
        self.isStreaming = False
        self.meta_reader = {}
        self.initialPt = {}
        self.pass_time = 250
        self.actionOpen_Stream.setVisible(False)

        self.VManager.viewport().installEventFilter(self)

        # Context Menu
        self.VManager.customContextMenuRequested.connect(self.__context_menu)
        self.removeAct = QAction(QIcon(":/imgFMV/images/mActionDeleteSelected.svg"),
                                 QCoreApplication.translate("ManagerDock", "Remove from list"), self,
                                 triggered=self.remove)

        self.VManager.setColumnWidth(1, 150)
        self.VManager.setColumnWidth(2, 80)
        self.VManager.setColumnWidth(3, 300)
        self.VManager.setColumnWidth(4, 300)
        self.VManager.verticalHeader().setDefaultAlignment(Qt.AlignHCenter)
        self.VManager.hideColumn(0)
        
        #Get Video Manager List
        VideoList = getVideoManagerList()
        for load_id in VideoList:
            filename = s.value(getNameSpace() + "/Manager_List/"+load_id)
            _, name = os.path.split(filename)
            self.AddFileRowToManager(name, filename, load_id)
            
        draw.setValues()
            
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
        cr = self.VManager.currentRow()
        row_id = self.VManager.item(cr, 0).text()
        self.VManager.removeRow(cr)
        # Remove video to Settings List
        RemoveVideoToSettings(row_id)
        return

    def openStreamDialog(self):
        ''' Open Stream Dialog '''
        self.isStreaming = True
        self.OpenStream = OpenStream(self.iface, parent=self)
        self.OpenStream.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.OpenStream.exec_()
        return

    def AddFileRowToManager(self, name, filename, load_id=None):
        ''' Add file Video to new Row '''
        # We limit the number of videos due to the buffer
        if self.VManager.rowCount() > 5:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "ManagerDock", "You must delete some video from the list before adding a new one"))
            return
        
        w = QWidget()
        layout = QVBoxLayout()
        pbar = QProgressBar()
        layout.addWidget(pbar)
        w.setLayout(layout)
        rowPosition = self.VManager.rowCount()
        
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

        # Disable row if not exist video file
        if not os.path.exists(filename):
            self.ToggleActiveRow(rowPosition, value="Missing source file")
            for j in range(self.VManager.columnCount()):
                try:
                    self.VManager.item(rowPosition, j).setFlags(Qt.NoItemFlags|Qt.ItemIsEnabled)
                    self.VManager.item(rowPosition, j).setBackground(QColor(211,211,211))
                except Exception:
                    self.VManager.cellWidget(rowPosition, j).setStyleSheet("background-color:rgb(211,211,211);");
                    pass
            return
        
        pbar.setValue(30)  
        if not self.isStreaming:
            info = FFMpeg().probe(filename)
            if info is None:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "ManagerDock", "Failed loading FFMPEG ! "))
                return
            info.format.duration
            # init non-blocking metadata buffered reader
            self.meta_reader[str(rowPosition)] = BufferedMetaReader(filename, pass_time=self.pass_time)
            qgsu.showUserAndLogMessage(
                "", "buffered non-blocking metadata reader initialized.", onlyLog=True)

            pbar.setValue(60)
            
            try:
                # init point we can center the video on
                self.initialPt[str(rowPosition)
                               ] = getVideoLocationInfo(filename)
                if not self.initialPt[str(rowPosition)]:
                    self.VManager.setItem(rowPosition, 4, QTableWidgetItem(
                        QCoreApplication.translate(
                            "ManagerDock", "Start location not available.")))
                    self.ToggleActiveRow(rowPosition, value="Not MISB")
                    pbar.setValue(99)
                    return
                else:
                    self.VManager.setItem(rowPosition, 4, QTableWidgetItem(
                        self.initialPt[str(rowPosition)][2]))
            except Exception:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "ManagerDock", "This video don't have Metadata ! "))
                pbar.setValue(99)
                self.ToggleActiveRow(rowPosition, value="Not MISB")
                return

            pbar.setValue(90)

            dtm_path = parser['GENERAL']['DTM_file']
            if self.initialPt[str(rowPosition)] and dtm_path != '':
                try:
                    initElevationModel(self.initialPt[str(
                        rowPosition)][0], self.initialPt[str(rowPosition)][1], dtm_path)
                    qgsu.showUserAndLogMessage(
                        "", "Elevation model initialized.", onlyLog=True)
                except Exception:
                    None
        else:
            self.meta_reader[str(rowPosition)] = None
            self.initialPt[str(rowPosition)] = None

        pbar.setValue(100)
        self.ToggleActiveRow(rowPosition, value="Ready")
        #Add video to settings list
        AddVideoToSettings(str(row_id),filename)

    def openVideoFileDialog(self):
        ''' Open video file dialog '''
        self.isStreaming = False
        Exts = ast.literal_eval(parser.get("FILES", "Exts"))
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "ManagerDock", "Open video"),
            exts=Exts)

        if filename:
            _, name = os.path.split(filename)
            self.AddFileRowToManager(name, filename)

        return

    # Manager row double clicked
    def PlayVideoFromManager(self, model):
        ''' Play video from manager dock '''
        # Don't enable Play if video doesn't have metadata
        row = model.row()
        if self.VManager.cellWidget(row, 5).findChild(QProgressBar).value() < 100:
            return

        path = self.VManager.item(row, 3).text()

        self.ToggleActiveRow(row)

        try:
            self._PlayerDlg.close()
        except Exception:
            None
        if self._PlayerDlg is None:
            self.CreatePlayer(path, row)
        else:
            if path != self._PlayerDlg.fileName:
                self.ToggleActiveFromTitle()
                self._PlayerDlg.playFile(path)
                return

    def CreatePlayer(self, path, row):
        ''' Create Player '''
        self._PlayerDlg = QgsFmvPlayer(self.iface, path, parent=self, meta_reader=self.meta_reader[str(
            row)], pass_time=self.pass_time, isStreaming=self.isStreaming)
        self._PlayerDlg.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self._PlayerDlg.show()
        self._PlayerDlg.activateWindow()

    def ToggleActiveFromTitle(self):
        ''' Toggle Active video status '''
        column = 2
        for row in range(self.VManager.rowCount()):
            if self.VManager.item(row, column) is not None:
                v = self.VManager.item(row, column).text()
                if v == "Playing":
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
            self._PlayerDlg.close()
        except Exception:
            None
        return
