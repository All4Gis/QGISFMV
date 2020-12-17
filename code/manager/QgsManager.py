# -*- coding: utf-8 -*-
import ast
from configparser import ConfigParser
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
from QGIS_FMV.manager.QgsMultiplexor import Multiplexor
from QGIS_FMV.manager.QgsFmvOpenStream import OpenStream
from QGIS_FMV.player.QgsFmvPlayer import QgsFmvPlayer
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
                                        getVideoLocationInfo)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu

try:
    from pydevd import *
except ImportError:
    None

s = QSettings()
parser = ConfigParser()
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
        self.pass_time = 500
        self.intervall = 1000
        self.notify_int = 3000

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
        row_text = self.VManager.item(cr, 1).text()
        self.VManager.removeRow(cr)
        # Remove video to Settings List
        RemoveVideoToSettings(row_id)
        # Remove folder if is local
        RemoveVideoFolder(row_text)

        if self.meta_reader[str(cr)] != None:
            self.meta_reader[str(cr)].dispose()
            self.meta_reader[str(cr)] = None

        return
    
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
        if self.VManager.rowCount() > 5:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "ManagerDock", "You must delete some video from the list before adding a new one"))
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
            self.isStreaming = True

        if not self.isStreaming:
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
                return

            pbar.setValue(30)
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
                               ] = getVideoLocationInfo(filename, islocal, klv_folder)
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
            self.meta_reader[str(rowPosition)] = StreamMetaReader(filename)
            qgsu.showUserAndLogMessage("", "StreamMetaReader initialized.", onlyLog=True)
            self.initialPt[str(rowPosition)] = None

        pbar.setValue(100)
        if islocal:
            self.ToggleActiveRow(rowPosition, value="Ready Local")
        else:
            self.ToggleActiveRow(rowPosition, value="Ready")
        # Add video to settings list
        AddVideoToSettings(str(row_id), filename)

    def openVideoFileDialog(self):
        ''' Open video file dialog '''
        Exts = ast.literal_eval(parser.get("FILES", "Exts"))
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "ManagerDock", "Open video"),
            exts=Exts)

        if filename:
            _, name = os.path.split(filename)
            self.AddFileRowToManager(name, filename)

        return

    def PlayVideoFromManager(self, model):
        ''' Play video from manager dock.
            Manager row double clicked
        '''
        # Don't enable Play if video doesn't have metadata
        row = model.row()
        if self.VManager.cellWidget(row, 5).findChild(QProgressBar).value() < 100:
            return

        path = self.VManager.item(row, 3).text()
        text = self.VManager.item(row, 1).text()
        self.ToggleActiveRow(row)

        folder = getVideoFolder(text)
        klv_folder = os.path.join(folder, "klv")
        exist = os.path.exists(klv_folder)
        try:
            if self._PlayerDlg.isVisible():
                self._PlayerDlg.close()
        except Exception:
            None
        # First time we open the player
        if self._PlayerDlg is None:
            if exist:
                self.CreatePlayer(path, row, islocal=True, klv_folder=klv_folder)
            else:
                self.CreatePlayer(path, row)
        else:
            #qgsu.CustomMessage("QGIS FMV", path, self._PlayerDlg.fileName, icon="Information")
            #if path != self._PlayerDlg.fileName:
            self._PlayerDlg.setMetaReader(self.meta_reader[str(row)])
            self.ToggleActiveFromTitle()
            self._PlayerDlg.show()
            self._PlayerDlg.activateWindow()
            if exist:
                self._PlayerDlg.playFile(path, islocal=True, klv_folder=klv_folder)
            else:
                self._PlayerDlg.playFile(path)

    def CreatePlayer(self, path, row, islocal=False, klv_folder=None):
        ''' Create Player '''
        self._PlayerDlg = QgsFmvPlayer(self.iface, path, parent=self, meta_reader=self.meta_reader[str(
            row)], pass_time=self.pass_time, islocal=islocal, klv_folder=klv_folder)
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
