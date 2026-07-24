# -*- coding: utf-8 -*-
"""Object tracking HUD, magnifier and stamp overlay painting."""
from qgis.PyQt.QtCore import QPointF, Qt, QPoint, QRectF
from qgis.PyQt.QtGui import (
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QBrush,
    QPixmap,
)

from QGISFMV.player.drawing import QgsFmvDrawingConfig as _drawing_config_mod
from QGISFMV.player.drawing.QgsFmvDrawingConfig import (
    drawing_config,
    glass_pen,
    transparent_brush,
    ensure_stamp_image,
)


def draw_object_tracking_hud(painter, x, y, w, h, lock_state="locked", label="TRACK"):
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


def draw_magnifier_on_video(widget, dragPos, source, painter, cache=None):
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
    painter.setPen(glass_pen)
    painter.setBrush(transparent_brush)
    painter.drawPath(clip_path)
    painter.restore()
    return


def draw_stamp_on_video(widget, painter):
    """Draw the confidential stamp image over the video frame."""
    ensure_stamp_image()
    confidential = _drawing_config_mod.confidential
    if confidential.isNull():
        return
    painter.drawPixmap(
        widget.surface.videoRect(),
        confidential,
        widget.surface.sourceRect(),
    )
    return
