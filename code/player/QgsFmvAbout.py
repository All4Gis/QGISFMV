# -*- coding: utf-8 -*-
import os.path

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import QDialog
from QGIS_FMV.gui.ui_FmvAbout import Ui_FmvAbout
from qgis.core import QgsApplication


try:
    from pydevd import *
except ImportError:
    None


class FmvAbout(QDialog, Ui_FmvAbout):
    """ About Dialog """

    def __init__(self):
        """ Contructor """
        QDialog.__init__(self)
        self.setupUi(self)
        self.webView.setContextMenuPolicy(Qt.NoContextMenu)
        path = os.path.normpath(os.path.abspath(
            QgsApplication.qgisSettingsDirPath() + "\\python\\plugins\\QGIS_FMV\\documents\\about\\about.html"))
        self.webView.load(QUrl.fromLocalFile(path))
