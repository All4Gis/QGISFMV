# -*- coding: utf-8 -*-
from PyQt5.QtCore import Qt, QRect, QPoint, QBasicTimer, QSize, QPointF
from PyQt5.QtGui import (QImage,
                         QPalette,
                         QPixmap,
                         QPainter,
                         QRegion,
                         QPainterPath,
                         QRadialGradient,
                         QColor,
                         QPen,
                         QBrush)
from PyQt5.QtMultimedia import (QAbstractVideoBuffer,
                                QVideoFrame,
                                QVideoSurfaceFormat,
                                QAbstractVideoSurface)
from PyQt5.QtMultimediaWidgets import QVideoWidget

from PyQt5.QtWidgets import QSizePolicy, QWidget, QRubberBand
from QGIS_FMV.utils.QgsFmvUtils import (SetImageSize,
                                        GetSensor,
                                        CommonLayer,
                                        GetFrameCenter,
                                        GetGCPGeoTransform,
                                        GetImageWidth,
                                        GetImageHeight)

from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.video.QgsVideoFilters import VideoFilters as filter
from QGIS_FMV.fmvConfig import Point_lyr, Line_lyr
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY

try:
    from pydevd import *
except ImportError:
    None

try:
    import cv2
except ImportError:
    None

invertColorFilter = False
edgeDetectionFilter = False
grayColorFilter = False
monoFilter = False
contrastFilter = False
objectTracking = False
magnifier = False
pointDrawer = False
lineDrawer = False
polygonDrawer = False
zoomRect = False

HOLD_TIME = 701
MAX_MAGNIFIER = 229


class VideoWidgetSurface(QAbstractVideoSurface):

    def __init__(self, widget, parent=None):
        ''' Constructor '''
        super(VideoWidgetSurface, self).__init__(parent)

        self.widget = widget
        self.imageFormat = QImage.Format_Invalid
        self.image = None
        self.zoomedrect = None

    def supportedPixelFormats(self, handleType=QAbstractVideoBuffer.NoHandle):
        ''' Available Frames Format '''
        formats = [QVideoFrame.PixelFormat()]
        if handleType == QAbstractVideoBuffer.NoHandle:
            for f in [QVideoFrame.Format_RGB32,
                      QVideoFrame.Format_ARGB32,
                      QVideoFrame.Format_ARGB32_Premultiplied,
                      QVideoFrame.Format_RGB565,
                      QVideoFrame.Format_RGB555
                      ]:
                formats.append(f)
        return formats

    def isFormatSupported(self, _format):
        ''' Check if is supported VideFrame format '''
        imageFormat = QVideoFrame.imageFormatFromPixelFormat(
            _format.pixelFormat())
        size = _format.frameSize()
        _bool = False
        if (imageFormat != QImage.Format_Invalid and not
            size.isEmpty() and
                _format.handleType() == QAbstractVideoBuffer.NoHandle):
            _bool = True
        return _bool

    def start(self, _format):
        ''' Start QAbstractVideoSurface '''
        imageFormat = QVideoFrame.imageFormatFromPixelFormat(
            _format.pixelFormat())
        size = _format.frameSize()
        if (imageFormat != QImage.Format_Invalid and not size.isEmpty()):
            self.imageFormat = imageFormat
            self.imageSize = size
            self.sourceRect = _format.viewport()
            QAbstractVideoSurface.start(self, _format)
            self.widget.updateGeometry()
            self.updateVideoRect()
            return True
        else:
            return False

    def stop(self):
        ''' Stop Video '''
        self.currentFrame = QVideoFrame()
        self.targetRect = QRect()
        QAbstractVideoSurface.stop(self)
        self.widget.update()

    def present(self, frame):
        ''' Present Frame '''
        if (self.surfaceFormat().pixelFormat() != frame.pixelFormat() or
                self.surfaceFormat().frameSize() != frame.size()):
            self.setError(QAbstractVideoSurface.IncorrectFormatError)
            self.stop()
            return False
        else:
            self.currentFrame = frame
            self.widget.repaint(self.targetRect)
            return True

    def videoRect(self):
        ''' Get Video Rectangle '''
        return self.targetRect

    def GetsourceRect(self):
        ''' Get Source Rectangle '''
        return self.sourceRect

    def updateVideoRect(self):
        ''' Update video rectangle '''
        size = self.surfaceFormat().sizeHint()
        size.scale(self.widget.size().boundedTo(size), Qt.KeepAspectRatio)
        self.targetRect = QRect(QPoint(0, 0), size)
        self.targetRect.moveCenter(self.widget.rect().center())

    def paint(self, painter):
        ''' Paint Frame'''
        if (self.currentFrame.map(QAbstractVideoBuffer.ReadOnly)):
            oldTransform = painter.transform()

            if (self.surfaceFormat().scanLineDirection() == QVideoSurfaceFormat.BottomToTop):
                painter.scale(1, -1)
                painter.translate(0, -self.widget.height())

            self.image = QImage(self.currentFrame.bits(),
                                self.currentFrame.width(),
                                self.currentFrame.height(),
                                self.currentFrame.bytesPerLine(),
                                self.imageFormat
                                )

            if grayColorFilter:
                self.image = filter.GrayFilter(self.image)

            if monoFilter:
                self.image = filter.MonoFilter(self.image)

            if edgeDetectionFilter:
                self.image = filter.EdgeFilter(self.image)

            if contrastFilter:
                self.image = filter.AutoContrastFilter(self.image)

            if invertColorFilter:
                self.image.invertPixels()

            if zoomRect and self.zoomedrect is not None:
                painter.drawImage(self.sourceRect, self.image, self.zoomedrect)
                painter.setTransform(oldTransform)
                self.currentFrame.unmap()
                return

            painter.drawImage(self.targetRect, self.image, self.sourceRect)
            painter.setTransform(oldTransform)
            self.currentFrame.unmap()


class VideoWidget(QVideoWidget):

    def __init__(self, parent=None):
        super(VideoWidget, self).__init__(parent)
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        pal = QPalette()
        pal.setBrush(QPalette.Highlight, QBrush(QColor(Qt.green)))
        self.rubberBand.setPalette(pal)
        self.setUpdatesEnabled(True)
        self.setMouseTracking(True)
        self.origin = QPoint()
        self.pressed = self.snapped = self.zoomed = self.zoomedRect = self.changeRubberBand = False
        self.gt = None

        self.parent = parent.parent()
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_PaintOnScreen, True)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        palette = self.palette()
        palette.setColor(QPalette.Background, Qt.black)
        self.setPalette(palette)
        self.setSizePolicy(QSizePolicy.MinimumExpanding,
                           QSizePolicy.MinimumExpanding)

        self.surface = VideoWidgetSurface(self)

        self.offset = QPoint()
        self.pressPos = QPoint()
        self.drawPtPos = []
        self.drawLines = []
        self.drawPolygon = []
        self.dragPos = QPoint()
        self.tapTimer = QBasicTimer()
        self.zoomPixmap = QPixmap()
        self.maskPixmap = QPixmap()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.setFullScreen(False)
            event.accept()
        elif event.key() == Qt.Key_Enter and event.modifiers() & Qt.Key_Alt:
            self.setFullScreen(not self.isFullScreen())
            event.accept()
        else:
            super(VideoWidget, self).keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        self.setFullScreen(not self.isFullScreen())
        event.accept()

    def videoSurface(self):
        return self.surface

    def UpdateSurface(self):
        self.surface.widget.update()

    def sizeHint(self):
        return self.surface.surfaceFormat().sizeHint()

    def GetCurrentFrame(self):
        ''' Return current frame QImage '''
        return self.surface.image

    def SetInvertColor(self, value):
        ''' Set Invert color filter '''
        global invertColorFilter
        invertColorFilter = value

    def SetObjectTracking(self, value):
        ''' Set Object Tracking '''
        global objectTracking
        objectTracking = value
        if value:
            self.video_cv2 = self.parent.video_cv2
            p = self.parent.player.position()
            self.video_cv2.set(cv2.CAP_PROP_POS_MSEC, p)
            success, image = self.video_cv2.read()

    def SetGray(self, value):
        ''' Set gray scale '''
        global grayColorFilter
        grayColorFilter = value

    def SetEdgeDetection(self, value):
        ''' Set Canny Edge filter '''
        global edgeDetectionFilter
        edgeDetectionFilter = value

    def SetAutoContrastFilter(self, value):
        ''' Set Automatic Contrast filter '''
        global contrastFilter
        contrastFilter = value

    def SetMonoFilter(self, value):
        ''' Set mono filter '''
        global monoFilter
        monoFilter = value

    def RestoreFilters(self):
        ''' Remove and restore all video filters '''
        global invertColorFilter, grayColorFilter, edgeDetectionFilter, monoFilter, contrastFilter
        invertColorFilter = grayColorFilter = edgeDetectionFilter = monoFilter = contrastFilter = False

    def GetXBlackZone(self):
        x = 0.0
        normalizedWidth = self.surface.widget.height(
        ) * (GetImageWidth() / GetImageHeight())
        if (self.surface.widget.width() / self.surface.widget.height()) > (GetImageWidth() / GetImageHeight()):
            x = (self.surface.widget.width() - (normalizedWidth)) / 2.0
        return x

    def GetYBlackZone(self):
        y = 0.0
        normalizedHeight = self.surface.widget.width(
        ) / (GetImageWidth() / GetImageHeight())
        if (self.surface.widget.width() / self.surface.widget.height()) < (GetImageWidth() / GetImageHeight()):
            y = (self.surface.widget.height() - (normalizedHeight)) / 2.0
        return y

    def IsPointOnScreen(self, x, y):
        ''' determines if a clicked point lands on the image (False if lands on the
            black borders or outside)
         '''
        res = True
        normalizedWidth = self.surface.widget.height(
        ) * (GetImageWidth() / GetImageHeight())
        normalizedHeight = self.surface.widget.width(
        ) / (GetImageWidth() / GetImageHeight())
        if x > (normalizedWidth + self.GetXBlackZone()) or x < self.GetXBlackZone():
            res = False
        if y > (normalizedHeight + self.GetYBlackZone()) or y < self.GetYBlackZone():
            res = False
        return res

    def GetXRatio(self):
        ''' ratio between event.x() and real image width on screen. '''
        return GetImageWidth() / (self.surface.widget.width() - (2 * self.GetXBlackZone()))

    def GetYRatio(self):
        ''' ratio between event.y() and real image height on screen. '''
        return GetImageHeight() / (self.surface.widget.height() - (2 * self.GetYBlackZone()))

    def GetTransf(self, event):
        ''' Return video coordinates to map coordinates '''
        return self.gt([(event.x() - self.GetXBlackZone()) * self.GetXRatio(), (event.y() - self.GetYBlackZone()) * self.GetYRatio()])    

    def paintEvent(self, event):
        ''' Paint Event '''
        self.gt = GetGCPGeoTransform()
        painter = QPainter(self)

        if (self.surface.isActive()):
            videoRect = self.surface.videoRect()
            if not videoRect.contains(event.rect()):
                region = event.region()
                region.subtracted(QRegion(videoRect))
                brush = self.palette().window()
                for rect in region.rects():
                    painter.fillRect(rect, brush)

            try:
                self.surface.paint(painter)
            except Exception:
                None
        else:
            painter.fillRect(event.rect(), self.palette().window())
        try:
            SetImageSize(self.surface.currentFrame.width(),
                         self.surface.currentFrame.height())
        except Exception:
            None

        #Draw clicked points on video
        for pt in self.drawPtPos:
            #adds a mark on the video
            self.drawPointOnVideo(pt)

        #Draw clicked lines on video
        for pt in self.drawLines:
            self.drawLinesOnVideo(pt)

        #Draw clicked Polygons on video adds a mark on the video
        # TODO
        self.drawPolygonOnVideo(self.drawPolygon)

        # Magnifier Glass
        if self.zoomed and magnifier:
            dim = min(self.width(), self.height())
            magnifierSize = min(MAX_MAGNIFIER, dim * 2 / 3)
            radius = magnifierSize / 2
            ring = radius - 15
            box = QSize(magnifierSize, magnifierSize)

            # reupdate our mask
            if self.maskPixmap.size() != box:
                self.maskPixmap = QPixmap(box)
                self.maskPixmap.fill(Qt.transparent)
                g = QRadialGradient()
                g.setCenter(radius, radius)
                g.setFocalPoint(radius, radius)
                g.setRadius(radius)
                g.setColorAt(1.0, QColor(64, 64, 64, 0))
                g.setColorAt(0.5, QColor(0, 0, 0, 255))
                mask = QPainter(self.maskPixmap)
                mask.setRenderHint(QPainter.Antialiasing)
                mask.setCompositionMode(QPainter.CompositionMode_Source)
                mask.setBrush(g)
                mask.setPen(Qt.NoPen)
                mask.drawRect(self.maskPixmap.rect())
                mask.setBrush(QColor(Qt.transparent))
                mask.drawEllipse(g.center(), ring, ring)
                mask.end()

            center = self.dragPos - QPoint(0, radius)
            center += QPoint(0, radius / 2)
            corner = center - QPoint(radius, radius)
            xy = center * 2 - QPoint(radius, radius)
            # only set the dimension to the magnified portion
            if self.zoomPixmap.size() != box:
                self.zoomPixmap = QPixmap(box)
                self.zoomPixmap.fill(Qt.lightGray)

            if True:
                painter = QPainter(self.zoomPixmap)
                painter.translate(-xy)
                self.largePixmap = QPixmap.fromImage(self.surface.image)
                painter.drawPixmap(self.offset, self.largePixmap)
                painter.end()

            clipPath = QPainterPath()
            clipPath.addEllipse(QPointF(center), ring, ring)
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipPath(clipPath)
            painter.drawPixmap(corner, self.zoomPixmap)
            painter.drawPixmap(corner, self.maskPixmap)
            painter.setPen(Qt.gray)
            painter.drawPath(clipPath)
        return

    def GetInverseMatrix(self, x, y):
        ''' inverse matrix transformation (lon-lat to video units x,y) '''
        transf = (~self.gt)([x, y])
        scr_x = (transf[0] / self.GetXRatio()) + self.GetXBlackZone()
        scr_y = (transf[1] / self.GetYRatio()) + self.GetYBlackZone()
        return scr_x, scr_y

    def drawLinesOnVideo(self, pt):
        ''' Draw Lines on Video '''
        scr_x, scr_y = self.GetInverseMatrix(pt[1], pt[0])

        radius = 3
        center = QPoint(scr_x, scr_y)

        pen = QPen(Qt.yellow)
        pen.setWidth(radius)
        pen.setCapStyle(Qt.RoundCap)
        pen.setDashPattern([1, 4, 5, 4])
        painter_p = QPainter(self)
        painter_p.setPen(pen)
        painter_p.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter_p.drawPoint(center)

        if len(self.drawLines) > 1:
            try:
                idx = self.drawLines.index(pt)
                scr_x, scr_y = self.GetInverseMatrix(self.drawLines[idx+1][1], self.drawLines[idx+1][0])
                end = QPoint(scr_x, scr_y)
                painter_p.drawLine(center, end)
            except Exception:
                None

        return

    def drawPointOnVideo(self, pt):
        ''' Draw Points on Video '''
        scr_x, scr_y = self.GetInverseMatrix(pt[1], pt[0])

        radius = 10
        center = QPoint(scr_x, scr_y)

        pen = QPen(Qt.red)
        pen.setWidth(radius)
        pen.setCapStyle(Qt.RoundCap)
        painter_p = QPainter(self)
        painter_p.setPen(pen)
        painter_p.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter_p.drawPoint(center)
        return

    def drawPolygonOnVideo(self, pt):
        ''' Draw Polygons on Video '''
#         scr_x, scr_y = self.GetInverseMatrix(pt[1], pt[0])
# 
#         radius = 10
#         center = QPoint(scr_x, scr_y)
# 
#         pen = QPen(Qt.red)
#         pen.setWidth(radius)
#         pen.setCapStyle(Qt.RoundCap)
#         painter_p = QPainter(self)
#         painter_p.setPen(pen)
#         painter_p.setRenderHint(QPainter.HighQualityAntialiasing, True)
#         painter_p.drawPoint(center)
        return

    def resizeEvent(self, event):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        QWidget.resizeEvent(self, event)
        self.zoomed = False
        self.surface.updateVideoRect()

    def mouseMoveEvent(self, event):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        # check if the point  is on picture (not in black borders)
        if(not self.IsPointOnScreen(event.x(), event.y())):
            return

        # Draw Line on the fly
        if self.gt is not None and lineDrawer:
                if len(self.drawLines) > 0:
                    scr_x, scr_y = self.GetInverseMatrix(self.drawLines[-1][1],self.drawLines[-1][1])

                    radius = 3
                    center = QPoint(scr_x, scr_y)

                    pen = QPen(Qt.yellow)
                    pen.setWidth(radius)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setDashPattern([1, 4, 5, 4])
                    painter_p = QPainter(self)
                    painter_p.setPen(pen)
                    painter_p.setRenderHint(QPainter.HighQualityAntialiasing, True) 
                    try:
                        transf = self.GetTransf(event)
                        scr_x, scr_y = self.GetInverseMatrix(float(round(transf[1], 4)) , float(round(transf[0], 4)))
                        end = QPoint(scr_x, scr_y)
                        painter_p.drawLine(center, end)
                        self.UpdateSurface()
                    except Exception:
                        None

        # Cursor Coordinates
        if self.gt is not None:

            transf = self.GetTransf(event)
            Longitude = transf[1]
            Latitude = transf[0]
            #Altitude = 0.0

            self.parent.lb_cursor_coord.setText("<span style='font-size:10pt; font-weight:bold;'>Lon :</span>" +
                                                "<span style='font-size:9pt; font-weight:normal;'>" + ("%.3f" % Longitude) + "</span>" +
                                                "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>" +
                                                "<span style='font-size:9pt; font-weight:normal;'>" + ("%.3f" % Latitude) + "</span>")
        else:
            self.parent.lb_cursor_coord.setText("<span style='font-size:10pt; font-weight:bold;'>Lon :</span>" +
                                                "<span style='font-size:9pt; font-weight:normal;'>Null</span>" +
                                                "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>" +
                                                "<span style='font-size:9pt; font-weight:normal;'>Null</span>")

        if not event.buttons():
            return

        if self.changeRubberBand:
            self.rubberBand.setGeometry(
                QRect(self.origin, event.pos()).normalized())

        if self.zoomed is True:
            self.rubberBand.hide()
            self.zoomedRect = False

        if not self.zoomed:
            if not self.pressed or not self.snapped:
                delta = event.pos() - self.pressPos
                self.pressPos = event.pos()
                self.pan(delta)
                return
            else:
                threshold = 10
                delta = event.pos() - self.pressPos
                if self.snapped:
                    self.snapped &= delta.x() < threshold
                    self.snapped &= delta.y() < threshold
                    self.snapped &= delta.x() > -threshold
                    self.snapped &= delta.y() > -threshold

                if not self.snapped:
                    self.tapTimer.stop()

        else:
            self.dragPos = event.pos()
            self.surface.updateVideoRect()

    def pan(self, delta):
        """ Pan Action """
        self.offset += delta
        self.surface.updateVideoRect()

    def timerEvent(self, _):
        """ Time Event """
        if not self.zoomed:
            self.activateMagnifier()
        self.surface.updateVideoRect()

    def mousePressEvent(self, event):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        if event.button() == Qt.LeftButton:
            self.pressed = self.snapped = True
            self.pressPos = self.dragPos = event.pos()
            self.tapTimer.stop()
            self.tapTimer.start(HOLD_TIME, self)

            if(not self.IsPointOnScreen(event.x(), event.y())):
                    return

            #point drawer
            if self.gt is not None and pointDrawer:
                transf = self.GetTransf(event)
                #targetAlt = GetFrameCenter()[2]
                Longitude = float(round(transf[1], 4))
                Latitude = float(round(transf[0], 4))
                #Altitude = targetAlt
                Altitude = 0.0
                pointLyr = qgsu.selectLayerByName(Point_lyr)
                pointLyr.startEditing()
                feature = QgsFeature()
                feature.setAttributes([Longitude, Latitude, Altitude])
                p = QgsPointXY()
                p.set(Longitude, Latitude)
                geom = QgsGeometry.fromPointXY(p)
                feature.setGeometry(geom)
                pointLyr.addFeatures([feature])

                CommonLayer(pointLyr)

                self.drawPtPos.append([Longitude, Latitude])

            #polygon drawer
            if self.gt is not None and polygonDrawer:
                transf = self.GetTransf(event)
                Longitude = float(round(transf[1], 4))
                Latitude = float(round(transf[0], 4))
                Altitude = 0.0
                return

            #line drawer
            if self.gt is not None and lineDrawer:
                transf = self.GetTransf(event)
                Longitude = float(round(transf[1], 4))
                Latitude = float(round(transf[0], 4))
                Altitude = 0.0
                linelyr = qgsu.selectLayerByName(Line_lyr)
                linelyr.startEditing()
                feature = QgsFeature()
                f = QgsFeature()
                if linelyr.featureCount() == 0:
                    f.setAttributes(
                        [Longitude, Latitude, Altitude])
                    surface = QgsGeometry.fromPolylineXY(
                        [QgsPointXY(Longitude, Latitude), QgsPointXY(Longitude, Latitude)])
                    f.setGeometry(surface)
                    linelyr.addFeatures([f])

                else:
                    f_last = linelyr.getFeature(linelyr.featureCount())
                    f.setAttributes(
                        [Longitude, Latitude, Altitude])
                    surface = QgsGeometry.fromPolylineXY(
                        [QgsPointXY(Longitude, Latitude),
                         QgsPointXY(f_last.attribute(0), f_last.attribute(1))])
                    f.setGeometry(surface)
                    linelyr.addFeatures([f])

                CommonLayer(linelyr)

                self.drawLines.append([Longitude, Latitude])

        self.UpdateSurface()

        if zoomRect and event.button() == Qt.LeftButton:
            self.origin = event.pos()
            self.rubberBand.setGeometry(QRect(self.origin, QSize()))
            self.rubberBand.show()
            self.changeRubberBand = True

    def activateMagnifier(self):
        """ Activate Magnifier Glass """
        self.zoomed = True
        self.tapTimer.stop()
        self.surface.updateVideoRect()

    def SetMagnifier(self, value):
        """ Set Magnifier Glass """
        global magnifier
        magnifier = value

    def SetPointDrawer(self, value):
        """ Set Point Drawer """
        global pointDrawer
        pointDrawer = value

    def SetLineDrawer(self, value):
        """ Set Line Drawer """
        global lineDrawer
        lineDrawer = value

    def SetPolygonDrawer(self, value):
        """ Set Polygon Drawer """
        global polygonDrawer
        polygonDrawer = value

    def SetZoomRect(self, value):
        """ Set Zoom Rectangle """
        global zoomRect
        zoomRect = value

    def mouseReleaseEvent(self, _):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        self.changeRubberBand = False
        if self.zoomed is True:
            return
        self.zoomed = False
        if not zoomRect:
            self.surface.updateVideoRect()
        else:
            # todo: remove and make object tracking
            self.rubberBand.hide()
            self.zoomedRect = True
            selRect = self.rubberBand.geometry()

            orig2widgScale = self.surface.widget.contentsRect().width() / \
                self.surface.image.width()

            X1 = selRect.topLeft().x() / orig2widgScale
            Y1 = selRect.topLeft().y() / orig2widgScale
            X2 = selRect.bottomRight().x() / self.surface.widget.contentsRect().bottomRight().x() * \
                self.surface.image.width()
            Y2 = selRect.bottomRight().y() / self.surface.widget.contentsRect().bottomRight().y() * \
                self.surface.image.height()

            wid2origRect = QRect(X1, Y1, X2, Y2)
            self.UpdateSurface()

    def leaveEvent(self, _):
        self.parent.lb_cursor_coord.setText("")
