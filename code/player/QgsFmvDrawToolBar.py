# -*- coding: utf-8 -*-
from QGIS_FMV.utils.QgsFmvUtils import (SetImageSize,
                                        GetSensor,
                                        convertQImageToMat,
                                        GetLine3DIntersectionWithDEM,
                                        GetLine3DIntersectionWithPlane,
                                        CommonLayer,
                                        GetFrameCenter,
                                        GetGCPGeoTransform,
                                        hasElevationModel)


from QGIS_FMV.video.QgsVideoUtils import VideoUtils as vut
from PyQt5.QtCore import Qt, QRect, QPoint, QBasicTimer, QSize, QPointF
from PyQt5.QtGui import (QImage,
                         QPalette,
                         QPixmap,
                         QPainter,
                         QRegion,
                         QPainterPath,
                         QRadialGradient,
                         QColor,
                         QFont,
                         QPen,
                         QBrush,
                         QPolygonF,
                         QCursor)
try:
    from pydevd import *
except ImportError:
    None


class DrawToolBar(object):

    @staticmethod
    def drawPointOnVideo(number, pt, painter, surface):
        return
