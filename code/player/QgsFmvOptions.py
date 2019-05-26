# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QUrl, Qt, QSettings, QPoint
from qgis.PyQt.QtWidgets import QDialog, QStyleOptionSlider, QToolTip

from PyQt5.QtGui import QColor

from QGIS_FMV.gui.ui_FmvOptions import Ui_OptionsDialog
from QGIS_FMV.utils.QgsFmvUtils import getNameSpace
from QGIS_FMV.player.QgsFmvDrawToolBar import DrawToolBar as draw

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
        self.NameSpace = getNameSpace()

        self.sl_Size.enterEvent = self.showSizeTip
        draw.setValues(self)
                 
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
            self.settings.setValue(self.NameSpace + "/Options/magnifier/shape", 0) #Square
        else:
            self.settings.setValue(self.NameSpace + "/Options/magnifier/shape", 1) #Circle
            

        self.settings.setValue(self.NameSpace + "/Options/magnifier/size", self.sl_Size.value())
        self.settings.setValue(self.NameSpace + "/Options/magnifier/factor", self.sb_factor.value())
        
        ####### Drawings #######
        
        self.settings.setValue(self.NameSpace + "/Options/drawings/polygons/width", self.poly_width.value())
        self.settings.setValue(self.NameSpace + "/Options/drawings/polygons/pen", self.poly_pen.color())
        self.settings.setValue(self.NameSpace + "/Options/drawings/polygons/brush", self.poly_brush.color())
        
        self.settings.setValue(self.NameSpace + "/Options/drawings/points/width", self.point_width.value())
        self.settings.setValue(self.NameSpace + "/Options/drawings/points/pen", self.point_pen.color())                
        
        self.settings.setValue(self.NameSpace + "/Options/drawings/lines/width", self.lines_width.value())
        self.settings.setValue(self.NameSpace + "/Options/drawings/lines/pen", self.lines_pen.color()) 
        
        self.settings.setValue(self.NameSpace + "/Options/drawings/measures/width", self.measures_width.value())
        self.settings.setValue(self.NameSpace + "/Options/drawings/measures/pen", self.measures_pen.color())
        self.settings.setValue(self.NameSpace + "/Options/drawings/measures/brush", self.measures_brush.color())
        
        draw.setValues(self)
        
        self.close()
        return