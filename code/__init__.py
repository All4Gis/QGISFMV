# -*- coding: utf-8 -*-
import sys
try:
    sys.path.append(
        "D:\eclipse\plugins\org.python.pydev.core_7.0.3.201811082356\pysrc")
    from pydevd import *
except ImportError:
    None

from QGIS_FMV.utils.QgsFmvInstaller import WindowsInstaller
import platform
windows = platform.system() == 'Windows'
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from PyQt5.QtWidgets import QMessageBox
from qgis.utils import iface
from qgis.utils import reloadPlugin
from qgis.core import Qgis as QGis

# Check dependencies
if windows:
    try:
        WindowsInstaller()
        reloadPlugin('QGIS_FMV')
        iface.messageBar().pushMessage("QGIS FMV", "QGIS Full Motion Video installed correctly", QGis.Info, 3)
    except Exception:
        None
#         buttonReply = qgsu.CustomMessage("QGIS FMV", "", "you need to restart your QGIS,Do you really close?", icon="Information")
#         if buttonReply == QMessageBox.Yes:
#             # TODO : Restart QGIS
#             iface.actionExit().trigger()


def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
