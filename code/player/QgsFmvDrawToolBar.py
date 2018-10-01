# -*- coding: utf-8 -*-
from QGIS_FMV.utils.QgsFmvUtils import (GetSensor,
                                        GetLine3DIntersectionWithPlane,
                                        GetFrameCenter,
                                        hasElevationModel)

from PyQt5.QtCore import QSize, QPointF
from QGIS_FMV.video.QgsVideoUtils import VideoUtils as vut
from PyQt5.QtCore import Qt, QPoint
from QGIS_FMV.geo import sphere as sphere
from PyQt5.QtGui import (QPainter,
                         QPainterPath,
                         QColor,
                         QFont,
                         QPixmap,
                         QRadialGradient,
                         QPen,
                         QBrush,
                         QPolygonF)
try:
    from pydevd import *
except ImportError:
    None

RulerTotalMeasure = 0.0


class DrawToolBar(object):

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

        radius = 10
        center = QPoint(scr_x, scr_y)

        pen = QPen(Qt.red)
        pen.setWidth(radius)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPoint(center)
        font12 = QFont("Arial", 12, weight=QFont.Bold)
        painter.setFont(font12)
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

        radius = 3
        center = QPoint(scr_x, scr_y)

        pen = QPen(Qt.yellow)
        pen.setWidth(radius)
        pen.setCapStyle(Qt.RoundCap)
        pen.setDashPattern([1, 4, 5, 4])

        painter.setPen(pen)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.drawPoint(center)

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

        painter.setPen(pen)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.drawPolygon(polygon)
        painter.fillPath(path, brush)
        return

    @staticmethod
    def resetRulerDistance():
        global RulerTotalMeasure
        RulerTotalMeasure = 0.0

    @staticmethod
    def drawRulerOnVideo(pt, idx, painter, surface, gt, drawRuler):
        ''' Draw Lines on Video '''
        if hasElevationModel():
            pt = GetLine3DIntersectionWithPlane(
                GetSensor(), pt, GetFrameCenter()[2])

        scr_x, scr_y = vut.GetInverseMatrix(
            pt[1], pt[0], gt, surface)

        center_pt = pt

        radius_pt = 5
        center = QPoint(scr_x, scr_y)

        if len(drawRuler) > 1:
            try:
                pen = QPen(Qt.red)
                pen.setWidth(3)
                painter.setPen(pen)

                end_pt = drawRuler[idx + 1]

                if hasElevationModel():
                    end_pt = GetLine3DIntersectionWithPlane(
                        GetSensor(), end_pt, GetFrameCenter()[2])
                scr_x, scr_y = vut.GetInverseMatrix(
                    end_pt[1], end_pt[0], gt, surface)
                end = QPoint(scr_x, scr_y)
                painter.drawLine(center, end)

                font12 = QFont("Arial", 12, weight=QFont.Bold)
                painter.setFont(font12)

                distance = round(sphere.distance(
                    (center_pt[0], center_pt[1]), (end_pt[0], end_pt[1])), 2)

                text = str(distance) + " m"
                global RulerTotalMeasure
                RulerTotalMeasure += distance

                # Draw Start/End Points
                pen = QPen(Qt.white)
                pen.setWidth(radius_pt)
                pen.setCapStyle(Qt.RoundCap)
                painter.setPen(pen)
                painter.setRenderHint(QPainter.HighQualityAntialiasing)
                painter.drawPoint(center)
                painter.drawPoint(end)

                painter.drawText(end + QPoint(5, -5), text)

                pen = QPen(QColor(255, 51, 153))
                painter.setPen(pen)
                painter.drawText(end + QPoint(5, 10),
                                 str(round(RulerTotalMeasure, 2)) + " m")

            except Exception:
                None
        return

    @staticmethod
    def drawMagnifierOnVideo(width, height, maskPixmap, dragPos, zoomPixmap, surface, painter, offset):
        dim = min(width, height)
        MAX_MAGNIFIER = 229
        magnifierSize = min(MAX_MAGNIFIER, dim * 2 / 3)
        radius = magnifierSize / 2
        ring = radius - 15
        box = QSize(magnifierSize, magnifierSize)

        # reupdate our mask
        if maskPixmap.size() != box:
            maskPixmap = QPixmap(box)
            maskPixmap.fill(Qt.transparent)
            g = QRadialGradient()
            g.setCenter(radius, radius)
            g.setFocalPoint(radius, radius)
            g.setRadius(radius)
            g.setColorAt(1.0, QColor(64, 64, 64, 0))
            g.setColorAt(0.5, QColor(0, 0, 0, 255))
            mask = QPainter(maskPixmap)
            mask.setRenderHint(QPainter.HighQualityAntialiasing)
            mask.setCompositionMode(QPainter.CompositionMode_Source)
            mask.setBrush(g)
            mask.setPen(Qt.NoPen)
            mask.drawRect(maskPixmap.rect())
            mask.setBrush(QColor(Qt.transparent))
            mask.drawEllipse(g.center(), ring, ring)
            mask.end()

        center = dragPos - QPoint(0, radius)
        center += QPoint(0, radius / 2)
        corner = center - QPoint(radius, radius)
        xy = center * 2 - QPoint(radius, radius)
        # only set the dimension to the magnified portion
        if zoomPixmap.size() != box:
            zoomPixmap = QPixmap(box)
            zoomPixmap.fill(Qt.lightGray)

        if True:
            painter_p = QPainter(zoomPixmap)
            painter_p.translate(-xy)
            largePixmap = QPixmap.fromImage(surface.image)
            painter_p.drawPixmap(offset, largePixmap)
            painter_p.end()

        clipPath = QPainterPath()
        clipPath.addEllipse(QPointF(center), ring, ring)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)
        painter.setClipPath(clipPath)
        painter.drawPixmap(corner, zoomPixmap)
        painter.setClipping(False)
        painter.drawPixmap(corner, maskPixmap)
        painter.setPen(Qt.gray)
        painter.drawPath(clipPath)
        return
