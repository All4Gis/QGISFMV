# -*- coding: utf-8 -*-
"""Point / line / polygon / military symbol / censure painting on the video frame."""
import os

from qgis.PyQt.QtCore import QPointF, QPoint, QRectF
from qgis.PyQt.QtGui import (
    QPainter,
    QPainterPath,
    QColor,
    QFont,
    QPen,
    QBrush,
    QPolygonF,
)

from qgis.PyQt.QtSvg import QSvgRenderer

from QGISFMV.player.dialogs.QgsFmvMilitarySymbols import symbol_svg_path
from QGISFMV.player.drawing.QgsFmvDrawingConfig import (
    drawing_config,
    white_pen,
    black_pen,
    black_brush,
)
from QGISFMV.utils.logging import log

from QGISFMV.video.playback.QgsVideoUtils import VideoUtils as vut


def split_at_separators(draw_list):
    """Split a drawing list into sub-lists at [None, None, None] sentinels.

    Returns a list of sub-lists, each containing the points between separators.
    The last sub-list includes any trailing points after the final separator.
    """
    if not draw_list or not any(x[1] is None for x in draw_list):
        return [draw_list] if draw_list else []

    segments = []
    current = []
    for pt in draw_list:
        if pt[0] is None:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(pt)

    # Also capture trailing segment after last separator
    try:
        last_sep_idx = len(draw_list) - draw_list[::-1].index([None, None, None])
        tail = draw_list[last_sep_idx:]
        if len(tail) > 1:
            segments.append(tail)
    except ValueError:
        pass

    if current and current not in segments:
        segments.append(current)

    return [s for s in segments if len(s) > 1]


def draw_point_on_video(number, pt, painter, surface, gt):
    """Draw Points on Video"""
    cfg = drawing_config

    scr_x, scr_y = vut.GetInverseMatrix(pt[1], pt[0], gt, surface)

    # don't draw something outside the screen.
    if scr_x < vut.GetXBlackZone(surface) or scr_y < vut.GetYBlackZone(surface):
        return

    if scr_x > vut.GetXBlackZone(surface) + vut.GetNormalizedWidth(
        surface
    ) or scr_y > vut.GetYBlackZone(surface) + vut.GetNormalizedHeight(surface):
        return

    center = QPoint(int(scr_x), int(scr_y))

    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QBrush(cfg.PointFillColor))
    painter.setPen(cfg.PointPen)
    painter.drawEllipse(center, cfg.PointRadius, cfg.PointRadius)

    label = str(number)
    painter.setFont(cfg.PointFont)
    metrics = painter.fontMetrics()
    label_pos = center + QPoint(cfg.PointRadius + 5, -cfg.PointRadius - 2)
    text_width = metrics.horizontalAdvance(label)
    text_height = metrics.height()
    pad = 3
    badge = QRectF(
        label_pos.x() - pad,
        label_pos.y() - text_height + pad,
        text_width + 2 * pad,
        text_height + pad,
    )
    painter.setBrush(QBrush(cfg.PointLabelBgColor))
    painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
    painter.drawRoundedRect(badge, 4, 4)
    painter.setPen(QPen(cfg.PointLabelColor))
    painter.drawText(label_pos, label)
    return


def draw_military_symbol_on_video(entry, painter, surface, gt):
    """Draw a military SVG symbol on the video at geo coordinates.

    Same convention as points/lines: entry stores [lon, lat, ...], but
    GetInverseMatrix expects (lat, lon) to match the GCP transform.
    Symbols are redrawn every frame so they reappear when the footprint
    covers their location again.
    """
    if not entry or len(entry) < 4 or gt is None:
        return
    lon, lat = entry[0], entry[1]
    symbol_id = entry[3]
    unit_name = entry[4] if len(entry) > 4 else ""

    # Match draw_point_on_video: inverse uses (lat, lon), not (lon, lat).
    scr_x, scr_y = vut.GetInverseMatrix(lat, lon, gt, surface)
    if scr_x < vut.GetXBlackZone(surface) or scr_y < vut.GetYBlackZone(surface):
        return
    if scr_x > vut.GetXBlackZone(surface) + vut.GetNormalizedWidth(surface):
        return
    if scr_y > vut.GetYBlackZone(surface) + vut.GetNormalizedHeight(surface):
        return

    svg_path = symbol_svg_path(symbol_id)
    if not svg_path or not os.path.isfile(svg_path):
        return

    size = 36
    rect = QRectF(scr_x - size / 2, scr_y - size / 2, size, size)
    renderer = QSvgRenderer(svg_path)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, rect)

    if unit_name:
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        metrics = painter.fontMetrics()
        label_pos = QPoint(
            int(scr_x - metrics.horizontalAdvance(unit_name) / 2),
            int(scr_y + size / 2 + 12),
        )
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.drawText(label_pos + QPoint(1, 1), unit_name)
        painter.setPen(QPen(QColor(20, 30, 40)))
        painter.drawText(label_pos, unit_name)
    return


def draw_lines_on_video(pt, idx, painter, surface, gt, drawLines):
    """Draw Lines on Video"""
    scr_x, scr_y = vut.GetInverseMatrix(pt[1], pt[0], gt, surface)

    center = QPoint(int(scr_x), int(scr_y))

    painter.setPen(drawing_config.LinePen)

    if len(drawLines) > 1:
        try:
            pt = drawLines[idx + 1]
            scr_x, scr_y = vut.GetInverseMatrix(pt[1], pt[0], gt, surface)
            end = QPoint(int(scr_x), int(scr_y))
            painter.drawLine(center, end)

            # Draw Start/End Points
            painter.setPen(white_pen)
            painter.drawPoint(center)
            painter.drawPoint(end)
        except Exception as exc:
            log.debug("drawLineOnVideo segment failed: %s", exc)
    return


def draw_polygon_on_video(values, painter, surface, gt):
    """Draw Polygons on Video"""
    cfg = drawing_config
    poly = []
    for pt in values:
        scr_x, scr_y = vut.GetInverseMatrix(pt[1], pt[0], gt, surface)
        poly.append(QPointF(scr_x, scr_y))

    polygon = QPolygonF(poly)

    path = QPainterPath()
    path.addPolygon(polygon)

    painter.setPen(cfg.PolyPen)
    painter.drawPolygon(polygon)
    painter.fillPath(path, cfg.PolyBrush)
    painter.setPen(white_pen)
    painter.drawPoints(polygon)
    return


def draw_censured_on_video(painter, drawCesure):
    """Draw Censure on Video"""
    try:
        for geom in drawCesure:
            painter.setPen(black_pen)
            painter.setBrush(black_brush)
            painter.drawRect(
                geom[0].x(), geom[0].y(), geom[0].width(), geom[0].height()
            )

    except Exception as exc:
        log.debug("drawCensuredOnVideo failed: %s", exc)
    return
