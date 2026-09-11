"""About dialog."""

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import QDialog
from pathlib import Path
from qgis.PyQt import uic

Ui_FmvAbout, _ = uic.loadUiType(
    str(Path(__file__).resolve().parent.parent / "ui/ui_FmvAbout.ui")
)


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
