import os

from PyQt5.QtCore import QSettings, pyqtSlot, QEvent, Qt, QCoreApplication, QPoint
from PyQt5.QtWidgets import QFileDialog, QDockWidget, QTableWidgetItem, QAction, QMenu
from QGIS_FMV.gui.generated.ui_FmvManager import Ui_ManagerWindow
from QGIS_FMV.player.QgsFmvPlayer import QgsFmvPlayer
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

        self.VManager.viewport().installEventFilter(self)

        # Context Menu
        self.VManager.customContextMenuRequested.connect(self.__context_menu)
        self.removeAct = QAction(QCoreApplication.translate("ManagerDock", "&Remove"), self,
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
        ''' Context Menu Rows '''
        if self.VManager.itemAt(position) is None:
            return
        menu = QMenu()
        menu.addAction(self.removeAct)
        menu.exec_(self.VManager.mapToGlobal(position))

    def remove(self):
        ''' Remove current row '''
        self.VManager.removeRow(self.VManager.currentRow())
        return

    def openVideoFileDialog(self):
        ''' Open video file dialog '''
        lastopened = s.value("QGIS_FMV/Manager/lastopened")
        filename, _ = QFileDialog.getOpenFileName(self, QCoreApplication.translate(
            "ManagerDock", "Open video"), lastopened, 'Videos (*.mpeg4 *.mp4 *.ts *.avi *.mpg)')

        if filename:
            path, name = os.path.split(filename)
            s.setValue("QGIS_FMV/Manager/lastopened", path)
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
        return

    def PlayVideoFromManager(self, model):
        ''' Play video from manager dock '''
        path = self.VManager.item(model.row(), 3).text()
        title = self.VManager.item(model.row(), 1).text()
        self.ToggleActiveRow(model.row())

        if self._PlayerDlg is None:
            self.CreatePlayer(path, title)
        else:
            self.ToggleActiveFromTitle()
            self._PlayerDlg.playFile(path)
            return

    def CreatePlayer(self, path, title):
        ''' Create Player '''
        self._PlayerDlg = QgsFmvPlayer(self.iface, path, parent=self)
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

    def closeEvent(self, evnt):
        ''' Close Manager Event '''
        FmvDock = qgis.utils.plugins["QGIS_FMV"]
        FmvDock._FMVManager = None
        try:
            self._PlayerDlg.close()  # TODO : Close player too?
        except:
            None
        return
