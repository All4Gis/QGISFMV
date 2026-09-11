"""FFprobe JSON tree viewer."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QHeaderView
from QGIS_FMV.utils.ui.QgsJsonModel import QJsonModel
from pathlib import Path
from qgis.PyQt import uic

Ui_FmvVideoInfo, _ = uic.loadUiType(
    str(Path(__file__).resolve().parent.parent / "ui/ui_FmvVideoInfo.ui")
)


class VideoInfoDialog(QDialog, Ui_FmvVideoInfo):
    """Dialog showing parsed ffprobe JSON in a tree view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        self._model = QJsonModel()
        self.treeView.setModel(self._model)
        self.treeView.header().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

    def load_json(self, payload) -> bool:
        """Load parsed ffprobe JSON into the tree model. Returns True on success."""
        return self._model.loadJsonFromConsole(payload)

    def expand_all(self):
        """Expand all nodes in the tree view."""
        self.treeView.expandAll()
