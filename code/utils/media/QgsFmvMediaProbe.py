# -*- coding: utf-8 -*-
"""Path / duration / stream-info helpers for FMV media backends."""

import json
import os
import re
import subprocess

from qgis.PyQt.QtCore import QUrl

from QGISFMV.utils.logging import log


def url_to_path(url):
    """Convert a QUrl or string to a local file path."""
    if isinstance(url, QUrl):
        path = url.toLocalFile()
        if path:
            return path
        return url.toString()
    return str(url)


# Private alias kept for callers that still use the underscore name.
_url_to_path = url_to_path


def probeDurationMs(path):
    """Return duration in milliseconds using ffprobe when OpenCV cannot."""
    try:
        from QGISFMV.utils.media.QgsFfmpegProbe import probe_json

        data = probe_json(path)
        if not data:
            return 0
        info = json.loads(data.decode("utf-8", errors="replace"))
        durationSec = float(info.get("format", {}).get("duration") or 0.0)
        if durationSec > 0:
            return int(durationSec * 1000)
    except Exception as exc:
        log.debug("ffprobe duration lookup failed: %s", exc)
    return 0


_probeDurationMs = probeDurationMs


def parse_fps(rate):
    """Parse ffprobe ``N/D`` or float FPS strings; default ``25.0`` on failure."""
    if not rate:
        return 25.0
    if isinstance(rate, (int, float)):
        return max(0.01, float(rate))
    text = str(rate)
    if "/" in text:
        num, den = text.split("/", 1)
        den = float(den) or 1.0
        return max(0.01, float(num) / den)
    try:
        return max(0.01, float(text))
    except (TypeError, ValueError):
        return 25.0


_parse_fps = parse_fps


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", re.IGNORECASE)
_SIZE_RE = re.compile(r"Video:\s[^\n]*?\s(\d{2,5})x(\d{2,5})", re.IGNORECASE)
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps", re.IGNORECASE)


def durationMsFromText(text):
    """Extract media duration in milliseconds from ffmpeg/ffprobe stderr text."""
    match = _DURATION_RE.search(text or "")
    if not match:
        return 0
    hours, minutes, seconds = match.groups()
    total = (int(hours) * 3600.0) + (int(minutes) * 60.0) + float(seconds)
    return int(total * 1000)


_durationMsFromText = durationMsFromText


def probe_video_info_from_stderr(path):
    """Fallback probe using ``ffmpeg -i`` stderr (works on difficult MPEG-TS)."""
    try:
        from QGISFMV.utils.media.QgsFfmpegRunner import available, popen_ffmpeg

        if not available():
            return None
        proc = popen_ffmpeg(
            ["-hide_banner", "-i", path],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        err = proc.communicate(timeout=15)[1].decode("utf-8", errors="replace")
        size_match = _SIZE_RE.search(err)
        if not size_match:
            return None
        width = int(size_match.group(1))
        height = int(size_match.group(2))
        if width <= 0 or height <= 0:
            return None
        fps_match = _FPS_RE.search(err)
        fps = float(fps_match.group(1)) if fps_match else 25.0
        return {
            "width": width,
            "height": height,
            "fps": max(0.01, fps),
            "durationMs": durationMsFromText(err),
        }
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        log.debug("ffmpeg stderr probe failed: %s", exc)
        return None


_probe_video_info_from_stderr = probe_video_info_from_stderr


def read_bytes(stream, nbytes):
    """Read up to *nbytes* from a binary stream (short-read safe)."""
    buf = bytearray()
    while len(buf) < nbytes:
        chunk = stream.read(nbytes - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


_read_bytes = read_bytes


def probe_video_info(path):
    """Return width/height/fps/duration for the first video stream."""
    try:
        from QGISFMV.utils.media.QgsFfmpegProbe import probe_json

        data = probe_json(path)
        if data:
            info = json.loads(data.decode("utf-8", errors="replace"))
            video = None
            for stream in info.get("streams") or []:
                if stream.get("codec_type") == "video":
                    video = stream
                    break
            if video:
                width = int(video.get("width") or 0)
                height = int(video.get("height") or 0)
                if width > 0 and height > 0:
                    fps = parse_fps(
                        video.get("avg_frame_rate") or video.get("r_frame_rate")
                    )
                    durationMs = probeDurationMs(path)
                    return {
                        "width": width,
                        "height": height,
                        "fps": fps,
                        "durationMs": durationMs,
                    }
    except Exception as exc:
        log.debug("ffprobe video info failed, trying stderr probe: %s", exc)
    return probe_video_info_from_stderr(path)


_probe_video_info = probe_video_info


def ffmpeg_available():
    """Return True when a usable ffmpeg binary is configured."""
    from QGISFMV.utils.media.QgsFfmpegRunner import available

    return available()


_ffmpeg_available = ffmpeg_available


def ffmpeg_popen(args):
    """Spawn ffmpeg with *args* via the shared runner."""
    from QGISFMV.utils.media.QgsFfmpegRunner import popen_ffmpeg

    return popen_ffmpeg(args)


_ffmpeg_popen = ffmpeg_popen


def validateMediaPath(path):
    """Return an error string if *path* is not a usable media file, else None."""
    if not path:
        return "File not found"
    is_stream = "://" in path
    if not is_stream and not os.path.isfile(path):
        return "File not found"
    return None


_validateMediaPath = validateMediaPath
