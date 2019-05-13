# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import Qt, QRect, QPoint, QBasicTimer, QSize
from qgis.PyQt.QtGui import (QImage,
                         QPalette,
                         QPixmap,
                         QPainter,
                         QRegion,
                         QColor,
                         QBrush,
                         QCursor)
from PyQt5.QtMultimedia import (QAbstractVideoBuffer,
                                QVideoFrame,
                                QAbstractVideoSurface,
                                QVideoSurfaceFormat)
from PyQt5.QtMultimediaWidgets import QVideoWidget
from qgis.PyQt.QtWidgets import QWidget, QRubberBand

from QGIS_FMV.utils.QgsFmvUtils import (SetImageSize,
                                        convertQImageToMat,
                                        GetGCPGeoTransform,
                                        hasElevationModel,
                                        GetImageHeight)

from QGIS_FMV.utils.QgsFmvLayers import (AddDrawPointOnMap,
                                         AddDrawLineOnMap,
                                         AddDrawPolygonOnMap,
                                         RemoveLastDrawPolygonOnMap,
                                         RemoveAllDrawPolygonOnMap,
                                         RemoveLastDrawPointOnMap,
                                         RemoveAllDrawPointOnMap,
                                         RemoveAllDrawLineOnMap)

from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.video.QgsVideoFilters import VideoFilters as filter
from QGIS_FMV.video.QgsVideoUtils import VideoUtils as vut
from QGIS_FMV.player.QgsFmvDrawToolBar import DrawToolBar as draw
from qgis.gui import QgsRubberBand
from qgis.utils import iface
from qgis.core import Qgis as QGis, QgsPointXY

try:
    from pydevd import *
except ImportError:
    None

try:
    import cv2
except ImportError:
    None


class InteractionState(object):
    """ Interaction Video Player Class """

    def __init__(self):
        self.pointDrawer = False
        self.ruler = False
        self.lineDrawer = False
        self.polygonDrawer = False
        self.magnifier = False
        self.objectTracking = False
        self.censure = False
        self.HandDraw = False

    def clear(self):
        self.__init__()


class FilterState(object):
    """ Filters State Video Player Class """

    def __init__(self):
        self.contrastFilter = False
        self.monoFilter = False
        self.MirroredHFilter = False
        self.edgeDetectionFilter = False
        self.grayColorFilter = False
        self.invertColorFilter = False
        self.NDVI = False

    def clear(self):
        self.__init__()


class VideoWidgetSurface(QAbstractVideoSurface):

    def __init__(self, widget, parent=None):
        ''' Constructor '''
        super().__init__(parent)

        self.widget = widget
        self.imageFormat = QImage.Format_Invalid
        self.image = None

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
        ''' Stop Video '''
        self.currentFrame = QVideoFrame()
        self._targetRect = QRect()
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
            self.widget.repaint(self._targetRect)
            return True

    def videoRect(self):
        ''' Get Video Rectangle '''
        return self._targetRect

    def sourceRect(self):
        ''' Get Source Rectangle '''
        return self._sourceRect

    def updateVideoRect(self):
        ''' Update video rectangle '''
        size = self.surfaceFormat().sizeHint()
        size.scale(self.widget.size().boundedTo(size), Qt.KeepAspectRatio)
        self._targetRect = QRect(QPoint(0, 0), size)
        self._targetRect.moveCenter(self.widget.rect().center())

    def paint(self, painter):
        ''' Paint Frame'''
        if (self.currentFrame.map(QAbstractVideoBuffer.ReadOnly)):
            oldTransform = painter.transform()
            painter.setTransform(oldTransform)

        self.image = QImage(self.currentFrame.bits(),
                            self.currentFrame.width(),
                            self.currentFrame.height(),
                            self.currentFrame.bytesPerLine(),
                            self.imageFormat
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
        self.currentFrame.unmap()
        return


class VideoWidget(QVideoWidget):

    def __init__(self, parent=None):
        ''' Constructor '''
        super().__init__(parent)
        self.surface = VideoWidgetSurface(self)
        self.Tracking_RubberBand = QRubberBand(QRubberBand.Rectangle, self)

        self.Censure_RubberBand = QRubberBand(QRubberBand.Rectangle, self)

        pal = QPalette()
        pal.setBrush(QPalette.Highlight, QBrush(QColor(Qt.blue)))
        self.Tracking_RubberBand.setPalette(pal)

        pal = QPalette()
        pal.setBrush(QPalette.Highlight, QBrush(QColor(Qt.black)))
        self.Censure_RubberBand.setPalette(pal)

        self._interaction = InteractionState()
        self._filterSatate = FilterState()

        self.snapped = False
        self.zoomed = False
        self._isinit = False
        self.gt = None

        self.drawCesure = []
        self.poly_coordinates, self.drawPtPos, self.drawLines, self.drawRuler, self.drawPolygon = [], [], [], [], []
        self.poly_RubberBand = QgsRubberBand(
            iface.mapCanvas(), True)  # Polygon type
        # set rubber band style
        color = QColor(176, 255, 128)
        self.poly_RubberBand.setColor(color)
        color.setAlpha(190)
        self.poly_RubberBand.setStrokeColor(color)
        self.poly_RubberBand.setWidth(3)

        self.parent = parent.parent()

        palette = self.palette()
        palette.setColor(QPalette.Background, Qt.transparent)
        self.setPalette(palette)

        self.origin, self.pressPos, self.dragPos = QPoint(), QPoint(), QPoint()
        self.tapTimer = QBasicTimer()
        

    def removeLastLine(self):
        ''' Remove Last Line Objects '''
        if self.drawLines:
            try:
                if self.drawLines[-1][3] == "mouseMoveEvent":
                    del self.drawLines[-1] # Remove mouseMoveEvent element
            except Exception:
                None
            for pt in range(len(self.drawLines) - 1, -1, -1):
                del self.drawLines[pt]
                try:
                    if self.drawLines[pt - 1][0] is None:
                        break
                except Exception:
                    None
            self.UpdateSurface()
            AddDrawLineOnMap(self.drawLines)
        return

    def removeLastSegmentLine(self):
        ''' Remove Last Segment Line Objects '''
        try:
            if self.drawLines[-1][3] == "mouseMoveEvent":
                del self.drawLines[-1] # Remove mouseMoveEvent element
        except Exception:
            None
        if self.drawLines:
            if self.drawLines[-1][0] is None:
                del self.drawLines[-1]
            
            del self.drawLines[-1]
            self.UpdateSurface()
            AddDrawLineOnMap(self.drawLines)
        return

    def removeAllLines(self):
        ''' Resets Line List '''
        if self.drawLines:
            self.drawLines = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawLineOnMap()

    def ResetDrawRuler(self):
        ''' Resets Ruler List '''
        self.drawRuler = []

    def removeAllCensure(self):
        ''' Remove All Censure Objects '''
        if self.drawCesure:
            self.drawCesure = []

    def removeLastCensured(self):
        ''' Remove Last Censure Objects '''
        if self.drawCesure:
            del self.drawCesure[-1]

    def removeLastPoint(self):
        ''' Remove All Point Drawer Objects '''
        if self.drawPtPos:
            del self.drawPtPos[-1]
            self.UpdateSurface()
            RemoveLastDrawPointOnMap()
        return

    def removeAllPoint(self):
        ''' Remove All Point Drawer Objects '''
        if self.drawPtPos:
            self.drawPtPos = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPointOnMap()
        return

    def removeAllPolygon(self):
        ''' Remove All Polygon Drawer Objects '''
        if self.drawPolygon:
            self.drawPolygon = []
            self.UpdateSurface()
            # Clear all Layer
            RemoveAllDrawPolygonOnMap()

    def removeLastPolygon(self):
        ''' Remove Last Polygon Drawer Objects '''
        if self.drawPolygon:
            try:
                if self.drawPolygon[-1][3] == "mouseMoveEvent":
                    del self.drawPolygon[-1] # Remove mouseMoveEvent element
            except Exception:
                None
            for pt in range(len(self.drawPolygon) - 1, -1, -1):
                del self.drawPolygon[pt]
                try:
                    if self.drawPolygon[pt - 1][0] is None:
                        break
                except Exception:
                    None
            
            self.UpdateSurface()
            # remove last index layer
            RemoveLastDrawPolygonOnMap()

    def keyPressEvent(self, event):
        ''' Exit fullscreen '''
        if event.key() == Qt.Key_Escape and self.isFullScreen():
            self.setFullScreen(False)
            event.accept()
        elif event.key() == Qt.Key_Enter and event.modifiers() & Qt.Key_Alt:
            self.setFullScreen(not self.isFullScreen())
            event.accept()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        if GetImageHeight() == 0:
            return

        if(not vut.IsPointOnScreen(event.x(), event.y(), self.surface)):
            return

        if self.gt is not None and self._interaction.lineDrawer:
            self.drawLines.append([None, None, None])
            self.UpdateSurface()
            return
        if self.gt is not None and self._interaction.ruler:
            self.drawRuler.append([None, None, None])
            self.UpdateSurface()
            return
        if self.gt is not None and self._interaction.polygonDrawer:
            self.drawPolygon.append([None, None, None])

            AddDrawPolygonOnMap(self.poly_coordinates)

            # Empty RubberBand
            for _ in range(self.poly_RubberBand.numberOfVertices()):
                self.poly_RubberBand.removeLastPoint()
            # Empty List
            self.poly_coordinates = []
            self.UpdateSurface()
            return

        self.setFullScreen(not self.isFullScreen())
        event.accept()

    def videoSurface(self):
        ''' Return video Surface '''
        return self.surface

    def UpdateSurface(self):
        ''' Update Video Surface '''
        self.surface.widget.update()

    def sizeHint(self):
        ''' This property holds the recommended size for the widget '''
        return self.surface.surfaceFormat().sizeHint()

    def currentFrame(self):
        ''' Return current frame QImage '''
        return self.surface.image

    def SetInvertColor(self, value):
        ''' Set Invert color filter '''
        self._filterSatate.invertColorFilter = value

    def SetObjectTracking(self, value):
        ''' Set Object Tracking '''
        self._interaction.objectTracking = value

    def SetRuler(self, value):
        ''' Set Ruler '''
        self._interaction.ruler = value

    def SetHandDraw(self, value):
        ''' Set Hand Draw '''
        self._interaction.HandDraw = value

    def SetCensure(self, value):
        ''' Set Censure Video Parts '''
        self._interaction.censure = value

    def SetGray(self, value):
        ''' Set gray scale '''
        self._filterSatate.grayColorFilter = value

    def SetMirrorH(self, value):
        ''' Set Horizontal Mirror '''
        self._filterSatate.MirroredHFilter = value

    def SetNDVI(self, value):
        ''' Set NDVI '''
        self._filterSatate.NDVI = value

    def SetEdgeDetection(self, value):
        ''' Set Canny Edge filter '''
        self._filterSatate.edgeDetectionFilter = value

    def SetAutoContrastFilter(self, value):
        ''' Set Automatic Contrast filter '''
        self._filterSatate.contrastFilter = value

    def SetMonoFilter(self, value):
        ''' Set mono filter '''
        self._filterSatate.monoFilter = value

    def RestoreFilters(self):
        ''' Remove and restore all video filters '''
        self._filterSatate.clear()

    def RestoreDrawer(self):
        ''' Remove and restore all Drawer Options '''
        self._interaction.clear()

    def paintEvent(self, event):
        ''' Paint Event '''
        self.gt = GetGCPGeoTransform()

        self.painter = QPainter(self)
        self.painter.setRenderHint(QPainter.HighQualityAntialiasing)
        brush = self.palette().window()
 
        region = event.region()
        self.painter.fillRect(region.boundingRect() ,  brush)
 
        try:
            self.surface.paint(self.painter)
        except Exception:
            None
        
        try:
            SetImageSize(self.surface.currentFrame.width(),
                         self.surface.currentFrame.height())
        except Exception:
            None

        # Draw On Video
        draw.drawOnVideo(self.drawPtPos, self.drawLines, self.drawPolygon,
                         self.drawRuler, self.drawCesure, self.painter, self.surface, self.gt)

        
        # Draw On Video Object tracking test
        if self._interaction.objectTracking and self._isinit:
            frame = convertQImageToMat(self.currentFrame())
            # Update tracker
            ok, bbox = self.tracker.update(frame)
            # Draw bounding box
            if ok:
                print("bbox Traking: ", str(bbox))
                self.painter.setPen(Qt.blue)
                self.painter.drawRect(int(bbox[0]), int(
                    bbox[1]), int(bbox[2]), int(bbox[3]))
            else:
                qgsu.showUserAndLogMessage(
                    "Tracking failure detected ", "", level=QGis.Warning)
                
        # Magnifier Glass
        if self.zoomed and self._interaction.magnifier:
            #self.grab(self.surface.videoRect()).toImage()
            draw.drawMagnifierOnVideo(self, self.dragPos, self.currentFrame(), self.painter)

        self.painter.end()
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
        self.update()
        print (" widget : " + str(self.width())+"  "+str(self.height()) )
        print (" Video Rectangle : " + str(self.surface.videoRect().width())+"  "+str(self.surface.videoRect().height()))
        print (" Source Rectangle : " + str(self.surface.sourceRect().width())+"  "+str(self.surface.sourceRect().height()))

        
    def AddMoveEventValue(self, values, Longitude, Latitude, Altitude):
        """
        Remove and Add move value for fluid drawing
        """
        for idx, pt in enumerate(values):
            if pt[-1]=="mouseMoveEvent":
                del values[idx]
        values.append([Longitude, Latitude, Altitude, "mouseMoveEvent"])

    def mouseMoveEvent(self, event):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        # check if the point  is on picture (not in black borders)
        if(not vut.IsPointOnScreen(event.x(), event.y(), self.surface)):
            self.setCursor(QCursor(Qt.ArrowCursor))
            return
        
        # Prevent draw on video if not started or finished
        if self.parent.player.position() == 0:
            return  

        # Mouser cursor drawing
        if self._interaction.pointDrawer or self._interaction.polygonDrawer or self._interaction.lineDrawer or self._interaction.ruler or self._interaction.censure or self._interaction.objectTracking:
            self.setCursor(QCursor(Qt.CrossCursor))
            
        # Cursor Coordinates
        if self.gt is not None:

            Longitude, Latitude, Altitude = vut.GetPointCommonCoords(
                event, self.surface)
            
            txt = "<span style='font-size:10pt; font-weight:bold;'>Lon :</span>"
            txt += "<span style='font-size:9pt; font-weight:normal;'>" + \
                ("%.3f" % Longitude) + "</span>"
            txt += "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>"
            txt += "<span style='font-size:9pt; font-weight:normal;'>" + \
                ("%.3f" % Latitude) + "</span>"

            if hasElevationModel():
                txt += "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>"
                txt += "<span style='font-size:9pt; font-weight:normal;'>" + \
                    ("%.0f" % Altitude) + "</span>"
            else:
                txt += "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>"
                txt += "<span style='font-size:9pt; font-weight:normal;'>-</span>"

            self.parent.lb_cursor_coord.setText(txt)

            # Polygon drawer mouseMoveEvent
            if self._interaction.polygonDrawer:
                self.AddMoveEventValue(self.drawPolygon, Longitude, Latitude, Altitude)
                
            # Line drawer mouseMoveEvent
            if self._interaction.lineDrawer:
                self.AddMoveEventValue(self.drawLines, Longitude, Latitude, Altitude)
               
            # Ruler drawer mouseMoveEvent
            if self._interaction.ruler and self.drawRuler:
                self.AddMoveEventValue(self.drawRuler, Longitude, Latitude, Altitude)
            
            self.UpdateSurface()

        else:
            self.parent.lb_cursor_coord.setText("<span style='font-size:10pt; font-weight:bold;'>Lon :</span>" + 
                                                "<span style='font-size:9pt; font-weight:normal;'>-</span>" + 
                                                "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>" + 
                                                "<span style='font-size:9pt; font-weight:normal;'>-</span>" + 
                                                "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>" + 
                                                "<span style='font-size:9pt; font-weight:normal;'>-</span>")

        if not event.buttons():
            return

        # Object tracking rubberband
        if not self.Tracking_RubberBand.isHidden():
            self.Tracking_RubberBand.setGeometry(
                QRect(self.origin, event.pos()).normalized())

        # Censure rubberband
        if not self.Censure_RubberBand.isHidden():
            self.Censure_RubberBand.setGeometry(
                QRect(self.origin, event.pos()).normalized())

        # Magnifier mouseMoveEvent
        if not self.zoomed:
            delta = event.pos() - self.pressPos
            if not self.snapped:
                self.pressPos = event.pos()
                self.tapTimer.stop()
                return
            else:
                threshold = 10
                self.snapped &= delta.x() < threshold
                self.snapped &= delta.y() < threshold
                self.snapped &= delta.x() > -threshold
                self.snapped &= delta.y() > -threshold

        else:
            self.dragPos = event.pos()
            #self.dragPos = self.mapToParent(event.pos())
            self.surface.updateVideoRect()

    def timerEvent(self, _):
        """ Time Event (Magnifier method)"""
        if not self.zoomed:
            self.activateMagnifier()

    def mousePressEvent(self, event):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        if GetImageHeight() == 0:
            return
        
        # Prevent draw on video if not started or finished
        if self.parent.player.position() == 0:
            return  

        if event.button() == Qt.LeftButton:
            self.snapped = True
            self.pressPos = self.dragPos = event.pos()
            self.tapTimer.stop()
            self.tapTimer.start(100, self)

            if(not vut.IsPointOnScreen(event.x(), event.y(), self.surface)):
                self.UpdateSurface()
                return

            # point drawer
            if self.gt is not None and self._interaction.pointDrawer:
                Longitude, Latitude, Altitude = vut.GetPointCommonCoords(
                    event, self.surface)

                pointIndex = len(self.drawPtPos) + 1
                AddDrawPointOnMap(pointIndex, Longitude,
                                  Latitude, Altitude)

                self.drawPtPos.append([Longitude, Latitude, Altitude])

            # polygon drawer
            if self.gt is not None and self._interaction.polygonDrawer:
                Longitude, Latitude, Altitude = vut.GetPointCommonCoords(
                    event, self.surface)
                self.poly_RubberBand.addPoint(QgsPointXY(Longitude, Latitude))
                self.poly_coordinates.extend(QgsPointXY(Longitude, Latitude))
                self.drawPolygon.append([Longitude, Latitude, Altitude])

            # line drawer
            if self.gt is not None and self._interaction.lineDrawer:
                Longitude, Latitude, Altitude = vut.GetPointCommonCoords(
                    event, self.surface)

                self.drawLines.append([Longitude, Latitude, Altitude])

                AddDrawLineOnMap(self.drawLines)

            # Object Tracking Interaction
            if self._interaction.objectTracking:
                self.origin = event.pos()
                self.Tracking_RubberBand.setGeometry(
                    QRect(self.origin, QSize()))
                self.Tracking_RubberBand.show()

            # Censure Interaction
            if self._interaction.censure:
                self.origin = event.pos()
                self.Censure_RubberBand.setGeometry(
                    QRect(self.origin, QSize()))
                self.Censure_RubberBand.show()

            # Ruler drawer
            if self.gt is not None and self._interaction.ruler:
                Longitude, Latitude, Altitude = vut.GetPointCommonCoords(
                    event, self.surface)
                self.drawRuler.append([Longitude, Latitude, Altitude])

        # if not called, the paint event is not triggered.
        self.UpdateSurface()

    def activateMagnifier(self):
        """ Activate Magnifier Glass """
        self.zoomed = True
        self.tapTimer.stop()
        self.surface.updateVideoRect()

    def SetMagnifier(self, value):
        """ Set Magnifier Glass """
        self._interaction.magnifier = value

    def SetPointDrawer(self, value):
        """ Set Point Drawer """
        self._interaction.pointDrawer = value

    def SetLineDrawer(self, value):
        """ Set Line Drawer """
        self._interaction.lineDrawer = value

    def SetPolygonDrawer(self, value):
        """ Set Polygon Drawer """
        self._interaction.polygonDrawer = value

    def mouseReleaseEvent(self, _):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        # Prevent draw on video if not started or finished
        if self.parent.player.position() == 0:
            return  

        if self._interaction.censure:
            geom = self.Censure_RubberBand.geometry()
            self.Censure_RubberBand.hide()
            self.drawCesure.append([geom])

        if self._interaction.objectTracking:
            geom = self.Tracking_RubberBand.geometry()
            bbox = (geom.x(), geom.y(), geom.width(), geom.height())
            print("bbox Ori : ", str(bbox))
            img = self.currentFrame()
            print("imagen ORI : " + img.width() + " " + img.height())
            frame = convertQImageToMat(img)
            self.Tracking_RubberBand.hide()
            self.tracker = cv2.TrackerBoosting_create()
            #self.tracker.clear()
            ok = self.tracker.init(frame, bbox)
            if ok:
                self._isinit = True
            else:
                self._isinit = False

    def leaveEvent(self, _):
        self.parent.lb_cursor_coord.setText("")
        self.setCursor(QCursor(Qt.ArrowCursor))
