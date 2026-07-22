# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtCore import QPointF, Qt, QPoint, QSettings, QRectF
from qgis.PyQt.QtGui import (
    QPainter,
    QPainterPath,
    QColor,
    QFont,
    QPixmap,
    QPen,
    QBrush,
    QPolygonF,
)

from qgis.PyQt.QtGui import QImage

from qgis.PyQt.QtSvg import QSvgRenderer

from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance, polygon_area as _geo_polygon_area
from QGISFMV.player.dialogs.QgsFmvMilitarySymbols import symbol_svg_path
from QGISFMV.utils.core.QgsFmvUtils import getNameSpace
from QGISFMV.utils.logging import log

from QGISFMV.video.playback.QgsVideoUtils import VideoUtils as vut

RulerTotalMeasure = 0.0


class DrawingConfig:
    """All mutable drawing parameters in one place."""

    __slots__ = (
        "MAX_MAGNIFIER", "MAX_FACTOR", "TYPE_MAGNIFIER",
        "PolyWidth", "PolyPen", "PolyBrush",
        "PointRadius", "PointFillColor", "PointOutlineColor",
        "PointLabelColor", "PointLabelBgColor", "PointPen", "PointFont",
        "LineWidth", "LinePen",
        "TrackLockColor", "TrackWeakColor", "TrackLostColor", "TrackHudFont",
        "MeasureWidth", "MeasurePen", "MeasureBrush",
        "MeasureLabelBg", "MeasureLabelFg",
        "MeasureVertexFill", "MeasureVertexOutline",
        "MeasureFont", "MeasureGlowPen",
    )

    def __init__(self):
        # Magnifier
        self.MAX_MAGNIFIER = 250
        self.MAX_FACTOR = 2
        self.TYPE_MAGNIFIER = 1

        # Polygon Draw
        self.PolyWidth = 3
        self.PolyPen = QPen(QColor(252, 215, 108), self.PolyWidth)
        self.PolyBrush = QBrush(QColor(252, 215, 108, 100))

        # Point Draw
        self.PointRadius = 6
        self.PointFillColor = QColor(255, 112, 67)
        self.PointOutlineColor = QColor(255, 255, 255)
        self.PointLabelColor = QColor(255, 255, 255)
        self.PointLabelBgColor = QColor(55, 71, 79, 220)
        self.PointPen = QPen(self.PointOutlineColor, 2, cap=Qt.PenCapStyle.RoundCap)
        self.PointFont = QFont("Segoe UI", 10, QFont.Weight.Bold)

        # Line Draw
        self.LineWidth = 3
        self.LinePen = QPen(QColor(252, 215, 108), self.LineWidth)

        # Object tracking HUD
        self.TrackLockColor = QColor(76, 175, 80)
        self.TrackWeakColor = QColor(255, 152, 0)
        self.TrackLostColor = QColor(229, 57, 53)
        self.TrackHudFont = QFont("Segoe UI", 9, QFont.Weight.Bold)

        # Measure Draw
        self.MeasureWidth = 3
        self.MeasurePen = QPen(
            QColor(0, 188, 212),
            self.MeasureWidth,
            cap=Qt.PenCapStyle.RoundCap,
            join=Qt.PenJoinStyle.RoundJoin,
        )
        self.MeasureBrush = QBrush(QColor(255, 193, 7, 100))
        self.MeasureLabelBg = QColor(20, 30, 40, 210)
        self.MeasureLabelFg = QColor(255, 255, 255)
        self.MeasureVertexFill = QColor(0, 188, 212)
        self.MeasureVertexOutline = QColor(255, 255, 255)
        self.MeasureFont = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.MeasureGlowPen = QPen(
            QColor(0, 0, 0, 110),
            self.MeasureWidth + 2,
            cap=Qt.PenCapStyle.RoundCap,
            join=Qt.PenJoinStyle.RoundJoin,
        )


drawing_config = DrawingConfig()


class DrawToolBar(object):

    NameSpace = getNameSpace()

    small_pt = 5
    white_pen = QPen(Qt.GlobalColor.white, small_pt)
    white_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    black_pen = QPen(Qt.GlobalColor.black, small_pt)
    black_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

    glass_pen = QPen(QColor(192, 192, 192, 128), 3)

    transparent_brush = QBrush(Qt.GlobalColor.transparent)

    black_brush = QBrush(Qt.GlobalColor.black)

    # Original confidential stamp PNG (no generated overlay)
    confidential = QPixmap()

    @staticmethod
    def _ensureStampImage():
        if not DrawToolBar.confidential.isNull():
            return
        try:
            from QGISFMV.utils.settings.QgsFmvSettings import plugin_root

            stamp_path = os.path.join(
                plugin_root(), "images", "stamp", "confidential.png"
            )
            if os.path.isfile(stamp_path):
                DrawToolBar.confidential = QPixmap(stamp_path)
        except Exception as exc:
            log.debug("Stamp image load failed: %s", exc)
        if DrawToolBar.confidential.isNull():
            DrawToolBar.confidential = QPixmap.fromImage(
                QImage(":/imgFMV/images/stamp/confidential.png")
            )

    @staticmethod
    def setValues(options=None):
        """Load drawing tool settings from QSettings and update drawing_config."""
        cfg = drawing_config
        DrawToolBar._ensureStampImage()
        s = QSettings()
        ns = DrawToolBar.NameSpace + "/Options"

        def _load_int(key, attr):
            val = s.value(f"{ns}/{key}")
            if val is not None:
                setattr(cfg, attr, int(val))

        def _load_pen(key, pen_attr, width_attr):
            val = s.value(f"{ns}/{key}")
            if val is not None:
                pen = QPen(QColor(val))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setWidth(getattr(cfg, width_attr))
                setattr(cfg, pen_attr, pen)

        # Magnifier settings
        shape_type = s.value(f"{ns}/magnifier/shape")
        if shape_type is not None:
            cfg.TYPE_MAGNIFIER = int(shape_type)
            if options is not None:
                if int(shape_type) == 0:
                    options.rB_Square_m.setChecked(True)
                else:
                    options.rB_Circle_m.setChecked(True)

        _load_int("magnifier/factor", "MAX_FACTOR")
        if options is not None:
            val = s.value(f"{ns}/magnifier/factor")
            if val is not None:
                options.sb_factor.setValue(int(val))

        _load_int("magnifier/size", "MAX_MAGNIFIER")
        if options is not None:
            val = s.value(f"{ns}/magnifier/size")
            if val is not None:
                options.sl_Size.setValue(int(val))

        # Polygon settings
        _load_int("drawings/polygons/width", "PolyWidth")
        if options is not None:
            val = s.value(f"{ns}/drawings/polygons/width")
            if val is not None:
                options.poly_width.setValue(int(val))

        poly_color = s.value(f"{ns}/drawings/polygons/pen")
        if poly_color is not None:
            cfg.PolyPen = QPen(QColor(poly_color))
            cfg.PolyPen.setCapStyle(Qt.PenCapStyle.RoundCap)
            cfg.PolyPen.setWidth(cfg.PolyWidth)
            if options is not None:
                options.poly_pen.setColor(QColor(poly_color))

        poly_brush_val = s.value(f"{ns}/drawings/polygons/brush")
        if poly_brush_val is not None:
            cfg.PolyBrush = QBrush(QColor(poly_brush_val))
            if options is not None:
                options.poly_brush.setColor(QColor(poly_brush_val))

        # Point settings
        _load_int("drawings/points/width", "PointRadius")
        if options is not None:
            val = s.value(f"{ns}/drawings/points/width")
            if val is not None:
                options.point_width.setValue(int(val))

        pt_color = s.value(f"{ns}/drawings/points/pen")
        if pt_color is not None:
            cfg.PointFillColor = QColor(pt_color)
            cfg.PointPen = QPen(cfg.PointOutlineColor, 2, cap=Qt.PenCapStyle.RoundCap)
            if options is not None:
                options.point_pen.setColor(QColor(pt_color))

        # Line settings
        _load_int("drawings/lines/width", "LineWidth")
        if options is not None:
            val = s.value(f"{ns}/drawings/lines/width")
            if val is not None:
                options.lines_width.setValue(int(val))

        _load_pen("drawings/lines/pen", "LinePen", "LineWidth")
        if options is not None:
            val = s.value(f"{ns}/drawings/lines/pen")
            if val is not None:
                options.lines_pen.setColor(QColor(val))

        # Measure settings
        _load_int("drawings/measures/width", "MeasureWidth")
        if options is not None:
            val = s.value(f"{ns}/drawings/measures/width")
            if val is not None:
                options.measures_width.setValue(int(val))

        m_color = s.value(f"{ns}/drawings/measures/pen")
        if m_color is not None:
            cfg.MeasurePen = QPen(QColor(m_color))
            cfg.MeasurePen.setCapStyle(Qt.PenCapStyle.RoundCap)
            cfg.MeasurePen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            cfg.MeasurePen.setWidth(cfg.MeasureWidth)
            cfg.MeasureVertexFill = QColor(m_color)
            cfg.MeasureGlowPen = QPen(
                QColor(0, 0, 0, 110), cfg.MeasureWidth + 2,
                cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin,
            )
            if options is not None:
                options.measures_pen.setColor(QColor(m_color))

        m_brush_val = s.value(f"{ns}/drawings/measures/brush")
        if m_brush_val is not None:
            cfg.MeasureBrush = QBrush(QColor(m_brush_val))
            if options is not None:
                options.measures_brush.setColor(QColor(m_brush_val))

    @staticmethod
    def _format_length_m(meters):
        from QGISFMV.utils.formatting import format_length
        return format_length(meters)

    @staticmethod
    def _format_area_m2(area_m2):
        from QGISFMV.utils.formatting import format_area
        return format_area(area_m2)

    @staticmethod
    def _draw_measure_label(painter, anchor, text, accent=None, above=True):
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

    @staticmethod
    def _draw_measure_vertex(painter, point, radius=5):
        cfg = drawing_config
        painter.setBrush(QBrush(cfg.MeasureVertexFill))
        painter.setPen(QPen(cfg.MeasureVertexOutline, 2))
        painter.drawEllipse(point, radius, radius)

    @staticmethod
    def _split_at_separators(draw_list):
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

    @staticmethod
    def drawOnVideo(
        drawPtPos,
        drawLines,
        drawPolygon,
        drawMDistance,
        drawMArea,
        drawCesure,
        drawMilSymbols,
        painter,
        surface,
        gt,
    ):
        """Paint all drawing overlays on the video frame."""
        for position, pt in enumerate(drawPtPos):
            DrawToolBar.drawPointOnVideo(position + 1, pt, painter, surface, gt)

        if drawMilSymbols:
            for entry in drawMilSymbols:
                DrawToolBar.drawMilitarySymbolOnVideo(entry, painter, surface, gt)

        # Draw lines
        if len(drawLines) > 1:
            for idx, pt in enumerate(drawLines):
                if pt[0] is not None:
                    DrawToolBar.drawLinesOnVideo(pt, idx, painter, surface, gt, drawLines)

        # Draw polygons (split at separators)
        for segment in DrawToolBar._split_at_separators(drawPolygon):
            DrawToolBar.drawPolygonOnVideo(segment, painter, surface, gt)

        # Draw measure distance
        if gt is not None and len(drawMDistance) > 1:
            DrawToolBar.resetMeasureDistance()
            for idx, pt in enumerate(drawMDistance):
                if pt[0] is None:
                    DrawToolBar.resetMeasureDistance()
                else:
                    DrawToolBar.drawMeasureDistanceOnVideo(
                        pt, idx, painter, surface, gt, drawMDistance
                    )

        # Draw measure area (split at separators)
        if gt is not None:
            for segment in DrawToolBar._split_at_separators(drawMArea):
                DrawToolBar.drawMeasureAreaOnVideo(segment, painter, surface, gt)

        # Draw censure
        if drawCesure:
            DrawToolBar.drawCensuredOnVideo(painter, drawCesure)

    @staticmethod
    def drawObjectTrackingHud(painter, x, y, w, h, lock_state="locked", label="TRACK"):
        """Draw FMV-style corner brackets + status label around a track bbox."""
        cfg = drawing_config
        if w < 2 or h < 2:
            return
        if lock_state == "weak":
            color = cfg.TrackWeakColor
        elif lock_state == "lost":
            color = cfg.TrackLostColor
        else:
            color = cfg.TrackLockColor

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(color, 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        arm = max(8, min(int(min(w, h) * 0.28), 22))
        x1, y1 = int(x), int(y)
        x2, y2 = int(x + w), int(y + h)

        # Top-left
        painter.drawLine(x1, y1, x1 + arm, y1)
        painter.drawLine(x1, y1, x1, y1 + arm)
        # Top-right
        painter.drawLine(x2, y1, x2 - arm, y1)
        painter.drawLine(x2, y1, x2, y1 + arm)
        # Bottom-left
        painter.drawLine(x1, y2, x1 + arm, y2)
        painter.drawLine(x1, y2, x1, y2 - arm)
        # Bottom-right
        painter.drawLine(x2, y2, x2 - arm, y2)
        painter.drawLine(x2, y2, x2, y2 - arm)

        # Center crosshair
        cx = int(x + w / 2)
        cy = int(y + h / 2)
        painter.drawLine(cx - 4, cy, cx + 4, cy)
        painter.drawLine(cx, cy - 4, cx, cy + 4)

        if label:
            painter.setFont(cfg.TrackHudFont)
            metrics = painter.fontMetrics()
            text_w = metrics.horizontalAdvance(label)
            text_h = metrics.height()
            pad = 3
            badge = QRectF(x1, max(0, y1 - text_h - 6), text_w + 2 * pad, text_h + pad)
            painter.setBrush(QBrush(QColor(20, 30, 40, 200)))
            painter.setPen(QPen(color, 1))
            painter.drawRoundedRect(badge, 3, 3)
            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(
                QPoint(int(badge.x()) + pad, int(badge.y()) + text_h - 2), label
            )
        painter.restore()

    @staticmethod
    def drawPointOnVideo(number, pt, painter, surface, gt):
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

    @staticmethod
    def drawMilitarySymbolOnVideo(entry, painter, surface, gt):
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

        # Match drawPointOnVideo: inverse uses (lat, lon), not (lon, lat).
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

    @staticmethod
    def drawLinesOnVideo(pt, idx, painter, surface, gt, drawLines):
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
                painter.setPen(DrawToolBar.white_pen)
                painter.drawPoint(center)
                painter.drawPoint(end)
            except Exception as exc:
                log.debug("drawLineOnVideo segment failed: %s", exc)
        return

    @staticmethod
    def drawPolygonOnVideo(values, painter, surface, gt):
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
        painter.setPen(DrawToolBar.white_pen)
        painter.drawPoints(polygon)
        return

    @staticmethod
    def resetMeasureDistance():
        """Reset the cumulative distance measurement counter to zero."""
        global RulerTotalMeasure
        RulerTotalMeasure = 0.0

    @staticmethod
    def drawMeasureDistanceOnVideo(pt, idx, painter, surface, gt, drawMDistance):
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
            DrawToolBar._draw_measure_label(
                painter,
                mid,
                DrawToolBar._format_length_m(distance),
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
                DrawToolBar._draw_measure_label(
                    painter,
                    end,
                    "Σ " + DrawToolBar._format_length_m(RulerTotalMeasure),
                    accent=QColor(255, 193, 7),
                    above=False,
                )

            DrawToolBar._draw_measure_vertex(painter, center)
            DrawToolBar._draw_measure_vertex(painter, end)
        except Exception as exc:
            log.debug("drawMeasureDistanceOnVideo segment failed: %s", exc)
        return

    @staticmethod
    def drawMeasureAreaOnVideo(values, painter, surface, gt):
        """Draw Measure Area on Video"""
        if not values or len(values) < 2:
            return
        try:
            # polygon_area expects a flat ring of (lon, lat[, ...]) points
            a_value = _geo_polygon_area(values)
        except Exception as exc:
            log.debug("drawMeasureAreaOnVideo area failed: %s", exc)
            a_value = 0.0

        cfg = drawing_config
        poly = []
        lats = []
        lons = []
        for pt in values:
            if pt is None or pt[0] is None:
                continue
            scr_x, scr_y = vut.GetInverseMatrix(pt[1], pt[0], gt, surface)
            poly.append(QPointF(scr_x, scr_y))
            lats.append(pt[0])
            lons.append(pt[1])
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
            DrawToolBar._draw_measure_vertex(
                painter, QPoint(int(p.x()), int(p.y())), radius=4
            )

        # Centroid from lon/lat mean (stable for labels)
        if lats and lons:
            scr_x, scr_y = vut.GetInverseMatrix(
                sum(lons) / len(lons), sum(lats) / len(lats), gt, surface
            )
            centroid = QPoint(int(scr_x), int(scr_y))
        else:
            centroid = QPoint(int(polygon.boundingRect().center().x()), int(polygon.boundingRect().center().y()))

        DrawToolBar._draw_measure_label(
            painter,
            centroid,
            DrawToolBar._format_area_m2(a_value),
            accent=QColor(255, 193, 7),
            above=True,
        )
        return

    @staticmethod
    def drawCensuredOnVideo(painter, drawCesure):
        """Draw Censure on Video"""
        try:
            for geom in drawCesure:
                painter.setPen(DrawToolBar.black_pen)
                painter.setBrush(DrawToolBar.black_brush)
                painter.drawRect(
                    geom[0].x(), geom[0].y(), geom[0].width(), geom[0].height()
                )

        except Exception as exc:
            log.debug("drawCensuredOnVideo failed: %s", exc)
        return

    @staticmethod
    def drawMagnifierOnVideo(widget, dragPos, source, painter, cache=None):
        """Draw Magnifier on Video (ROI crop — only magnifies a small source region)."""
        if source is None or source.isNull():
            return

        cfg = drawing_config
        video_rect = widget.surface.videoRect()
        if video_rect.isEmpty() or not video_rect.contains(dragPos):
            return

        dim = min(widget.width(), widget.height())
        magnifier_size = int(min(cfg.MAX_MAGNIFIER, dim * 2 / 3))
        radius = magnifier_size // 2
        ring = radius - 15

        center = dragPos - QPoint(0, radius // 2)
        corner = center - QPoint(radius, radius)

        rel_x = (dragPos.x() - video_rect.x()) / float(video_rect.width())
        rel_y = (dragPos.y() - video_rect.y()) / float(video_rect.height())
        src_x = int(rel_x * source.width())
        src_y = int(rel_y * source.height())

        roi_size = max(8, int(magnifier_size / max(1.0, float(cfg.MAX_FACTOR))))
        half = roi_size // 2
        x0 = max(0, min(source.width() - roi_size, src_x - half))
        y0 = max(0, min(source.height() - roi_size, src_y - half))
        cache_key = (x0, y0, roi_size, source.cacheKey())

        zoom_pixmap = None
        if (
            cache is not None
            and cache.get("key") == cache_key
            and cache.get("pixmap") is not None
        ):
            zoom_pixmap = cache["pixmap"]
        else:
            roi = source.copy(x0, y0, roi_size, roi_size)
            zoom_pixmap = QPixmap.fromImage(
                roi.scaled(
                    magnifier_size,
                    magnifier_size,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            if cache is not None:
                cache["key"] = cache_key
                cache["pixmap"] = zoom_pixmap

        clip_path = QPainterPath()
        center_f = QPointF(center)
        if cfg.TYPE_MAGNIFIER == 0:
            clip_path.addRect(
                center_f.x() - radius,
                center_f.y() - radius,
                magnifier_size,
                magnifier_size,
            )
        else:
            clip_path.addEllipse(center_f, ring, ring)

        painter.save()
        painter.setClipPath(clip_path)
        painter.drawPixmap(corner, zoom_pixmap)
        painter.setPen(DrawToolBar.glass_pen)
        painter.setBrush(DrawToolBar.transparent_brush)
        painter.drawPath(clip_path)
        painter.restore()
        return

    @staticmethod
    def drawStampOnVideo(widget, painter):
        """Draw the confidential stamp image over the video frame."""
        DrawToolBar._ensureStampImage()
        if DrawToolBar.confidential.isNull():
            return
        painter.drawPixmap(
            widget.surface.videoRect(),
            DrawToolBar.confidential,
            widget.surface.sourceRect(),
        )
        return
