# -*- coding: utf-8 -*-
"""About dialog."""

from qgis.PyQt.QtCore import QUrl, Qt
from qgis.PyQt.QtWidgets import QDialog

from QGISFMV.gui.ui_FmvAbout import Ui_FmvAbout


class FmvAbout(QDialog, Ui_FmvAbout):
    """About Dialog"""

    def __init__(self, parent=None):
        """Initialise the about dialog."""
        super().__init__(parent)
        self.setupUi(self)
        self.webView.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        url = "https://all4gis.github.io/QGISFMV/"
        if hasattr(self.webView, "load"):
            self.webView.load(QUrl(url))
        else:
            self.webView.setHtml(f'<p><a href="{url}">QGIS FMV</a></p>')
