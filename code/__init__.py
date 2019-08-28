# -*- coding: utf-8 -*-
import sys
from QGIS_FMV.utils.QgsFmvInstaller import WindowsInstaller, LinuxInstaller
import platform
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.utils import iface
from qgis.utils import reloadPlugin
from qgis.core import Qgis as QGis
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication

# Check dependencies
try:
    QApplication.setOverrideCursor(Qt.PointingHandCursor)
    QApplication.processEvents()
    
    windows = platform.system() == 'Windows'
    
    if windows:  # Windows Installer
        try:
            sys.path.append(
                "D:\eclipse\plugins\org.python.pydev.core_7.1.0.201902031515\pysrc")
            from pydevd import *
        except ImportError:
            None
        
        WindowsInstaller()
    else:  # Linux Installer
        try:
            sys.path.append(
                "/home/fran/Escritorio/eclipse/plugins/org.python.pydev.core_7.2.1.201904261721/pysrc")
            from pydevd import *
        except ImportError:
            None 
        LinuxInstaller() 
    
    reloadPlugin('QGIS_FMV')
    iface.messageBar().pushMessage("QGIS FMV", "QGIS Full Motion Video installed correctly!", QGis.Info, 3)
    QApplication.restoreOverrideCursor()
except Exception as e:
    iface.messageBar().pushMessage("QGIS FMV", "Ooops! QGIS Full Motion Video instalation failed!", QGis.Warning, 3)
    QApplication.restoreOverrideCursor()
    None

def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
