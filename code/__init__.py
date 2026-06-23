# -*- coding: utf-8 -*-
import platform
from QGIS_FMV.utils.QgsFmvInstaller import WindowsInstaller, LinuxInstaller
from QGIS_FMV.gui import resources_rc  # noqa: F401  (registers Qt resources/icons)
from qgis.utils import iface
from qgis.utils import reloadPlugin
from qgis.core import Qgis as QGis
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QApplication

# Check dependencies
try:
    QApplication.setOverrideCursor(Qt.CursorShape.PointingHandCursor)
    QApplication.processEvents()

    if platform.system() == 'Windows':
        WindowsInstaller()
    else:
        LinuxInstaller()

    reloadPlugin('QGIS_FMV')
    iface.messageBar().pushMessage("QGIS FMV", "QGIS Full Motion Video installed correctly!", QGis.MessageLevel.Info, 3)
    QApplication.restoreOverrideCursor()
except Exception:
    iface.messageBar().pushMessage("QGIS FMV", "Ooops! QGIS Full Motion Video instalation failed!", QGis.MessageLevel.Warning, 3)
    QApplication.restoreOverrideCursor()


def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
