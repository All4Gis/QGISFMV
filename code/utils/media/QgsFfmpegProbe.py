# -*- coding: utf-8 -*-
"""Lightweight ffprobe/ffmpeg helpers (replaces legacy converter/ package)."""

import json
import os
import re
import subprocess

from qgis.PyQt.QtCore import QCoreApplication

from QGISFMV.utils.core.QgsFmvUtils import _spawn
from QGISFMV.utils.logging import log

_TIME_RE = re.compile(r"time=([0-9.:]+) ")


def probe_json(path, timeout_sec=None):
    """Return ffprobe JSON output as bytes, or None on failure."""
    from QGISFMV.utils.media.QgsFmvStreamUtils import isStreamUri

    if not path:
        return None
    if not isStreamUri(path) and not os.path.exists(path):
        return None

    is_stream = isStreamUri(path)
    args = [
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
    ]
    if is_stream:
        args.extend(["-analyzeduration", "2000000", "-probesize", "1000000"])
    elif os.path.splitext(path)[1].lower() in (".ts", ".mts", ".m2ts", ".mpeg", ".mpg"):
        args.extend(["-analyzeduration", "10000000", "-probesize", "10000000"])
    args.append(path)

    proc = _spawn(args, t="probe")
    try:
        communicate_timeout = timeout_sec if timeout_sec else (3.0 if is_stream else None)
        out, _ = proc.communicate(timeout=communicate_timeout)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception as kill_exc:
            log.debug("ffprobe kill after timeout failed: %s", kill_exc)
        return None
    except Exception as exc:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception as kill_exc:
            log.debug("ffprobe kill after error failed: %s", kill_exc)
        log.debug("ffprobe failed for %s: %s", path, exc)
        return None
    if proc.returncode != 0 or not out:
        return None
    return out


def is_valid_stream(uri, timeout_sec=3.0):
    """Return True when ffprobe finds a video/audio stream on a live URI."""
    from QGISFMV.utils.media.QgsFmvStreamUtils import isStreamUri

    if not isStreamUri(uri):
        return False
    data = probe_json(uri)
    if data:
        try:
            info = json.loads(data.decode("utf-8", errors="replace"))
            for stream in info.get("streams") or []:
                if stream.get("codec_type") in ("video", "audio"):
                    return True
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    # ffprobe on UDP can fail even when ffmpeg can decode — try decoding one frame.
    try:
        import cv2

        cap = cv2.VideoCapture(uri, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(uri)
        try:
            ok, frame = cap.read()
            return bool(ok and frame is not None)
        finally:
            cap.release()
    except Exception as exc:
        log.debug("OpenCV stream validation failed for %s: %s", uri, exc)

    # Fallback: try ffmpeg subprocess to decode a single frame
    try:
        from QGISFMV.utils.media.QgsFfmpegRunner import available, popen_ffmpeg

        if not available():
            return False

        proc = popen_ffmpeg(
            [
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                uri,
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                "-",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = proc.communicate(timeout=timeout_sec + 2)
        return len(out) > 0
    except Exception as _exc:
        log.debug("ffmpeg stream decode validation failed for %s: %s", uri, _exc)
        return False


def probe_json_to_file(path, output_path):
    """Write ffprobe JSON for a media file."""
    data = probe_json(path)
    if data is None:
        raise OSError("ffprobe failed for " + str(path))
    with open(output_path, "wb") as fh:
        fh.write(data)


def is_valid_media(path):
    """Return True when ffprobe finds at least one audio or video stream."""
    data = probe_json(path)
    if not data:
        return False
    try:
        info = json.loads(data.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    for stream in info.get("streams") or []:
        if stream.get("codec_type") in ("video", "audio"):
            return True
    return False


def _parse_timecode(value):
    if ":" in value:
        seconds = 0.0
        for part in value.split(":"):
            seconds = 60 * seconds + float(part)
        return seconds
    return float(value)


def _media_duration(path):
    data = probe_json(path)
    if not data:
        return 0.0
    try:
        info = json.loads(data.decode("utf-8", errors="replace"))
        return float(info.get("format", {}).get("duration") or 0.0)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError, ValueError):
        return 0.0


def _run_ffmpeg(cmds, task, duration=0.0):
    """Run ffmpeg and update task progress from stderr timecodes."""
    proc = _spawn(cmds)
    try:
        proc.stdin.close()
        buf = ""
        while True:
            if task.isCanceled():
                proc.kill()
                return False

            chunk = proc.stderr.read(256)
            if not chunk:
                break

            buf += chunk.decode("utf-8", errors="replace")
            if "\r" in buf:
                line, buf = buf.split("\r", 1)
                matches = _TIME_RE.findall(line)
                if matches and duration > 0.01:
                    task.setProgress(int(100.0 * _parse_timecode(matches[-1]) / duration))

        proc.stdout.close()
        proc.stderr.close()
    finally:
        proc.wait()
    return proc.returncode == 0


def convert_video(task, infile, outfile):
    """Remux to another container; re-encode only if stream copy fails."""
    if task.isCanceled() or not os.path.exists(infile):
        return None

    duration = _media_duration(infile)
    copy_cmds = ["-i", infile, "-map", "0", "-c", "copy", "-y", outfile]
    if _run_ffmpeg(copy_cmds, task, duration):
        task.setProgress(100)
        return {"task": task.description()}

    if task.isCanceled():
        return None

    encode_cmds = [
        "-i",
        infile,
        "-map",
        "0",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-y",
        outfile,
    ]
    if _run_ffmpeg(encode_cmds, task, duration):
        task.setProgress(100)
        return {"task": task.description()}
    return None


def save_probe_json_task(task, fname, output):
    """QgsTask helper: save ffprobe JSON."""
    try:
        if task.isCanceled():
            return None
        probe_json_to_file(fname, output)
        return {"task": task.description()}
    except Exception as exc:
        return {"task": task.description(), "error": str(exc)}


def show_probe_json_task(task, fname):
    """QgsTask helper: load ffprobe JSON for the info dialog."""
    try:
        if task.isCanceled():
            return None
        data = probe_json(fname)
        if data is None:
            return {
                "task": task.description(),
                "error": QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Could not read video information. Check ffprobe in settings.ini.",
                ),
            }
        return {"task": task.description(), "json": data}
    except Exception as exc:
        return {"task": task.description(), "error": str(exc)}
