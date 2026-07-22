# -*- coding: utf-8 -*-

"""

Video rendering surface for QGIS FMV (Qt6 / QGIS 4).



Receives frames from ``QVideoSink``, applies filters once per frame (not on

every paint), and exposes the filtered image for display and mosaic capture.

Slow OpenCV filters run on a background thread with frame dropping.

"""

from qgis.PyQt.QtCore import Qt, QRect, QPoint, QSize

from QGISFMV.video.filters import VideoFilters

from QGISFMV.video.filters.QgsFilterWorker import FilterThreadPool
from QGISFMV.utils.core.QgsFmvUtils import SetImageSize


class _SinkFormat(object):
    """Tiny stand-in for QVideoSurfaceFormat.sizeHint()."""

    def __init__(self, size):

        self._size = size

    def sizeHint(self):

        return self._size


class VideoSinkSurface(object):
    """QVideoSink based surface. Filters run in ``_on_frame`` so paint stays fast

    and ``currentFrame()`` is always available for mosaic capture."""

    def __init__(self, widget, sink):

        self.widget = widget

        self.image = None

        self._rawImage = None

        self._nativeSize = QSize(0, 0)

        self._targetRect = QRect()

        self._sourceRect = QRect()

        self._active = False

        self._sink = sink

        self._filter_pool = FilterThreadPool()
        self._filter_pool.filtered.connect(self._on_filtered_frame)
        sink.videoFrameChanged.connect(self._on_frame)

    def _needs_async_filters(self):
        """Return True when the current filter set requires off-thread processing."""

        return VideoFilters._needs_processing(self.widget._filterSatate)

    def pushFrame(self, img):
        """Display a QImage pushed by OpenCV playback (bypasses QVideoSink)."""
        if img is None or img.isNull():
            return
        self._apply_image(img)

    def _on_frame(self, frame):
        """Handle a new QVideoFrame from the sink and dispatch to filter pipeline."""

        if frame is None or not frame.isValid():

            return

        img = frame.toImage()

        if img.isNull():

            return

        self._apply_image(img)

    def _apply_image(self, img):
        """Store the raw frame, apply filters, and trigger a widget repaint."""

        self._rawImage = img

        self._nativeSize = img.size()

        self._sourceRect = QRect(QPoint(0, 0), img.size())

        SetImageSize(img.width(), img.height())

        if self._targetRect.isEmpty():

            self.updateVideoRect()

        self._active = True

        if self._needs_async_filters():

            submitted = self._filter_pool.submit(img, self.widget._filterSatate)

            if not submitted and self.image is None:

                self.image = img

                self.widget.update()

            return

        self.image = VideoFilters.apply(
            img, self.widget._filterSatate, downscale_slow=True
        )

        self.widget.update()

    def _on_filtered_frame(self, result):
        """Slot: receive the filtered frame from the thread pool and repaint."""

        self.image = result

        self.widget.update()

    def isActive(self):
        """True when the surface has received at least one valid frame."""

        return self._active and self.image is not None

    def surfaceFormat(self):
        """Return the video surface format describing native resolution."""

        return _SinkFormat(QSize(self._nativeSize))

    def videoRect(self):
        """Return the target rectangle where the video is painted."""

        return self._targetRect

    def sourceRect(self):
        """Return the source rectangle of the raw video frame."""

        return self._sourceRect

    def updateVideoRect(self):
        """Recalculate the target rectangle to fit the widget while preserving aspect ratio."""

        widget_size = self.widget.size()

        native = QSize(self._nativeSize)

        if native.isEmpty():

            return

        if widget_size.isEmpty():

            return

        bounded = widget_size.boundedTo(native)

        native.scale(bounded, Qt.AspectRatioMode.KeepAspectRatio)

        self._targetRect = QRect(QPoint(0, 0), native)

        self._targetRect.moveCenter(self.widget.rect().center())

    def ensureDisplayReady(self):
        """Keep the last frame visible after pause, resize, or fullscreen toggles."""
        if self._rawImage is None or self._rawImage.isNull():
            return False

        self._active = True

        if self.image is None:
            self.image = self._rawImage

        self.updateVideoRect()
        return not self._targetRect.isEmpty()

    def stop(self):
        """Clear all frames and deactivate the surface."""

        self._rawImage = None

        self.image = None

        self._active = False

        self._targetRect = QRect()

        self.widget.update()

    def refreshFilters(self):
        """Re-apply filters to the last raw frame (e.g. when toggling a filter)."""

        if self._rawImage is None:

            return

        if self._needs_async_filters():

            self._filter_pool.submit(self._rawImage, self.widget._filterSatate)

            return

        self.image = VideoFilters.apply(
            self._rawImage, self.widget._filterSatate, downscale_slow=True
        )

        self.widget.update()

    def paint(self, painter):
        """Draw the current filtered frame onto the widget's painter."""

        if self.image is None:

            return

        if self._targetRect.isEmpty():
            self.updateVideoRect()

        if self._targetRect.isEmpty():

            return

        painter.drawImage(self._targetRect, self.image, self._sourceRect)

    def dispose(self):
        """Shut down the filter thread pool and release resources."""

        self._filter_pool.shutdown()
