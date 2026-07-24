# -*- coding: utf-8 -*-
"""Measure distance/area painting: labels, vertices and running totals."""
from qgis.PyQt.QtCore import QPointF, Qt, QPoint, QRectF
from qgis.PyQt.QtGui import (
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QBrush,
    QPolygonF,
)

from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance, polygon_area as _geo_polygon_area
from QGISFMV.player.drawing.QgsFmvDrawingConfig import drawing_config
from QGISFMV.utils.logging import log

from QGISFMV.video.playback.QgsVideoUtils import VideoUtils as vut

RulerTotalMeasure = 0.0


def _format_length_m(meters):
    from QGISFMV.utils.formatting import format_length
    return format_length(meters)


def _format_area_m2(area_m2):
    from QGISFMV.utils.formatting import format_area
    return format_area(area_m2)


def draw_measure_label(painter, anchor, text, accent=None, above=True):
    """Draw a dark rounded chip with measure text next to a vertex."""
    cfg = drawing_config
    painter.setFont(cfg.MeasureFont)
    metrics = painter.fontMetrics()
    text_w = metrics.horizontalAdvance(text)
    text_h = metrics.height()
    pad_x, pad_y = 6, 3
    dy = -(text_h + 8) if above else 8
    badge = QRectF(
        anchor.x() + 8,
        anchor.y() + dy,
        text_w + 2 * pad_x,
        text_h + 2 * pad_y,
    )
    painter.setBrush(QBrush(cfg.MeasureLabelBg))
    border = QColor(accent) if accent is not None else QColor(255, 255, 255, 160)
    painter.setPen(QPen(border, 1))
    painter.drawRoundedRect(badge, 5, 5)
    painter.setPen(QPen(cfg.MeasureLabelFg))
    painter.drawText(
        QPoint(int(badge.x() + pad_x), int(badge.y() + text_h + pad_y - 4)),
        text,
    )


def draw_measure_vertex(painter, point, radius=5):
    cfg = drawing_config
    painter.setBrush(QBrush(cfg.MeasureVertexFill))
    painter.setPen(QPen(cfg.MeasureVertexOutline, 2))
    painter.drawEllipse(point, radius, radius)


def reset_measure_distance():
    """Reset the cumulative distance measurement counter to zero."""
    global RulerTotalMeasure
    RulerTotalMeasure = 0.0


def draw_measure_distance_on_video(pt, idx, painter, surface, gt, drawMDistance):
    """Draw Measure Distance on Video"""
    if pt is None or pt[0] is None:
        return
    if idx + 1 >= len(drawMDistance):
        return
    end_pt = drawMDistance[idx + 1]
    if end_pt is None or end_pt[0] is None:
        return

    cfg = drawing_config
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        scr_x, scr_y = vut.GetInverseMatrix(pt[1], pt[0], gt, surface)
        center = QPoint(int(scr_x), int(scr_y))
        scr_x, scr_y = vut.GetInverseMatrix(end_pt[1], end_pt[0], gt, surface)
        end = QPoint(int(scr_x), int(scr_y))

        # Soft under-stroke for contrast on bright frames
        painter.setPen(cfg.MeasureGlowPen)
        painter.drawLine(center, end)
        painter.setPen(cfg.MeasurePen)
        painter.drawLine(center, end)

        distance = _geo_distance((pt[0], pt[1]), (end_pt[0], end_pt[1]))
        global RulerTotalMeasure
        RulerTotalMeasure += distance

        mid = QPoint(
            int((center.x() + end.x()) / 2),
            int((center.y() + end.y()) / 2),
        )
        draw_measure_label(
            painter,
            mid,
            _format_length_m(distance),
            accent=cfg.MeasurePen.color(),
            above=True,
        )
        # Total only on the last drawn segment of the current chain
        next_ok = (
            idx + 2 < len(drawMDistance)
            and drawMDistance[idx + 2] is not None
            and drawMDistance[idx + 2][0] is not None
        )
        if not next_ok:
            draw_measure_label(
                painter,
                end,
                "Σ " + _format_length_m(RulerTotalMeasure),
                accent=QColor(255, 193, 7),
                above=False,
            )

        draw_measure_vertex(painter, center)
        draw_measure_vertex(painter, end)
    except Exception as exc:
        log.debug("drawMeasureDistanceOnVideo segment failed: %s", exc)
    return


def draw_measure_area_on_video(values, painter, surface, gt):
    """Draw Measure Area on Video"""
    # Keep only valid geo vertices (skip None separators).
    ring = [pt for pt in (values or []) if pt is not None and pt[0] is not None]
    if len(ring) < 2:
        return
    try:
        # polygon_area expects a flat ring of (lon, lat[, ...]) points
        a_value = _geo_polygon_area(ring) if len(ring) >= 3 else 0.0
    except Exception as exc:
        log.debug("drawMeasureAreaOnVideo area failed: %s", exc)
        a_value = 0.0

    cfg = drawing_config
    poly = []
    lats = []
    lons = []
    for pt in ring:
        # Stored as [lon, lat, ...]; GetInverseMatrix expects (lat, lon).
        scr_x, scr_y = vut.GetInverseMatrix(pt[1], pt[0], gt, surface)
        poly.append(QPointF(scr_x, scr_y))
        lons.append(pt[0])
        lats.append(pt[1])
    if len(poly) < 2:
        return

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    polygon = QPolygonF(poly)
    path = QPainterPath()
    path.addPolygon(polygon)

    # Outline: measure pen; fill: amber brush
    area_pen = QPen(cfg.MeasurePen)
    area_pen.setWidth(max(2, cfg.MeasureWidth))
    painter.setPen(QPen(QColor(0, 0, 0, 100), area_pen.width() + 2))
    painter.drawPolygon(polygon)
    painter.setPen(area_pen)
    painter.drawPolygon(polygon)
    painter.fillPath(path, cfg.MeasureBrush)

    for p in poly:
        draw_measure_vertex(
            painter, QPoint(int(p.x()), int(p.y())), radius=4
        )

    # Centroid from lon/lat mean (stable for labels)
    if lats and lons:
        scr_x, scr_y = vut.GetInverseMatrix(
            sum(lats) / len(lats), sum(lons) / len(lons), gt, surface
        )
        centroid = QPoint(int(scr_x), int(scr_y))
    else:
        centroid = QPoint(int(polygon.boundingRect().center().x()), int(polygon.boundingRect().center().y()))

    if len(ring) >= 3:
        draw_measure_label(
            painter,
            centroid,
            _format_area_m2(a_value),
            accent=QColor(255, 193, 7),
            above=True,
        )
    return
