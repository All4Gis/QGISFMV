# -*- coding: utf-8 -*-
"""Timeline widget showing event markers along the video duration."""

from qgis.PyQt.QtCore import Qt, QRectF, pyqtSignal
from qgis.PyQt.QtGui import QColor, QPainter, QPen, QBrush, QFont
from qgis.PyQt.QtWidgets import QWidget, QToolTip


class TimelineEvent:
    """One event marker on the timeline."""

    __slots__ = ("time_sec", "label", "color")

    def __init__(self, time_sec, label="", color=QColor(255, 200, 0)):
        self.time_sec = time_sec
        self.label = label
        self.color = color


class TimelineWidget(QWidget):
    """Horizontal timeline with event markers and a playback cursor."""

    seekRequested = pyqtSignal(float)  # seconds

    HEIGHT = 32
    MARKER_R = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(self.HEIGHT)
        self.setMaximumHeight(self.HEIGHT)
        self.setMouseTracking(True)
        self._duration = 1.0
        self._position = 0.0
        self._events = []
        self._hover_idx = -1

    def setDuration(self, seconds):
        """Set the total timeline duration in seconds."""
        self._duration = max(0.1, seconds)

    def setPosition(self, seconds):
        """Set the current playback position in seconds."""
        self._position = max(0.0, seconds)

    def clearEvents(self):
        """Remove all event markers from the timeline."""
        self._events.clear()

    # -- internal helpers --
    def _timeToX(self, t):
        if self._duration <= 0:
            return 0
        return (t / self._duration) * self.width()

    def _xToTime(self, x):
        if self.width() <= 0:
            return 0.0
        return (x / self.width()) * self._duration

    # -- events --
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            t = self._xToTime(event.position().x())
            self.seekRequested.emit(t)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        t = self._xToTime(x)
        # find closest event
        closest = -1
        min_dist = 10  # pixel threshold
        for i, ev in enumerate(self._events):
            ex = self._timeToX(ev.time_sec)
            dist = abs(ex - x)
            if dist < min_dist:
                min_dist = dist
                closest = i
        if closest != self._hover_idx:
            self._hover_idx = closest
            self.update()
        if closest >= 0:
            ev = self._events[closest]
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{ev.label} @ {ev.time_sec:.1f}s",
                self,
            )
        else:
            QToolTip.hideText()

    def leaveEvent(self, event):
        self._hover_idx = -1
        QToolTip.hideText()
        self.update()

    # -- painting --
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(30, 30, 30))

        # Track line
        track_y = h // 2
        painter.setPen(QPen(QColor(80, 80, 80), 2))
        painter.drawLine(0, track_y, w, track_y)

        # Progress fill
        px = self._timeToX(self._position)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(0, 120, 255, 80)))
        painter.drawRect(0, track_y - 4, int(px), 8)

        # Event markers
        for i, ev in enumerate(self._events):
            ex = self._timeToX(ev.time_sec)
            r = self.MARKER_R + (2 if i == self._hover_idx else 0)
            painter.setPen(QPen(ev.color.darker(130), 1))
            painter.setBrush(QBrush(ev.color))
            painter.drawEllipse(QRectF(ex - r, track_y - r, r * 2, r * 2))

        # Cursor
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(int(px), 4, int(px), h - 4)

        # Time labels
        font = QFont("Sans", 7)
        painter.setFont(font)
        painter.setPen(QColor(160, 160, 160))
        n_ticks = max(2, min(10, w // 80))
        for i in range(n_ticks + 1):
            t = (i / n_ticks) * self._duration
            x = self._timeToX(t)
            painter.drawText(QRectF(x - 20, 2, 40, 12), Qt.AlignmentFlag.AlignCenter, f"{t:.0f}s")

        painter.end()
