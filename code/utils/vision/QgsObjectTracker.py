# -*- coding: utf-8 -*-
"""Object tracking for FMV video — OpenCV MOSSE when available, numpy MOSSE fallback."""

from __future__ import annotations

import numpy as np

from QGISFMV.utils.logging import log

_CV2_TRACKER = None
_CV2_IMPORT_ERROR = ""


def _load_cv2_tracker_factory():
    global _CV2_TRACKER, _CV2_IMPORT_ERROR
    if _CV2_TRACKER is not None or _CV2_IMPORT_ERROR:
        return _CV2_TRACKER
    try:
        import cv2
    except ImportError as exc:
        _CV2_IMPORT_ERROR = str(exc)
        return None
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerMOSSE_create"):
        _CV2_TRACKER = cv2.legacy.TrackerMOSSE_create
    elif hasattr(cv2, "TrackerMOSSE_create"):
        _CV2_TRACKER = cv2.TrackerMOSSE_create
    else:
        _CV2_IMPORT_ERROR = "TrackerMOSSE_create is not available in this OpenCV build"
    return _CV2_TRACKER


def cv2_available() -> bool:
    """True if ``import cv2`` works in this process (not only MOSSE tracker)."""
    try:
        import cv2  # noqa: F401

        return True
    except Exception as exc:
        from QGISFMV.utils.logging import log
        log.debug("cv2 import failed: %s", exc)
        return _load_cv2_tracker_factory() is not None


def has_object_tracking() -> bool:
    """Return True when any tracker backend can run (numpy is bundled with QGIS)."""
    try:
        import numpy as _np  # noqa: F401
    except ImportError:
        return False
    return True


class _OpenCvTrackerAdapter:
    """Normalize OpenCV tracker API to init/update booleans."""

    def __init__(self, tracker):
        self._tracker = tracker

    def init(self, frame, bbox):
        try:
            ok = self._tracker.init(frame, bbox)
        except Exception as exc:
            from QGISFMV.utils.logging import log
            log.debug("tracker init failed: %s", exc)
            return False
        return ok is not False

    def update(self, frame):
        try:
            ok, bbox = self._tracker.update(frame)
        except Exception as exc:
            from QGISFMV.utils.logging import log
            log.debug("tracker update failed: %s", exc)
            return False, None
        if not ok or bbox is None:
            return False, None
        return True, tuple(int(v) for v in bbox)


def _cosine_window(h, w):
    wy = np.hanning(max(h, 2))
    wx = np.hanning(max(w, 2))
    return np.outer(wy[:h], wx[:w]).astype(np.float32)


def _gaussian_response(h, w, sigma=2.0):
    cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
    y, x = np.mgrid[0:h, 0:w]
    dist = (x - cx) ** 2 + (y - cy) ** 2
    return np.exp(-dist / (2 * sigma * sigma)).astype(np.float32)


class NumpyMosseTracker:
    """
    MOSSE correlation-filter tracker using only numpy FFT.

    Same family of algorithm as OpenCV's legacy TrackerMOSSE, but slower and
    less robust than the native OpenCV build. Good enough as a macOS fallback.
    """

    ETA = 0.125
    SIGMA = 2.0
    EPS = 1e-3
    MIN_RESPONSE = 0.12

    def __init__(self):
        self._bbox = None
        self._size = None
        self._Ai = None
        self._Bi = None
        self._H = None
        self._window = None

    @staticmethod
    def _gray(frame):
        if frame.ndim == 3:
            return (
                0.299 * frame[:, :, 0]
                + 0.587 * frame[:, :, 1]
                + 0.114 * frame[:, :, 2]
            ).astype(np.float32)
        return frame.astype(np.float32)

    def _preprocess(self, patch):
        p = patch.astype(np.float32)
        p = np.log1p(np.maximum(p, 0.0))
        p = (p - p.mean()) / (p.std() + 1e-5)
        return p * self._window

    def _extract(self, gray, x, y, w, h):
        if x < 0 or y < 0 or x + w > gray.shape[1] or y + h > gray.shape[0]:
            return None
        patch = gray[y : y + h, x : x + w]
        if patch.shape != (h, w):
            return None
        return patch

    def init(self, frame, bbox):
        """Initialise the tracker with the first frame and bounding box."""
        x, y, w, h = [int(v) for v in bbox]
        if w < 4 or h < 4:
            return False
        gray = self._gray(frame)
        patch = self._extract(gray, x, y, w, h)
        if patch is None:
            return False

        self._bbox = (x, y, w, h)
        self._size = (w, h)
        self._window = _cosine_window(h, w)

        fi = self._preprocess(patch)
        gi = _gaussian_response(h, w, self.SIGMA)
        Fi = np.fft.fft2(fi)
        Gi = np.fft.fft2(gi)
        self._Ai = Gi * np.conj(Fi)
        self._Bi = Fi * np.conj(Fi)
        self._H = self._Ai / (self._Bi + self.EPS)
        return True

    def _response_peak(self, patch):
        fi = self._preprocess(patch)
        Gi = self._H * np.fft.fft2(fi)
        gi = np.real(np.fft.ifft2(Gi))
        peak = float(gi.max())
        cy, cx = np.unravel_index(int(np.argmax(gi)), gi.shape)
        return peak, cx, cy

    def update(self, frame):
        """Track the object in a new frame; returns (ok, new_bbox)."""
        if self._H is None or self._bbox is None or self._size is None:
            return False, None

        x, y, w, h = self._bbox
        gray = self._gray(frame)
        patch = self._extract(gray, x, y, w, h)
        if patch is None:
            return False, None

        peak, cx, cy = self._response_peak(patch)
        if peak < self.MIN_RESPONSE:
            return False, None

        dx = int(round(cx - (w - 1) / 2.0))
        dy = int(round(cy - (h - 1) / 2.0))
        nx = max(0, min(gray.shape[1] - w, x + dx))
        ny = max(0, min(gray.shape[0] - h, y + dy))

        new_patch = self._extract(gray, nx, ny, w, h)
        if new_patch is None:
            return False, None

        fi = self._preprocess(new_patch)
        gi = _gaussian_response(h, w, self.SIGMA)
        Fi = np.fft.fft2(fi)
        Gi = np.fft.fft2(gi)
        self._Ai = self.ETA * (Gi * np.conj(Fi)) + (1.0 - self.ETA) * self._Ai
        self._Bi = self.ETA * (Fi * np.conj(Fi)) + (1.0 - self.ETA) * self._Bi
        self._H = self._Ai / (self._Bi + self.EPS)
        self._bbox = (nx, ny, w, h)
        return True, self._bbox


def create_object_tracker():
    """
    Return (tracker, backend_name).

    Prefers OpenCV MOSSE; falls back to a numpy MOSSE implementation when cv2
    is unavailable (e.g. macOS without admin rights).
    """
    factory = _load_cv2_tracker_factory()
    if factory is not None:
        try:
            return _OpenCvTrackerAdapter(factory()), "opencv"
        except Exception as exc:
            log.debug("OpenCV MOSSE tracker init failed, using numpy: %s", exc)
    return NumpyMosseTracker(), "numpy-mosse"
