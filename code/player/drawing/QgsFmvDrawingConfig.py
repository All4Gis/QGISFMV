# -*- coding: utf-8 -*-
"""Central mutable drawing configuration + settings loading + stamp asset caching.

This module owns:

* :class:`DrawingConfig` — all mutable drawing parameters (pens/brushes/fonts).
* ``drawing_config`` — the process-wide singleton instance of ``DrawingConfig``.
* Shared pens/brushes that are not part of ``DrawingConfig`` but are reused as
  simple constants by the drawing submodules (small point pens, glass pen,
  transparent/black brushes).
* Stamp (confidential overlay) lazy-loading helpers.
* :func:`setValues` — loads persisted QSettings values into ``drawing_config``
  (and optionally reflects them onto an options dialog).
"""

import os

from qgis.PyQt.QtCore import Qt, QSettings
from qgis.PyQt.QtGui import QColor, QFont, QPen, QBrush, QPixmap, QImage

from QGISFMV.utils.core.QgsFmvUtils import getNameSpace
from QGISFMV.utils.logging import log

NameSpace = getNameSpace()


class DrawingConfig:
    """All mutable drawing parameters in one place."""

    __slots__ = (
        "MAX_MAGNIFIER",
        "MAX_FACTOR",
        "TYPE_MAGNIFIER",
        "PolyWidth",
        "PolyPen",
        "PolyBrush",
        "PointRadius",
        "PointFillColor",
        "PointOutlineColor",
        "PointLabelColor",
        "PointLabelBgColor",
        "PointPen",
        "PointFont",
        "LineWidth",
        "LinePen",
        "TrackLockColor",
        "TrackWeakColor",
        "TrackLostColor",
        "TrackHudFont",
        "MeasureWidth",
        "MeasurePen",
        "MeasureBrush",
        "MeasureLabelBg",
        "MeasureLabelFg",
        "MeasureVertexFill",
        "MeasureVertexOutline",
        "MeasureFont",
        "MeasureGlowPen",
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


# ---------------------------------------------------------------------------
# Shared pens/brushes reused across the drawing submodules (not part of the
# per-frame-tunable DrawingConfig, but still shared/static state).
# ---------------------------------------------------------------------------
small_pt = 5

white_pen = QPen(Qt.GlobalColor.white, small_pt)
white_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

black_pen = QPen(Qt.GlobalColor.black, small_pt)
black_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

glass_pen = QPen(QColor(192, 192, 192, 128), 3)

transparent_brush = QBrush(Qt.GlobalColor.transparent)

black_brush = QBrush(Qt.GlobalColor.black)


# ---------------------------------------------------------------------------
# Stamp (confidential overlay) lazy loading.
# ---------------------------------------------------------------------------

# Original confidential stamp PNG (no generated overlay)
confidential = QPixmap()


def ensure_stamp_image():
    """Lazily load the confidential stamp pixmap (disk first, resource fallback)."""
    global confidential
    if not confidential.isNull():
        return confidential
    try:
        from QGISFMV.utils.settings.QgsFmvSettings import plugin_root

        stamp_path = os.path.join(plugin_root(), "images", "stamp", "confidential.png")
        if os.path.isfile(stamp_path):
            confidential = QPixmap(stamp_path)
    except Exception as exc:
        log.debug("Stamp image load failed: %s", exc)
    if confidential.isNull():
        confidential = QPixmap.fromImage(
            QImage(":/imgFMV/images/stamp/confidential.png")
        )
    return confidential


# ---------------------------------------------------------------------------
# Settings persistence.
# ---------------------------------------------------------------------------


def setValues(options=None):
    """Load drawing tool settings from QSettings and update drawing_config."""
    cfg = drawing_config
    ensure_stamp_image()
    s = QSettings()
    ns = NameSpace + "/Options"

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
            QColor(0, 0, 0, 110),
            cfg.MeasureWidth + 2,
            cap=Qt.PenCapStyle.RoundCap,
            join=Qt.PenJoinStyle.RoundJoin,
        )
        if options is not None:
            options.measures_pen.setColor(QColor(m_color))

    m_brush_val = s.value(f"{ns}/drawings/measures/brush")
    if m_brush_val is not None:
        cfg.MeasureBrush = QBrush(QColor(m_brush_val))
        if options is not None:
            options.measures_brush.setColor(QColor(m_brush_val))
