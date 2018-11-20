# -*- coding: utf-8 -*-
import os

from PyQt5.QtCore import QSettings, pyqtSlot, QEvent, Qt, QCoreApplication, QPoint
from PyQt5.QtWidgets import (QDockWidget,
                             QTableWidgetItem,
                             QAction,
                             QMenu,
                             QProgressBar,
                             QVBoxLayout,
                             QWidget)
from QGIS_FMV.gui.ui_FmvManager import Ui_ManagerWindow
from QGIS_FMV.player.QgsFmvOpenStream import OpenStream
from QGIS_FMV.player.QgsFmvPlayer import QgsFmvPlayer
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.fmvConfig import DTM_file as dtm_path, Exts, min_buffer_size
from QGIS_FMV.utils.QgsFmvUtils import (askForFiles,
                                        BufferedMetaReader,
                                        initElevationModel,
                                        getVideoLocationInfo)
import qgis.utils
from QGIS_FMV.converter.ffmpeg import FFMpeg

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
        self.isStreaming = False
        self.meta_reader = {}
        self.initialPt = {}
        self.pBars = {}
        # don't go too low with pass_time or we won't catch any metadata at
        # all.

        self.pass_time = 250
        self.buffer_intervall = 500
        # 8 x 500 = 4000ms buffer time
        # min_buffer_size x buffer_intervall = Miliseconds buffer time
        self.min_buffer_size = min_buffer_size

        self.actionOpen_Stream.setVisible(False)

        self.VManager.viewport().installEventFilter(self)

        # Context Menu
        self.VManager.customContextMenuRequested.connect(self.__context_menu)
        self.removeAct = QAction(QCoreApplication.translate("ManagerDock", "Remove"), self,
                                 statusTip=QCoreApplication.translate(
                                     "ManagerDock", "Remove the current selection's video"),
                                 triggered=self.remove)

        self.VManager.setColumnWidth(0, 25)
        self.VManager.setColumnWidth(1, 150)
        self.VManager.setColumnWidth(2, 80)
        self.VManager.setColumnWidth(3, 300)
        self.VManager.setColumnWidth(4, 300)
        self.VManager.setColumnWidth(5, 150)
        self.VManager.verticalHeader().setDefaultAlignment(Qt.AlignHCenter)

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
        self.isStreaming = True
        self.OpenStream = OpenStream(self.iface, parent=self)
        self.OpenStream.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        self.OpenStream.exec_()
        return

    def AddFileRowToManager(self, name, filename):
        ''' Add file Video to new Row '''
        w = QWidget()
        layout = QVBoxLayout()
        pbar = QProgressBar()
        layout.addWidget(pbar)
        w.setLayout(layout)
        rowPosition = self.VManager.rowCount()

        self.VManager.insertRow(rowPosition)
        self.VManager.setItem(
            rowPosition, 0, QTableWidgetItem(str(rowPosition)))
        self.VManager.setItem(rowPosition, 1, QTableWidgetItem(name))
        self.VManager.setItem(rowPosition, 2, QTableWidgetItem(QCoreApplication.translate(
            "ManagerDock", "Loading")))
        self.VManager.setItem(rowPosition, 3, QTableWidgetItem(filename))
        self.VManager.setItem(rowPosition, 4, QTableWidgetItem("-"))
        self.VManager.setCellWidget(rowPosition, 5, w)

        self.VManager.setVisible(False)
        self.VManager.horizontalHeader().setStretchLastSection(True)

        pbar.setGeometry(0, 0, 300, 30)
        pbar.setValue(30)
        pbar.setMaximumHeight(30)
        self.pBars[str(rowPosition)] = pbar
        self.VManager.setVisible(True)

        if not self.isStreaming:
            info = FFMpeg().probe(filename)
            info.format.duration
            # init non-blocking metadata buffered reader
            self.meta_reader[str(rowPosition)] = BufferedMetaReader(
                filename, pass_time=self.pass_time, intervall=self.buffer_intervall, min_buffer_size=self.min_buffer_size)
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
                            "ManagerDock", "Start location not available!")))
                    self.ToggleActiveRow(rowPosition, value="Not MISB")
                    pbar.setValue(0)
                    return
                else:
                    self.VManager.setItem(rowPosition, 4, QTableWidgetItem(
                        self.initialPt[str(rowPosition)][2]))
            except Exception:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "ManagerDock", "This video don't have Metadata ! "))
                pbar.setValue(0)
                self.ToggleActiveRow(rowPosition, value="Not MISB")
                return

            pbar.setValue(90)

            if self.initialPt[str(rowPosition)] and dtm_path != '':
                initElevationModel(self.initialPt[str(
                    rowPosition)][0], self.initialPt[str(rowPosition)][1], dtm_path)
                qgsu.showUserAndLogMessage(
                    "", "Elevation model initialized.", onlyLog=True)
        else:
            self.meta_reader[str(rowPosition)] = None
            self.initialPt[str(rowPosition)] = None

        pbar.setValue(100)
        self.ToggleActiveRow(rowPosition, value="Ready")

    def openVideoFileDialog(self):
        ''' Open video file dialog '''
        self.isStreaming = False
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "ManagerDock", "Open video"),
            exts=Exts)

        if filename:
            _, name = os.path.split(filename)
            self.AddFileRowToManager(name, filename)

        return

    # mgr row double clicked
    def PlayVideoFromManager(self, model):
        ''' Play video from manager dock '''

        # Not Play if not have metadata
        if self.pBars[str(model.row())].value() < 100:
            return

        path = self.VManager.item(model.row(), 3).text()
        self.ToggleActiveRow(model.row())

        if self._PlayerDlg is None:
            self.CreatePlayer(path, model.row())
        else:
            if path != self._PlayerDlg.fileName:
                self.ToggleActiveFromTitle()
                self._PlayerDlg.playFile(path)
                return

    def CreatePlayer(self, path, row):
        ''' Create Player '''

        self._PlayerDlg = QgsFmvPlayer(self.iface, path, parent=self, meta_reader=self.meta_reader[str(
            row)], pass_time=self.pass_time, initialPt=self.initialPt[str(row)], isStreaming=self.isStreaming)
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
        FmvDock = qgis.utils.plugins["QGIS_FMV"]
        FmvDock._FMVManager = None
        try:
            self._PlayerDlg.close()
        except Exception:
            None
        return
