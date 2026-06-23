# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QUrl, Qt
from qgis.PyQt.QtWidgets import QDialog
from QGIS_FMV.gui.ui_FmvAbout import Ui_FmvAbout

class FmvAbout(QDialog, Ui_FmvAbout):
    """ About Dialog """

    def __init__(self):
        """ Contructor """
        QDialog.__init__(self)
        self.setupUi(self)
        self.webView.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        url = "https://all4gis.github.io/QGISFMV/"
        if hasattr(self.webView, "load"):
            self.webView.load(QUrl(url))
        else:
            self.webView.setHtml(
                '<p><a href="%s">QGIS FMV</a></p>' % url)
