  # -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtGui import QPixmap, QIcon
from qgis.PyQt.QtWidgets import QMessageBox, QSpacerItem, QSizePolicy 
from QGIS_FMV.utils.QgsFmvLog import log
from qgis.core import (QgsProject,
                       Qgis as QGis)
from qgis.utils import iface
from qgis.PyQt.QtCore import QSettings, Qt

class QgsUtils(object):

    @staticmethod
    def GetIcon(icon):
        ''' Get Icon for Custom Informative Message '''
        if icon == "Question":
            i = QPixmap(":/imgFMV/images/Question.png")
        elif icon == "Information":
            i = QPixmap(":/imgFMV/images/Information.png")
        elif icon == "Warning":
            i = QPixmap(":/imgFMV/images/Warning.png")
        else:
            i = QPixmap(":/imgFMV/images/Critical.png")
        return i

    @staticmethod
    def CustomMessage(title, msg, informative="", icon="Critical"):
        ''' Custom Informative Message '''
        d = QMessageBox()
        d.setTextFormat(Qt.TextFormat.RichText)
        d.setWindowTitle(title)
        d.setWindowIcon(QIcon(QPixmap(":/imgFMV/images/icon.png")))
        d.setText(msg)
        d.setInformativeText(informative)
        d.setIconPixmap(QgsUtils.GetIcon(icon))
        d.addButton(QMessageBox.StandardButton.Yes)
        d.addButton(QMessageBox.StandardButton.No)
        d.setDefaultButton(QMessageBox.StandardButton.No)
       
        # Trick resize QMessageBox
        horizontalSpacer = QSpacerItem(500, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout = d.layout()
        layout.addItem(horizontalSpacer, layout.rowCount(), 0, 1, layout.columnCount())
        
        ret = d.exec()
        return ret

    @staticmethod
    def getLayerExtent(layer=None):
        ''' Get Layer extent '''
        return iface.mapCanvas().mapSettings().layerExtentToOutputExtent(layer, layer.extent())

    @staticmethod
    def selectLayerByName(layerName, group=None):
        ''' Select Layer by Name '''
        returnLayer = None
        try:
            if group is None:
                returnLayer = QgsProject.instance().mapLayersByName(layerName)[0]
                return returnLayer
            else:
                root = QgsProject.instance().layerTreeRoot()
                returnLayer = QgsProject.instance().mapLayersByName(layerName)
                g = root.findGroup(group)
                if g is not None:
                    for child in returnLayer:
                        layer = g.findLayer(child.id())
                        if layer is not None:
                            returnLayer = child
                            return returnLayer
        except IndexError:
            return returnLayer

    @staticmethod
    def createFolderByName(path, name):
        ''' Create Folder by Name '''
        directory = os.path.join(path, name)
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
        except OSError:
            None

    @staticmethod
    def showUserAndLogMessage(before, text="", level=QGis.MessageLevel.Info, duration=3, onlyLog=False):
        ''' Show user & log info/warning/error messages '''
        if not onlyLog:
            iface.messageBar().popWidget()
            iface.messageBar().pushMessage(
                before, text, level=level, duration=duration)
        if level == QGis.MessageLevel.Info:
            log.info(text)
        elif level == QGis.MessageLevel.Warning:
            log.warning(text)
        elif level == QGis.MessageLevel.Critical:
            log.error(text)
        return

#     @staticmethod
#     def removeMosaicFolder(video_file):
#         ''' Remove mosaic folder '''
#         folder = getVideoFolder(video_file)
#         out = os.path.join(folder, "mosaic")
#         try:
#             shutil.rmtree(out, ignore_errors=True)
#         except Exception:
#             None

    @staticmethod
    def removeFile(path):
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def SetShortcutForPluginFMV(text, value="Alt+F"):
        ''' Set DEFAULT or find user shortcut '''
        settings = QSettings()
        settings.beginGroup('shortcuts')
        # Find all saved shortcuts:
        keys = [key for key in settings.childKeys() if key == text]
        if not len(keys):
            # Nothing found in settings - fallback to default:
            shortcut = value
            settings.setValue(text, shortcut)
        elif len(keys) == 1:
            # Just one setting found, take that!
            shortcut = settings.value(keys[0])
        return shortcut
