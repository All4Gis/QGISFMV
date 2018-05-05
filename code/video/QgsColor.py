# -*- coding: utf-8 -*-
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import QDialog, QApplication
from QGIS_FMV.gui.generated.ui_ColorDialog import Ui_ColorDialog


try:
    from pydevd import *
except ImportError:
    None


class ColorDialog(QDialog, Ui_ColorDialog):
    """ Color Dialog """

    def __init__(self, parent=None):
        """ Constructor """
        super(ColorDialog, self).__init__(parent)
        self.setupUi(self)
        self.parent = parent

        p = self.parent.player.position()
        self.state = self.parent.player.state()

        self.parent.player.setVideoOutput(self.parent.videoWidget)
        QApplication.processEvents()
        self.parent.player.setPosition(p)

        if self.state == QMediaPlayer.PausedState:
            self.parent.player.play()
            self.parent.player.pause()
        elif self.state == QMediaPlayer.StoppedState:
            self.parent.player.play()
            self.parent.player.stop()

        # self.parent.videoWidget.update()
        QApplication.processEvents()

        self.videoWidget = self.parent.videoWidget

        # TODO : Esto no funciona y si le pongo el valor a fuego si
        # Implemetar el cambio de color en videosurface?
        self.videoWidget.setBrightness(int(self.videoWidget.brightness()))
        self.videoWidget.setContrast(self.contrastSlider.value())
        self.videoWidget.setHue(self.hueSlider.value())
        self.videoWidget.setSaturation(self.saturationSlider.value())
        QApplication.processEvents()

        self.LoadInitialValues()
        QApplication.processEvents()

        self.videoWidget.brightnessChanged.connect(
            self.brightnessSlider.setValue)
        self.videoWidget.contrastChanged.connect(
            self.contrastSlider.setValue)
        self.videoWidget.hueChanged.connect(
            self.hueSlider.setValue)
        self.videoWidget.saturationChanged.connect(
            self.saturationSlider.setValue)

    def ColorChange(self, value):
        """ Color Video Change """
        sender = self.sender().objectName()
        if sender == "brightnessSlider":
            self.videoWidget.setBrightness(value)
        elif sender == "contrastSlider":
            self.videoWidget.setContrast(value)
        elif sender == "hueSlider":
            self.videoWidget.setHue(value)
        elif sender == "saturationSlider":
            self.videoWidget.setSaturation(value)

    def ResetColorValues(self):
        """ Reset default values """
        self.videoWidget.setBrightness(0)
        self.videoWidget.setContrast(0)
        self.videoWidget.setHue(0)
        self.videoWidget.setSaturation(0)

    def LoadInitialValues(self):
        """ Init Values"""
        self.brightnessSlider.setValue(self.videoWidget.brightness())
        self.contrastSlider.setValue(self.videoWidget.contrast())
        self.hueSlider.setValue(self.videoWidget.hue())
        self.saturationSlider.setValue(self.videoWidget.saturation())

        self.ResetColorValues()

    def closeEvent(self, evt):
        """ Close Event"""
        # TODO : SE QUEDA NEGRA LA PANTALLA
        if self.state == QMediaPlayer.PausedState:
            self.parent.player.play()
            self.parent.player.pause()
        elif self.state == QMediaPlayer.StoppedState:
            self.parent.player.play()
            self.parent.player.stop()
