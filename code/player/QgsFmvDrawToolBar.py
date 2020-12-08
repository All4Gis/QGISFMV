# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QSize, QPointF, Qt, QPoint, QSettings
from qgis.PyQt.QtGui import (QPainter,
                         QPainterPath,
                         QColor,
                         QFont,
                         QPixmap,
                         QPen,
                         QBrush,
                         QPolygonF)

from PyQt5.QtGui import QImage

from QGIS_FMV.geo import sphere
from QGIS_FMV.utils.QgsFmvUtils import (GetSensor,
                                        GetLine3DIntersectionWithPlane,
                                        GetFrameCenter,
                                        hasElevationModel,
                                        getNameSpace)
                                        
from QGIS_FMV.video.QgsVideoUtils import VideoUtils as vut

from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu

try:
    from pydevd import *
except ImportError:
    None

RulerTotalMeasure = 0.0
MAX_MAGNIFIER = 250
MAX_FACTOR = 2
TYPE_MAGNIFIER = 1

# Polygon Draw
PolyWidth = 3
PolyPen = QPen(QColor(252, 215, 108), PolyWidth)
PolyBrush = QBrush(QColor(252, 215, 108, 100))

# Point Draw
PointWidth = 10
PointPen = QPen(QColor(220, 20, 60), PointWidth, cap=Qt.RoundCap)

# Line Draw
LineWidth = 3
LinePen = QPen(QColor(252, 215, 108), LineWidth)

# Measure Draw
MeasureWidth = 3
MeasurePen = QPen(QColor(185, 224, 175), MeasureWidth, cap=Qt.RoundCap, join=Qt.RoundJoin)
MeasureBrush = QBrush(QColor(185, 224, 175, 100))


class DrawToolBar(object):

    NameSpace = getNameSpace()

    small_pt = 5
    white_pen = QPen(Qt.white, small_pt)
    white_pen.setCapStyle(Qt.RoundCap)

    black_pen = QPen(Qt.black, small_pt)
    black_pen.setCapStyle(Qt.RoundCap)

    glass_pen = QPen(QColor(192, 192, 192, 128), 3)

    transparent_brush = QBrush(Qt.transparent)

    black_brush = QBrush(Qt.black)

    bold_12 = QFont("Arial", 12, QFont.Bold)

    # Stamp Image
    confidential = QPixmap.fromImage(QImage(":/imgFMV/images/stamp/confidential.png"))

    @staticmethod
    def setValues(options=None):
        ''' Function to set Drawing Values '''
        s = QSettings()

        # Magnifier Glass #

        shape_type = s.value(DrawToolBar.NameSpace + "/Options/magnifier/shape")
        if shape_type is not None:
            global TYPE_MAGNIFIER
            TYPE_MAGNIFIER = shape_type
            if options is not None:
                if TYPE_MAGNIFIER == 0:
                    # Square
                    options.rB_Square_m.setChecked(True)
                else:
                    # Circle
                    options.rB_Circle_m.setChecked(True)

        mFactor = s.value(DrawToolBar.NameSpace + "/Options/magnifier/factor")
        if mFactor is not None:
            global MAX_FACTOR
            MAX_FACTOR = int(mFactor)
            if options is not None:
                options.sb_factor.setValue(MAX_FACTOR)

        mSize = s.value(DrawToolBar.NameSpace + "/Options/magnifier/size")
        if mSize is not None:
            global MAX_MAGNIFIER
            MAX_MAGNIFIER = int(mSize)
            if options is not None:
                options.sl_Size.setValue(MAX_MAGNIFIER)

        # Drawings #

        poly_w = s.value(DrawToolBar.NameSpace + "/Options/drawings/polygons/width")
        if poly_w is not None:
            global PolyWidth
            PolyWidth = int(poly_w)
            if options is not None:
                options.poly_width.setValue(PolyWidth)

        poly_p = s.value(DrawToolBar.NameSpace + "/Options/drawings/polygons/pen")
        if poly_p is not None:
            global PolyPen
            PolyPen = QPen(QColor(poly_p))
            PolyPen.setCapStyle(Qt.RoundCap)
            PolyPen.setWidth(PolyWidth)
            if options is not None:
                options.poly_pen.setColor(QColor(poly_p))

        poly_b = s.value(DrawToolBar.NameSpace + "/Options/drawings/polygons/brush")
        if poly_b is not None:
            global PolyBrush
            PolyBrush = QBrush(QColor(poly_b))
            if options is not None:
                options.poly_brush.setColor(QColor(poly_b))

        point_w = s.value(DrawToolBar.NameSpace + "/Options/drawings/points/width")
        if point_w is not None:
            global PointWidth
            PointWidth = int(point_w)
            if options is not None:
                options.point_width.setValue(PointWidth)

        point_p = s.value(DrawToolBar.NameSpace + "/Options/drawings/points/pen")
        if point_p is not None:
            global PointPen
            PointPen = QPen(QColor(point_p))
            PointPen.setCapStyle(Qt.RoundCap)
            PointPen.setWidth(PointWidth)
            if options is not None:
                options.point_pen.setColor(QColor(point_p))

        line_w = s.value(DrawToolBar.NameSpace + "/Options/drawings/lines/width")
        if line_w is not None:
            global LineWidth
            LineWidth = int(line_w)
            if options is not None:
                options.lines_width.setValue(LineWidth)

        line_p = s.value(DrawToolBar.NameSpace + "/Options/drawings/lines/pen")
        if line_p is not None:
            global LinePen
            LinePen = QPen(QColor(line_p))
            LinePen.setCapStyle(Qt.RoundCap)
            LinePen.setWidth(LineWidth)
            if options is not None:
                options.lines_pen.setColor(QColor(line_p))

        measure_w = s.value(DrawToolBar.NameSpace + "/Options/drawings/measures/width")
        if measure_w is not None:
            global MeasureWidth
            MeasureWidth = int(measure_w)
            if options is not None:
                options.measures_width.setValue(MeasureWidth)

        measure_p = s.value(DrawToolBar.NameSpace + "/Options/drawings/measures/pen")
        if measure_p is not None:
            global MeasurePen
            MeasurePen = QPen(QColor(measure_p))
            MeasurePen.setCapStyle(Qt.RoundCap)
            MeasurePen.setWidth(MeasureWidth)
            if options is not None:
                options.measures_pen.setColor(QColor(measure_p))

        measure_b = s.value(DrawToolBar.NameSpace + "/Options/drawings/measures/brush")
        if measure_b is not None:
            global MeasureBrush
            MeasureBrush = QBrush(QColor(measure_b))
            if options is not None:
                options.measures_brush.setColor(QColor(measure_b))

        return

    @staticmethod
    def drawOnVideo(drawPtPos, drawLines, drawPolygon, drawMDistance, drawMArea, drawCesure, painter, surface, gt):
        ''' Function to paint over the video '''
        # Draw clicked points on video
        for position, pt in enumerate(drawPtPos):
            DrawToolBar.drawPointOnVideo(position + 1, pt, painter, surface, gt)

        # Draw clicked lines on video
        if len(drawLines) > 1:
            for idx, pt in enumerate(drawLines):
                if pt[0] is None:
                    continue
                else:
                    DrawToolBar.drawLinesOnVideo(
                        pt, idx, painter, surface, gt, drawLines)

        # Draw clicked Polygons on video
        if len(drawPolygon) > 1:
            poly = []
            if any(x[1] is None for x in drawPolygon):
                for pt in drawPolygon:
                    if pt[0] is None:
                        DrawToolBar.drawPolygonOnVideo(
                            poly, painter, surface, gt)
                        poly = []
                        continue
                    poly.append(pt)
                last_occurence = len(
                    drawPolygon) - drawPolygon[::-1].index([None, None, None])
                poly = []
                for pt in range(last_occurence, len(drawPolygon)):
                    poly.append(drawPolygon[pt])
                if len(poly) > 1:
                    DrawToolBar.drawPolygonOnVideo(
                        poly, painter, surface, gt)
            else:
                DrawToolBar.drawPolygonOnVideo(
                    drawPolygon, painter, surface, gt)

        # Draw Measure Distance on video
        # the measures don't persist in the video
        if len(drawMDistance) > 1:
            DrawToolBar.resetMeasureDistance()
            for idx, pt in enumerate(drawMDistance):
                if pt[0] is None:
                    DrawToolBar.resetMeasureDistance()
                    continue
                else:
                    DrawToolBar.drawMeasureDistanceOnVideo(
                        pt, idx, painter, surface, gt, drawMDistance)

        # Draw Measure Area on video
        # the measures don't persist in the video
        if len(drawMArea) > 1:
            poly = []
            if any(x[1] is None for x in drawMArea):
                for pt in drawMArea:
                    if pt[0] is None:
                        DrawToolBar.drawMeasureAreaOnVideo(
                            poly, painter, surface, gt)
                        poly = []
                        continue
                    poly.append(pt)
                last_occurence = len(
                    drawMArea) - drawMArea[::-1].index([None, None, None])
                poly = []
                for pt in range(last_occurence, len(drawMArea)):
                    poly.append(drawMArea[pt])
                if len(poly) > 1:
                    DrawToolBar.drawMeasureAreaOnVideo(
                        poly, painter, surface, gt)
            else:
                DrawToolBar.drawMeasureAreaOnVideo(
                    drawMArea, painter, surface, gt)

        # Draw Censure
        if drawCesure:
            DrawToolBar.drawCensuredOnVideo(painter, drawCesure)
            return

        return

    @staticmethod
    def drawPointOnVideo(number, pt, painter, surface, gt):
        ''' Draw Points on Video '''
               
        #if hasElevationModel():
        #    pt = GetLine3DIntersectionWithPlane(
        #        GetSensor(), pt, GetFrameCenter()[2])
        
        scr_x, scr_y = vut.GetInverseMatrix(
            pt[1], pt[0], gt, surface)
                
        # don't draw something outside the screen.
        if scr_x < vut.GetXBlackZone(surface) or scr_y < vut.GetYBlackZone(surface):
            return

        if scr_x > vut.GetXBlackZone(surface) + vut.GetNormalizedWidth(surface) or scr_y > vut.GetYBlackZone(surface) + vut.GetNormalizedHeight(surface):
            return

        center = QPoint(scr_x, scr_y)

        painter.setPen(PointPen)
        painter.drawPoint(center)
        painter.setFont(DrawToolBar.bold_12)
        painter.drawText(center + QPoint(5, -5), str(number))
        return

    @staticmethod
    def drawLinesOnVideo(pt, idx, painter, surface, gt, drawLines):
        ''' Draw Lines on Video '''
#         if hasElevationModel():
#             pt = GetLine3DIntersectionWithPlane(
#                 GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = vut.GetInverseMatrix(
            pt[1], pt[0], gt, surface)

        center = QPoint(scr_x, scr_y)

        painter.setPen(LinePen)

        if len(drawLines) > 1:
            try:
                pt = drawLines[idx + 1]
#                 if hasElevationModel():
#                     pt = GetLine3DIntersectionWithPlane(
#                         GetSensor(), pt, GetFrameCenter()[2])
                scr_x, scr_y = vut.GetInverseMatrix(
                    pt[1], pt[0], gt, surface)
                end = QPoint(scr_x, scr_y)
                painter.drawLine(center, end)

                # Draw Start/End Points
                painter.setPen(DrawToolBar.white_pen)
                painter.drawPoint(center)
                painter.drawPoint(end)
            except Exception:
                None
        return

    @staticmethod
    def drawPolygonOnVideo(values, painter, surface, gt):
        ''' Draw Polygons on Video '''
        poly = []
        for pt in values:
#             if hasElevationModel():
#                 pt = GetLine3DIntersectionWithPlane(
#                     GetSensor(), pt, GetFrameCenter()[2])
            scr_x, scr_y = vut.GetInverseMatrix(
                pt[1], pt[0], gt, surface)
            center = QPoint(scr_x, scr_y)
            poly.append(center)

        polygon = QPolygonF(poly)

        path = QPainterPath()
        path.addPolygon(polygon)

        painter.setPen(PolyPen)
        painter.drawPolygon(polygon)
        painter.fillPath(path, PolyBrush)
        painter.setPen(DrawToolBar.white_pen)
        painter.drawPoints(polygon)
        return

    @staticmethod
    def resetMeasureDistance():
        global RulerTotalMeasure
        RulerTotalMeasure = 0.0

    @staticmethod
    def drawMeasureDistanceOnVideo(pt, idx, painter, surface, gt, drawMDistance):
        ''' Draw Measure Distance on Video '''
#         if hasElevationModel():
#             pt = GetLine3DIntersectionWithPlane(
#                 GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = vut.GetInverseMatrix(
            pt[1], pt[0], gt, surface)

        center = QPoint(scr_x, scr_y)

        if len(drawMDistance) > 1:
            try:
                painter.setPen(MeasurePen)

                end_pt = drawMDistance[idx + 1]

#                 if hasElevationModel():
#                     end_pt = GetLine3DIntersectionWithPlane(
#                         GetSensor(), end_pt, GetFrameCenter()[2])
                scr_x, scr_y = vut.GetInverseMatrix(
                    end_pt[1], end_pt[0], gt, surface)
                end = QPoint(scr_x, scr_y)
                painter.drawLine(center, end)

                painter.setFont(DrawToolBar.bold_12)

                distance = round(sphere.distance(
                    (pt[0], pt[1]), (end_pt[0], end_pt[1])), 2)

                text = str(distance) + " m"
                global RulerTotalMeasure
                RulerTotalMeasure += distance

                # Line lenght
                painter.setPen(MeasurePen)
                painter.drawText(end + QPoint(5, -10), text)

                painter.setPen(DrawToolBar.white_pen)
                # Total lenght
                painter.drawText(end + QPoint(5, 10),
                                 str(round(RulerTotalMeasure, 2)) + " m")

                # Draw Start/End Points
                painter.drawPoint(center)
                painter.drawPoint(end)
            except Exception:
                None
        return

    @staticmethod
    def drawMeasureAreaOnVideo(values, painter, surface, gt):
        ''' Draw Measure Area on Video '''
        a_value = sphere.polygon_area([values])

        poly = []
        lat = []
        long = []
        for pt in values:
#             if hasElevationModel():
#                 pt = GetLine3DIntersectionWithPlane(
#                     GetSensor(), pt, GetFrameCenter()[2])
            scr_x, scr_y = vut.GetInverseMatrix(
                pt[1], pt[0], gt, surface)
            center = QPoint(scr_x, scr_y)
            poly.append(center)

            lat.append(pt[0])
            long.append(pt[1])

        lat = list(dict.fromkeys(lat))
        long = list(dict.fromkeys(long))

        # Calculate Centroid Position
        scr_x, scr_y = vut.GetInverseMatrix(
            sum(long) / len(long), sum(lat) / len(lat), gt, surface)

        centroid = QPoint(scr_x, scr_y)

        # Create Poligon
        polygon = QPolygonF(poly)

        path = QPainterPath()
        path.addPolygon(polygon)

        painter.setFont(DrawToolBar.bold_12)

        painter.setPen(MeasurePen)
        painter.drawPolygon(polygon)
        painter.fillPath(path, MeasureBrush)
        painter.setPen(DrawToolBar.white_pen)
        painter.drawPoints(polygon)

        # Area
        if a_value >= 10000:
            painter.drawText(centroid, str(round(a_value / 1000000, 2)) + " km²")
        else:
            painter.drawText(centroid, str(round(a_value, 2)) + " m²")
        return

    @staticmethod
    def drawCensuredOnVideo(painter, drawCesure):
        ''' Draw Censure on Video '''
        try:
            for geom in drawCesure:
                painter.setPen(DrawToolBar.black_pen)
                painter.setBrush(DrawToolBar.black_brush)
                painter.drawRect(geom[0].x(), geom[0].y(),
                                 geom[0].width(), geom[0].height())

        except Exception:
            None
        return

    @staticmethod
    def drawMagnifierOnVideo(widget, dragPos, source, painter):
        ''' Draw Magnifier on Video '''
        oldTransform = painter.transform()
        painter.setTransform(oldTransform)
        painter.setBrush(DrawToolBar.transparent_brush)
        dim = min(widget.width(), widget.height())

        magnifierSize = min(MAX_MAGNIFIER, dim * 2 / 3)
        radius = magnifierSize / 2
        ring = radius - 15
        box = QSize(magnifierSize, magnifierSize)

        center = dragPos - QPoint(0, radius)
        center += QPoint(0, radius / 2)
        corner = center - QPoint(radius, radius)

        xy = center * MAX_FACTOR - QPoint(radius, radius)

        # only set the dimension to the magnified portion
        zoomPixmap = QPixmap(box)
        zoomPixmap.fill(Qt.black)

        painter_p = QPainter(zoomPixmap)
        painter_p.setRenderHint(QPainter.HighQualityAntialiasing)
        painter_p.translate(-xy)
        painter_p.scale(MAX_FACTOR, MAX_FACTOR)
        painter_p.drawImage(widget.surface.videoRect(), source, widget.surface.sourceRect())

        painter_p.end()

        clipPath = QPainterPath()
        center = QPointF(center)

        # Shape Type
        if TYPE_MAGNIFIER == 0:
            # Square
            clipPath.addRect(center.x(), center.y(), magnifierSize, magnifierSize)
            clipPath.translate(-radius, -radius)
        else:
            # Circle
            clipPath.addEllipse(center, ring, ring)

        painter.setClipPath(clipPath)
        painter.drawPixmap(corner, zoomPixmap)
        painter.setPen(DrawToolBar.glass_pen)
        painter.drawPath(clipPath)
        return

    @staticmethod
    def drawStampOnVideo(widget, painter):
        ''' Draw Stamp Confidential on Video '''
        painter.drawPixmap(widget.surface.videoRect(), DrawToolBar.confidential, widget.surface.sourceRect())

