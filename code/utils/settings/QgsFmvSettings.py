# -*- coding: utf-8 -*-
"""Central access to ``settings.ini`` with reload support."""

import os
import platform
import shutil

from configparser import ConfigParser

try:
    from QGISFMV.utils.logging import log
except ImportError:
    import logging
    log = logging.getLogger("qgis_fmv")

_PLUGIN_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
SETTINGS_PATH = os.path.join(_PLUGIN_ROOT, "settings.ini")

_parser = ConfigParser(delimiters=(":"), comment_prefixes="/", allow_no_value=True)
_loaded = False

DEFAULTS = {
    "GENERAL": {
        "dtm_file": "",
        "dtm_buffer_size": "2000",
        "reverse_geocoding_url": (
            "https://nominatim.openstreetmap.org/reverse?format=json&lat={}&lon={}"
        ),
        "ffmpeg": "",
        "min_buffer_size": "5",
    },
    "LAYERS": {
        "platform_lyr": "Platform",
        "beams_lyr": "Beams",
        "footprint_lyr": "Footprint",
        "trajectory_lyr": "Trajectory",
        "framecenter_lyr": "Frame Center",
        "frameaxis_lyr": "Frame Axis",
        "point_lyr": "Drawings Point",
        "symbol_lyr": "Military Symbols",
        "line_lyr": "Drawings Line",
        "polygon_lyr": "Drawings Polygon",
        "objecttrack_lyr": "Object Track",
        "objectposition_lyr": "Object Position",
        "detections_lyr": "AI Detections",
        "detectiontrail_lyr": "AI Detection Trail",
        "measuredistance_lyr": "Measure Distance",
        "measurearea_lyr": "Measure Area",
        "epsg": "EPSG:4326",
        "frames_g": "FMV Georeferenced Frames",
    },
    "FILES": {
        "exts": (
            '["All Videos *.ts *.mpeg4 *.mp4 *.avi *.mpg *.H264 *.mov *.mpeg", '
            '"ts","mpeg4","mp4","avi","mpg","H264","mov","mpeg"]'
        ),
    },
    "MOSAIC": {
        "min_interval_sec": "2.0",
        "min_move_meters": "30",
        "max_frame_dimension": "960",
        "feather_px": "56",
        "max_output_size": "2048",
        "footprint_grow_ratio": "1.12",
        "footprint_grow_meters": "35",
        "refresh_every": "3",
        "display_every": "2",
        "max_kept_frames": "80",
    },
    "DNN": {
        "use_dnn_detection": "false",
        "dnn_model_profile": "aerial",
        "onnx_model": "",
        "onnx_model_type": "yolov8",
        "onnx_input_size": "640",
        "onnx_confidence": "0.15",
        "onnx_nms": "0.45",
        "dnn_building_class_ids": "",
        "dnn_road_class_ids": "",
        "dnn_vehicle_class_ids": "",
        "dnn_person_class_ids": "",
        "dnn_fire_class_ids": "",
        "dnn_smoke_class_ids": "",
        "dnn_flood_class_ids": "",
        "onnx_model_building": "",
        "onnx_model_road": "",
        "onnx_model_vehicle": "",
        "onnx_model_person": "",
        "onnx_model_fire": "",
        "onnx_model_smoke": "",
        "onnx_model_flood": "",
    },
    "FILTERS": {
        "profile": "aerial",
        "overlay_abs_threshold": "0.10",
        "overlay_adaptive_min_cov": "0.6",
        "overlay_weight_gate": "0.12",
        "overlay_adaptive_percentile": "74",
        "detection_percentile": "70",
        "detection_default_threshold": "0.10",
        "detection_min_pos": "20",
        "detection_min_area_frac": "0.000012",
        "detection_min_extent": "0.08",
        "detection_mask_blend": "0.55",
        "vehicle_min_area_frac": "0.000006",
        "person_min_area_frac": "0.00004",
        "building_min_area_frac": "0.0006",
        "road_min_area_frac": "0.0008",
        "ema_alpha": "0.42",
        "clahe_pregain": "true",
        "dnn_fallback_when_empty": "true",
        "multiscale_detection": "true",
        "box_nms_iou": "0.42",
        "show_box_confidence": "true",
        "tracking_enabled": "true",
    },
}


def pluginRoot():
    """Return the absolute path to the plugin root directory."""
    return _PLUGIN_ROOT


def settingsFile():
    """Return the absolute path to settings.ini."""
    return SETTINGS_PATH


def _default_ffmpeg_folder():
    """Return the platform-specific default FFmpeg installation folder.

    Paths are built with ``os.path.join`` so Mac / Linux / Windows behave the
    same. Prefer ``shutil.which`` before hard-coded Homebrew/system prefixes.
    """
    system = platform.system()
    if system == "Windows":
        base = (os.environ.get("LOCALAPPDATA") or "").strip() or os.path.expanduser("~")
        return os.path.join(base, "QGISFMV", "ffmpeg")
    if system == "Darwin":
        found = shutil.which("ffmpeg")
        if found:
            return os.path.dirname(os.path.realpath(found))
        candidates = [
            os.path.join(os.path.expanduser("~"), "Applications", "homebrew", "bin"),
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
        ]
        for folder in candidates:
            if _resolve_ffmpeg_binary(folder, "ffmpeg"):
                return folder
        return "/opt/homebrew/bin"
    # Linux / other Unix: prefer PATH, then common install prefixes.
    found = shutil.which("ffmpeg")
    if found:
        return os.path.dirname(os.path.realpath(found))
    for folder in ("/usr/local/bin", "/usr/bin", "/snap/bin"):
        if _resolve_ffmpeg_binary(folder, "ffmpeg"):
            return folder
    return "/usr/bin"


def _ensure_file():
    """Create settings.ini with defaults if it does not exist."""
    if os.path.isfile(SETTINGS_PATH):
        return
    parser = ConfigParser(delimiters=(":"), comment_prefixes="/", allow_no_value=True)
    for section, options in DEFAULTS.items():
        parser.add_section(section)
        for key, value in options.items():
            parser.set(section, key, value)
    parser.set("GENERAL", "ffmpeg", _default_ffmpeg_folder())
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        parser.write(fh)


def repairFfmpegSetting(persist=True):
    """If settings.ini points to a missing ffmpeg folder, try to auto-detect.

    Call explicitly on plugin start, FMV Settings open, or after installing
    FFmpeg — never from ordinary get()/setValue() so user values are preserved.
    """
    load()
    if not _parser.has_section("GENERAL"):
        return False
    try:
        folder = _parser.get("GENERAL", "ffmpeg", fallback="").strip()
    except Exception as _exc:
        log.debug("ffmpeg folder settings read failed: %s", _exc)
        folder = ""
    if _resolve_ffmpeg_binary(folder, "ffmpeg"):
        return False
    detected = _default_ffmpeg_folder()
    if not _resolve_ffmpeg_binary(detected, "ffmpeg"):
        return False
    _parser.set("GENERAL", "ffmpeg", detected)
    if persist:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
            _parser.write(fh)
    return True


def load(force=False):
    """Load settings.ini into the module-level parser, returning it."""
    global _loaded
    _ensure_file()
    if force or not _loaded:
        _parser.read(SETTINGS_PATH, encoding="utf-8")
        _loaded = True
    return _parser


def get(section, option, fallback=""):
    """Read a single setting value from settings.ini."""
    load()
    try:
        return _parser.get(section, option, fallback=fallback).strip()
    except Exception as _exc:
        log.debug("settings read failed for [%s] %s: %s", section, option, _exc)
        return fallback


def default(section, option):
    """Factory default from DEFAULTS (used when settings.ini omits a key)."""
    return DEFAULTS.get(section, {}).get(option, "")


def getLayer(option):
    """Read a [LAYERS] name with DEFAULTS fallback."""
    return get("LAYERS", option, default("LAYERS", option))


def reverseGeocodingUrl():
    """Reverse geocoding endpoint (supports legacy ini key spelling)."""
    return get("GENERAL", "reverse_geocoding_url") or get(
        "GENERAL", "Reverse_geocoding_url"
    )


def getInt(section, option):
    """Read a numeric setting with DEFAULTS fallback."""
    raw = get(section, option, default(section, option))
    try:
        return int(raw)
    except (TypeError, ValueError):
        try:
            return int(default(section, option) or 0)
        except (TypeError, ValueError):
            return 0


def setValue(section, option, value):
    """Write a single setting value to the in-memory parser."""
    load()
    if not _parser.has_section(section):
        _parser.add_section(section)
    _parser.set(section, option, str(value).strip())


def save():
    """Persist the in-memory parser to settings.ini and reload runtime."""
    load()
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
        _parser.write(fh)
    reloadRuntime()


def _resetDtmCache(fmv_utils):
    """Drop cached elevation tiles so a new DTM path takes effect."""
    fmv_utils.dtm_data = []
    fmv_utils.dtm_transform = None
    fmv_utils.dtm_colLowerBound = 0
    fmv_utils.dtm_rowLowerBound = 0


def _apply_mosaic_settings(fmv_utils):
    """Push [MOSAIC] settings into constants + QgsFmvUtils attributes."""
    from QGISFMV.utils import constants as mosaic_cfg

    section = "MOSAIC"
    _float = lambda k: float(get(section, k, default(section, k)))
    _int = lambda k: int(get(section, k, default(section, k)))
    values = {
        "MOSAIC_MIN_INTERVAL_SEC": _float("min_interval_sec"),
        "MOSAIC_MIN_MOVE_METERS": _float("min_move_meters"),
        "MOSAIC_MAX_FRAME_DIMENSION": _int("max_frame_dimension"),
        "MOSAIC_FEATHER_PX": _int("feather_px"),
        "MOSAIC_MAX_OUTPUT_SIZE": _int("max_output_size"),
        "MOSAIC_FOOTPRINT_GROW_RATIO": _float("footprint_grow_ratio"),
        "MOSAIC_FOOTPRINT_GROW_METERS": _float("footprint_grow_meters"),
        "MOSAIC_MAX_KEPT_FRAMES": _int("max_kept_frames"),
    }
    for name, value in values.items():
        setattr(mosaic_cfg, name, value)
        setattr(fmv_utils, name, value)


_LAYER_ATTR_MAP = {
    "platform_lyr": "Platform_lyr",
    "beams_lyr": "Beams_lyr",
    "footprint_lyr": "Footprint_lyr",
    "framecenter_lyr": "FrameCenter_lyr",
    "frameaxis_lyr": "FrameAxis_lyr",
    "point_lyr": "Point_lyr",
    "symbol_lyr": "Symbol_lyr",
    "line_lyr": "Line_lyr",
    "polygon_lyr": "Polygon_lyr",
    "objecttrack_lyr": "ObjectTrack_lyr",
    "objectposition_lyr": "ObjectPosition_lyr",
    "detections_lyr": "Detections_lyr",
    "detectiontrail_lyr": "DetectionTrail_lyr",
    "measuredistance_lyr": "MeasureDistance_lyr",
    "measurearea_lyr": "MeasureArea_lyr",
    "frames_g": "frames_g",
    "trajectory_lyr": "Trajectory_lyr",
}


def _sync_layer_module(layers):
    """Refresh QgsFmvLayers cached names from settings.ini."""
    layers.parser = load()
    for ini_key, attr in _LAYER_ATTR_MAP.items():
        setattr(layers, attr, getLayer(ini_key))
    layers.epsg = getLayer("epsg")


def _sync_fmv_utils_module(fmv_utils):
    """Refresh QgsFmvUtils cached settings from settings.ini."""
    fmv_utils.parser = load()
    fmv_utils.ffmpegConf = ffmpegFolder()
    fmv_utils.frames_g = getLayer("frames_g")
    fmv_utils.Reverse_geocoding_url = reverseGeocodingUrl()
    fmv_utils.min_buffer_size = getInt("GENERAL", "min_buffer_size")
    fmv_utils.dtm_buffer = getInt("GENERAL", "dtm_buffer_size")
    for ini_key, attr in _LAYER_ATTR_MAP.items():
        setattr(fmv_utils, attr, getLayer(ini_key))

    ff_bin = ffmpegBinary()
    fp_bin = ffprobeBinary()
    if ff_bin:
        fmv_utils.ffmpeg_path = ff_bin
    if fp_bin:
        fmv_utils.ffprobe_path = fp_bin

    _resetDtmCache(fmv_utils)
    _apply_mosaic_settings(fmv_utils)


def reloadRuntime():
    """Push settings.ini into modules that cache values for hot paths."""
    load(force=True)

    import QGISFMV.utils.core.QgsFmvUtils as fmv_utils
    import QGISFMV.utils.layers.QgsFmvLayers as layers

    _sync_fmv_utils_module(fmv_utils)
    _sync_layer_module(layers)

    try:
        from QGISFMV.utils.media.QgsFfmpegRunner import invalidate_paths

        invalidate_paths()
        fmv_utils._ensureFfmpegPaths()
    except Exception as exc:
        log.debug("FFmpeg path refresh failed: %s", exc)

    log.info("Settings reloaded from " + SETTINGS_PATH)

    try:
        from QGISFMV.video.dnn.QgsFmvOnnxDetector import reset_dnn_cache

        reset_dnn_cache()
    except Exception as exc:
        log.debug("DNN cache reset failed: %s", exc)


def _resolve_ffmpeg_binary(folder, exe_name):
    """Locate an ffmpeg/ffprobe binary in *folder* or its 'bin' subdirectory."""
    if not folder:
        return None
    folder = folder.strip()
    if os.path.isfile(folder) and os.path.basename(folder).lower() == exe_name.lower():
        return folder
    for candidate in (
        os.path.join(folder, exe_name),
        os.path.join(folder, "bin", exe_name),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def ffmpegFolder():
    """Return the configured FFmpeg binary folder path."""
    return get("GENERAL", "ffmpeg")


def ffmpegBinary():
    """Return the absolute path to the ffmpeg binary, or None."""
    exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
    folder = get("GENERAL", "ffmpeg")
    resolved = _resolve_ffmpeg_binary(folder, exe)
    if resolved:
        return resolved
    found = shutil.which(exe)
    return found or _resolve_ffmpeg_binary(folder, exe)


def ffprobeBinary():
    """Return the absolute path to the ffprobe binary, or None."""
    exe = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
    folder = get("GENERAL", "ffmpeg")
    resolved = _resolve_ffmpeg_binary(folder, exe)
    if resolved:
        return resolved
    found = shutil.which(exe)
    return found or _resolve_ffmpeg_binary(folder, exe)


# ── Backward-compatible aliases (legacy snake_case names) ──
plugin_root = pluginRoot
settings_file = settingsFile
ffmpeg_binary = ffmpegBinary
ffmpeg_folder = ffmpegFolder
ffprobe_binary = ffprobeBinary
get_layer = getLayer
reverse_geocoding_url = reverseGeocodingUrl
get_int = getInt
repair_ffmpeg_setting = repairFfmpegSetting
set_value = setValue


# Initial load (runtime sync happens when the plugin class is constructed)
load()
