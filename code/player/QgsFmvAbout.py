# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QUrl, Qt
from qgis.PyQt.QtWidgets import QDialog
from QGIS_FMV.gui.ui_FmvAbout import Ui_FmvAbout

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
        self.webView.load(QUrl("https://all4gis.github.io/QGISFMV/"))
