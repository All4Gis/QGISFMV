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
from QGIS_FMV.QgsFmvConstants import isWindows

# Check dependencies
try:
    QApplication.setOverrideCursor(Qt.PointingHandCursor)
    QApplication.processEvents()

    if isWindows:  # Windows Installer
        try:
            sys.path.append(
                "D:/eclipse/plugins/org.python.pydev.core_7.5.0.202001101138/pysrc"
            )
            from pydevd import *
        except ImportError:
            None

        WindowsInstaller()
    else:  # Linux Installer
        try:
            sys.path.append(
                "/home/fragalop/.eclipse/360744286_linux_gtk_x86_64/plugins/org.python.pydev.core_8.1.0.202012051215/pysrc"
            )
            from pydevd import *
        except ImportError:
            None
        LinuxInstaller()

    reloadPlugin("QGIS_FMV")
    iface.messageBar().pushMessage(
        "QGIS FMV", "QGIS Full Motion Video installed correctly!", QGis.Info, 3
    )
    QApplication.restoreOverrideCursor()
except Exception as e:
    iface.messageBar().pushMessage(
        "QGIS FMV", "Ooops! QGIS Full Motion Video instalation failed!", QGis.Warning, 3
    )
    QApplication.restoreOverrideCursor()
    None


def classFactory(iface):
    from .QgsFmv import Fmv

    return Fmv(iface)
