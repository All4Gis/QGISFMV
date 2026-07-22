# -*- coding: utf-8 -*-
"""Table cell progress bar widget loaded from .ui."""

from qgis.PyQt.QtWidgets import QWidget

from QGISFMV.gui.ui_FmvTableProgress import Ui_FmvTableProgress


class TableProgressWidget(QWidget, Ui_FmvTableProgress):
    """Progress bar cell for the video manager table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)


def create_table_progress_widget(parent=None) -> TableProgressWidget:
    """Create and return a TableProgressWidget instance."""
    return TableProgressWidget(parent)
