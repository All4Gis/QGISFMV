# -*- coding: utf-8 -*-
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QMessageBox
from QGIS_FMV.utils.QgsFmvLog import log
from qgis.core import Qgis as QGis
from qgis.core import QgsProject
from qgis.utils import iface


try:
    from pydevd import *
except ImportError:
    None


class QgsUtils(object):

    @staticmethod
    def GetIcon(icon):
        ''' Get Icon for Custom Informative Message '''
        if icon == "Question":
            i = QPixmap(":/imgFMV/images/Question.png")
        elif icon == "Information":
            i = QPixmap(":/imgFMV/images/Information.png")
        elif icon == "Warning":
            i = QPixmap(":/imgFMV/images/Warning.png")
        else:
            i = QPixmap(":/imgFMV/images/Critical.png")
        return i

    @staticmethod
    def CustomMessage(title, msg, informative="", icon="Critical"):
        ''' Custom Informative Message '''
        d = QMessageBox()
        d.setWindowTitle(title)
        d.setText(msg)
        d.setInformativeText(informative)
        d.setIconPixmap(QgsUtils.GetIcon(icon))
        d.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowTitleHint)
        d.addButton(QMessageBox.Yes)
        d.addButton(QMessageBox.No)
        d.setDefaultButton(QMessageBox.No)
        ret = d.exec_()
        return ret

    @staticmethod
    def selectLayerByName(layerName):
        ''' Select Layer by Name '''
        returnLayer = None
        try:
            returnLayer = QgsProject.instance().mapLayersByName(layerName)[0]
            return returnLayer
        except IndexError:
            return returnLayer

    @staticmethod
    def createFolderByName(path, name):
        ''' Create Folder by Name '''
        directory = os.path.join(path, name)
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
        except OSError:
            print ('Error: Creating directory. ' + directory)

    @staticmethod
    def showUserAndLogMessage(before, text="", level=QGis.Info, duration=3, onlyLog=False):
        ''' Show user & log info/warning/error messages '''
        if not onlyLog:
            iface.messageBar().popWidget()
            iface.messageBar().pushMessage(
                before, text, level=level, duration=duration)
        if level == QGis.Info:
            log.info(text)
        elif level == QGis.Warning:
            log.warning(text)
        elif level == QGis.Critical:
            log.error(text)
        return
