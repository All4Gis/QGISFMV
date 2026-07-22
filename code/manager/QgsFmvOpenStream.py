# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QRegularExpression, QCoreApplication
from qgis.PyQt.QtGui import QIntValidator, QRegularExpressionValidator
from qgis.PyQt.QtWidgets import QDialog
from QGISFMV.gui.ui_FmvOpenStream import Ui_FmvOpenStream
from QGISFMV.utils.media.QgsFmvStreamUtils import (
    buildStreamUri,
    streamDisplayName,
    validateStreamEndpoint,
    vlcHintText,
)
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from qgis.core import Qgis as QGis


class OpenStream(QDialog, Ui_FmvOpenStream):
    """Connect to a live UDP/TCP/RTP/RTSP MISB stream."""

    def __init__(self, iface, parent=None):
        """Initialise the open-stream dialog."""
        super().__init__(parent)
        self.setupUi(self)
        self.parent = parent
        self.iface = iface

        self.onlyInt = QIntValidator()
        self.ln_port.setValidator(self.onlyInt)

        rx = QRegularExpression(
            r"((1{0,1}[0-9]{0,2}|2[0-4][0-9]{1,1}|25[0-5]{1,1})\.){3,3}"
            r"(1{0,1}[0-9]{0,2}|2[0-4][0-9]{1,1}|25[0-5]{1,1})"
        )
        self.ln_host.setValidator(QRegularExpressionValidator(rx, self))

        self.updateStreamHint(self.cmb_protocol.currentText())

    def updateStreamHint(self, protocol):
        """Update the VLC hint text and RTSP path visibility for *protocol*."""
        self.lbl_hint.setPlainText(vlcHintText(protocol))
        self.lbl_hint.viewport().setAutoFillBackground(False)
        is_rtsp = (protocol or "").upper() == "RTSP"
        self.lbl_path.setVisible(is_rtsp)
        self.ln_path.setVisible(is_rtsp)

    def OpenStream(self, _):
        """Validate inputs, build the stream URI, and open it in the player."""
        protocol = self.cmb_protocol.currentText()
        host = self.ln_host.text().strip() or "127.0.0.1"
        port = self.ln_port.text().strip()
        path = self.ln_path.text().strip()

        ok, msg = validateStreamEndpoint(protocol, host, port)
        if not ok:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvOpenStream", "Invalid stream settings"
                ),
                msg,
                level=QGis.MessageLevel.Warning,
            )
            return

        try:
            uri = buildStreamUri(protocol, host, port, path)
        except ValueError as exc:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmvOpenStream", "Invalid stream settings"
                ),
                str(exc),
                level=QGis.MessageLevel.Warning,
            )
            return

        name = streamDisplayName(uri)
        self.parent.AddFileRowToManager(name, uri)
        self.accept()
