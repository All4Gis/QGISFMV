# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QUrl, Qt, QSettings
from qgis.PyQt.QtWidgets import QDialog

from QGIS_FMV.gui.ui_FmvOptions import Ui_OptionsDialog
from QGIS_FMV.utils.QgsFmvUtils import getNameSpace

try:
    from pydevd import *
except ImportError:
    None


class FmvOptions(QDialog, Ui_OptionsDialog):
    """ Options Dialog """

    def __init__(self):
        """ Contructor """
        QDialog.__init__(self)
        self.setupUi(self)
        self.settings = QSettings()
        shape_type = self.settings.value(getNameSpace() + "/Options/magnifier/shape")
        
        if shape_type is not None:    
            if shape_type == 0:
                # Square
                self.rB_Square_m.setChecked(True)
            else:
                # Circle
                self.rB_Circle_m.setChecked(True)
            
    def SaveOptions(self):
        # Magnifier Glass
        # Shape Type
        if self.rB_Square_m.isChecked():
            self.settings.setValue(getNameSpace() + "/Options/magnifier/shape", 0) #Square
        else:
            self.settings.setValue(getNameSpace() + "/Options/magnifier/shape", 1) #Circle
            
        self.close()
        return