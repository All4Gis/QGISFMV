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
                         QBrush,
                         QPolygonF)

from PyQt5.QtMultimedia import (QAbstractVideoBuffer,
                                QVideoFrame,
                                QAbstractVideoSurface)
from PyQt5.QtMultimediaWidgets import QVideoWidget

from PyQt5.QtWidgets import QSizePolicy, QWidget, QRubberBand

from QGIS_FMV.utils.QgsFmvUtils import (SetImageSize,
                                        GetSensor,
                                        convertQImageToMat,
                                        GetLine3DIntersectionWithDEM,
                                        GetLine3DIntersectionWithPlane,
                                        CommonLayer,
                                        GetFrameCenter,
                                        GetGCPGeoTransform,
                                        hasElevationModel,
                                        GetImageWidth,
                                        GetImageHeight)

from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.video.QgsVideoFilters import VideoFilters as filter
from QGIS_FMV.fmvConfig import Point_lyr, Line_lyr, Polygon_lyr
from qgis.gui import QgsRubberBand
from qgis.utils import iface
from qgis.core import Qgis as QGis, QgsDistanceArea, QgsCoordinateReferenceSystem, QgsProject, QgsFeature, QgsGeometry, QgsPointXY

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

HOLD_TIME = 100
MAX_MAGNIFIER = 229


class VideoWidgetSurface(QAbstractVideoSurface):

    def __init__(self, widget, parent=None):
        ''' Constructor '''
        super(VideoWidgetSurface, self).__init__(parent)

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
            self.sourceRect = _format.viewport()
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
            painter.setRenderHint(QPainter.Antialiasing)

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

            painter.drawImage(self.targetRect, self.image, self.sourceRect)

            if objectTracking and self.widget._isinit:
                frame = convertQImageToMat(self.image)
                # Update tracker
                ok, bbox = self.widget.tracker.update(frame)
                # Draw bounding box
                if ok:
                    qgsu.showUserAndLogMessage("bbox : ",str(bbox), level=QGis.Warning)
                    painter.setPen(Qt.blue)
                    painter.drawRect(QRect(int(bbox[0]),int(bbox[1]),int(bbox[2]),int(bbox[3])));
                else:
                    qgsu.showUserAndLogMessage("Tracking failure detected ","", level=QGis.Warning)

            self.currentFrame.unmap()


class VideoWidget(QVideoWidget):

    def __init__(self, parent=None):
        ''' Constructor '''
        super(VideoWidget, self).__init__(parent)
        self.surface = VideoWidgetSurface(self)
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self)
        pal = QPalette()
        pal.setBrush(QPalette.Highlight, QBrush(QColor(Qt.blue)))
        self.rubberBand.setPalette(pal)
        self.setUpdatesEnabled(True)
        self.setMouseTracking(True)
        self.snapped = self.zoomed = self.TrackingRubberBand = False
        self._isinit = False
        self.gt = None

        self.poly_coordinates, self.drawPtPos, self.drawLines, self.drawPolygon = [], [], [], []
        self.poly_RubberBand = QgsRubberBand(iface.mapCanvas(), True) # Polygon type
        # set rubber band style
        color = QColor(176, 255, 128)
        self.poly_RubberBand.setColor(color)
        color.setAlpha(190)
        self.poly_RubberBand.setStrokeColor(color)
        self.poly_RubberBand.setWidth(3)

        self.parent = parent.parent()

        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_PaintOnScreen)
        self.setAttribute(Qt.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        palette = self.palette()
        palette.setColor(QPalette.Background, Qt.black)
        self.setPalette(palette)
        self.setSizePolicy(QSizePolicy.MinimumExpanding,
                           QSizePolicy.MinimumExpanding)

        self.offset, self.origin, self.pressPos, self.dragPos = QPoint(), QPoint(), QPoint(), QPoint()
        self.tapTimer = QBasicTimer()
        self.zoomPixmap, self.maskPixmap = QPixmap(), QPixmap()

    def keyPressEvent(self, event):
        ''' Exit fullscreen '''
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
        if(not self.IsPointOnScreen(event.x(), event.y())):
            return

        if self.gt is not None and lineDrawer:
            self.drawLines.append([None, None, None])
            self.UpdateSurface()
            return
        if self.gt is not None and polygonDrawer:
            self.drawPolygon.append([None, None, None])
            # Add Polygon
            polyLyr = qgsu.selectLayerByName(Polygon_lyr)
            polyLyr.startEditing()
            feature = QgsFeature()
            point = QPointF()
            # create  float polygon --> construcet out of 'point'

            list_polygon = QPolygonF()
            for x in xrange(0, len(self.poly_coordinates)):
                if x % 2 == 0:
                    point.setX(self.poly_coordinates[x])
                    point.setY(self.poly_coordinates[x+1])
                    list_polygon.append(point)
            point.setX(self.poly_coordinates[0])
            point.setY(self.poly_coordinates[1])
            list_polygon.append(point)

            geomP = QgsGeometry.fromQPolygonF(list_polygon)
            feature.setGeometry(geomP)

            # Calculate Area WSG84 (Meters)
            area_wsg84 = QgsDistanceArea()
            area_wsg84.setSourceCrs(QgsCoordinateReferenceSystem.fromOgcWmsCrs('EPSG:4326'), QgsProject.instance().transformContext())
            if (area_wsg84.sourceCrs().isGeographic()):
                area_wsg84.setEllipsoid(area_wsg84.sourceCrs().ellipsoidAcronym())

            # Calculate Centroid
            centroid = feature.geometry().centroid().asPoint()

            feature.setAttributes([centroid.x(), centroid.y(), 0.0, area_wsg84.measurePolygon(geomP.asPolygon()[0])])

            polyLyr.addFeatures([feature])

            CommonLayer(polyLyr)
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
        ''' Return is X in black screen on video '''
        x = 0.0
        normalizedWidth = self.surface.widget.height(
        ) * (GetImageWidth() / GetImageHeight())
        if (self.surface.widget.width() / self.surface.widget.height()) > (GetImageWidth() / GetImageHeight()):
            x = (self.surface.widget.width() - (normalizedWidth)) / 2.0
        return x

    def GetYBlackZone(self):
        ''' Return is Y in black screen on video '''
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

    def GetPointCommonCoords(self, event):
        ''' Common functon for get coordinates on mousepressed '''
        transf = self.GetTransf(event)
        targetAlt = GetFrameCenter()[2]

        Longitude = float(round(transf[1], 4))
        Latitude = float(round(transf[0], 4))
        Altitude = float(round(targetAlt, 0))

        if hasElevationModel():
            sensor = GetSensor()
            target = [transf[0], transf[1], targetAlt]
            projPt = GetLine3DIntersectionWithDEM(sensor, target)
            if projPt:
                Longitude = float(round(projPt[1], 4))
                Latitude = float(round(projPt[0], 4))
                Altitude = float(round(projPt[2], 0))
        return Longitude, Latitude, Altitude

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
        if len(self.drawLines) > 1:
            for idx, pt in enumerate(self.drawLines):
                if pt[0] is None:
                    continue
                else:
                    self.drawLinesOnVideo(pt, idx)

        # Draw clicked Polygons on video
        if len(self.drawPolygon) > 1:
            poly = []
            if any(None == x[1] for x in self.drawPolygon):
                for pt in self.drawPolygon:
                    if pt[0] is None:
                        self.drawPolygonOnVideo(poly)
                        poly = []
                        continue
                    poly.append(pt)
                last_occurence = len(self.drawPolygon)-self.drawPolygon[::-1].index([None, None, None])
                poly = []
                for pt in range(last_occurence, len(self.drawPolygon)):
                    poly.append(self.drawPolygon[pt])
                if len(poly) > 1:
                    self.drawPolygonOnVideo(poly)
            else:
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
            painter.end()
        return

    def GetInverseMatrix(self, x, y):
        ''' inverse matrix transformation (lon-lat to video units x,y) '''
        transf = (~self.gt)([x, y])
        scr_x = (transf[0] / self.GetXRatio()) + self.GetXBlackZone()
        scr_y = (transf[1] / self.GetYRatio()) + self.GetYBlackZone()
        return scr_x, scr_y

    def drawLinesOnVideo(self, pt, idx):
        ''' Draw Lines on Video '''
        if hasElevationModel():
            pt = GetLine3DIntersectionWithPlane(GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = self.GetInverseMatrix(pt[1], pt[0])

        radius = 3
        center = QPoint(scr_x, scr_y)

        pen = QPen(Qt.yellow)
        pen.setWidth(radius)
        pen.setCapStyle(Qt.RoundCap)
        pen.setDashPattern([1, 4, 5, 4])
        painter = QPainter(self)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.drawPoint(center)

        if len(self.drawLines) > 1:
            try:
                pt = self.drawLines[idx+1]
                if hasElevationModel():
                    pt = GetLine3DIntersectionWithPlane(GetSensor(), pt, GetFrameCenter()[2])
                scr_x, scr_y = self.GetInverseMatrix(pt[1], pt[0])
                end = QPoint(scr_x, scr_y)
                painter.drawLine(center, end)
            except Exception:
                None
        painter.end()
        return

    def drawPointOnVideo(self, pt):
        ''' Draw Points on Video '''
        if hasElevationModel():
            pt = GetLine3DIntersectionWithPlane(GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = self.GetInverseMatrix(pt[1], pt[0])

        radius = 10
        center = QPoint(scr_x, scr_y)

        pen = QPen(Qt.red)
        pen.setWidth(radius)
        pen.setCapStyle(Qt.RoundCap)

        painter = QPainter(self)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.drawPoint(center)
        painter.end()
        return

    def drawPolygonOnVideo(self, values):
        ''' Draw Polygons on Video '''
        poly = []
        for pt in values:
            if hasElevationModel():
                pt = GetLine3DIntersectionWithPlane(GetSensor(), pt, GetFrameCenter()[2])
            scr_x, scr_y = self.GetInverseMatrix(pt[1], pt[0])
            center = QPoint(scr_x, scr_y)
            poly.append(center)

        poly.append(poly[0])

        radius = 3
        polygon = QPolygonF(poly)
        pen = QPen()
        pen.setColor(Qt.green)
        pen.setWidth(radius)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)

        brush = QBrush()
        brush.setColor(QColor(176, 255, 128, 28))
        brush.setStyle(Qt.SolidPattern)

        path = QPainterPath()
        path.addPolygon(polygon)

        painter = QPainter(self)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.HighQualityAntialiasing, True)
        painter.drawPolygon(polygon)
        painter.fillPath(path, brush)
        painter.end()
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

        # Cursor Coordinates
        if self.gt is not None:

            Longitude, Latitude, Altitude = self.GetPointCommonCoords(event)

            txt = "<span style='font-size:10pt; font-weight:bold;'>Lon :</span>"
            txt += "<span style='font-size:9pt; font-weight:normal;'>" + ("%.3f" % Longitude) + "</span>" 
            txt += "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>" 
            txt += "<span style='font-size:9pt; font-weight:normal;'>" + ("%.3f" % Latitude) + "</span>"

            if hasElevationModel():
                txt += "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>"
                txt += "<span style='font-size:9pt; font-weight:normal;'>" + ("%.0f" % Altitude) + "</span>"
            else:
                txt += "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>"
                txt += "<span style='font-size:9pt; font-weight:normal;'>-</span>"

            self.parent.lb_cursor_coord.setText(txt)

        else:
            self.parent.lb_cursor_coord.setText("<span style='font-size:10pt; font-weight:bold;'>Lon :</span>" +
                                                "<span style='font-size:9pt; font-weight:normal;'>-</span>" +
                                                "<span style='font-size:10pt; font-weight:bold;'> Lat :</span>" +
                                                "<span style='font-size:9pt; font-weight:normal;'>-</span>"+
                                                "<span style='font-size:10pt; font-weight:bold;'> Alt :</span>" +
                                                "<span style='font-size:9pt; font-weight:normal;'>-</span>")

        if not event.buttons():
            return

        if self.TrackingRubberBand:
            self.rubberBand.setGeometry(
                QRect(self.origin, event.pos()).normalized())

        if not self.zoomed:
            delta = event.pos() - self.pressPos
            if not self.snapped:
                self.pressPos = event.pos()
                self.pan(delta)
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
            self.snapped = True
            self.pressPos = self.dragPos = event.pos()
            self.tapTimer.stop()
            self.tapTimer.start(HOLD_TIME, self)

            if(not self.IsPointOnScreen(event.x(), event.y())):
                    self.UpdateSurface()
                    return

            #point drawer
            if self.gt is not None and pointDrawer:
                Longitude, Latitude, Altitude = self.GetPointCommonCoords(event)
                #add pin point on the map
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

                self.drawPtPos.append([Longitude, Latitude, Altitude])

            #polygon drawer
            if self.gt is not None and polygonDrawer:
                Longitude, Latitude, Altitude = self.GetPointCommonCoords(event)
                self.poly_RubberBand.addPoint(QgsPointXY(Longitude, Latitude))
                self.poly_coordinates.extend(QgsPointXY(Longitude, Latitude))
                self.drawPolygon.append([Longitude, Latitude, Altitude])

            #line drawer
            if self.gt is not None and lineDrawer:
                Longitude, Latitude, Altitude = self.GetPointCommonCoords(event)

                #add pin on the map
                linelyr = qgsu.selectLayerByName(Line_lyr)
                linelyr.startEditing()
                feature = QgsFeature()
                f = QgsFeature()
                if linelyr.featureCount() == 0 or self.drawLines[-1][0] is None:
                    f.setAttributes(
                        [Longitude, Latitude, Altitude])
                    geom = QgsGeometry.fromPolylineXY(
                        [QgsPointXY(Longitude, Latitude), QgsPointXY(Longitude, Latitude)])
                    f.setGeometry(geom)
                    linelyr.addFeatures([f])

                else:
                    f_last = linelyr.getFeature(linelyr.featureCount())
                    f.setAttributes(
                        [Longitude, Latitude, Altitude])
                    geom = QgsGeometry.fromPolylineXY(
                        [QgsPointXY(Longitude, Latitude),
                         QgsPointXY(f_last.attribute(0), f_last.attribute(1))])
                    f.setGeometry(geom)
                    linelyr.addFeatures([f])

                CommonLayer(linelyr)

                self.drawLines.append([Longitude, Latitude, Altitude])

            if objectTracking:
                self.origin = event.pos()
                self.rubberBand.setGeometry(QRect(self.origin, QSize()))
                self.rubberBand.show()
                self.TrackingRubberBand = True

        #if not called, the paint event is not triggered.
        self.UpdateSurface()

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

    def mouseReleaseEvent(self, _):
        """
        :type event: QMouseEvent
        :param event:
        :return:
        """
        self.TrackingRubberBand = False
        if objectTracking:
            geom = self.rubberBand.geometry()
            bbox = (geom.x(), geom.y(), geom.width(), geom.height())
            frame = convertQImageToMat(self.GetCurrentFrame())
            self.rubberBand.hide()
            self.tracker = cv2.TrackerBoosting_create()
            self.tracker.clear()
            ok = self.tracker.init(frame, bbox)
            if ok:
                self._isinit = True
            else:
                self._isinit = False

    def leaveEvent(self, _):
        self.parent.lb_cursor_coord.setText("")
