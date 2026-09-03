# -*- coding: utf-8 -*-
"""QImage ↔ numpy conversion (no dependency on layers / video playback)."""

import numpy as np
from qgis.PyQt.QtGui import QImage

try:
    from cv2 import COLOR_BGR2RGB, COLOR_GRAY2RGB, cvtColor

    _HAS_CV2 = True
except ImportError:
    COLOR_BGR2RGB = None
    COLOR_GRAY2RGB = None
    cvtColor = None
    _HAS_CV2 = False


def convertQImageToMat(img, cn=3):
    """Convert QImage to an owned OpenCV-compatible numpy array."""
    if img is None or img.isNull():
        raise ValueError("empty QImage")
    fmt = QImage.Format.Format_Grayscale8 if cn == 1 else QImage.Format.Format_RGB888
    if img.format() != fmt:
        img = img.convertToFormat(fmt)
    h, w = img.height(), img.width()
    bpl = img.bytesPerLine()
    ptr = img.bits()
    if hasattr(ptr, "setsize"):
        ptr.setsize(h * bpl)
    try:
        buf = memoryview(ptr)
    except TypeError:
        buf = ptr
    arr = np.frombuffer(buf, np.uint8).reshape((h, bpl))
    if cn == 1:
        return np.ascontiguousarray(arr[:, :w]).copy()
    return np.ascontiguousarray(arr[:, : w * cn].reshape((h, w, cn))).copy()


def convertMatToQImage(img, t=QImage.Format.Format_RGB888, bgr=True):
    """Convert a numpy image to QImage."""
    if img is None:
        raise ValueError("empty image")
    height, width = img.shape[:2]
    if img.ndim == 2:
        if _HAS_CV2:
            rgb = cvtColor(img, COLOR_GRAY2RGB)
        else:
            rgb = np.stack([img, img, img], axis=2)
    elif img.ndim == 3 and img.shape[2] == 3:
        if bgr:
            if _HAS_CV2:
                rgb = cvtColor(img, COLOR_BGR2RGB)
            else:
                rgb = np.ascontiguousarray(img[:, :, ::-1])
        else:
            rgb = img
    else:
        raise ValueError("Unsupported image data format")
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    height = int(height)
    width = int(width)
    bpl = int((width * 3 + 3) & ~3)
    if bpl == width * 3:
        buf = rgb
    else:
        buf = np.zeros((height, bpl), dtype=np.uint8)
        buf[:, : width * 3] = rgb.reshape(height, width * 3)
    return QImage(buf.data, width, height, bpl, t).copy()
