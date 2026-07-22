# -*- coding: utf-8 -*-
"""Brightness / Contrast slider dialog for numpy-based filter."""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog

from QGISFMV.gui.ui_FmvBrightnessContrast import Ui_FmvBrightnessContrast


class BrightnessContrastDialog(QDialog, Ui_FmvBrightnessContrast):
    """Lightweight dialog with brightness and contrast sliders."""

    brightnessChanged = pyqtSignal(int)
    contrastChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowStaysOnTopHint
        )

    def onBrightnessChanged(self, value):
        """Slot: emit the brightnessChanged signal with *value*."""
        self.brightnessChanged.emit(int(value))

    def onContrastChanged(self, value):
        """Slot: emit the contrastChanged signal with *value*."""
        self.contrastChanged.emit(int(value))

    def resetValues(self):
        """Reset both sliders to zero."""
        self.brightnessSlider.setValue(0)
        self.contrastSlider.setValue(0)
