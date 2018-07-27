# -*- coding: utf-8 -*-
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QIntValidator, QRegExpValidator
from PyQt5.QtWidgets import QDialog
from QGIS_FMV.gui.ui_FmvOpenStream import Ui_FmvOpenStream


try:
    from pydevd import *
except ImportError:
    None


class OpenStream(QDialog, Ui_FmvOpenStream):
    """ Open Stream Dialog """

    def __init__(self, iface, parent=None):
        """ Contructor """
        super(OpenStream, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface

        # Int Validator
        self.onlyInt = QIntValidator()
        self.ln_port.setValidator(self.onlyInt)

        # IP Validator
        v = QRegExpValidator(self)
        rx = QRegExp(
            "((1{0,1}[0-9]{0,2}|2[0-4]{1,1}[0-9]{1,1}|25[0-5]{1,1})\\.){3,3}(1{0,1}[0-9]{0,2}|2[0-4]{1,1}[0-9]{1,1}|25[0-5]{1,1})")
        v.setRegExp(rx)
        self.ln_host.setValidator(v)

    def OpenStream(self, _):
        protocol = self.cmb_protocol.currentText().lower()
        host = self.ln_host.text()
        port = self.ln_port.text()
        v = protocol + "://" + host + ":" + port
        if host != "" and port != "":
            self.parent.AddFileRowToManager(v, v)
            self.close()
