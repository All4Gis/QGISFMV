# -*- coding: utf-8 -*-
from QGIS_FMV.utils.QgsFmvUtils import (GetSensor,
                                        GetLine3DIntersectionWithPlane,
                                        GetFrameCenter,
                                        hasElevationModel)

from qgis.PyQt.QtCore import QSize, QPointF
from QGIS_FMV.video.QgsVideoUtils import VideoUtils as vut
from qgis.PyQt.QtCore import Qt, QPoint
from QGIS_FMV.geo import sphere

from qgis.PyQt.QtGui import (QPainter,
                         QPainterPath,
                         QColor,
                         QFont,
                         QPixmap,
                         QPen,
                         QBrush,
                         QPolygonF)
try:
    from pydevd import *
except ImportError:
    None

RulerTotalMeasure = 0.0


class DrawToolBar(object):
    
    MAX_MAGNIFIER = 250
    zoomPixmap = QPixmap()
    
    line_width = 3
    yellow_pen = QPen(QColor(252,215,108),line_width) 

    small_pt = 5
    white_pen = QPen(Qt.white, small_pt)
    white_pen.setCapStyle(Qt.RoundCap)
    
    black_pen = QPen(Qt.black, small_pt)
    black_pen.setCapStyle(Qt.RoundCap)
    
    green_pen = QPen(QColor(185, 224, 175),line_width, cap=Qt.RoundCap, join=Qt.RoundJoin)

    big_radius = 10
    red_pen = QPen(QColor(220, 20, 60), big_radius, cap=Qt.RoundCap)
    
    glass_pen = QPen(QColor(192, 192, 192, 128), 6)
    
    green_brush = QBrush(QColor(185, 224, 175, 100))
    yellow_brush = QBrush(QColor(252,215,108, 100))
    transparent_brush = QBrush(Qt.transparent)
    
    black_brush = QBrush(Qt.black)
    
    bold_12 = QFont("Arial", 12, QFont.Bold)
        
          
    @staticmethod
    def drawOnVideo(drawPtPos, drawLines, drawPolygon, drawMDistance, drawMArea, drawCesure, painter, surface, gt):
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
            if any(None == x[1] for x in drawPolygon):
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
            if any(None == x[1] for x in drawMArea):
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
        if hasElevationModel():
            pt = GetLine3DIntersectionWithPlane(
                GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = vut.GetInverseMatrix(
            pt[1], pt[0], gt, surface)

        # don't draw something outside the screen.
        if scr_x < vut.GetXBlackZone(surface) or scr_y < vut.GetYBlackZone(surface):
            return

        if scr_x > vut.GetXBlackZone(surface) + vut.GetNormalizedWidth(surface) or scr_y > vut.GetYBlackZone(surface) + vut.GetNormalizedHeight(surface):
            return
       
        center = QPoint(scr_x, scr_y)
        
        painter.setPen(DrawToolBar.red_pen)
        painter.drawPoint(center)
        painter.setFont(DrawToolBar.bold_12)
        painter.drawText(center + QPoint(5, -5), str(number))
        return

    @staticmethod
    def drawLinesOnVideo(pt, idx, painter, surface, gt, drawLines):
        ''' Draw Lines on Video '''
        if hasElevationModel():
            pt = GetLine3DIntersectionWithPlane(
                GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = vut.GetInverseMatrix(
            pt[1], pt[0], gt, surface)

        center = QPoint(scr_x, scr_y)

        painter.setPen(DrawToolBar.yellow_pen)

        if len(drawLines) > 1:
            try:
                pt = drawLines[idx + 1]
                if hasElevationModel():
                    pt = GetLine3DIntersectionWithPlane(
                        GetSensor(), pt, GetFrameCenter()[2])
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
            if hasElevationModel():
                pt = GetLine3DIntersectionWithPlane(
                    GetSensor(), pt, GetFrameCenter()[2])
            scr_x, scr_y = vut.GetInverseMatrix(
                pt[1], pt[0], gt, surface)
            center = QPoint(scr_x, scr_y)
            poly.append(center)
 
        polygon = QPolygonF(poly)
        
        path = QPainterPath()
        path.addPolygon(polygon)

        painter.setPen(DrawToolBar.yellow_pen)
        painter.drawPolygon(polygon)
        painter.fillPath(path, DrawToolBar.yellow_brush)
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
        if hasElevationModel():
            pt = GetLine3DIntersectionWithPlane(
                GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = vut.GetInverseMatrix(
            pt[1], pt[0], gt, surface)

        center = QPoint(scr_x, scr_y)

        if len(drawMDistance) > 1:
            try:
                painter.setPen(DrawToolBar.green_pen)

                end_pt = drawMDistance[idx + 1]

                if hasElevationModel():
                    end_pt = GetLine3DIntersectionWithPlane(
                        GetSensor(), end_pt, GetFrameCenter()[2])
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
                painter.setPen(DrawToolBar.green_pen)
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
            if hasElevationModel():
                pt = GetLine3DIntersectionWithPlane(
                    GetSensor(), pt, GetFrameCenter()[2])
            scr_x, scr_y = vut.GetInverseMatrix(
                pt[1], pt[0], gt, surface)
            center = QPoint(scr_x, scr_y)
            poly.append(center)
            
            lat.append(pt[0])
            long.append(pt[1])

#         Fix: Temporary correction
#         mousePressEvent calls after mouseMoveEvent.
#         A problem occurs because the centroid is miscalculated.
#         We remove duplicates values
        lat = list(dict.fromkeys(lat))
        long = list(dict.fromkeys(long))

        # Calculate Centroid Position
        scr_x, scr_y = vut.GetInverseMatrix(
                sum(long)/len(long), sum(lat)/len(lat), gt, surface)
        
        centroid = QPoint(scr_x, scr_y)
        
        # Create Poligon
        polygon = QPolygonF(poly)
        
        path = QPainterPath()
        path.addPolygon(polygon)
        
        painter.setFont(DrawToolBar.bold_12)
        painter.setPen(DrawToolBar.green_pen)
        painter.drawPolygon(polygon)
        painter.fillPath(path, DrawToolBar.green_brush)
        painter.setPen(DrawToolBar.white_pen)
        painter.drawPoints(polygon)
        
        # Area
        if a_value >= 10000:
            painter.drawText(centroid , str(round(a_value/1000000, 2)) + " km²")
        else:
            painter.drawText(centroid , str(round(a_value, 2)) + " m²")
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
        #print (" source : " + str(source.width()) + "   " + str(source.height()))
        oldTransform = painter.transform()
        painter.setTransform(oldTransform)
        painter.setBrush(DrawToolBar.transparent_brush)
        dim = min(widget.width(), widget.height())
        magnifierSize = min(DrawToolBar.MAX_MAGNIFIER, dim * 2 / 3)
        radius = magnifierSize / 2
        ring = radius - 15
        box = QSize(magnifierSize,magnifierSize)

        center = dragPos - QPoint(0, radius)
        center += QPoint(0, radius / 2)
        corner = center - QPoint(radius, radius)
        xy = center * 2 - QPoint(radius, radius)
        # only set the dimension to the magnified portion
        if DrawToolBar.zoomPixmap.size() != box:
            zoomPixmap = QPixmap(box)
            zoomPixmap.fill(Qt.lightGray)

        painter_p = QPainter(zoomPixmap)
        painter_p.translate(-xy)
        painter_p.drawImage(QPoint(0,0), source)
        #painter_p.drawImage(widget.surface.videoRect(), source, widget.surface.sourceRect())
        painter_p.end()

        clipPath = QPainterPath()
        clipPath.addEllipse(QPointF(center), ring, ring)
        painter.setClipPath(clipPath)
        painter.drawPixmap(corner, zoomPixmap)
        #print (" zoomPixmap : " + str(zoomPixmap.width()) + "   " + str(zoomPixmap.height()))
        painter.setPen(DrawToolBar.glass_pen)
        painter.drawPath(clipPath)
        return
