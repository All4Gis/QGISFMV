# -*- coding: utf-8 -*-
import numpy as np
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QImage

import QGISFMV.video.filters.QgsFmvFilterCore as _fcore
from QGISFMV.utils.core.QgsImageMat import convertMatToQImage, convertQImageToMat
from QGISFMV.utils.logging import log
from QGISFMV.video.filters.QgsFmvDetectionFilters import FmvDetectionFilters
from QGISFMV.video.filters.QgsFmvFilterCore import (
    _COLORMAP_NRVI,
    _HAS_CV2,
    _MAX_SLOW_FILTER_DIM,
    FilterCore,
    _canny_numpy,
    _clahe_numpy,
    _conv2d,
    _get_mog2_subtractor,
)


class VideoFilters(object):
    """Video frame filters applied frame-by-frame."""

    _SLOW_FLAGS = (
        "edgeDetectionFilter",
        "contrastFilter",
        "brightnessContrastFilter",
        "claheFilter",
        "sharpenFilter",
        "sobelFilter",
        "falseColorFilter",
        "exgFilter",
        "exrFilter",
        "variFilter",
        "nrviFilter",
        "dehazeFilter",
        "roadEnhanceFilter",
        "hotspotFilter",
        "motionDetectionFilter",
        "backgroundSubtractionFilter",
        "buildingDetectionFilter",
        "roadSegmentationFilter",
        "vehicleSegmentationFilter",
        "personSegmentationFilter",
        "fireDetectionFilter",
        "smokeDetectionFilter",
        "floodDetectionFilter",
    )

    @staticmethod
    def _needs_processing(state):
        """Return True if any computationally expensive filter is active."""
        return any(getattr(state, f) for f in VideoFilters._SLOW_FLAGS)

    @staticmethod
    def _downscale_for_processing(image, max_dim=_MAX_SLOW_FILTER_DIM):
        """Downscale QImage for faster filter processing, return (scaled, scale_factor)."""
        w, h = image.width(), image.height()
        if max(w, h) <= max_dim:
            return image, 1.0
        scale = max_dim / float(max(w, h))
        nw, nh = int(w * scale), int(h * scale)
        return (
            image.scaled(
                nw,
                nh,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            ),
            scale,
        )

    # Lookup table: (state_attr, filter_method_or_None_for_special, needs_args)
    _FILTER_DISPATCH = (
        ("brightnessContrastFilter", "_BrightnessContrast", True),
        ("roadEnhanceFilter", "RoadEnhanceFilter", False),
        ("claheFilter", "CLAHEFilter", False),
        ("dehazeFilter", "DehazeFilter", False),
        ("sharpenFilter", "SharpenFilter", False),
        ("sobelFilter", "SobelFilter", False),
        ("falseColorFilter", "FalseColorFilter", False),
        ("exgFilter", "ExGFilter", False),
        ("exrFilter", "ExRFilter", False),
        ("variFilter", "VARIFilter", False),
        ("nrviFilter", "NRVIFilter", False),
        ("hotspotFilter", "HotspotFilter", False),
        ("buildingDetectionFilter", "BuildingDetectionFilter", False),
        ("roadSegmentationFilter", "RoadSegmentationFilter", False),
        ("vehicleSegmentationFilter", "VehicleSegmentationFilter", False),
        ("personSegmentationFilter", "PersonSegmentationFilter", False),
        ("fireDetectionFilter", "FireDetectionFilter", False),
        ("smokeDetectionFilter", "SmokeDetectionFilter", False),
        ("floodDetectionFilter", "FloodDetectionFilter", False),
        ("edgeDetectionFilter", "EdgeFilter", False),
        ("contrastFilter", "AutoContrastFilter", False),
        ("motionDetectionFilter", "MotionDetectionFilter", False),
        ("backgroundSubtractionFilter", "BackgroundSubtractionFilter", False),
    )

    @staticmethod
    def _BrightnessContrast(image, state):
        return VideoFilters.BrightnessContrastFilter(
            image, state.brightness, state.contrastLevel
        )

    @staticmethod
    def apply(image, state, downscale_slow=True):
        """Apply all active filters to image and return the result."""
        if image is None or image.isNull():
            return image
        if state.grayColorFilter:
            image = VideoFilters.GrayFilter(image)
        if state.MirroredHFilter:
            image = VideoFilters.MirrorFilter(image)
        if state.monoFilter:
            image = VideoFilters.MonoFilter(image)
        if state.invertColorFilter:
            image = image.copy()
            image.invertPixels()
        if not VideoFilters._needs_processing(state):
            return image
        work = image
        scale = 1.0
        if downscale_slow:
            work, scale = VideoFilters._downscale_for_processing(image)
        try:
            for attr, method_name, needs_args in VideoFilters._FILTER_DISPATCH:
                if getattr(state, attr, False):
                    method = getattr(VideoFilters, method_name)
                    work = method(work, state) if needs_args else method(work)
                    break
        except Exception as exc:
            log.warning("VideoFilters.apply failed: %s", exc, exc_info=True)
            return VideoFilters._failure_overlay(image, str(exc))
        if scale < 1.0:
            work = work.scaled(
                image.width(),
                image.height(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        return work

    @staticmethod
    def _failure_overlay(image, message):
        """Return a visibly marked frame instead of failing silently."""
        try:
            rgb = convertQImageToMat(image, cn=3).copy()
            FilterCore.draw_filter_banner(
                rgb, "FILTER ERROR  " + (message or "")[:48], (255, 40, 40)
            )
            # Red corner chips so the failure is obvious even without OpenCV text.
            rgb[:12, :12] = (255, 0, 0)
            rgb[:12, -12:] = (255, 0, 0)
            return convertMatToQImage(rgb, bgr=False)
        except Exception as exc:
            log.debug("failure overlay rendering failed: %s", exc)
            return image

    @staticmethod
    def GrayFilter(image):
        """Convert QImage to grayscale."""
        return image.convertToFormat(QImage.Format.Format_Grayscale8)

    @staticmethod
    def MirrorFilter(image):
        """Mirror QImage horizontally."""
        return image.mirrored(True, False)

    @staticmethod
    def MonoFilter(image):
        """Convert QImage to 1-bit monochrome."""
        return image.convertToFormat(QImage.Format.Format_Mono)

    @staticmethod
    def EdgeFilter(image, sigma=0.33):
        """Canny edges overlaid on a dimmed original frame (visible on dark video)."""
        gray = convertQImageToMat(image, cn=1)
        rgb = convertQImageToMat(image, cn=3)
        if _HAS_CV2:
            blurred = _fcore.GaussianBlur(gray, (5, 5), 1.2)
            v = float(np.median(blurred))
            # Keep a usable band even on very dark / bright frames.
            lower = int(max(20, min(100, (1.0 - sigma) * v)))
            upper = int(max(lower + 40, min(220, (1.0 + sigma) * v * 1.5)))
            canny = _fcore.Canny(blurred, lower, upper)
            # Slight dilation so thin edges are visible after downscale.
            kernel = _fcore.getStructuringElement(_fcore.MORPH_RECT, (2, 2))
            canny = _fcore.morphologyEx(
                canny, _fcore.MORPH_DILATE, kernel, iterations=1
            )
        else:
            canny = _canny_numpy(gray, sigma)

        out = (rgb.astype(np.float64) * 0.35).astype(np.uint8)
        edges = canny > 0
        # Cyan edges on dimmed RGB background.
        out[edges, 0] = 0
        out[edges, 1] = 255
        out[edges, 2] = 255
        return convertMatToQImage(out, bgr=False)

    @staticmethod
    def AutoContrastFilter(image):
        """Auto contrast using CLAHE on the L channel."""
        img = convertQImageToMat(image, cn=3)
        if _HAS_CV2:
            # convertQImageToMat yields RGB — use RGB↔LAB, not BGR.
            lab = _fcore.cvtColor(img, _fcore.COLOR_RGB2LAB)
            l_ch, a_ch, b_ch = _fcore.split(lab)
            l_ch = _fcore._clahe.apply(l_ch)
            result = _fcore.cvtColor(
                _fcore.merge((l_ch, a_ch, b_ch)), _fcore.COLOR_LAB2RGB
            )
            return convertMatToQImage(result, bgr=False)
        else:
            bgr = img.astype(np.float64) / 255.0
            rgb_lin = np.where(
                bgr <= 0.04045, bgr / 12.92, ((bgr + 0.055) / 1.055) ** 2.4
            )
            m = np.array(
                [
                    [0.4124564, 0.3575761, 0.1804375],
                    [0.2126729, 0.7151522, 0.0721750],
                    [0.0193339, 0.1191920, 0.9503041],
                ]
            )
            xyz = rgb_lin @ m.T
            ref = np.array([0.95047, 1.0, 1.08883])
            xyz_n = xyz / ref
            f = np.where(xyz_n > 0.008856, np.cbrt(xyz_n), 7.787 * xyz_n + 16.0 / 116.0)
            L = 116.0 * f[:, :, 1] - 16.0
            a = 500.0 * (f[:, :, 0] - f[:, :, 1])
            b_ch = 200.0 * (f[:, :, 1] - f[:, :, 2])
            L8 = np.clip(L * 255.0 / 100.0, 0, 255).astype(np.uint8)
            L8_eq = _clahe_numpy(L8)
            L_eq = L8_eq.astype(np.float64) * 100.0 / 255.0
            fy = (L_eq + 16.0) / 116.0
            fx = a / 500.0 + fy
            fz = fy - b_ch / 200.0
            xyz_out = np.stack(
                [
                    ref[0]
                    * np.where(fx**3 > 0.008856, fx**3, (fx - 16.0 / 116.0) / 7.787),
                    ref[1]
                    * np.where(fy**3 > 0.008856, fy**3, (fy - 16.0 / 116.0) / 7.787),
                    ref[2]
                    * np.where(fz**3 > 0.008856, fz**3, (fz - 16.0 / 116.0) / 7.787),
                ],
                axis=2,
            )
            rgb_lin_out = xyz_out @ np.linalg.inv(m).T
            rgb_srgb = np.where(
                rgb_lin_out <= 0.0031308,
                rgb_lin_out * 12.92,
                1.055 * np.power(np.clip(rgb_lin_out, 0, None), 1.0 / 2.4) - 0.055,
            )
            result = (np.clip(rgb_srgb, 0, 1) * 255).astype(np.uint8)
            return convertMatToQImage(result, bgr=False)

    @staticmethod
    def BrightnessContrastFilter(image, brightness=0, contrast=0):
        """Manual brightness (-100..100) and contrast (-100..100) adjustment."""
        # convertQImageToMat returns RGB — keep that order for QImage.
        img = convertQImageToMat(image, cn=3).astype(np.float64)
        if brightness != 0:
            img = img + brightness * 2.55
        if contrast != 0:
            factor = (130.0 + contrast * 2.6) / 130.0
            img = (img - 128.0) * factor + 128.0
        result = np.clip(img, 0, 255).astype(np.uint8)
        return convertMatToQImage(result, bgr=False)

    # --- Analysis filters ---

    @staticmethod
    def CLAHEFilter(image):
        """Adaptive histogram equalization — improves local contrast."""
        img = convertQImageToMat(image, cn=3)
        if _HAS_CV2:
            bgr = _fcore.cvtColor(img, _fcore.COLOR_RGB2BGR)
            lab = _fcore.cvtColor(bgr, _fcore.COLOR_BGR2LAB)
            l_ch, a_ch, b_ch = _fcore.split(lab)
            clahe = _fcore.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
            l_ch = clahe.apply(l_ch)
            result_bgr = _fcore.cvtColor(
                _fcore.merge((l_ch, a_ch, b_ch)), _fcore.COLOR_LAB2BGR
            )
            return convertMatToQImage(result_bgr, bgr=True)
        gray = convertQImageToMat(image, cn=1)
        eq = _clahe_numpy(gray, clip_limit=3.5)
        return convertMatToQImage(np.dstack((eq, eq, eq)), bgr=False)

    @staticmethod
    def SharpenFilter(image):
        """Unsharp mask — enhances edges and fine details."""
        img = convertQImageToMat(image, cn=3)
        if _HAS_CV2:
            bgr = _fcore.cvtColor(img, _fcore.COLOR_RGB2BGR)
            blurred = _fcore.GaussianBlur(bgr, (0, 0), 2.5)
            amount = 1.8
            sharpened = np.clip(
                bgr.astype(np.float64)
                + (bgr.astype(np.float64) - blurred.astype(np.float64)) * amount,
                0,
                255,
            ).astype(np.uint8)
            return convertMatToQImage(sharpened, bgr=True)
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]], dtype=np.float64)
        rgb = img.astype(np.float64)
        sharpened = np.stack([_conv2d(rgb[:, :, c], kernel) for c in range(3)], axis=2)
        result = np.clip(sharpened, 0, 255).astype(np.uint8)
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def MotionDetectionFilter(image):
        """Frame differencing — highlights moving objects between consecutive frames."""
        # motion state in _fcore
        gray = convertQImageToMat(image, cn=1)
        if _HAS_CV2:
            img_blur = _fcore.GaussianBlur(gray, (15, 15), 0)
            if (
                _fcore._prev_motion_frame is None
                or _fcore._prev_motion_frame.shape != img_blur.shape
            ):
                _fcore._prev_motion_frame = img_blur
                return image
            diff = np.abs(
                img_blur.astype(np.int16) - _fcore._prev_motion_frame.astype(np.int16)
            ).astype(np.uint8)
            _, thresh = _fcore.threshold(diff, 18, 255, _fcore.THRESH_BINARY)
            # Overlay motion (green) on the original frame for readability.
            rgb = convertQImageToMat(image, cn=3).copy()
            motion = thresh > 0
            rgb[motion, 1] = np.clip(
                rgb[motion, 1].astype(np.int16) + 120, 0, 255
            ).astype(np.uint8)
            rgb[motion, 0] = (rgb[motion, 0] * 0.4).astype(np.uint8)
            rgb[motion, 2] = (rgb[motion, 2] * 0.4).astype(np.uint8)
            _fcore._prev_motion_frame = img_blur
            return convertMatToQImage(rgb, bgr=False)

        if (
            _fcore._prev_motion_frame is None
            or _fcore._prev_motion_frame.shape != gray.shape
        ):
            _fcore._prev_motion_frame = gray
            return image
        diff = np.abs(
            gray.astype(np.int16) - _fcore._prev_motion_frame.astype(np.int16)
        ).astype(np.uint8)
        motion = diff > 18
        rgb = convertQImageToMat(image, cn=3).copy()
        rgb[motion, 1] = 255
        rgb[motion, 0] = (rgb[motion, 0] * 0.3).astype(np.uint8)
        rgb[motion, 2] = (rgb[motion, 2] * 0.3).astype(np.uint8)
        _fcore._prev_motion_frame = gray
        return convertMatToQImage(rgb, bgr=False)

    @staticmethod
    def SobelFilter(image):
        """Sobel edge detection — gradient magnitude highlights structures."""
        gray = convertQImageToMat(image, cn=1)
        if _HAS_CV2:
            gx = _fcore.Sobel(gray, _fcore.CV_64F, 1, 0, ksize=3)
            gy = _fcore.Sobel(gray, _fcore.CV_64F, 0, 1, ksize=3)
            magnitude = np.sqrt(gx**2 + gy**2)
        else:
            magnitude, _ = _fcore._sobel_gradients(gray.astype(np.float64))
        peak = float(magnitude.max()) if magnitude.size else 0.0
        if peak > 1e-6:
            magnitude = magnitude * (255.0 / peak)
        result = np.clip(magnitude, 0, 255).astype(np.uint8)
        rgb = np.dstack((result, result, result))
        return QImage(
            rgb.data,
            rgb.shape[1],
            rgb.shape[0],
            rgb.shape[1] * 3,
            QImage.Format.Format_RGB888,
        ).copy()

    @staticmethod
    def FalseColorFilter(image):
        """False color using Turbo colormap — visualizes intensity differences."""
        gray = convertQImageToMat(image, cn=1)
        if _HAS_CV2:
            # applyColorMap returns BGR
            result = _fcore.applyColorMap(gray, _fcore.COLORMAP_TURBO)
            return convertMatToQImage(result, bgr=True)
        n = gray.astype(np.float64) / 255.0
        r = np.clip(1.5 - np.abs(n * 4.0 - 3.0), 0, 1)
        g = np.clip(1.5 - np.abs(n * 4.0 - 2.0), 0, 1)
        b = np.clip(1.5 - np.abs(n * 4.0 - 1.0), 0, 1)
        result = (np.stack((r, g, b), axis=2) * 255).astype(np.uint8)
        return convertMatToQImage(result, bgr=False)

    @staticmethod
    def _index_heatmap_blend(img, score, tint_rgb, amplify_positive=True):
        """Map an index score to a tinted heatmap blended over the frame."""
        s = score.astype(np.float64)
        if amplify_positive:
            s = np.clip(s, 0, None)
        peak = float(np.percentile(np.abs(s), 99)) if s.size else 1.0
        if peak < 1e-6:
            peak = 1.0
        norm = (
            np.clip(s / peak, 0, 1)
            if amplify_positive
            else np.clip((s / peak + 1.0) * 0.5, 0, 1)
        )
        heat = (norm * 255.0).astype(np.float64)
        tint = np.asarray(tint_rgb, dtype=np.float64)
        colored = np.empty_like(img, dtype=np.float64)
        colored[:, :, 0] = heat * (tint[0] / 255.0)
        colored[:, :, 1] = heat * (tint[1] / 255.0)
        colored[:, :, 2] = heat * (tint[2] / 255.0)
        blend = np.clip(img.astype(np.float64) * 0.35 + colored * 0.90, 0, 255)
        return convertMatToQImage(blend.astype(np.uint8), bgr=False)

    @staticmethod
    def ExGFilter(image):
        """Excess Green: ExG = 2G − R − B (vegetation highlight)."""
        img = convertQImageToMat(image, cn=3)
        r = img[:, :, 0].astype(np.float64)
        g = img[:, :, 1].astype(np.float64)
        b = img[:, :, 2].astype(np.float64)
        return VideoFilters._index_heatmap_blend(
            img, 2.0 * g - r - b, (40, 220, 60), amplify_positive=True
        )

    @staticmethod
    def ExRFilter(image):
        """Excess Red: ExR = 1.4R − G (soil / red-dominant surfaces)."""
        img = convertQImageToMat(image, cn=3)
        r = img[:, :, 0].astype(np.float64)
        g = img[:, :, 1].astype(np.float64)
        return VideoFilters._index_heatmap_blend(
            img, 1.4 * r - g, (240, 50, 40), amplify_positive=True
        )

    @staticmethod
    def VARIFilter(image):
        """Visible Atmospherically Resistant Index: (G−R)/(G+R−B)."""
        img = convertQImageToMat(image, cn=3)
        r = img[:, :, 0].astype(np.float64)
        g = img[:, :, 1].astype(np.float64)
        b = img[:, :, 2].astype(np.float64)
        vari = (g - r) / np.maximum(g + r - b, 1.0)
        return VideoFilters._index_heatmap_blend(
            img, vari, (30, 200, 255), amplify_positive=True
        )

    @staticmethod
    def BackgroundSubtractionFilter(image):
        """MOG2 background subtraction — detects foreground moving objects."""
        img = convertQImageToMat(image, cn=3)
        if _HAS_CV2:
            bgr = _fcore.cvtColor(img, _fcore.COLOR_RGB2BGR)
            sub = _get_mog2_subtractor()
            if sub is not None:
                fgmask = sub.apply(bgr)
                # Green overlay on movers; keep a dim background for context.
                rgb = img.copy()
                motion = fgmask > 127
                rgb[motion, 1] = 255
                rgb[motion, 0] = (rgb[motion, 0] * 0.25).astype(np.uint8)
                rgb[motion, 2] = (rgb[motion, 2] * 0.25).astype(np.uint8)
                dim = ~motion
                rgb[dim] = (rgb[dim].astype(np.float64) * 0.55).astype(np.uint8)
                return convertMatToQImage(rgb, bgr=False)
        return VideoFilters.MotionDetectionFilter(image)

    @staticmethod
    def DehazeFilter(image):
        """Dehazing using CLAHE + contrast stretch for foggy scenes."""
        img = convertQImageToMat(image, cn=3)
        if _HAS_CV2:
            bgr = _fcore.cvtColor(img, _fcore.COLOR_RGB2BGR)
            lab = _fcore.cvtColor(bgr, _fcore.COLOR_BGR2LAB)
            l_ch, a_ch, b_ch = _fcore.split(lab)
            clahe = _fcore.createCLAHE(clipLimit=6.0, tileGridSize=(16, 16))
            l_ch = clahe.apply(l_ch)
            p2, p98 = np.percentile(l_ch, (2, 98))
            l_ch = np.clip(
                (l_ch.astype(np.float64) - p2) / (p98 - p2 + 1e-6) * 255, 0, 255
            ).astype(np.uint8)
            result_bgr = _fcore.cvtColor(
                _fcore.merge((l_ch, a_ch, b_ch)), _fcore.COLOR_LAB2BGR
            )
            return convertMatToQImage(result_bgr, bgr=True)
        gray = convertQImageToMat(image, cn=1)
        eq = _clahe_numpy(gray, clip_limit=6.0, grid_size=16)
        return convertMatToQImage(np.dstack((eq, eq, eq)), bgr=False)

    @staticmethod
    def RoadEnhanceFilter(image):
        """Road and structure enhancement — CLAHE + Sobel + Sharpen combined."""
        img = convertQImageToMat(image, cn=3)
        if _HAS_CV2:
            bgr = _fcore.cvtColor(img, _fcore.COLOR_RGB2BGR)
            lab = _fcore.cvtColor(bgr, _fcore.COLOR_BGR2LAB)
            l_ch, a_ch, b_ch = _fcore.split(lab)
            clahe = _fcore.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
            l_ch = clahe.apply(l_ch)
            enhanced = _fcore.cvtColor(
                _fcore.merge((l_ch, a_ch, b_ch)), _fcore.COLOR_LAB2BGR
            )
            blurred = _fcore.GaussianBlur(enhanced, (0, 0), 2)
            sharpened = np.clip(
                enhanced.astype(np.float64)
                + (enhanced.astype(np.float64) - blurred.astype(np.float64)) * 1.5,
                0,
                255,
            ).astype(np.uint8)
            gray_eq = _fcore.cvtColor(enhanced, _fcore.COLOR_BGR2GRAY)
            edges = _fcore.Canny(gray_eq, 40, 140)
            edges_bgr = _fcore.cvtColor(edges, _fcore.COLOR_GRAY2BGR)
            result_bgr = np.clip(
                sharpened.astype(np.float64) * 0.75
                + edges_bgr.astype(np.float64) * 0.35,
                0,
                255,
            ).astype(np.uint8)
            return convertMatToQImage(result_bgr, bgr=True)
        gray = convertQImageToMat(image, cn=1)
        eq = _clahe_numpy(gray)
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float64)
        sharpened = _conv2d(eq.astype(np.float64), kernel)
        result = np.clip(sharpened, 0, 255).astype(np.uint8)
        return convertMatToQImage(np.dstack((result, result, result)), bgr=False)

    @staticmethod
    def HotspotFilter(image):
        """Highlight the brightest pixels (thermal/hotspot detection)."""
        gray = convertQImageToMat(image, cn=1)
        p92 = float(np.percentile(gray, 92))
        mask = gray > p92
        rgb = np.dstack((gray, gray, gray)).astype(np.float64)
        # Dim background, paint hotspots red.
        rgb *= 0.45
        rgb[mask, 0] = 255
        rgb[mask, 1] = np.clip(gray[mask].astype(np.float64) * 0.35, 0, 120)
        rgb[mask, 2] = 0
        return convertMatToQImage(np.clip(rgb, 0, 255).astype(np.uint8), bgr=False)

    @staticmethod
    def NRVIFilter(image):
        """Normalized Ratio Vegetation Index (RGB approx: NIR≈Green).

        NRVI = (NIR - Red) / (NIR + Red). Without a NIR band, green is used as
        a practical proxy for aerial RGB / EO FMV.
        """
        img = convertQImageToMat(image, cn=3).astype(np.float64)
        red = img[:, :, 0]
        nir = img[:, :, 1]  # green proxy
        nrvi = (nir - red) / (nir + red + 1e-6)
        # Map [-1, 1] → [0, 255] for a vegetation colormap.
        mapped = np.clip((nrvi + 1.0) * 0.5 * 255.0, 0, 255).astype(np.uint8)
        if _HAS_CV2 and _COLORMAP_NRVI is not None:
            colored_bgr = _fcore.applyColorMap(mapped, _COLORMAP_NRVI)
            return convertMatToQImage(colored_bgr, bgr=True)
        # Fallback: brown → yellow → green
        t = mapped.astype(np.float64) / 255.0
        r = np.clip(1.2 - t * 1.1, 0, 1)
        g = np.clip(0.3 + t * 0.7, 0, 1)
        b = np.clip(0.15 * (1.0 - t), 0, 1)
        rgb = (np.stack((r, g, b), axis=2) * 255).astype(np.uint8)
        return convertMatToQImage(rgb, bgr=False)

    BuildingDetectionFilter = staticmethod(FmvDetectionFilters.BuildingDetectionFilter)
    RoadSegmentationFilter = staticmethod(FmvDetectionFilters.RoadSegmentationFilter)
    VehicleSegmentationFilter = staticmethod(
        FmvDetectionFilters.VehicleSegmentationFilter
    )
    PersonSegmentationFilter = staticmethod(
        FmvDetectionFilters.PersonSegmentationFilter
    )
    FireDetectionFilter = staticmethod(FmvDetectionFilters.FireDetectionFilter)
    SmokeDetectionFilter = staticmethod(FmvDetectionFilters.SmokeDetectionFilter)
    FloodDetectionFilter = staticmethod(FmvDetectionFilters.FloodDetectionFilter)
