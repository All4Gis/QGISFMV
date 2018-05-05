import traceback

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QCoreApplication
from PyQt5.QtMultimedia import *
from PyQt5.QtMultimediaWidgets import *
from PyQt5.QtWidgets import *
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.core import *
from qgis.gui import *


try:
    import cv2
except Exception as e:
    qgsu.showUserAndLogMessage(QCoreApplication.translate(
        "VideoProcessor", "Error: Missing OpenCV packages"))

try:
    from pydevd import *
except ImportError:
    None


class ExtractFramesProcessor(QObject):
    ''' Extract All Frames '''
    finished = pyqtSignal(str, str)
    error = pyqtSignal(str, Exception, basestring)
    progress = pyqtSignal(float)

    @pyqtSlot(str, str)
    def ExtractFrames(self, directory, fileName):
        try:
            vidcap = cv2.VideoCapture(fileName)
            success, image = vidcap.read()
            length = int(vidcap.get(cv2.CAP_PROP_FRAME_COUNT))
            count = 0
            success = True
            while success:
                success, image = vidcap.read()
                cv2.imwrite(directory + "\\frame_%d.jpg" %
                            count, image)  # save frame as JPEG file
                self.progress.emit(count * 100 / length)
                count += 1
            vidcap.release()
            cv2.destroyAllWindows()
            self.progress.emit(100)
            self.finished.emit("ExtractFramesProcessor",
                               "Capture All Frames Finished!")
        except Exception as e:
            self.error.emit("ExtractFramesProcessor",
                            e, traceback.format_exc())
            return
