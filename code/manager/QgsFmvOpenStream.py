from qgis.PyQt.QtCore import QRegExp, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIntValidator, QRegExpValidator
from qgis.PyQt.QtWidgets import QDialog, QApplication
from QGIS_FMV.gui.ui_FmvOpenStream import Ui_FmvOpenStream
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.core import Qgis as QGis

try:
    from pydevd import *
except ImportError:
    None

try:
    import cv2
except ImportError:
    None


class OpenStream(QDialog, Ui_FmvOpenStream):
    """ Open Stream Dialog """

    def __init__(self, iface, parent=None):
        """ Contructor """
        super().__init__(parent)
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
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvOpenStream", "Checking connection!"))
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QApplication.processEvents()
            # Check if connection exist
            cap = cv2.VideoCapture(v)
            ret, _ = cap.read()
            cap.release()
            if ret:
                self.parent.AddFileRowToManager(v, v)
                self.close()
            else:
                qgsu.showUserAndLogMessage(
                    QCoreApplication.translate(
                        "QgsFmvOpenStream",
                        "There is no such connection!"),
                    level=QGis.Warning)
            QApplication.restoreOverrideCursor()
