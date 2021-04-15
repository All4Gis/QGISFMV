import os
from qgis.PyQt.QtGui import QPixmap, QIcon
from qgis.PyQt.QtWidgets import QMessageBox, QSpacerItem, QSizePolicy
from QGIS_FMV.utils.QgsFmvLog import log
from qgis.core import Qgis as QGis
from qgis.utils import iface
from qgis.PyQt.QtCore import QSettings, Qt
from datetime import datetime

try:
    from pydevd import *
except ImportError:
    None

""" 
Python utilities
"""


class QgsUtils(object):
    @staticmethod
    def GetIcon(icon):
        """ Get Icon for Custom Informative Message """
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
        """ Custom Informative Message """
        d = QMessageBox()
        d.setTextFormat(Qt.RichText)
        d.setWindowTitle(title)
        d.setWindowIcon(QIcon(QPixmap(":/imgFMV/images/icon.png")))
        d.setText(msg)
        d.setInformativeText(informative)
        d.setIconPixmap(QgsUtils.GetIcon(icon))
        d.addButton(QMessageBox.Yes)
        d.addButton(QMessageBox.No)
        d.setDefaultButton(QMessageBox.No)

        # Trick resize QMessageBox
        horizontalSpacer = QSpacerItem(
            500, 0, QSizePolicy.Minimum, QSizePolicy.Expanding
        )
        layout = d.layout()
        layout.addItem(horizontalSpacer, layout.rowCount(), 0, 1, layout.columnCount())

        ret = d.exec_()
        return ret

    @staticmethod
    def _convert_timestamp(ts):
        """Translates the values from a regex match for two timestamps of the
        form 00:12:34,567 into seconds."""
        start = int(ts.group(1)) * 3600 + int(ts.group(2)) * 60
        start += int(ts.group(3))
        start += float(ts.group(4)) / 10 ** len(ts.group(4))
        end = int(ts.group(5)) * 3600 + int(ts.group(6)) * 60
        end += int(ts.group(7))
        end += float(ts.group(8)) / 10 ** len(ts.group(8))
        return start, end

    @staticmethod
    def _add_secs_to_time(timeval, secs_to_add):
        """ Seconds to time """
        secs = timeval.hour * 3600 + timeval.minute * 60 + timeval.second
        secs += secs_to_add
        return QgsUtils._seconds_to_time(secs)

    @staticmethod
    def _time_to_seconds(dateStr):
        """
        Time to seconds
        @type dateStr: String
        @param dateStr: Date string value
        """
        timeval = datetime.strptime(dateStr, "%H:%M:%S.%f")
        secs = (
            timeval.hour * 3600
            + timeval.minute * 60
            + timeval.second
            + timeval.microsecond / 1000000
        )

        return secs

    @staticmethod
    def _seconds_to_time(sec):
        """Returns a string representation of the length of time provided.
        For example, 3675.14 -> '01:01:15'
        @type sec: String
        @param sec: seconds string value
        """
        hours = int(sec / 3600)
        sec -= hours * 3600
        minutes = int(sec / 60)
        sec -= minutes * 60
        return "%02d:%02d:%02d" % (hours, minutes, sec)

    @staticmethod
    def _seconds_to_time_frac(sec, comma=False):
        """Returns a string representation of the length of time provided,
        including partial seconds.
        For example, 3675.14 -> '01:01:15.140000'
        @type sec: String
        @param sec: seconds string value
        """
        hours = int(sec / 3600)
        sec -= hours * 3600
        minutes = int(sec / 60)
        sec -= minutes * 60
        if comma:
            frac = int(round(sec % 1.0 * 1000))
            return "%02d:%02d:%02d,%03d" % (hours, minutes, sec, frac)
        else:
            return "%02d:%02d:%07.4f" % (hours, minutes, sec)

    @staticmethod
    def createFolderByName(path, name):
        """ Create Folder by Name """
        directory = os.path.join(path, name)
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
        except OSError:
            None

    @staticmethod
    def showUserAndLogMessage(
        before, text="", level=QGis.Info, duration=3, onlyLog=False
    ):
        """ Show user & log info/warning/error messages """
        if not onlyLog:
            iface.messageBar().popWidget()
            iface.messageBar().pushMessage(before, text, level=level, duration=duration)
        if level == QGis.Info:
            log.info(text)
        elif level == QGis.Warning:
            log.warning(text)
        elif level == QGis.Critical:
            log.error(text)
        return

    @staticmethod
    def removeFile(path):
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def SetShortcutForPluginFMV(text, value="Alt+F"):
        """ Set DEFAULT or find user shortcut """
        settings = QSettings()
        settings.beginGroup("shortcuts")
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

    #     @staticmethod
    #     def removeMosaicFolder(video_file):
    #         ''' Remove mosaic folder '''
    #         folder = getVideoFolder(video_file)
    #         out = os.path.join(folder, "mosaic")
    #         try:
    #             shutil.rmtree(out, ignore_errors=True)
    #         except Exception:
    #             None
