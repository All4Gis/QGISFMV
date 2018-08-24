# -*- coding: utf-8 -*-
import os

from PyQt5.QtCore import QSettings, pyqtSlot, QEvent, Qt, QCoreApplication, QPoint
from PyQt5.QtWidgets import QDockWidget, QTableWidgetItem, QAction, QMenu
from QGIS_FMV.gui.ui_FmvManager import Ui_ManagerWindow
from QGIS_FMV.player.QgsFmvOpenStream import OpenStream
from QGIS_FMV.player.QgsFmvPlayer import QgsFmvPlayer
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.fmvConfig import DTM_file as dtm_path
from QGIS_FMV.utils.QgsFmvUtils import (askForFiles,
                                        BufferedMetaReader,
                                        initElevationModel,
                                        getVideoLocationInfo)
import qgis.utils


try:
    from pydevd import *
except ImportError:
    None

s = QSettings()


class FmvManager(QDockWidget, Ui_ManagerWindow):
    ''' Video Manager '''

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface
        self._PlayerDlg = None

        self.meta_reader = {}
        self.initialPt = {}
        #don't go too low with pass_time or we won't catch any metadata at all.
        self.pass_time = 250
        self.buffer_intervall = 500
        self.min_buffer_size = 8

        self.actionOpen_Stream.setVisible(False)

        self.VManager.viewport().installEventFilter(self)

        # Context Menu
        self.VManager.customContextMenuRequested.connect(self.__context_menu)
        self.removeAct = QAction(QCoreApplication.translate("ManagerDock", "Remove"), self,
                                 statusTip=QCoreApplication.translate(
                                     "ManagerDock", "Remove the current selection's video"),
                                 triggered=self.remove)

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
        self.VManager.removeRow(self.VManager.currentRow())
        return

    def openStreamDialog(self):
        ''' Open Stream Dialog '''
        self.OpenStream = OpenStream(self.iface, parent=self)
        self.OpenStream.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.OpenStream.exec_()
        return

    def AddFileRowToManager(self, name, filename):
        ''' Add file Video to new Row '''
        rowPosition = self.VManager.rowCount()

        self.VManager.insertRow(rowPosition)
        self.VManager.setItem(
            rowPosition, 0, QTableWidgetItem(str(rowPosition)))
        self.VManager.setItem(rowPosition, 1, QTableWidgetItem(name))
        self.VManager.setItem(rowPosition, 2, QTableWidgetItem("False"))
        self.VManager.setItem(rowPosition, 3, QTableWidgetItem(filename))

        self.VManager.setVisible(False)
        self.VManager.resizeColumnsToContents()
        self.VManager.horizontalHeader().setStretchLastSection(True)
        self.VManager.setVisible(True)

        #init non-blocking metadata buffered reader
        self.meta_reader[str(rowPosition)] = BufferedMetaReader(filename, pass_time=self.pass_time, intervall=self.buffer_intervall, min_buffer_size=self.min_buffer_size)
        qgsu.showUserAndLogMessage("", "buffered non-blocking metadata reader initialized.", onlyLog=True)

        #init point we can center the video on
        self.initialPt[str(rowPosition)] = getVideoLocationInfo(filename)

        if self.initialPt[str(rowPosition)] and dtm_path != '':
            initElevationModel(self.initialPt[str(rowPosition)][0], self.initialPt[str(rowPosition)][1], dtm_path)
            qgsu.showUserAndLogMessage("", "Elevation model initialized.", onlyLog=True)

    def openVideoFileDialog(self):
        ''' Open video file dialog '''
        filename, _ = askForFiles(self,QCoreApplication.translate(
                                      "ManagerDock", "Open video"),
                                  exts=["mpeg4","mp4","ts","avi","mpg","H264","mov"])
        if filename:
            _, name = os.path.split(filename)
            self.AddFileRowToManager(name, filename)

        return

    def PlayVideoFromManager(self, model):
        ''' Play video from manager dock '''
        path = self.VManager.item(model.row(), 3).text()
        self.ToggleActiveRow(model.row())

        if self._PlayerDlg is None:
            self.CreatePlayer(path, model.row())
        else:
            self.ToggleActiveFromTitle()
            self._PlayerDlg.playFile(path)
            return

    def CreatePlayer(self, path, row):
        ''' Create Player '''
        self._PlayerDlg = QgsFmvPlayer(self.iface, path, parent=self, meta_reader=self.meta_reader[str(row)], pass_time=self.pass_time, initialPt=self.initialPt[str(row)])
        self._PlayerDlg.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self._PlayerDlg.show()
        self._PlayerDlg.activateWindow()

    def ToggleActiveFromTitle(self):
        ''' Toggle Active video status '''
        column = 2
        for row in range(self.VManager.rowCount()):
            if self.VManager.item(row, column) is not None:
                v = self.VManager.item(row, column).text()
                if v == "True":
                    self.ToggleActiveRow(row, value="False")
                    return

    def ToggleActiveRow(self, row, value="True"):
        ''' Toggle Active row manager video status '''
        self.VManager.setItem(row, 2, QTableWidgetItem(value))
        return

    def closeEvent(self, _):
        ''' Close Manager Event '''
        FmvDock = qgis.utils.plugins["QGIS_FMV"]
        FmvDock._FMVManager = None
        try:
            self._PlayerDlg.close()
        except Exception:
            None
        return
