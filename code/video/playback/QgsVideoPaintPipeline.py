# -*- coding: utf-8 -*-
"""Paint pipeline extracted from VideoWidget.paintEvent (QgsVideo.py).

Keeps the z-order painting logic (background, drawings, overlays, HUD) in a
single place so paintEvent itself stays a thin dispatch call.
"""

from qgis.PyQt.QtCore import QRect, Qt
from qgis.PyQt.QtGui import QColor, QFont, QPainter, QPen

from QGISFMV.player.drawing.QgsFmvDrawToolBar import DrawToolBar as draw
from QGISFMV.utils.core.QgsFmvUtils import GetGCPGeoTransform
from QGISFMV.utils.logging import log
from QGISFMV.video.playback.QgsVideoUtils import VideoUtils as vut


class VideoPaintPipeline:
    """Runs the full paint z-order pipeline for VideoWidget.paintEvent."""

    @staticmethod
    def paint(widget, event):
        """Paint background, video frame, overlays and HUD, in z-order."""
        if not widget.surface.isActive():
            if not widget.surface.ensureDisplayReady():
                return

        widget.painter = QPainter(widget)
        widget.painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        VideoPaintPipeline._paint_background(widget, event)

        try:
            widget.surface.paint(widget.painter)
        except Exception as exc:
            log.warning("Video paint failed: %s", exc)

        VideoPaintPipeline._paint_drawings(widget)
        VideoPaintPipeline._paint_military_symbol_preview(widget)
        VideoPaintPipeline._paint_tracking_hud(widget)
        VideoPaintPipeline._paint_magnifier(widget)
        VideoPaintPipeline._paint_stamp(widget)
        VideoPaintPipeline._paintToolPlacementHint(widget)
        VideoPaintPipeline._paint_hud(widget)

        widget.painter.end()

    @staticmethod
    def _paint_background(widget, event):
        """Fill the widget background before painting the video frame."""
        region = event.region()
        widget.painter.fillRect(region.boundingRect(), widget.brush)

    @staticmethod
    def _paint_drawings(widget):
        """Paint all user drawing overlays (points, lines, polygons, etc.)."""
        gcp_gt = GetGCPGeoTransform()
        draw.drawOnVideo(
            widget.drawPtPos,
            widget.drawLines,
            widget.drawPolygon,
            widget.drawMeasureDistance,
            widget.drawMeasureArea,
            widget.drawCesure,
            widget.drawMilSymbols,
            widget.painter,
            widget.surface,
            gcp_gt,
        )

    @staticmethod
    def _paint_military_symbol_preview(widget):
        """Paint the military symbol preview at the current cursor position."""
        gcp_gt = GetGCPGeoTransform()
        if (
            widget._interaction.militarySymbolDrawer
            and widget._milSymbolPreview
            and gcp_gt is not None
        ):
            widget.painter.save()
            widget.painter.setOpacity(0.55)
            draw.drawMilitarySymbolOnVideo(
                widget._milSymbolPreview,
                widget.painter,
                widget.surface,
                gcp_gt,
            )
            widget.painter.restore()

    @staticmethod
    def _paint_tracking_hud(widget):
        """Paint the object-tracking bounding-box HUD on the video."""
        if not (widget._interaction.objectTracking and widget._isinit):
            return
        bbox = widget._last_track_bbox
        if bbox is None:
            return
        offset = widget.surface.videoRect()
        x = bbox[0] + offset.x()
        y = bbox[1] + offset.y()
        if vut.IsPointOnScreen(x, y, widget.surface):
            label = "TRACK #%s" % widget._track_id
            lock_state = getattr(widget._track_lock_state, "value", None) or "locked"
            if lock_state == "weak":
                label = "%s · WEAK" % label
            draw.drawObjectTrackingHud(
                widget.painter,
                x,
                y,
                bbox[2],
                bbox[3],
                lock_state=lock_state,
                label=label,
            )

    @staticmethod
    def _paint_magnifier(widget):
        """Paint the magnifier-glass overlay."""
        if widget._interaction.magnifier and not widget.dragPos.isNull():
            draw.drawMagnifierOnVideo(
                widget,
                widget.dragPos,
                widget.currentFrame(),
                widget.painter,
                widget._magnifier_cache,
            )

    @staticmethod
    def _paint_stamp(widget):
        """Paint the timestamp overlay on the video."""
        if widget._interaction.stamp:
            draw.drawStampOnVideo(widget, widget.painter)

    @staticmethod
    def _paint_hud(widget):
        """Paint the external HUD overlay (if bound)."""
        hud = getattr(widget, "_hudRef", None)
        if hud is not None:
            hud.paint(widget.painter, widget.width(), widget.height())

    @staticmethod
    def _paintToolPlacementHint(widget):
        """Paint a flashing banner hint when a draw/measure tool is active."""
        if not widget._toolHintText:
            return
        if GetGCPGeoTransform() is None:
            return

        rect = widget.surface.videoRect()
        if rect.isNull() or rect.isEmpty():
            return

        banner_h = 34
        banner = QRect(rect.x(), rect.y(), rect.width(), banner_h)
        widget.painter.fillRect(banner, QColor(46, 125, 50, 200))
        widget.painter.setPen(QColor(255, 255, 255))
        font = QFont(widget.font())
        font.setBold(True)
        font.setPointSize(max(9, font.pointSize()))
        widget.painter.setFont(font)
        widget.painter.drawText(
            banner,
            int(Qt.AlignmentFlag.AlignCenter),
            widget._toolHintText,
        )

        if widget._toolHintFlash % 2:
            pen = QPen(QColor(255, 235, 59), 4)
            widget.painter.setPen(pen)
            widget.painter.setBrush(Qt.BrushStyle.NoBrush)
            widget.painter.drawRect(rect.adjusted(2, 2, -2, -2))
