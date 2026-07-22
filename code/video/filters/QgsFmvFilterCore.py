# -*- coding: utf-8 -*-
"""Shared OpenCV environment and image primitives for video filters."""

import numpy as np

from QGISFMV.utils.logging import log

_HAS_SCIPY = False
try:
    from scipy.signal import convolve2d as _scipy_conv2d
    _HAS_SCIPY = True
except ImportError:
    pass

_HAS_NDIMAGE = False
try:
    from scipy import ndimage as _ndimage

    _HAS_NDIMAGE = True
except ImportError:
    _ndimage = None

_HAS_CV2 = False
_CV2_IMPORT_ERROR = ""
try:
    import cv2 as _cv2

    cvtColor = _cv2.cvtColor
    Canny = _cv2.Canny
    COLOR_BGR2GRAY = _cv2.COLOR_BGR2GRAY
    COLOR_BGR2LAB = _cv2.COLOR_BGR2LAB
    COLOR_RGB2LAB = _cv2.COLOR_RGB2LAB
    COLOR_LAB2BGR = _cv2.COLOR_LAB2BGR
    COLOR_LAB2RGB = _cv2.COLOR_LAB2RGB
    COLOR_RGB2BGR = _cv2.COLOR_RGB2BGR
    COLOR_GRAY2BGR = _cv2.COLOR_GRAY2BGR
    createCLAHE = _cv2.createCLAHE
    merge = _cv2.merge
    split = _cv2.split
    GaussianBlur = _cv2.GaussianBlur
    CV_64F = _cv2.CV_64F
    Sobel = _cv2.Sobel
    applyColorMap = _cv2.applyColorMap
    COLORMAP_TURBO = _cv2.COLORMAP_TURBO
    createBackgroundSubtractorMOG2 = _cv2.createBackgroundSubtractorMOG2
    threshold = _cv2.threshold
    THRESH_BINARY = _cv2.THRESH_BINARY
    getStructuringElement = _cv2.getStructuringElement
    MORPH_RECT = _cv2.MORPH_RECT
    MORPH_DILATE = _cv2.MORPH_DILATE
    morphologyEx = _cv2.morphologyEx
    LINE_AA = _cv2.LINE_AA
    putText = _cv2.putText
    FONT_HERSHEY_SIMPLEX = _cv2.FONT_HERSHEY_SIMPLEX
    _HAS_CV2 = True
except Exception as _cv2_exc:  # ImportError, OSError (Team ID), etc.
    _CV2_IMPORT_ERROR = str(_cv2_exc)
    log.warning("OpenCV unavailable for video filters: %s", _CV2_IMPORT_ERROR)

_COLORMAP_NRVI = None
if _HAS_CV2:
    try:
        _COLORMAP_NRVI = getattr(_cv2, "COLORMAP_RDYLGN", COLORMAP_TURBO)
    except Exception as _exc:
        log.debug('COLORMAP_RDYLGN lookup failed, using TURBO: %s', _exc)
        _COLORMAP_NRVI = COLORMAP_TURBO


_cv2_runtime = _cv2 if _HAS_CV2 else None


def _cv2_from_tracker():
    """Same OpenCV probe used by object tracking (MOSSE) in this QGIS process."""
    try:
        from QGISFMV.utils.vision.QgsObjectTracker import cv2_available

        if not cv2_available():
            return None
        import cv2 as cv2_mod

        return cv2_mod
    except Exception as _exc:
        log.debug('cv2_from_tracker probe failed: %s', _exc)
        return None


def _get_cv2_module():
    """Return OpenCV module (shared with object tracking)."""
    global _HAS_CV2, _cv2_runtime, _CV2_IMPORT_ERROR
    if _cv2_runtime is not None:
        return _cv2_runtime
    if _HAS_CV2:
        try:
            import cv2 as _cv2_mod

            _cv2_runtime = _cv2_mod
            return _cv2_mod
        except Exception as exc:
            _CV2_IMPORT_ERROR = str(exc)
    cv2_mod = _cv2_from_tracker()
    if cv2_mod is not None:
        _cv2_runtime = cv2_mod
        _HAS_CV2 = True
        _CV2_IMPORT_ERROR = ""
        return cv2_mod
    try:
        import cv2 as _cv2_mod

        _cv2_runtime = _cv2_mod
        _HAS_CV2 = True
        _CV2_IMPORT_ERROR = ""
        return _cv2_mod
    except Exception as exc:
        _CV2_IMPORT_ERROR = str(exc)
        return None


def opencv_available():
    """True when OpenCV works in this process (same check as object tracking)."""
    if _get_cv2_module() is not None:
        return True
    try:
        from QGISFMV.utils.vision.QgsObjectTracker import cv2_available

        return cv2_available()
    except Exception as _exc:
        log.debug('opencv_available check failed: %s', _exc)
        return False


def opencv_status_text():
    """Return a human-readable string describing OpenCV availability."""
    if opencv_available():
        cv2_mod = _get_cv2_module()
        ver = getattr(cv2_mod, "__version__", "") if cv2_mod is not None else ""
        return "Native CV OK" + (f" ({ver})" if ver else "")
    if _CV2_IMPORT_ERROR:
        return "Native CV unavailable (numpy fallback): " + _CV2_IMPORT_ERROR[:160]
    return "Native CV unavailable (numpy fallback)"


_MAX_SLOW_FILTER_DIM = 720
_clahe = createCLAHE(clipLimit=4.0, tileGridSize=(8, 8)) if _HAS_CV2 else None
_prev_motion_frame = None
_mog2_subtractor = None


def _get_mog2_subtractor():
    """Return (and lazily create) the MOG2 background subtractor singleton."""
    global _mog2_subtractor
    if _HAS_CV2 and _mog2_subtractor is None:
        _mog2_subtractor = createBackgroundSubtractorMOG2(
            history=300, varThreshold=32, detectShadows=False
        )
    return _mog2_subtractor


def _gaussian_kernel(ksize=5, sigma=1.0):
    """Return a 2D Gaussian kernel of given size and sigma."""
    ax = np.arange(ksize, dtype=np.float32) - ksize // 2
    xx, yy = np.meshgrid(ax, ax)
    kernel = np.exp(-(xx**2 + yy**2) / (2.0 * sigma**2))
    return (kernel / kernel.sum()).astype(np.float32)


def _conv2d(image, kernel):
    """Fast 2D convolution — uses scipy when available, numpy stride-tricks otherwise."""
    if _HAS_SCIPY and kernel.shape[0] <= 7 and kernel.shape[1] <= 7:
        return _scipy_conv2d(image, kernel, mode="same", boundary="symm")
    kh, kw = kernel.shape
    pad_h, pad_w = kh // 2, kw // 2
    padded = np.pad(image, ((pad_h, pad_h), (pad_w, pad_w)), mode="reflect")
    h, w = image.shape
    shape = (h, w, kh, kw)
    strides = padded.strides * 2
    view = np.lib.stride_tricks.as_strided(padded, shape=shape, strides=strides)
    return np.einsum("ijkl,kl->ij", view, kernel)


def _sobel_gradients(gray):
    """Compute gradient magnitude and direction using Sobel operators."""
    sobel_x = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
    sobel_y = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float32)
    gx = _conv2d(gray.astype(np.float32), sobel_x)
    gy = _conv2d(gray.astype(np.float32), sobel_y)
    magnitude = np.hypot(gx, gy)
    direction = np.arctan2(gy, gx) * (180.0 / np.pi)
    direction[direction < 0] += 180
    return magnitude, direction


def _non_maximum_suppression(magnitude, direction):
    """Thin edges by keeping only local maxima along gradient direction."""
    h, w = magnitude.shape
    result = np.zeros((h, w), dtype=np.float32)
    a = direction.copy()
    a[a >= 168.75] = 0
    n_right = magnitude[1:-1, 2:]
    n_left = magnitude[1:-1, :-2]
    n_up_right = magnitude[:-2, 2:]
    n_down_left = magnitude[2:, :-2]
    n_down = magnitude[2:, 1:-1]
    n_up = magnitude[:-2, 1:-1]
    n_up_left = magnitude[:-2, :-2]
    n_down_right = magnitude[2:, 2:]
    center = magnitude[1:-1, 1:-1]
    ang = a[1:-1, 1:-1]
    q = np.zeros_like(center)
    r = np.zeros_like(center)
    m0 = (ang < 22.5) | (ang >= 157.5)
    m45 = (ang >= 22.5) & (ang < 67.5)
    m90 = (ang >= 67.5) & (ang < 112.5)
    m135 = (ang >= 112.5) & (ang < 157.5)
    q[m0] = n_right[m0]
    r[m0] = n_left[m0]
    q[m45] = n_down_left[m45]
    r[m45] = n_up_right[m45]
    q[m90] = n_down[m90]
    r[m90] = n_up[m90]
    q[m135] = n_up_left[m135]
    r[m135] = n_down_right[m135]
    keep = (center >= q) & (center >= r)
    result[1:-1, 1:-1] = np.where(keep, center, 0)
    return result


def _double_threshold_hysteresis(suppressed, low, high):
    """Apply double threshold and hysteresis to link weak edges to strong."""
    h, w = suppressed.shape
    strong = np.uint8(255)
    result = np.zeros((h, w), dtype=np.uint8)
    result[suppressed >= high] = strong
    weak_mask = (suppressed >= low) & (suppressed < high)
    result[weak_mask] = np.uint8(75)
    kernel = np.ones((3, 3), dtype=np.uint8)
    for _ in range(8):
        strong_mask = (result == strong).astype(np.uint8)
        if _HAS_SCIPY:
            promoted = _scipy_conv2d(strong_mask, kernel, mode="same", boundary="fill")
        else:
            # Vectorized promotion without Python loops.
            padded = np.pad(strong_mask, 1, mode="constant")
            promoted = np.zeros((h, w), dtype=np.int32)
            for di in range(3):
                for dj in range(3):
                    promoted += padded[di:di + h, dj:dj + w]
        newly_strong = weak_mask & (promoted > 0)
        if not np.any(newly_strong):
            break
        result[newly_strong] = strong
    result[result != strong] = 0
    return result


def _canny_numpy(gray, sigma=0.33):
    """Pure-numpy Canny edge detection (fully vectorized)."""
    blurred = _conv2d(gray.astype(np.float32), _gaussian_kernel(5, sigma))
    magnitude, direction = _sobel_gradients(blurred)
    suppressed = _non_maximum_suppression(magnitude, direction)
    v = float(np.median(suppressed[suppressed > 0])) if np.any(suppressed > 0) else 128.0
    low = max(0, (1.0 - sigma) * v)
    high = min(255, (1.0 + sigma) * v)
    return _double_threshold_hysteresis(suppressed, low, high)


def _clahe_numpy(gray, clip_limit=4.0, grid_size=8):
    """Pure-numpy CLAHE with vectorized histogram clipping."""
    h, w = gray.shape
    tile_h = max(1, h // grid_size)
    tile_w = max(1, w // grid_size)
    result = np.empty_like(gray)
    clip_pixels = int(clip_limit * 256.0 / grid_size)  # Approx per-tile budget.
    for gy in range(grid_size):
        for gx in range(grid_size):
            y0, y1 = gy * tile_h, min((gy + 1) * tile_h, h)
            x0, x1 = gx * tile_w, min((gx + 1) * tile_w, w)
            tile = gray[y0:y1, x0:x1]
            total = tile.size
            hist, _ = np.histogram(tile, bins=256, range=(0, 256))
            tile_clip = int(clip_limit * total / 256.0)
            excess = np.maximum(hist - tile_clip, 0).sum()
            hist = np.clip(hist, 0, tile_clip)
            hist += excess // 256
            hist[:int(excess % 256)] += 1
            cdf = np.cumsum(hist).astype(np.float32)
            cdf_min = float(cdf[cdf > 0].min()) if np.any(cdf > 0) else 0.0
            denom = total - cdf_min
            if denom <= 0:
                denom = 1
            lut = np.clip(((cdf - cdf_min) / denom) * 255, 0, 255).astype(np.uint8)
            result[y0:y1, x0:x1] = lut[tile]
    return result

def reset_temporal_filter_state():
    """Clear motion background state (detection state cleared separately)."""
    global _prev_motion_frame, _mog2_subtractor
    _prev_motion_frame = None
    _mog2_subtractor = None
    try:
        from QGISFMV.video.filters.QgsFmvDetectionFilters import reset_detection_state
        reset_detection_state()
    except Exception as _exc:
        log.debug('Failed to reset detection state: %s', _exc)


def resetTemporalFilterState():
    """Backward-compatible alias for reset_temporal_filter_state."""
    reset_temporal_filter_state()


def opencvAvailable():
    """Backward-compatible alias for opencv_available."""
    return opencv_available()


def opencvStatusText():
    """Backward-compatible alias for opencv_status_text."""
    return opencv_status_text()


def _box3x3_sum(padded):
    """Sum of 3x3 neighborhoods over a pre-padded array (no-loop fallback for scipy)."""
    return (
        padded[:-2, :-2] + padded[:-2, 1:-1] + padded[:-2, 2:]
        + padded[1:-1, :-2] + padded[1:-1, 1:-1] + padded[1:-1, 2:]
        + padded[2:, :-2] + padded[2:, 1:-1] + padded[2:, 2:]
    )


class FilterCore:
    """Shared drawing / image primitives for video filters."""

    @staticmethod
    def draw_filter_banner(out_rgb, text, color_rgb):
        """Always-visible status strip so analysis filters are never a silent no-op."""
        h = int(out_rgb.shape[0])
        w = int(out_rgb.shape[1])
        band_h = int(max(36, h // 12))
        color = np.asarray(color_rgb, dtype=np.float64)
        out_rgb[0:band_h, :] = (
            out_rgb[0:band_h, :].astype(np.float64) * 0.2 + color * 0.8
        ).astype(np.uint8)
        # Thick border + corner chips (readable without OpenCV putText).
        out_rgb[:4, :] = color_rgb
        out_rgb[-4:, :] = color_rgb
        out_rgb[:, :4] = color_rgb
        out_rgb[:, -4:] = color_rgb
        chip = int(max(10, min(h, w) // 40))
        out_rgb[:chip, :chip] = color_rgb
        out_rgb[:chip, -chip:] = color_rgb
        out_rgb[-chip:, :chip] = color_rgb
        out_rgb[-chip:, -chip:] = color_rgb
        if _HAS_CV2:
            scale = max(0.55, min(1.2, w / 640.0))
            putText(
                out_rgb,
                text,
                (10, int(band_h * 0.72)),
                FONT_HERSHEY_SIMPLEX,
                scale,
                (255, 255, 255),
                max(1, int(scale * 2)),
                LINE_AA,
            )
        else:
            # Numpy "bar code" encoding of mode so the banner is never blank.
            text_u = str(text or "")
            mode = 1 if "ROAD" in text_u.upper() else 2 if "BUILD" in text_u.upper() else 3
            for i in range(8):
                x0 = 12 + i * 14
                x1 = x0 + 10
                if x1 >= w - 8:
                    break
                on = bool((mode + i) & 1) if i < 4 else bool(i % 2)
                out_rgb[8:band_h - 8, x0:x1] = (255, 255, 255) if on else (20, 20, 20)
        return out_rgb

    @staticmethod
    def draw_box_numpy(out_rgb, x0, y0, x1, y1, color, thickness=2):
        """Draw a rectangular border on an RGB uint8 image (no OpenCV dependency)."""
        h, w = out_rgb.shape[:2]
        x0 = max(0, min(w - 1, int(x0)))
        x1 = max(0, min(w - 1, int(x1)))
        y0 = max(0, min(h - 1, int(y0)))
        y1 = max(0, min(h - 1, int(y1)))
        if x1 <= x0 or y1 <= y0:
            return
        t = max(1, int(thickness))
        out_rgb[y0 : y0 + t, x0:x1] = color
        out_rgb[y1 - t : y1, x0:x1] = color
        out_rgb[y0:y1, x0 : x0 + t] = color
        out_rgb[y0:y1, x1 - t : x1] = color

    @staticmethod
    def draw_line_numpy(out_rgb, x0, y0, x1, y1, color):
        """Bresenham line on an RGB uint8 image (no OpenCV dependency)."""
        h, w = out_rgb.shape[:2]
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            if 0 <= x0 < w and 0 <= y0 < h:
                out_rgb[y0, x0] = color
                if 0 <= x0 + 1 < w:
                    out_rgb[y0, x0 + 1] = color
                if 0 <= y0 + 1 < h:
                    out_rgb[y0 + 1, x0] = color
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    @staticmethod
    def rgb_channels(rgb):
        """Decompose an RGB image into individual channels plus luminance, chroma, and ExG."""
        r = rgb[:, :, 0].astype(np.float64)
        g = rgb[:, :, 1].astype(np.float64)
        b = rgb[:, :, 2].astype(np.float64)
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        chroma = np.maximum(np.abs(r - g), np.maximum(np.abs(g - b), np.abs(r - b)))
        exg = 2.0 * g - r - b
        return r, g, b, lum, chroma, exg

    @staticmethod
    def rgb_to_hsv(rgb):
        """Vectorized RGB→HSV. H in [0,180] (OpenCV-like), S/V in [0,255]."""
        rf = rgb[:, :, 0].astype(np.float32) / 255.0
        gf = rgb[:, :, 1].astype(np.float32) / 255.0
        bf = rgb[:, :, 2].astype(np.float32) / 255.0
        cmax = np.maximum(np.maximum(rf, gf), bf)
        cmin = np.minimum(np.minimum(rf, gf), bf)
        delta = cmax - cmin
        h = np.zeros_like(cmax, dtype=np.float32)
        mask = delta > 1e-8
        rmax = mask & (cmax == rf)
        gmax = mask & (cmax == gf)
        bmax = mask & (cmax == bf)
        inv_delta = np.zeros_like(delta)
        inv_delta[mask] = 1.0 / delta[mask]
        h[rmax] = ((gf[rmax] - bf[rmax]) * inv_delta[rmax]) % 6.0
        h[gmax] = (bf[gmax] - rf[gmax]) * inv_delta[gmax] + 2.0
        h[bmax] = (rf[bmax] - gf[bmax]) * inv_delta[bmax] + 4.0
        h *= 30.0  # 0..180
        s = np.where(cmax > 1e-8, delta / cmax, 0.0) * 255.0
        v = cmax * 255.0
        return h, s, v

    @staticmethod
    def edge_mag(gray):
        """Compute edge magnitude using Sobel (scipy) or numpy finite-difference fallback."""
        if _HAS_NDIMAGE:
            gx = _ndimage.sobel(gray, axis=1, mode="nearest")
            gy = _ndimage.sobel(gray, axis=0, mode="nearest")
            return np.hypot(gx, gy)
        gx = np.abs(np.diff(gray, axis=1, prepend=gray[:, :1]))
        gy = np.abs(np.diff(gray, axis=0, prepend=gray[:1, :]))
        return gx + gy

    @staticmethod
    def smooth(score, sigma=1.2):
        """Gaussian smooth a 2-D array (scipy or 3x3 box-filter fallback)."""
        if _HAS_NDIMAGE:
            return _ndimage.gaussian_filter(score, sigma=sigma)
        pad = np.pad(score, 1, mode="edge")
        return _box3x3_sum(pad) / 9.0

    @staticmethod
    def morph_mask(mask, open_iter=1, close_iter=2):
        """Clean binary mask with morphology (scipy) or tiny numpy fallback."""
        m = mask.astype(bool)
        if _HAS_NDIMAGE:
            struct = np.ones((3, 3), dtype=bool)
            if open_iter:
                m = _ndimage.binary_opening(m, structure=struct, iterations=open_iter)
            if close_iter:
                m = _ndimage.binary_closing(m, structure=struct, iterations=close_iter)
            return m
        # Cheap 3x3 majority open/close approximation.
        for _ in range(max(open_iter, close_iter)):
            pad = np.pad(m.astype(np.uint8), 1, mode="edge")
            s = _box3x3_sum(pad)
            if open_iter:
                m = s >= 7
            if close_iter:
                m = s >= 3
        return m

    @staticmethod
    def label_boxes(
        mask,
        min_area_frac=0.0004,
        max_area_frac=0.25,
        aspect_range=(0.2, 6.0),
        min_extent=0.18,
        max_boxes=40,
        prefer_vertical=False,
    ):
        """Connected-component boxes from a boolean mask. Returns list of (x0,y0,x1,y1)."""
        h, w = mask.shape
        frame = float(h * w)
        boxes = []
        if not np.any(mask):
            return boxes
        if _HAS_NDIMAGE:
            labeled, nlab = _ndimage.label(mask)
            if nlab == 0:
                return boxes
            # slices is faster than per-label where
            slices = _ndimage.find_objects(labeled)
            for i, sl in enumerate(slices, start=1):
                if sl is None:
                    continue
                ys, xs = sl[0], sl[1]
                y0, y1 = ys.start, ys.stop
                x0, x1 = xs.start, xs.stop
                region = labeled[ys, xs] == i
                area = float(np.count_nonzero(region))
                if area < frame * min_area_frac or area > frame * max_area_frac:
                    continue
                bw, bh = x1 - x0, y1 - y0
                if bw < 6 or bh < 6:
                    continue
                aspect = bw / float(bh)
                if prefer_vertical:
                    aspect = bh / float(bw)
                    if aspect < aspect_range[0] or aspect > aspect_range[1]:
                        continue
                elif aspect < aspect_range[0] or aspect > aspect_range[1]:
                    continue
                extent = area / float(max(bw * bh, 1))
                if extent < min_extent:
                    continue
                boxes.append((x0, y0, x1, y1, area))
        else:
            # Fallback: coarse block clustering with early termination.
            block = max(8, min(h, w) // 28)
            half_block = block // 2
            visited = np.zeros_like(mask, dtype=bool)
            for y in range(0, h - block, block):
                for x in range(0, w - block, block):
                    if visited[y, x] or not mask[y : y + block, x : x + block].mean() > 0.45:
                        continue
                    x0, y0, x1, y1 = x, y, min(w, x + block), min(h, y + block)
                    grew = True
                    while grew:
                        grew = False
                        if x1 < w and mask[y0:y1, x1 : min(w, x1 + half_block)].mean() > 0.35:
                            x1 = min(w, x1 + half_block)
                            grew = True
                        if y1 < h and mask[y1 : min(h, y1 + half_block), x0:x1].mean() > 0.35:
                            y1 = min(h, y1 + half_block)
                            grew = True
                    visited[y0:y1, x0:x1] = True
                    area = float(np.count_nonzero(mask[y0:y1, x0:x1]))
                    if area < frame * min_area_frac:
                        continue
                    bw, bh = x1 - x0, y1 - y0
                    aspect = (bh / float(bw)) if prefer_vertical else (bw / float(bh))
                    if aspect < aspect_range[0] or aspect > aspect_range[1]:
                        continue
                    boxes.append((x0, y0, x1, y1, area))
        boxes.sort(key=lambda t: t[4], reverse=True)
        return [(a, b, c, d) for a, b, c, d, _ in boxes[:max_boxes]]

    # ── camelCase aliases (per CODING_STANDARDS.md) ──
    drawFilterBanner = draw_filter_banner
    drawBoxNumpy = draw_box_numpy
    drawLineNumpy = draw_line_numpy
    rgbChannels = rgb_channels
    rgbToHsv = rgb_to_hsv
    edgeMag = edge_mag
    morphMask = morph_mask
    labelBoxes = label_boxes
