# -*- coding: utf-8 -*-
"""Live georeferenced mosaic capture, blending, and extension."""

import os
import shutil
import time

import numpy as np

try:
    from osgeo import gdal, osr
except ImportError:
    gdal = None
    osr = None

from QGISFMV.utils.logging import log
from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_mosaic_frame_counter = 0
_mosaic_log_once = {"frame": False, "image": False, "affine": False, "write": False}
_mosaic_capture_state = {"time": 0.0, "lat": None, "lon": None, "footprint_span": None}
_feather_weights_cache = {}
_FEATHER_CACHE_MAX = 32
_cached_wgs84_srs = None


# ---------------------------------------------------------------------------
# WGS84 SRS cache
# ---------------------------------------------------------------------------


def _get_wgs84_srs():
    global _cached_wgs84_srs
    if _cached_wgs84_srs is None:
        _cached_wgs84_srs = osr.SpatialReference()
        _cached_wgs84_srs.ImportFromEPSG(4326)
    return _cached_wgs84_srs


# ---------------------------------------------------------------------------
# Frame capture helpers
# ---------------------------------------------------------------------------


def _footprint_ground_span_m():
    """Approximate ground radius of the current video footprint."""
    from QGISFMV.utils.core.QgsFmvUtils import gv

    if gv is None:
        return None
    corners = [
        gv.getCornerUL(),
        gv.getCornerUR(),
        gv.getCornerLR(),
        gv.getCornerLL(),
    ]
    if any(c is None or None in c for c in corners):
        return None
    lats = [c[0] for c in corners]
    lons = [c[1] for c in corners]
    center_lat = sum(lats) / 4.0
    center_lon = sum(lons) / 4.0
    center = (center_lon, center_lat)
    return max(_geo_distance(center, (c[1], c[0])) for c in corners)


def _should_accept_mosaic_frame():
    """Skip frames unless the platform moved or the footprint changed enough."""
    from QGISFMV.utils import constants as mosaic_cfg
    from QGISFMV.utils.core.QgsFmvUtils import gv

    global _mosaic_capture_state
    if gv is None:
        return True

    now = time.monotonic()
    lat = gv.getSensorLatitude()
    lon = gv.getSensorLongitude()
    if lat is None or lon is None:
        lat = gv.getFrameCenterLat()
        lon = gv.getFrameCenterLon()
    footprint_span = _footprint_ground_span_m()

    if lat is None or lon is None:
        _mosaic_capture_state.update(
            time=now, lat=lat, lon=lon, footprint_span=footprint_span
        )
        return True

    last_lat = _mosaic_capture_state["lat"]
    last_lon = _mosaic_capture_state["lon"]
    last_time = _mosaic_capture_state["time"]
    last_span = _mosaic_capture_state.get("footprint_span")
    if last_lat is None or last_lon is None:
        _mosaic_capture_state.update(
            time=now, lat=lat, lon=lon, footprint_span=footprint_span
        )
        return True

    elapsed = now - last_time
    moved = _geo_distance((last_lon, last_lat), (lon, lat))
    span_grew = False
    if footprint_span is not None and last_span is not None:
        span_grew = footprint_span >= max(
            last_span * mosaic_cfg.MOSAIC_FOOTPRINT_GROW_RATIO,
            last_span + mosaic_cfg.MOSAIC_FOOTPRINT_GROW_METERS,
        )

    if (
        span_grew
        or elapsed >= mosaic_cfg.MOSAIC_MIN_INTERVAL_SEC
        or moved >= mosaic_cfg.MOSAIC_MIN_MOVE_METERS
    ):
        _mosaic_capture_state.update(
            time=now, lat=lat, lon=lon, footprint_span=footprint_span
        )
        return True

    return False


def _downscale_qimage_for_mosaic(image, max_dimension=None):
    """Reduce frame size for mosaic I/O and blending."""
    from qgis.PyQt.QtCore import Qt

    if max_dimension is None:
        from QGISFMV.utils import constants as mosaic_cfg

        max_dimension = mosaic_cfg.MOSAIC_MAX_FRAME_DIMENSION
    width = image.width()
    height = image.height()
    if max(width, height) <= max_dimension:
        return image
    scale = max_dimension / float(max(width, height))
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    return image.scaled(
        new_w,
        new_h,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ---------------------------------------------------------------------------
# Feather / weight helpers
# ---------------------------------------------------------------------------


def _mosaic_feather_weights(height, width, feather_px=None):
    """Source-image edge ramp (image space) for soft frame borders.

    Results are cached by (height, width, feather_px) to avoid repeated
    numpy allocations during mosaic frame writes.
    """
    if feather_px is None:
        from QGISFMV.utils import constants as mosaic_cfg

        feather_px = mosaic_cfg.MOSAIC_FEATHER_PX
    feather_px = max(8, int(feather_px))
    key = (height, width, feather_px)
    cached = _feather_weights_cache.get(key)
    if cached is not None:
        return cached
    y = np.minimum(np.arange(height), np.arange(height)[::-1]).astype(np.float32)
    x = np.minimum(np.arange(width), np.arange(width)[::-1]).astype(np.float32)
    fy = np.clip(y / feather_px, 0.0, 1.0)
    fx = np.clip(x / feather_px, 0.0, 1.0)
    result = np.minimum.outer(fy, fx)
    if len(_feather_weights_cache) < _FEATHER_CACHE_MAX:
        _feather_weights_cache[key] = result
    return result


def _footprint_weights_from_mask(valid, feather_px=None):
    """Feather weights from distance to the footprint edge (not mosaic canvas)."""
    if feather_px is None:
        from QGISFMV.utils import constants as mosaic_cfg

        feather_px = mosaic_cfg.MOSAIC_FEATHER_PX
    feather_px = max(8, int(feather_px))
    valid = np.asarray(valid, dtype=bool)
    if not valid.any():
        return np.zeros(valid.shape, dtype=np.float32)

    try:
        from cv2 import DIST_L2, DIST_MASK_3, distanceTransform

        dist = distanceTransform(valid.astype(np.uint8), DIST_L2, DIST_MASK_3)
        return np.clip(dist / float(feather_px), 0.0, 1.0).astype(np.float32)
    except Exception as _exc:
        log.debug("cv2 distance transform unavailable: %s", _exc)

    try:
        from scipy import ndimage

        dist = ndimage.distance_transform_edt(valid)
        return np.clip(dist / float(feather_px), 0.0, 1.0).astype(np.float32)
    except Exception as _exc:
        log.debug("scipy distance transform unavailable: %s", _exc)

    # Fallback: distance to the valid bounding-box edge.
    ys, xs = np.where(valid)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    yy = np.arange(valid.shape[0], dtype=np.float32)[:, None]
    xx = np.arange(valid.shape[1], dtype=np.float32)[None, :]
    dy = np.minimum(yy - y0, y1 - yy)
    dx = np.minimum(xx - x0, x1 - xx)
    dist = np.minimum(dy, dx)
    weights = np.clip(dist / float(feather_px), 0.0, 1.0).astype(np.float32)
    return np.where(valid, weights, 0.0).astype(np.float32)


# ---------------------------------------------------------------------------
# Raster I/O helpers
# ---------------------------------------------------------------------------


def _dataset_extent_wgs84(path):
    ds = gdal.Open(path)
    if ds is None:
        return None
    gt = ds.GetGeoTransform()
    if gt is None:
        ds = None
        return None
    width = ds.RasterXSize
    height = ds.RasterYSize
    xs = []
    ys = []
    for col, row in ((0, 0), (width, 0), (0, height), (width, height)):
        xs.append(gt[0] + col * gt[1] + row * gt[2])
        ys.append(gt[3] + col * gt[4] + row * gt[5])
    ds = None
    return min(xs), min(ys), max(xs), max(ys)


def _union_extent(paths):
    extents = [_dataset_extent_wgs84(path) for path in paths]
    extents = [ext for ext in extents if ext is not None]
    if not extents:
        return None
    minx = min(ext[0] for ext in extents)
    miny = min(ext[1] for ext in extents)
    maxx = max(ext[2] for ext in extents)
    maxy = max(ext[3] for ext in extents)
    return minx, miny, maxx, maxy


def _mosaic_output_resolution(bounds, max_output_size=None):
    if max_output_size is None:
        from QGISFMV.utils import constants as mosaic_cfg

        max_output_size = mosaic_cfg.MOSAIC_MAX_OUTPUT_SIZE
    minx, miny, maxx, maxy = bounds
    span_x = max(abs(maxx - minx), 1e-12)
    span_y = max(abs(maxy - miny), 1e-12)
    if span_x >= span_y:
        width = max_output_size
        height = max(1, int(round(max_output_size * (span_y / span_x))))
    else:
        height = max_output_size
        width = max(1, int(round(max_output_size * (span_x / span_y))))
    xres = span_x / width
    yres = span_y / height
    return xres, yres, width, height


def _warp_raster_to_grid(path, bounds, xres, yres):
    """Warp a mosaic source onto a common grid.

    Do not treat RGB 0 as source nodata — night/dark video would punch holes.
    Empty areas outside the source footprint are still filled with 0 by Warp.
    """
    minx, miny, maxx, maxy = bounds
    opts = gdal.WarpOptions(
        format="MEM",
        outputBounds=(minx, miny, maxx, maxy),
        xRes=xres,
        yRes=yres,
        dstNodata=0,
        resampleAlg=gdal.GRA_Bilinear,
    )
    return gdal.Warp("", path, options=opts)


def _read_rgba_arrays(dataset):
    """Return (rgb[3,h,w], alpha[h,w]) as float32. Alpha in 0..255."""
    if dataset is None:
        return None, None
    if dataset.RasterCount >= 3:
        bands = [
            dataset.GetRasterBand(idx).ReadAsArray().astype(np.float32)
            for idx in (1, 2, 3)
        ]
        rgb = np.stack(bands, axis=0)
    else:
        band = dataset.GetRasterBand(1).ReadAsArray().astype(np.float32)
        rgb = np.stack([band, band, band], axis=0)

    if dataset.RasterCount >= 4:
        alpha = dataset.GetRasterBand(4).ReadAsArray().astype(np.float32)
    else:
        # Legacy RGB-only frames: footprint = non-empty warp coverage.
        # Use footprint-edge feather instead of mosaic-canvas feather.
        coverage = np.any(rgb > 0, axis=0)
        alpha = _footprint_weights_from_mask(coverage) * 255.0
    return rgb, alpha


def _write_rgba_geotiff(path, rgb, alpha, geotransform, projection):
    if rgb.ndim != 3 or rgb.shape[0] < 3:
        return False
    _, height, width = rgb.shape
    driver = gdal.GetDriverByName("GTiff")
    if driver is None:
        return False
    dataset = driver.Create(
        path,
        width,
        height,
        4,
        gdal.GDT_Byte,
        options=["TILED=YES", "COMPRESS=LZW", "BIGTIFF=IF_SAFER"],
    )
    if dataset is None:
        return False
    dataset.SetGeoTransform(geotransform)
    dataset.SetProjection(projection)
    for idx in range(3):
        band = dataset.GetRasterBand(idx + 1)
        band.WriteArray(rgb[idx].astype(np.uint8))
    alpha_band = dataset.GetRasterBand(4)
    alpha_u8 = np.clip(alpha, 0, 255).astype(np.uint8)
    alpha_band.WriteArray(alpha_u8)
    alpha_band.SetNoDataValue(0)
    dataset.FlushCache()
    dataset = None
    return True


def _extend_mosaic_weighted(sources, out_path):
    """Blend sources with per-footprint (alpha / distance) weights."""
    bounds = _union_extent(sources)
    if bounds is None:
        return False

    xres, yres, _, _ = _mosaic_output_resolution(bounds)
    accum = None
    weight_sum = None
    geotransform = None
    projection = None

    for path in sources:
        warped = _warp_raster_to_grid(path, bounds, xres, yres)
        if warped is None:
            continue
        rgb, alpha = _read_rgba_arrays(warped)
        if rgb is None or alpha is None:
            warped = None
            continue
        weights = np.clip(alpha / 255.0, 0.0, 1.0).astype(np.float32)
        # If alpha is nearly binary (coverage only), soften footprint edges.
        if float(weights.max()) > 0 and float(np.mean(weights[weights > 0])) > 0.95:
            weights = _footprint_weights_from_mask(weights > 0.01)
        weighted = rgb * weights
        if accum is None:
            accum = weighted
            weight_sum = weights.copy()
            geotransform = warped.GetGeoTransform()
            projection = warped.GetProjection()
        else:
            accum += weighted
            weight_sum += weights
        warped = None

    if accum is None or weight_sum is None:
        return False

    safe = np.maximum(weight_sum, 1e-6)
    out_rgb = np.clip(accum / safe, 0, 255)
    out_alpha = np.clip(weight_sum * 255.0, 0, 255)
    out_alpha[weight_sum < 1e-3] = 0
    return _write_rgba_geotiff(out_path, out_rgb, out_alpha, geotransform, projection)


def _scale_affine_for_resize(affine, old_width, old_height, new_width, new_height):
    """Keep ground georeferencing correct after downscaling a video frame."""
    if (
        affine is None
        or (old_width == new_width and old_height == new_height)
        or old_width <= 0
        or old_height <= 0
        or new_width <= 0
        or new_height <= 0
    ):
        return affine
    sx = old_width / float(new_width)
    sy = old_height / float(new_height)
    return (
        affine[0],
        affine[1] * sx,
        affine[2] * sx,
        affine[3],
        affine[4] * sy,
        affine[5] * sy,
    )


# ---------------------------------------------------------------------------
# Georeferenced frame writing
# ---------------------------------------------------------------------------


def _write_georef_frame_gdal(image, dst_filename, affine):
    """Write RGBA GeoTIFF: RGB untouched, alpha = source-edge feather."""
    from QGISFMV.utils.core.QgsImageMat import convertQImageToMat

    rgb = convertQImageToMat(image)
    if rgb is None or rgb.size == 0:
        return None
    if rgb.ndim == 2:
        rgb = np.stack([rgb, rgb, rgb], axis=2)
    elif rgb.shape[2] > 3:
        rgb = rgb[:, :, :3]

    h, w = rgb.shape[0], rgb.shape[1]
    feather = _mosaic_feather_weights(h, w)
    alpha = np.clip(feather * 255.0, 0, 255).astype(np.uint8)
    # Fully transparent outside the soft edge (not black RGB).
    alpha[feather < 0.04] = 0

    driver = gdal.GetDriverByName("GTiff")
    if driver is None:
        return None

    dst_ds = driver.Create(
        dst_filename,
        w,
        h,
        4,
        gdal.GDT_Byte,
        options=["COMPRESS=LZW", "TILED=NO"],
    )
    if dst_ds is None:
        return None

    for idx in range(3):
        dst_ds.GetRasterBand(idx + 1).WriteArray(rgb[:, :, idx])
    alpha_band = dst_ds.GetRasterBand(4)
    alpha_band.WriteArray(alpha)
    alpha_band.SetNoDataValue(0)

    dst_ds.SetProjection(_get_wgs84_srs().ExportToWkt())
    dst_ds.SetGeoTransform(affine)
    dst_ds.FlushCache()
    dst_ds = None
    return dst_filename


def WriteGeoreferencedFrame(image, output, frame_id, affine):
    """Save one georeferenced RGBA GeoTIFF used as a mosaic source."""
    ext = ".tiff"
    dst_filename = os.path.join(output, "g_" + frame_id + ext)
    # Always write via GDAL RGBA path so feather lives in alpha, not RGB.
    return _write_georef_frame_gdal(image, dst_filename, affine)


def _gdal_raster_readable(path):
    if not path or not os.path.isfile(path):
        return False
    ds = None
    try:
        ds = gdal.OpenEx(path, gdal.OF_RASTER | gdal.OF_READONLY)
        return ds is not None
    except Exception as e:
        log.debug("GDAL raster unreadable: %s: %s", path, e)
        return False
    finally:
        ds = None


# ---------------------------------------------------------------------------
# Main entry points
# ---------------------------------------------------------------------------


def resetMosaicFrameCounter():
    """Reset per-session mosaic frame numbering."""
    global _mosaic_frame_counter, _mosaic_log_once, _mosaic_capture_state
    _mosaic_frame_counter = 0
    _mosaic_log_once = {
        "frame": False,
        "image": False,
        "affine": False,
        "write": False,
    }
    _mosaic_capture_state = {
        "time": 0.0,
        "lat": None,
        "lon": None,
        "footprint_span": None,
    }


def georeferencingVideo(parent):
    """Add the current frame to the live mosaic."""
    global _mosaic_frame_counter

    from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
    from QGISFMV.utils.core.QgsFmvUtils import gv, getVideoFolder
    from QGISFMV.utils.core.QgsFmvUtils import (
        _videoFrameImage,
        _syncVideoImageSizeFromParent,
    )
    from QGISFMV.utils.core.QgsFmvGeoReferencing import (
        SetImageSize,
        _affineTransformIsUsable,
        _refreshAffineFromStoredCorners,
    )

    if parent is None:
        return

    _syncVideoImageSizeFromParent(parent)

    image = _videoFrameImage(parent)
    if image is None:
        if not _mosaic_log_once["image"]:
            _mosaic_log_once["image"] = True
            qgsu.showUserAndLogMessage(
                "", "Mosaic: no video frame available yet.", onlyLog=True
            )
        return

    SetImageSize(image.width(), image.height())

    affine = gv.getAffineTransform()
    if not _affineTransformIsUsable(affine):
        _refreshAffineFromStoredCorners()
        affine = gv.getAffineTransform()
    if not _affineTransformIsUsable(affine):
        if not _mosaic_log_once["affine"]:
            _mosaic_log_once["affine"] = True
            qgsu.showUserAndLogMessage(
                "", "Mosaic: affine transform not available yet.", onlyLog=True
            )
        return

    if not _should_accept_mosaic_frame():
        return

    orig_w = image.width()
    orig_h = image.height()
    image = _downscale_qimage_for_mosaic(image)
    affine = _scale_affine_for_resize(
        affine, orig_w, orig_h, image.width(), image.height()
    )

    folder = getVideoFolder(parent.fileName)
    qgsu.createFolderByName(folder, "mosaic")
    out = os.path.join(folder, "mosaic")

    _mosaic_frame_counter += 1
    frame_id = f"{_mosaic_frame_counter:06d}"

    try:
        written = WriteGeoreferencedFrame(image, out, frame_id, affine)
    except Exception as e:
        if not _mosaic_log_once["write"]:
            _mosaic_log_once["write"] = True
            qgsu.showUserAndLogMessage(
                "", "Mosaic: frame write failed: " + str(e), onlyLog=True
            )
        return
    if not written or not _gdal_raster_readable(written):
        if not _mosaic_log_once["write"]:
            _mosaic_log_once["write"] = True
            qgsu.showUserAndLogMessage(
                "",
                "Mosaic: georeferenced frame file is missing or unreadable.",
                onlyLog=True,
            )
        return

    if not _mosaic_log_once["frame"]:
        _mosaic_log_once["frame"] = True
        qgsu.showUserAndLogMessage(
            "",
            f"Mosaic: first frame {frame_id} written. Mosaic is working.",
            onlyLog=True,
        )
    parent.onMosaicFrameAdded(written)
    return


def ExtendMosaic(task, out_path, new_frames, base_path=None):
    """Extend a running georeferenced mosaic with new frame(s), panorama-style."""
    if task is not None and task.isCanceled():
        return None

    frames = [p for p in (new_frames or []) if _gdal_raster_readable(p)]
    if not frames:
        return {"error": "no readable georeferenced frames"}

    base_ok = (
        base_path and os.path.isfile(base_path) and _gdal_raster_readable(base_path)
    )
    sources = ([base_path] if base_ok else []) + frames
    full_rebuild = not base_ok and len(sources) > 1
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    try:
        if len(sources) == 1:
            shutil.copy2(sources[0], out_path)
        elif not _extend_mosaic_weighted(sources, out_path):
            result = gdal.Warp(
                out_path,
                sources,
                format="GTiff",
                dstNodata=0,
                multithread=True,
                resampleAlg=gdal.GRA_Bilinear,
                creationOptions=[
                    "TILED=YES",
                    "COMPRESS=LZW",
                    "BIGTIFF=IF_SAFER",
                ],
            )
            if result is None:
                return {"error": "GDAL Warp produced no output"}
            result.FlushCache()
            result = None
    except Exception as exc:
        return {"error": str(exc)}

    if task is not None and task.isCanceled():
        try:
            os.remove(out_path)
        except OSError:
            pass
        return None

    if not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
        return {"error": "mosaic output file missing or empty"}

    return {
        "task": task.description() if task is not None else "ExtendMosaic",
        "out": out_path,
        "frames": len(frames),
        "full_rebuild": full_rebuild,
    }
