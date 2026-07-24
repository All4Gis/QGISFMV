# -*- coding: utf-8 -*-
from datetime import datetime
from math import sin, radians
import json
import os
import platform
import shutil
import time
from qgis.PyQt.QtCore import QSettings, QUrl, QEventLoop
from qgis.PyQt.QtCore import QPoint
from qgis.PyQt.QtGui import QPainter
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import (
    QgsNetworkAccessManager,
    Qgis as QGis,
)

from QGISFMV.utils.logging import log
from QGISFMV.utils.core.QgsFmvUtilsState import globalVariablesState  # noqa: F401
from QGISFMV.utils.core.QgsFmvVideoSession import (
    VideoSession,
    ensure_session,
    get_active_session,
    set_active_session,
)
from QGISFMV.utils.media import QgsFfmpegRunner as _ffmpeg_runner

import pymisb.klvdata  # noqa: F401  (register ST0601 parsers)
from pymisb.klvdata.element import UnknownElement
from pymisb.klvdata.streamparser import StreamParser
from QGISFMV.utils.layers.QgsFmvLayers import (
    UpdateTrajectoryData,
    UpdatePlatformData,
    UpdateFrameCenterData,
    UpdateFrameAxisData,
    SetcrtSensorSrc,
    SetcrtPltTailNum,
)
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.settings.QgsFmvSettings import (
    get_int,
    get_layer,
    reverse_geocoding_url as _reverse_geocoding_url,
)

# ---------------------------------------------------------------------------
# Backward-compat re-exports from domain modules
# ---------------------------------------------------------------------------
from QGISFMV.utils.core.QgsFmvGeoReferencing import (  # noqa: F401
    DEFAULT_TARGET_WIDTH,
    _find_homography,
    _find_homography_numpy,
    _affineTransformIsUsable,
    _footprint_inputs_changed,
    _refreshAffineFromStoredCorners,
    _update_footprint_beams_gcp,
    GetDemAltAt,
    GetFrameCenter,
    GetGCPGeoTransform,
    GetGeotransform_affine,
    GetImageHeight,
    GetImageWidth,
    GetLine3DIntersectionWithDEM,
    GetSensor,
    SetGCPsToGeoTransform,
    SetImageSize,
    hasElevationModel,
)
from QGISFMV.utils.core.QgsFmvCornerEstimation import (  # noqa: F401
    CornerEstimationWithOffsets,
    CornerEstimationWithoutOffsets,
)

from QGISFMV.utils.core.QgsFmvMosaic import (  # noqa: F401
    ExtendMosaic,
    WriteGeoreferencedFrame,
    _gdal_raster_readable,
    _get_wgs84_srs,
    _mosaic_source_files,
    georeferencingVideo,
    resetMosaicFrameCounter,
)
from QGISFMV.utils.core.QgsFmvMapCenter import (  # noqa: F401
    followMapCenter,
    centerCanvasOnLayer,
    _transformExtentToCanvas,
    _layerExtentInCanvasCrs,
    _transformPointToCanvas,
    _latest_layer_feature,
    _layer_center_on_canvas,
    _center_fallback_point,
)
from QGISFMV.utils.ui.QgsFmvFileDialogs import (  # noqa: F401
    pluginSetting,
    setPluginSetting,
    askForFiles,
    askForFolder,
)

settings = QSettings()
windows = platform.system() == "Windows"

# Cached settings (refreshed by QgsFmvSettings.reloadRuntime())
frames_g = get_layer("frames_g")
Reverse_geocoding_url = _reverse_geocoding_url()
dtm_buffer = get_int("GENERAL", "dtm_buffer_size")
Platform_lyr = get_layer("platform_lyr")
Beams_lyr = get_layer("beams_lyr")
Footprint_lyr = get_layer("footprint_lyr")
FrameCenter_lyr = get_layer("framecenter_lyr")
FrameAxis_lyr = get_layer("frameaxis_lyr")
Point_lyr = get_layer("point_lyr")
Symbol_lyr = get_layer("symbol_lyr")
Line_lyr = get_layer("line_lyr")
Polygon_lyr = get_layer("polygon_lyr")
ObjectTrack_lyr = get_layer("objecttrack_lyr")
ObjectPosition_lyr = get_layer("objectposition_lyr")
Trajectory_lyr = get_layer("trajectory_lyr")
# Defer ffmpeg/ffprobe resolution to QgsFfmpegRunner (avoids shutil.which at import).
# Kept as module attrs for backward compatibility with tests / callers.
ffmpeg_path = "ffmpeg.exe" if windows else "ffmpeg"
ffprobe_path = "ffprobe.exe" if windows else "ffprobe"

PLUGIN_NAMESPACE = "QGISFMV"

# Active video session (alias of VideoSession). Prefer get_active_session().
gv = None

dtm_data = []
dtm_transform = None
dtm_colLowerBound = 0
dtm_rowLowerBound = 0


def qmouse_pos(event):
    """Local position of a QMouseEvent or QPoint (Qt6)."""
    if isinstance(event, QPoint):
        return event
    return event.position().toPoint()


def _resolve_ffmpeg_binary(folder, exe_name):
    """Resolve an ffmpeg/ffprobe binary, falling back to a 'bin' subfolder
    (common layout of official Windows builds)."""
    from QGISFMV.utils.settings.QgsFmvSettings import _resolve_ffmpeg_binary as _resolve

    result = _resolve(folder, exe_name)
    if result:
        return result
    # Fallback: return the direct candidate even if not found (for startup path)
    return os.path.join(folder, exe_name)


def AddVideoToSettings(row_id, path):
    """Add video to settings list"""
    settings.setValue(getNameSpace() + "/Manager_List/" + row_id, path)


def RemoveVideoToSettings(row_id):
    """Remove video in settings list"""
    settings.remove(getNameSpace() + "/Manager_List/%s" % row_id)


def getVideoManagerList():
    """Get Video Manager List"""
    try:
        settings.beginGroup(getNameSpace() + "/Manager_List")
        VideoList = settings.childKeys()
        settings.endGroup()
        return VideoList
    except Exception as e:
        from QGISFMV.utils.logging import log
        log.debug("getVideoManagerList failed: %s", e)
        return []


def getVideoFolder(video_file):
    """Get or create Video Temporal folder"""
    home = os.path.expanduser("~")

    qgsu.createFolderByName(home, "QGISFMV")

    root, _ = os.path.splitext(os.path.basename(video_file))
    homefmv = os.path.join(home, "QGISFMV")

    qgsu.createFolderByName(homefmv, root)
    return os.path.join(homefmv, root)


def RemoveVideoFolder(filename):
    """Remove video temporal folder if exist"""
    videoFile, _ = os.path.splitext(filename)
    folder = getVideoFolder(videoFile)
    try:
        shutil.rmtree(folder, ignore_errors=True)
    except Exception as e:
        from QGISFMV.utils.logging import log
        log.debug("RemoveVideoFolder failed: %s", e)


def getNameSpace():
    """Get plugin name space"""
    return PLUGIN_NAMESPACE


def setCenterMode(mode, interface):
    """Create/activate a :class:`VideoSession` and set map-center mode."""
    global gv
    session = VideoSession(iface=interface)
    session.setCenterMode(mode)
    set_active_session(session)
    gv = session
    return session


def ensureGlobalState(interface):
    """Ensure an active :class:`VideoSession` exists before layer/mosaic updates."""
    global gv
    session = ensure_session(interface)
    gv = session
    return session


KLV_HEADER_0601 = b"\x06\x0e+4\x02\x0b\x01\x01\x0e\x01\x03\x01\x01\x00\x00\x00"
KLV_HEADER_EG0104 = b"\x06\x0e+4\x02\x01\x01\x01\x0e\x01\x01\x02\x01\x01\x00\x00"

# Cache for KLV stream index lookups to avoid re-probing the same file.
# Bounded to 256 entries to prevent unbounded growth in long sessions.
_klv_index_cache = {}
_KLV_CACHE_MAX = 256


def _ensureFfmpegPaths():
    """Refresh cached ffmpeg/ffprobe paths (delegates to QgsFfmpegRunner)."""
    global ffmpeg_path, ffprobe_path
    ffmpeg_path, ffprobe_path = _ffmpeg_runner.ensure_paths()


def _klvIndexFromProbe(videoPath):
    """Return the ``0:d:N`` index for the first KLV data stream, if any."""
    try:
        from QGISFMV.utils.media.QgsFfmpegProbe import probe_json

        data = probe_json(videoPath)
        if not data:
            return None
        info = json.loads(data.decode("utf-8", errors="replace"))
        data_idx = 0
        for stream in info.get("streams") or []:
            if stream.get("codec_type") != "data":
                continue
            codec = (stream.get("codec_name") or "").lower()
            tag = (stream.get("codec_tag_string") or "").upper()
            if codec == "klv" or tag == "KLVA":
                return data_idx
            data_idx += 1
    except Exception as e:
        from QGISFMV.utils.logging import log
        log.debug("KLV probe failed for %s: %s", videoPath, e)
    return None


def _klvDataLooksValid(rawData):
    return bool(rawData) and (
        KLV_HEADER_0601 in rawData or KLV_HEADER_EG0104 in rawData
    )


def getKlvStreamIndex(videoPath, quiet=False):
    """Return the ffprobe data-stream index containing KLV metadata."""
    _ensureFfmpegPaths()

    # Return cached result if available
    if videoPath in _klv_index_cache:
        return _klv_index_cache[videoPath]

    probed = _klvIndexFromProbe(videoPath)
    if probed is not None:
        if len(_klv_index_cache) >= _KLV_CACHE_MAX:
            _klv_index_cache.clear()
        _klv_index_cache[videoPath] = probed
        return probed

    for i in range(6):
        for cmd in (
            ["-i", videoPath, "-t", "1", "-map", "0:d:" + str(i), "-f", "data", "-"],
            [
                "-i",
                videoPath,
                "-ss",
                "00:00:00",
                "-to",
                "00:00:01",
                "-map",
                "0:d:" + str(i),
                "-f",
                "data",
                "-",
            ],
        ):
            p = _spawn(cmd)
            stdout_data, _ = p.communicate(timeout=15)
            if not _klvDataLooksValid(stdout_data):
                continue
            if len(_klv_index_cache) >= _KLV_CACHE_MAX:
                _klv_index_cache.clear()
            _klv_index_cache[videoPath] = i
            return i

        if not quiet:
            qgsu.showUserAndLogMessage(
                "", "skipping stream " + str(i) + " not a klv stream.", onlyLog=True
            )

    if not quiet:
        qgsu.showUserAndLogMessage(
            "Error interpreting klv data, metadata cannot be read.",
            "the parser did not recognize KLV data",
            level=QGis.MessageLevel.Warning,
        )
    if len(_klv_index_cache) >= _KLV_CACHE_MAX:
        _klv_index_cache.clear()
    _klv_index_cache[videoPath] = 0
    return 0


def _coordsFromKlvStream(rawData):
    for packet in StreamParser(rawData):
        if isinstance(packet, UnknownElement):
            continue
        centerLat = packet.FrameCenterLatitude
        centerLon = packet.FrameCenterLongitude
        if centerLat is None or centerLon is None:
            centerLat = packet.SensorLatitude
            centerLon = packet.SensorLongitude
        if centerLat is not None and centerLon is not None:
            return [centerLat, centerLon]
    return []


def fetchReverseGeocodeLabel(centerLat, centerLon):
    """Thread-safe reverse geocode (urllib); for QgsTask / worker threads."""
    from QGISFMV.utils.media.QgsFmvGeocode import (
        fetchReverseGeocodeLabel as _fetch_label,
    )

    return _fetch_label(Reverse_geocoding_url, centerLat, centerLon)


def _fetchReverseGeocodeJson(centerLat, centerLon, useQtNetwork=True):
    """Fetch reverse-geocode JSON (Qt network on GUI thread, urllib otherwise)."""
    from QGISFMV.utils.media.QgsFmvGeocode import (
        GEOCODE_USER_AGENT,
        normalizeReverseGeocodeUrl,
        fetchReverseGeocodeJson as _fetch_urllib,
    )

    if Reverse_geocoding_url == "" or centerLat is None or centerLon is None:
        return None
    if not useQtNetwork:
        return _fetch_urllib(Reverse_geocoding_url, centerLat, centerLon)

    try:
        from qgis.PyQt.QtCore import QTimer

        url = normalizeReverseGeocodeUrl(
            Reverse_geocoding_url.format(str(centerLat), str(centerLon))
        )
        request = QNetworkRequest(QUrl(url))
        request.setHeader(
            QNetworkRequest.KnownHeaders.UserAgentHeader,
            GEOCODE_USER_AGENT,
        )
        request.setRawHeader(b"Accept", b"application/json")
        reply = QgsNetworkAccessManager.instance().get(request)
        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        _timeout = QTimer()
        _timeout.setSingleShot(True)
        _timeout.timeout.connect(loop.quit)
        _timeout.start(8000)
        loop.exec()
        _timeout.stop()
        reply.finished.disconnect(loop.quit)
        if not reply.isFinished():
            reply.abort()
            log.warning("Reverse geocode timed out for %s, %s", centerLat, centerLon)
            return None
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        raw = bytes(reply.readAll().data())
        if status and int(status) >= 400:
            log.warning(
                "Reverse geocode HTTP %s: %s",
                status,
                raw[:200].decode("utf-8", errors="replace"),
            )
            return None
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as exc:
        log.warning(
            "Reverse geocode (Qt) failed for %s, %s: %s", centerLat, centerLon, exc
        )
        return None


def _reverseGeocodeLabelFromJson(data):
    """Build a short Start Location label from a Nominatim JSON payload."""
    from QGISFMV.utils.media.QgsFmvGeocode import reverseGeocodeLabelFromJson

    return reverseGeocodeLabelFromJson(data)


def _videoFrameImage(parent):
    """Best available QImage from the player (display or raw decode buffer)."""
    if parent is None:
        return None
    vw = getattr(parent, "videoWidget", None)
    if vw is None:
        return None
    img = vw.currentFrame()
    if img is None or img.isNull():
        tracker = getattr(vw, "trackingFrame", None)
        if callable(tracker):
            img = tracker()
    return img if img is not None and not img.isNull() else None


def _syncVideoImageSizeFromParent(parent):
    """Align GCP pixel dimensions with the current decoded video frame."""
    img = _videoFrameImage(parent)
    if img is not None:
        SetImageSize(img.width(), img.height())


def _spawn(cmds, t="ffmpeg"):
    """Spawn ffmpeg/ffprobe (delegates to :mod:`QgsFfmpegRunner`)."""
    global ffmpeg_path, ffprobe_path
    proc = _ffmpeg_runner.spawn(cmds, t=t)
    ffmpeg_path, ffprobe_path = _ffmpeg_runner.ensure_paths()
    return proc


RECORD_CONTAINER_FORMATS = ("ts", "mp4", "mkv", "mov")

RAW_VIDEO_EXTENSIONS = frozenset(
    {"h264", "264", "hevc", "h265", "avc", "265"}
)


def recordSaveExtensions(source_path=None):
    """Extensions offered when saving a trimmed FMV clip."""
    if source_path:
        ext = os.path.splitext(source_path)[1].lower().lstrip(".")
        if ext in RAW_VIDEO_EXTENSIONS:
            return list(RECORD_CONTAINER_FORMATS)
        if ext in ("ts", "mts", "m2ts", "mpg", "mpeg"):
            return ["ts", "mp4", "mkv", "mov"]
        if ext in RECORD_CONTAINER_FORMATS:
            ordered = [ext]
            for fmt in RECORD_CONTAINER_FORMATS:
                if fmt not in ordered:
                    ordered.append(fmt)
            return ordered
    return list(RECORD_CONTAINER_FORMATS)


def buildRecordFfmpegArgs(infile, start_record, end_record, out_path):
    """Build a stream-copy FFmpeg command for Record Video."""
    ext = os.path.splitext(out_path)[1].lower().lstrip(".")
    args = [
        "-y",
        "-i",
        infile,
        "-ss",
        start_record,
        "-to",
        end_record,
        "-c",
        "copy",
    ]
    if ext in RAW_VIDEO_EXTENSIONS:
        # Raw elementary streams cannot carry audio or KLV metadata tracks.
        args.extend(["-map", "0:v:0", "-an", "-sn", "-dn"])
    else:
        args.extend(["-map", "0", "-avoid_negative_ts", "make_zero"])
        if ext in ("ts", "mts", "m2ts", "mpg", "mpeg"):
            args.extend(["-f", "mpegts"])
    args.append(out_path)
    return args


def ResetData(group_name=None):
    """Reset layer feature caches and active session telemetry fields."""
    from QGISFMV.utils.layers.QgsFmvLayers import resetLayerCaches

    SetcrtSensorSrc()
    SetcrtPltTailNum()
    resetLayerCaches(group_name)
    session = get_active_session()
    if session is not None:
        session.reset_telemetry()


_last_canvas_refresh = 0.0
CANVAS_REFRESH_MIN_INTERVAL = 0.25


def UpdateLayers(packet, parent=None, mosaic=False, group=None):
    """Update Layers Values"""
    global gv
    if gv is None:
        return False
    if parent is not None:
        _syncVideoImageSizeFromParent(parent)
    gv.setGroupName(group)
    groupName = group
    # Keep layer helpers and map-centering on the same video group.
    if group is not None:
        import QGISFMV.utils.layers.QgsFmvLayers as _layers

        _layers.groupName = group
    geometry_ok = False
    gv.setFrameCenterElevation(packet.FrameCenterElevation)
    gv.setSensorLatitude(packet.SensorLatitude)
    gv.setSensorLongitude(packet.SensorLongitude)

    sensorTrueAltitude = packet.SensorTrueAltitude
    gv.setSensorTrueAltitude(sensorTrueAltitude)
    sensorRelativeElevationAngle = packet.SensorRelativeElevationAngle
    slantRange = packet.SlantRange
    OffsetLat1 = packet.OffsetCornerLatitudePoint1
    LatitudePoint1Full = packet.CornerLatitudePoint1Full

    UpdatePlatformData(packet, hasElevationModel())
    UpdateTrajectoryData(packet, hasElevationModel())

    frameCenterPoint = [
        packet.FrameCenterLatitude,
        packet.FrameCenterLongitude,
        packet.FrameCenterElevation,
    ]

    # Incomplete frame center (either axis null) — skip footprint/GCP math.
    if frameCenterPoint[0] is None or frameCenterPoint[1] is None:
        gv.setTransform(None)
        return True

    # No framecenter altitude
    if frameCenterPoint[2] is None:
        if (
            sensorRelativeElevationAngle is not None
            and slantRange is not None
            and sensorTrueAltitude is not None
        ):
            frameCenterPoint[2] = (
                sensorTrueAltitude
                - sin(radians(sensorRelativeElevationAngle)) * slantRange
            )
        else:
            frameCenterPoint[2] = 0.0

    if not _footprint_inputs_changed(packet) and _affineTransformIsUsable(
        gv.getAffineTransform()
    ):
        geometry_ok = True
    elif OffsetLat1 is not None and LatitudePoint1Full is None:
        if hasElevationModel():
            frameCenterPoint = GetLine3DIntersectionWithDEM(
                GetSensor(), frameCenterPoint
            )

        geometry_ok = CornerEstimationWithOffsets(packet)

    elif OffsetLat1 is None and LatitudePoint1Full is None:
        if hasElevationModel():
            frameCenterPoint = GetLine3DIntersectionWithDEM(
                GetSensor(), frameCenterPoint
            )

        geometry_ok = CornerEstimationWithoutOffsets(packet)

    else:
        cornerPointUL = [
            packet.CornerLatitudePoint1Full,
            packet.CornerLongitudePoint1Full,
        ]
        if None in cornerPointUL:
            return False

        cornerPointUR = [
            packet.CornerLatitudePoint2Full,
            packet.CornerLongitudePoint2Full,
        ]
        if None in cornerPointUR:
            return False

        cornerPointLR = [
            packet.CornerLatitudePoint3Full,
            packet.CornerLongitudePoint3Full,
        ]

        if None in cornerPointLR:
            return False

        cornerPointLL = [
            packet.CornerLatitudePoint4Full,
            packet.CornerLongitudePoint4Full,
        ]

        if None in cornerPointLL:
            return False

        _update_footprint_beams_gcp(
            packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL,
            frameCenterPoint, hasElevationModel(),
        )
        geometry_ok = True

    UpdateFrameCenterData(frameCenterPoint, hasElevationModel())
    UpdateFrameAxisData(
        packet.ImageSourceSensor, GetSensor(), frameCenterPoint, hasElevationModel()
    )

    if mosaic and geometry_ok and parent is not None:
        georeferencingVideo(parent)

    # Follow map center when a center-on action is checked in the player.
    iface = gv.getIface()
    centerMode = gv.getCenterMode()
    recentered = followMapCenter(iface, centerMode, groupName)

    if iface is not None:
        global _last_canvas_refresh
        now = time.monotonic()
        if recentered or now - _last_canvas_refresh >= CANVAS_REFRESH_MIN_INTERVAL:
            iface.mapCanvas().refresh()
            _last_canvas_refresh = now

    return True


# Mosaic tuning constants (refreshed by QgsFmvSettings._apply_mosaic_settings)
MOSAIC_MIN_INTERVAL_SEC = 2.0
MOSAIC_MIN_MOVE_METERS = 30.0
MOSAIC_MAX_FRAME_DIMENSION = 960
MOSAIC_FEATHER_PX = 56
MOSAIC_MAX_OUTPUT_SIZE = 2048
MOSAIC_MAX_KEPT_FRAMES = 80
MOSAIC_FOOTPRINT_GROW_RATIO = 1.12
MOSAIC_FOOTPRINT_GROW_METERS = 35.0


def _time_to_seconds(dateStr):
    """Convert time string HH:MM:SS.ffffff to seconds"""
    timeval = datetime.strptime(dateStr, "%H:%M:%S.%f")
    return (
        timeval.hour * 3600
        + timeval.minute * 60
        + timeval.second
        + timeval.microsecond / 1e6
    )


def _seconds_to_time(sec):
    """Convert seconds to HH:MM:SS string"""
    hours, remainder = divmod(int(sec), 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)


def BurnDrawingsImage(source, overlay):
    """Burn drawings into image.

    Operates directly at the source resolution to avoid two
    scale passes.  The overlay is drawn scaled-to-fit in one shot.
    """
    if source is None or source.isNull():
        return overlay
    if overlay is None or overlay.isNull():
        return source

    # Composite at source resolution — no intermediate scale.
    result = source.copy()
    p = QPainter()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.begin(result)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    p.drawImage(result.rect(), overlay)
    p.end()
    return result


try:
    from QGISFMV.utils.settings.QgsFmvSettings import _apply_mosaic_settings

    _apply_mosaic_settings(__import__(__name__))
except Exception as e:
    from QGISFMV.utils.logging import log
    log.debug("Mosaic settings import failed (non-critical): %s", e)
