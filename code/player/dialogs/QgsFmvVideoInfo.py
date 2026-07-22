# -*- coding: utf-8 -*-
"""FFprobe JSON tree viewer."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QHeaderView

from QGISFMV.gui.ui_FmvVideoInfo import Ui_FmvVideoInfo
from QGISFMV.utils.ui.QgsJsonModel import QJsonModel


class VideoInfoDialog(QDialog, Ui_FmvVideoInfo):
    """Dialog showing parsed ffprobe JSON in a tree view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
        )
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
