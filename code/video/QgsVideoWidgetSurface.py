from qgis.PyQt.QtCore import Qt, QRect, QPoint
from qgis.PyQt.QtGui import QImage

from PyQt5.QtMultimedia import (
    QAbstractVideoBuffer,
    QVideoFrame,
    QAbstractVideoSurface,
)

from QGIS_FMV.video.QgsVideoFilters import VideoFilters as filter

try:
    from pydevd import *
except ImportError:
    None

"""
Video Abstract Surface
"""


class VideoWidgetSurface(QAbstractVideoSurface):
    def __init__(self, widget):
        """ Constructor """
        super().__init__()

        self.widget = widget
        self.imageFormat = QImage.Format_Invalid
        self.image = None

    def supportedPixelFormats(self, handleType=QAbstractVideoBuffer.NoHandle):
        """ Available Frames Format """
        formats = [QVideoFrame.PixelFormat()]
        if handleType == QAbstractVideoBuffer.NoHandle:
            for f in [
                QVideoFrame.Format_RGB32,
                QVideoFrame.Format_ARGB32,
                QVideoFrame.Format_ARGB32_Premultiplied,
                QVideoFrame.Format_RGB565,
                QVideoFrame.Format_RGB555,
            ]:
                formats.append(f)
        return formats

    def isFormatSupported(self, _format):
        """ Check if is supported VideFrame format """
        imageFormat = QVideoFrame.imageFormatFromPixelFormat(_format.pixelFormat())
        size = _format.frameSize()
        _bool = False
        if (
            imageFormat != QImage.Format_Invalid
            and not size.isEmpty()
            and _format.handleType() == QAbstractVideoBuffer.NoHandle
        ):
            _bool = True
        return _bool

    def start(self, _format):
        """ Start QAbstractVideoSurface """
        imageFormat = QVideoFrame.imageFormatFromPixelFormat(_format.pixelFormat())
        size = _format.frameSize()
        if imageFormat != QImage.Format_Invalid and not size.isEmpty():
            self._sourceRect = _format.viewport()
            QAbstractVideoSurface.start(self, _format)
            self.imageFormat = imageFormat
            self.imageSize = size
            self.widget.updateGeometry()
            self.updateVideoRect()
            return True
        else:
            return False

    def stop(self):
        """ Stop Video """
        self._currentFrame = QVideoFrame()
        self._targetRect = QRect()
        QAbstractVideoSurface.stop(self)
        self.widget.update()

    def present(self, frame):
        """ Present Frame """
        if (
            self.surfaceFormat().pixelFormat() != frame.pixelFormat()
            or self.surfaceFormat().frameSize() != frame.size()
        ):
            self.setError(QAbstractVideoSurface.IncorrectFormatError)
            # if is a hight quality frame is stopped and not call start function
            # self.stop()
            return False
        else:
            self._currentFrame = frame
            self.widget.update()
            return True

    def videoRect(self):
        """ Get Video Rectangle """
        return self._targetRect

    def sourceRect(self):
        """ Get Source Rectangle """
        return self._sourceRect

    def updateVideoRect(self):
        """ Update video rectangle """
        size = self.surfaceFormat().sizeHint()
        size.scale(self.widget.size().boundedTo(size), Qt.KeepAspectRatio)
        self._targetRect = QRect(QPoint(0, 0), size)
        self._targetRect.moveCenter(self.widget.rect().center())

    def paint(self, painter):
        """ Paint Frame"""
        if self._currentFrame.map(QAbstractVideoBuffer.ReadOnly):
            oldTransform = painter.transform()
            painter.setTransform(oldTransform)

        self.image = QImage(
            self._currentFrame.bits(),
            self._currentFrame.width(),
            self._currentFrame.height(),
            self._currentFrame.bytesPerLine(),
            self.imageFormat,
        )

        if self.widget._filterSatate.grayColorFilter:
            self.image = filter.GrayFilter(self.image)

        if self.widget._filterSatate.MirroredHFilter:
            self.image = filter.MirrredFilter(self.image)

        if self.widget._filterSatate.monoFilter:
            self.image = filter.MonoFilter(self.image)

        if self.widget._filterSatate.invertColorFilter:
            self.image.invertPixels()

        # TODO : Test in other thread
        if self.widget._filterSatate.edgeDetectionFilter:
            try:
                self.image = filter.EdgeFilter(self.image)
            except Exception:
                None
        # TODO : Test in other thread
        if self.widget._filterSatate.contrastFilter:
            try:
                self.image = filter.AutoContrastFilter(self.image)
            except Exception:
                None

        # TODO : Test in other thread
        if self.widget._filterSatate.NDVI:
            try:
                self.image = filter.NDVIFilter(self.image)
            except Exception:
                None

        painter.drawImage(self._targetRect, self.image, self._sourceRect)
        self._currentFrame.unmap()
        return
