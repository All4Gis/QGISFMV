# -*- coding: utf-8 -*-
"""Public façade for the video drawing tools.

The actual implementations live in focused sibling modules:

* :mod:`QgsFmvDrawingConfig` — ``DrawingConfig``/``drawing_config``, settings
  persistence (``setValues``) and stamp asset caching.
* :mod:`QgsFmvDrawShapes` — point / line / polygon / military symbol / censure
  painting.
* :mod:`QgsFmvDrawMeasure` — measure distance/area painting and running totals.
* :mod:`QgsFmvDrawHud` — object tracking HUD, magnifier and stamp painting.

``DrawToolBar`` keeps the exact same staticmethod API as before so external
call sites (``QgsVideoPaintPipeline``, ``QgsFmvSettings``, ``QgsManager``, ...)
do not need to change.
"""

from QGISFMV.player.drawing.QgsFmvDrawingConfig import (
    DrawingConfig,
    drawing_config,
    setValues as _setValues,
)
from QGISFMV.player.drawing.QgsFmvDrawShapes import (
    split_at_separators as _split_at_separators,
    draw_point_on_video,
    draw_military_symbol_on_video,
    draw_lines_on_video,
    draw_polygon_on_video,
    draw_censured_on_video,
)
from QGISFMV.player.drawing.QgsFmvDrawMeasure import (
    RulerTotalMeasure,
    reset_measure_distance,
    draw_measure_distance_on_video,
    draw_measure_area_on_video,
)
from QGISFMV.player.drawing.QgsFmvDrawHud import (
    draw_object_tracking_hud,
    draw_magnifier_on_video,
    draw_stamp_on_video,
)

__all__ = ["DrawToolBar", "DrawingConfig", "drawing_config", "RulerTotalMeasure"]


class DrawToolBar(object):

    @staticmethod
    def setValues(options=None):
        """Load drawing tool settings from QSettings and update drawing_config."""
        _setValues(options)

    @staticmethod
    def _split_at_separators(draw_list):
        """Split a drawing list into sub-lists at [None, None, None] sentinels."""
        return _split_at_separators(draw_list)

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
                    DrawToolBar.drawLinesOnVideo(
                        pt, idx, painter, surface, gt, drawLines
                    )

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
        return draw_object_tracking_hud(painter, x, y, w, h, lock_state, label)

    @staticmethod
    def drawPointOnVideo(number, pt, painter, surface, gt):
        """Draw Points on Video"""
        return draw_point_on_video(number, pt, painter, surface, gt)

    @staticmethod
    def drawMilitarySymbolOnVideo(entry, painter, surface, gt):
        """Draw a military SVG symbol on the video at geo coordinates."""
        return draw_military_symbol_on_video(entry, painter, surface, gt)

    @staticmethod
    def drawLinesOnVideo(pt, idx, painter, surface, gt, drawLines):
        """Draw Lines on Video"""
        return draw_lines_on_video(pt, idx, painter, surface, gt, drawLines)

    @staticmethod
    def drawPolygonOnVideo(values, painter, surface, gt):
        """Draw Polygons on Video"""
        return draw_polygon_on_video(values, painter, surface, gt)

    @staticmethod
    def resetMeasureDistance():
        """Reset the cumulative distance measurement counter to zero."""
        reset_measure_distance()

    @staticmethod
    def drawMeasureDistanceOnVideo(pt, idx, painter, surface, gt, drawMDistance):
        """Draw Measure Distance on Video"""
        return draw_measure_distance_on_video(
            pt, idx, painter, surface, gt, drawMDistance
        )

    @staticmethod
    def drawMeasureAreaOnVideo(values, painter, surface, gt):
        """Draw Measure Area on Video"""
        return draw_measure_area_on_video(values, painter, surface, gt)

    @staticmethod
    def drawCensuredOnVideo(painter, drawCesure):
        """Draw Censure on Video"""
        return draw_censured_on_video(painter, drawCesure)

    @staticmethod
    def drawMagnifierOnVideo(widget, dragPos, source, painter, cache=None):
        """Draw Magnifier on Video (ROI crop — only magnifies a small source region)."""
        return draw_magnifier_on_video(widget, dragPos, source, painter, cache)

    @staticmethod
    def drawStampOnVideo(widget, painter):
        """Draw the confidential stamp image over the video frame."""
        return draw_stamp_on_video(widget, painter)
