# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QUrl, Qt, QSettings, QPoint
from qgis.PyQt.QtWidgets import QDialog, QStyleOptionSlider, QToolTip

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
        mSize = self.settings.value(getNameSpace() + "/Options/magnifier/size")
        mFactor = self.settings.value(getNameSpace() + "/Options/magnifier/factor")
        
        self.sl_Size.enterEvent = self.showSizeTip
        
        ####### Magnifier Glass #######
        # Shape
        if shape_type is not None:    
            if shape_type == 0:
                # Square
                self.rB_Square_m.setChecked(True)
            else:
                # Circle
                self.rB_Circle_m.setChecked(True)
        # Size
        if mSize is not None: 
            self.sl_Size.setValue(int(mSize)) 
        
        # Factor
        if mFactor is not None: 
            self.sb_factor.setValue(int(mFactor)) 
                
    def showSizeTip(self, _):
        ''' Size Slider Tooltip Trick '''
        self.style = self.sl_Size.style()
        self.opt = QStyleOptionSlider()
        self.sl_Size.initStyleOption(self.opt)
        rectHandle = self.style.subControlRect(
            self.style.CC_Slider, self.opt, self.style.SC_SliderHandle, self.sl_Size)
        self.tip_offset = QPoint(5, 15)
        pos_local = rectHandle.topLeft() + self.tip_offset
        pos_global = self.sl_Size.mapToGlobal(pos_local)
        QToolTip.showText(pos_global, str(
            self.sl_Size.value()) + " px", self)
    
    def SaveOptions(self):
        ''' Save Options '''
        ####### Magnifier Glass #######
        # Shape Type
        if self.rB_Square_m.isChecked():
            self.settings.setValue(getNameSpace() + "/Options/magnifier/shape", 0) #Square
        else:
            self.settings.setValue(getNameSpace() + "/Options/magnifier/shape", 1) #Circle
            

        self.settings.setValue(getNameSpace() + "/Options/magnifier/size", self.sl_Size.value())
        self.settings.setValue(getNameSpace() + "/Options/magnifier/factor", self.sb_factor.value())
        
        self.close()
        return