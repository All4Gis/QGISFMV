# -*- coding: utf-8 -*-
"""
Video playback for QGIS FMV.

Uses OpenCV when available, otherwise FFmpeg (same codecs as Windows, no LAV
Filters on macOS). Qt ``QMediaPlayer`` is only a last resort for simple formats.
"""

import json
import os
import platform
import re
import subprocess
import time
from enum import IntEnum

from qgis.PyQt.QtCore import QObject, QTimer, QUrl, QThread, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QImage

from QGISFMV.utils.logging import log

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from qgis.PyQt.QtMultimedia import QMediaPlayer, QAudioOutput

    _HAS_QT_MEDIA = True
except ImportError:
    QMediaPlayer = None
    QAudioOutput = None
    _HAS_QT_MEDIA = False


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PlaybackState(IntEnum):
    """Media playback state constants."""
    Stopped = 0
    Playing = 1
    Paused = 2


class MediaStatus(IntEnum):
    """Media source status constants."""
    NoMedia = 0
    Loading = 1
    Loaded = 2
    Buffering = 3
    Buffered = 4
    Stalled = 5
    Invalid = 6
    EndOfMedia = 7


class PlaylistMode(IntEnum):
    """Playlist playback mode constants."""
    Sequential = 0
    Loop = 1


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _url_to_path(url):
    """Convert a QUrl or string to a local file path."""
    if isinstance(url, QUrl):
        path = url.toLocalFile()
        if path:
            return path
        return url.toString()
    return str(url)


def _probeDurationMs(path):
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


def _parse_fps(rate):
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


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", re.IGNORECASE)
_SIZE_RE = re.compile(r"Video:\s[^\n]*?\s(\d{2,5})x(\d{2,5})", re.IGNORECASE)
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps", re.IGNORECASE)


def _durationMsFromText(text):
    match = _DURATION_RE.search(text or "")
    if not match:
        return 0
    hours, minutes, seconds = match.groups()
    total = (int(hours) * 3600.0) + (int(minutes) * 60.0) + float(seconds)
    return int(total * 1000)


def _probe_video_info_from_stderr(path):
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
            "durationMs": _durationMsFromText(err),
        }
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        log.debug("ffmpeg stderr probe failed: %s", exc)
        return None


def _read_bytes(stream, nbytes):
    buf = bytearray()
    while len(buf) < nbytes:
        chunk = stream.read(nbytes - len(buf))
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


def _probe_video_info(path):
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
                    fps = _parse_fps(
                        video.get("avg_frame_rate") or video.get("r_frame_rate")
                    )
                    durationMs = _probeDurationMs(path)
                    return {
                        "width": width,
                        "height": height,
                        "fps": fps,
                        "durationMs": durationMs,
                    }
    except Exception as exc:
        log.debug("ffprobe video info failed, trying stderr probe: %s", exc)
    return _probe_video_info_from_stderr(path)


def _ffmpeg_available():
    from QGISFMV.utils.media.QgsFfmpegRunner import available

    return available()


def _ffmpeg_popen(args):
    from QGISFMV.utils.media.QgsFfmpegRunner import popen_ffmpeg

    return popen_ffmpeg(args)


def _validateMediaPath(path):
    """Return an error string if *path* is not a usable media file, else None."""
    if not path:
        return "File not found"
    is_stream = "://" in path
    if not is_stream and not os.path.isfile(path):
        return "File not found"
    return None


# ---------------------------------------------------------------------------
# Decode workers
# ---------------------------------------------------------------------------

class _FrameDecodeWorker(QObject):
    """OpenCV VideoCapture decode worker running on a background thread."""

    frameReady = pyqtSignal(int, object)
    openFinished = pyqtSignal(object)
    openPathRequested = pyqtSignal(str, int)
    decodeRequested = pyqtSignal(int)
    decodeNextRequested = pyqtSignal()
    releaseRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._cap = None
        self._fps = 25.0
        self._durationMs = 0
        self._isStream = False
        self.openPathRequested.connect(self._openPath)
        self.decodeRequested.connect(self._decodeAt)
        self.decodeNextRequested.connect(self._decodeNext)
        self.releaseRequested.connect(self._releaseCapture)

    def _frameToQImage(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width, channels = rgb.shape
            return QImage(
                rgb.data, width, height, channels * width, QImage.Format.Format_RGB888
            ).copy()
        except Exception as _exc:
            log.debug("frame BGR to RGB conversion failed: %s", _exc)
            return None

    def _positionMsFromCapture(self, frameIdx=None):
        if self._cap is None or cv2 is None:
            return 0
        posMsec = float(self._cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0)
        if posMsec > 0.0:
            return int(posMsec)
        if frameIdx is None:
            frameIdx = max(
                0.0, float(self._cap.get(cv2.CAP_PROP_POS_FRAMES) or 0.0) - 1.0
            )
        return int((frameIdx / self._fps) * 1000)

    def _probeOpenCvPath(self, path):
        """Try opening *path* with OpenCV, returning an opened VideoCapture or None."""
        cap = cv2.VideoCapture(path, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return None
        return cap

    @pyqtSlot(str, int)
    def _openPath(self, path, generation):
        self._releaseCapture()
        result = {
            "generation": generation,
            "path": path,
            "ok": False,
            "error": "",
            "fps": 25.0,
            "durationMs": 0,
            "isStream": False,
        }
        if cv2 is None:
            result["error"] = "Native video decoder is not installed"
            self.openFinished.emit(result)
            return

        error = _validateMediaPath(path)
        if error:
            result["error"] = error
            self.openFinished.emit(result)
            return

        cap = self._probeOpenCvPath(path)
        if cap is None:
            result["error"] = "Cannot open video"
            self.openFinished.emit(result)
            return

        is_stream = "://" in (path or "")
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0.01:
            fps = 25.0
        frameCount = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        durationMs = 0 if is_stream else int((frameCount / fps) * 1000)
        if durationMs <= 0 and not is_stream:
            durationMs = _probeDurationMs(path)

        self._cap = cap
        self._fps = max(0.01, fps)
        self._durationMs = max(0, int(durationMs))
        self._isStream = bool(is_stream)
        result.update(
            {
                "ok": True,
                "fps": self._fps,
                "durationMs": self._durationMs,
                "isStream": is_stream,
            }
        )
        self.openFinished.emit(result)

    @pyqtSlot()
    def _decodeNext(self):
        """Read the next frame sequentially (reliable during playback)."""
        if self._cap is None or cv2 is None:
            return
        try:
            ok, frame = self._cap.read()
            if self._isStream and ok and frame is not None:
                while True:
                    ok2, newer = self._cap.read()
                    if not ok2 or newer is None:
                        break
                    frame = newer
                    ok = ok2
        except Exception as _exc:
            log.debug("sequential frame read failed: %s", _exc)
            self.frameReady.emit(-1, None)
            return
        if not ok or frame is None:
            self.frameReady.emit(-1, None)
            return
        qimg = self._frameToQImage(frame)
        if qimg is None:
            self.frameReady.emit(-1, None)
            return
        self.frameReady.emit(self._positionMsFromCapture(), qimg)

    @pyqtSlot(int)
    def _decodeAt(self, ms):
        if self._cap is None or cv2 is None:
            return
        if self._durationMs > 0:
            ms = max(0, min(int(ms), self._durationMs))
        else:
            ms = max(0, int(ms))

        ok = False
        frame = None
        try:
            self._cap.set(cv2.CAP_PROP_POS_MSEC, ms)
            ok, frame = self._cap.read()
        except Exception as _exc:
            log.debug("frame seek decode failed at %sms: %s", ms, _exc)
            ok = False
            frame = None

        if not ok or frame is None:
            frameIdx = max(0, int(round((ms / 1000.0) * self._fps)))
            try:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, frameIdx)
                ok, frame = self._cap.read()
            except Exception as _exc:
                log.debug("fallback frame seek failed: %s", _exc)
                self.frameReady.emit(ms, None)
                return

        if not ok or frame is None:
            self.frameReady.emit(ms, None)
            return

        qimg = self._frameToQImage(frame)
        if qimg is None:
            self.frameReady.emit(ms, None)
            return
        self.frameReady.emit(self._positionMsFromCapture(), qimg)

    @pyqtSlot()
    def _releaseCapture(self):
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception as exc:
                log.debug("OpenCV capture release failed: %s", exc)
            self._cap = None
        self._isStream = False


class _FfmpegDecodeWorker(QObject):
    """FFmpeg subprocess decode worker running on a background thread."""

    frameReady = pyqtSignal(int, object)
    openFinished = pyqtSignal(object)
    openPathRequested = pyqtSignal(str, int)
    decodeRequested = pyqtSignal(int)
    decodeNextRequested = pyqtSignal()
    releaseRequested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._path = None
        self._proc = None
        self._width = 0
        self._height = 0
        self._frameBytes = 0
        self._fps = 25.0
        self._durationMs = 0
        self._isStream = False
        self._frameIndex = 0
        self._mapSpec = "v:0"
        self.openPathRequested.connect(self._openPath)
        self.decodeRequested.connect(self._decodeAt)
        self.decodeNextRequested.connect(self._decodeNext)
        self.releaseRequested.connect(self._releasePipe)

    def _releasePipe(self):
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
        except Exception as exc:
            log.debug("FFmpeg pipe release failed: %s", exc)

    def _rawArgs(self, seekMs=None, singleFrame=False):
        args = ["-nostdin", "-loglevel", "error"]
        if self._isStream:
            args.extend(["-fflags", "nobuffer", "-flags", "low_delay"])
        if singleFrame and not self._isStream:
            args.extend(["-i", self._path])
            if seekMs is not None and seekMs > 0:
                args.extend(["-ss", f"{seekMs / 1000.0:.6f}"])
        else:
            if seekMs is not None and seekMs > 0 and not self._isStream:
                args.extend(["-ss", f"{seekMs / 1000.0:.6f}"])
            args.extend(["-i", self._path])
        args.extend(["-an", "-sn", "-map", self._mapSpec])
        if singleFrame:
            args.extend(["-frames:v", "1"])
        args.extend(["-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"])
        return args

    def _readFrame(self, proc):
        if self._frameBytes <= 0 or proc.stdout is None:
            return None
        data = _read_bytes(proc.stdout, self._frameBytes)
        if len(data) != self._frameBytes:
            return None
        return QImage(
            data,
            self._width,
            self._height,
            self._width * 3,
            QImage.Format.Format_RGB888,
        ).copy()

    def _probeFfmpegPath(self):
        """Try decoding a probe frame with several map specs.  Return True on success."""
        for map_spec in ("v:0", "0:v:0", "0:v"):
            self._mapSpec = map_spec
            proc = None
            try:
                proc = _ffmpeg_popen(self._rawArgs(seekMs=0, singleFrame=True))
                if self._readFrame(proc) is not None:
                    return True
            except Exception as exc:
                log.debug("FFmpeg probe frame with map %s failed: %s", map_spec, exc)
            finally:
                if proc is not None:
                    try:
                        if proc.poll() is None:
                            proc.kill()
                            proc.wait(timeout=2)
                    except Exception as kill_exc:
                        log.debug("FFmpeg probe process cleanup failed: %s", kill_exc)
        return False

    @pyqtSlot(str, int)
    def _openPath(self, path, generation):
        self._releasePipe()
        result = {
            "generation": generation,
            "path": path,
            "ok": False,
            "error": "",
            "fps": 25.0,
            "durationMs": 0,
            "isStream": False,
        }
        error = _validateMediaPath(path)
        if error:
            result["error"] = error
            self.openFinished.emit(result)
            return
        if not _ffmpeg_available():
            result["error"] = "FFmpeg is not configured"
            self.openFinished.emit(result)
            return

        info = _probe_video_info(path)
        if not info:
            result["error"] = "Cannot open video (FFmpeg probe failed)"
            self.openFinished.emit(result)
            return

        log.info(
            "FFmpeg video probe: %sx%s @ %.2f fps, %s ms",
            info["width"],
            info["height"],
            info["fps"],
            info["durationMs"],
        )

        self._path = path
        self._width = info["width"]
        self._height = info["height"]
        self._frameBytes = self._width * self._height * 3
        self._fps = max(0.01, info["fps"])
        self._durationMs = max(0, int(info["durationMs"]))
        self._isStream = bool("://" in (path or ""))
        self._frameIndex = 0

        if not self._probeFfmpegPath():
            result["error"] = "Cannot decode video frames"
            self.openFinished.emit(result)
            return

        result.update(
            {
                "ok": True,
                "fps": self._fps,
                "durationMs": self._durationMs,
                "isStream": self._isStream,
            }
        )
        self.openFinished.emit(result)

    @pyqtSlot(int)
    def _decodeAt(self, ms):
        self._releasePipe()
        if not self._path:
            return
        if self._durationMs > 0:
            ms = max(0, min(int(ms), self._durationMs))
        else:
            ms = max(0, int(ms))

        qimg = None
        proc = None
        try:
            proc = _ffmpeg_popen(self._rawArgs(seekMs=ms, singleFrame=True))
            qimg = self._readFrame(proc)
            if proc.poll() is None:
                proc.wait(timeout=30)
        except Exception as exc:
            log.debug("FFmpeg seek decode failed at %sms: %s", ms, exc)
            qimg = None
        finally:
            if proc is not None and proc is not self._proc:
                try:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=2)
                except Exception as kill_exc:
                    log.debug("FFmpeg seek process cleanup failed: %s", kill_exc)

        self._frameIndex = max(0, int(round((ms / 1000.0) * self._fps)))
        if qimg is None:
            self.frameReady.emit(ms, None)
            return
        pos = int((self._frameIndex / self._fps) * 1000)
        self.frameReady.emit(pos, qimg)

    @pyqtSlot()
    def _decodeNext(self):
        if not self._path:
            return
        if self._proc is None or self._proc.poll() is not None:
            seekMs = 0 if self._isStream else int((self._frameIndex / self._fps) * 1000)
            try:
                self._proc = _ffmpeg_popen(
                    self._rawArgs(seekMs=seekMs, singleFrame=False)
                )
            except Exception as _exc:
                log.debug("FFmpeg continuous decode popen failed: %s", _exc)
                self.frameReady.emit(-1, None)
                return

        try:
            qimg = self._readFrame(self._proc)
        except Exception as _exc:
            log.debug("FFmpeg continuous frame read failed: %s", _exc)
            qimg = None
        if qimg is None:
            self._releasePipe()
            self.frameReady.emit(-1, None)
            return

        self._frameIndex += 1
        if self._isStream:
            pos = -1
        else:
            pos = int((self._frameIndex / self._fps) * 1000)
        self.frameReady.emit(pos, qimg)


# ---------------------------------------------------------------------------
# Backward-compatible aliases (used by OpenCvMediaPlayer, FmvPlaylist, etc.)
# ---------------------------------------------------------------------------

PlayingState = PlaybackState.Playing
PausedState = PlaybackState.Paused
StoppedState = PlaybackState.Stopped

NoMedia = MediaStatus.NoMedia
LoadingMedia = MediaStatus.Loading
LoadedMedia = MediaStatus.Loaded
BufferingMedia = MediaStatus.Buffering
BufferedMedia = MediaStatus.Buffered
StalledMedia = MediaStatus.Stalled
InvalidMedia = MediaStatus.Invalid
EndOfMedia = MediaStatus.EndOfMedia

# ---------------------------------------------------------------------------
# Player backends
# ---------------------------------------------------------------------------

class OpenCvMediaPlayer(QObject):
    """QMediaPlayer-compatible player using OpenCV VideoCapture or FFmpeg pipe."""

    durationChanged = pyqtSignal(int)
    positionChanged = pyqtSignal(int)
    frameDisplayed = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(int)
    playbackRateChanged = pyqtSignal(float)
    playbackLooped = pyqtSignal()

    def __init__(self, parent=None, decode_worker_factory=None):
        super().__init__(parent)
        self._path = None
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._onTick)
        self._positionMs = 0
        self._durationMs = 0
        self._fps = 25.0
        self._rate = 1.0
        self._state = StoppedState
        self._status = NoMedia
        self._videoWidget = None
        self._muted = False
        self._loops = 1
        self._error = ""
        self._lastNotifyMs = 0
        self._openGeneration = 0
        self._hasCapture = False
        self._forceNotifyNext = False
        self._autoPlayWhenReady = False
        self._decodeBusy = False
        self._pendingSeekMs = None
        self._isStream = False
        self._playStartMono = None
        self._streamFrameCount = 0
        self._ffmpegBackend = decode_worker_factory is _FfmpegDecodeWorker

        self._openTimeout = QTimer(self)
        self._openTimeout.setSingleShot(True)
        self._openTimeout.timeout.connect(self._onOpenTimeout)

        # Unparented: parented QThreads abort Qt if still running when destroyed.
        self._decodeThread = QThread()
        worker_factory = decode_worker_factory or _FrameDecodeWorker
        self._decodeWorker = worker_factory()
        self._decodeWorker.moveToThread(self._decodeThread)
        self._decodeWorker.frameReady.connect(self._onFrameReady)
        self._decodeWorker.openFinished.connect(self._onOpenFinished)
        self._decodeThread.start()

    def setVideoWidget(self, videoWidget):
        """Set the video output widget for frame rendering."""
        self._videoWidget = videoWidget

    def setAutoPlayWhenReady(self, enabled=True):
        """Enable auto-play once the media source is ready."""
        self._autoPlayWhenReady = bool(enabled)

    def _closeCapture(self):
        self._timer.stop()
        self._openTimeout.stop()
        self._decodeWorker.releaseRequested.emit()
        self._hasCapture = False
        self._decodeBusy = False
        self._pendingSeekMs = None
        self._openGeneration += 1

    def shutdown(self):
        """Stop the decode thread cleanly before the player is destroyed."""
        from QGISFMV.utils.core.QgsFmvThreads import stop_qthread

        self._timer.stop()
        self._openTimeout.stop()
        # Ask the worker to drop capture/ffmpeg, then stop its event loop.
        try:
            self._decodeWorker.releaseRequested.emit()
        except Exception as exc:
            from QGISFMV.utils.logging import log
            log.debug("decodeWorker releaseRequested emit failed: %s", exc)
        thread = self._decodeThread
        self._decodeThread = None
        self._hasCapture = False
        self._decodeBusy = False
        stop_qthread(thread)

    def setSource(self, url):
        """Set the media source URL and prepare for playback."""
        self._closeCapture()
        self._error = ""
        path = _url_to_path(url)
        is_stream = path and "://" in path
        if not path or (not is_stream and not os.path.isfile(path)):
            self._status = InvalidMedia
            self._error = "File not found"
            self.mediaStatusChanged.emit(self._status)
            return

        if cv2 is None and not self._ffmpegBackend:
            self._status = InvalidMedia
            self._error = "Native video decoder is not installed"
            self.mediaStatusChanged.emit(self._status)
            return

        if cv2 is None and not _ffmpeg_available():
            self._status = InvalidMedia
            self._error = "FFmpeg is not configured"
            self.mediaStatusChanged.emit(self._status)
            return

        self._status = LoadingMedia
        self.mediaStatusChanged.emit(self._status)
        self._path = path
        self._isStream = bool(is_stream)
        self._openGeneration += 1
        generation = self._openGeneration
        if self._ffmpegBackend:
            self._openTimeout.start(90000)
        self._decodeWorker.openPathRequested.emit(path, generation)

    def _onOpenTimeout(self):
        if self._status != LoadingMedia:
            return
        self._status = InvalidMedia
        self._error = "Video open timed out (FFmpeg)"
        self._autoPlayWhenReady = False
        self._hasCapture = False
        self._openTimeout.stop()
        self.mediaStatusChanged.emit(self._status)

    def _onOpenFinished(self, result):
        self._openTimeout.stop()
        if result.get("generation") != self._openGeneration:
            return

        if not result.get("ok"):
            self._status = InvalidMedia
            self._error = result.get("error") or "Cannot open video"
            self._autoPlayWhenReady = False
            self.mediaStatusChanged.emit(self._status)
            return

        self._fps = result["fps"]
        self._durationMs = result["durationMs"]
        self._isStream = bool(result.get("isStream"))
        self._positionMs = 0
        self._lastNotifyMs = 0
        self._state = StoppedState
        self._status = LoadedMedia
        self._hasCapture = True
        self.mediaStatusChanged.emit(self._status)
        self.durationChanged.emit(self._durationMs)
        self._showFrameAt(0, forceNotify=True)
        if self._autoPlayWhenReady:
            self._autoPlayWhenReady = False
            self.play()

    def _showFrameAt(self, ms, forceNotify=False):
        if self._decodeBusy:
            self._pendingSeekMs = int(ms)
            if forceNotify:
                self._forceNotifyNext = True
            return
        self._decodeBusy = True
        self._forceNotifyNext = forceNotify or self._forceNotifyNext
        self._decodeWorker.decodeRequested.emit(int(ms))

    def _requestNextFrame(self):
        if self._decodeBusy:
            return
        self._decodeBusy = True
        self._decodeWorker.decodeNextRequested.emit()

    def _onFrameReady(self, positionMs, qimg):
        self._decodeBusy = False

        if qimg is None:
            if positionMs < 0 and self._state == PlayingState:
                self._timer.stop()
                self._state = PausedState
                self._status = EndOfMedia
                self.playbackStateChanged.emit(self._state)
                self.mediaStatusChanged.emit(self._status)
            pending = self._pendingSeekMs
            self._pendingSeekMs = None
            if pending is not None:
                self._showFrameAt(pending)
            return

        if (
            qimg is not None
            and self._videoWidget is not None
            and hasattr(self._videoWidget, "surface")
        ):
            self._videoWidget.surface.pushFrame(qimg)

        if self._isStream:
            if self._state == PlayingState:
                if self._playStartMono is None:
                    self._playStartMono = time.monotonic()
                self._streamFrameCount += 1
                self._positionMs = int((time.monotonic() - self._playStartMono) * 1000)
            elif positionMs >= 0:
                self._positionMs = max(0, int(positionMs))
            else:
                self._positionMs = 0
            self._lastNotifyMs = self._positionMs
            self.positionChanged.emit(self._positionMs)
            self.frameDisplayed.emit(self._positionMs)
        elif positionMs >= 0:
            self._positionMs = positionMs
            self._lastNotifyMs = self._positionMs
            self.positionChanged.emit(self._positionMs)
            self.frameDisplayed.emit(self._positionMs)
        self._forceNotifyNext = False

        pending = self._pendingSeekMs
        self._pendingSeekMs = None
        if pending is not None:
            self._showFrameAt(pending)
        elif self._state == PlayingState and self._isStream:
            self._requestNextFrame()

    def _scheduleStreamDecode(self):
        if self._state == PlayingState and self._isStream and not self._decodeBusy:
            self._requestNextFrame()

    def play(self):
        """Start or resume media playback."""
        if not self._hasCapture:
            self._autoPlayWhenReady = True
            return
        if self._positionMs >= self._durationMs and self._durationMs > 0:
            self._showFrameAt(0, forceNotify=True)
        if self._isStream:
            self._playStartMono = time.monotonic()
            self._streamFrameCount = 0
            self._positionMs = 0
            self._lastNotifyMs = -1
        self._state = PlayingState
        self.playbackStateChanged.emit(self._state)
        interval = max(1, int(1000.0 / (self._fps * max(0.1, self._rate))))
        if self._isStream:
            interval = max(interval, 33)
            self._scheduleStreamDecode()
        self._timer.start(interval)

    def pause(self):
        """Pause media playback."""
        self._timer.stop()
        if self._state != StoppedState:
            self._state = PausedState
            self.playbackStateChanged.emit(self._state)

    def stop(self):
        """Stop playback and reset to the beginning."""
        self._timer.stop()
        self._state = StoppedState
        self._playStartMono = None
        self._streamFrameCount = 0
        self.playbackStateChanged.emit(self._state)
        self._showFrameAt(0, forceNotify=True)

    def _onTick(self):
        if not self._hasCapture or self._decodeBusy:
            return
        if self._isStream:
            self._scheduleStreamDecode()
            return
        if (
            not self._isStream
            and self._durationMs
            and self._positionMs >= self._durationMs
        ):
            if self._loops == -1:
                self.playbackLooped.emit()
                self._showFrameAt(0, forceNotify=True)
                return
            self._positionMs = self._durationMs
            self._showFrameAt(self._positionMs, forceNotify=True)
            self._timer.stop()
            self._state = PausedState
            self._status = EndOfMedia
            self.playbackStateChanged.emit(self._state)
            self.mediaStatusChanged.emit(self._status)
            return
        self._requestNextFrame()

    def setPosition(self, ms):
        """Seek to position *ms* in milliseconds."""
        self._showFrameAt(ms, forceNotify=True)

    def position(self):
        """Return the current playback position in milliseconds."""
        return self._positionMs

    def duration(self):
        """Return the total media duration in milliseconds."""
        return self._durationMs

    def setPlaybackRate(self, rate):
        """Set the playback speed multiplier."""
        rate = float(rate)
        if rate == self._rate:
            return
        self._rate = max(0.1, rate)
        self.playbackRateChanged.emit(self._rate)
        if self._state == PlayingState:
            interval = max(1, int(1000.0 / (self._fps * self._rate)))
            self._timer.start(interval)

    def playbackRate(self):
        """Return the current playback speed multiplier."""
        return self._rate

    def setMuted(self, muted):
        """Enable or disable audio muting."""
        self._muted = bool(muted)

    def isMuted(self):
        """Return True when audio is muted."""
        return self._muted

    def setLoops(self, loops):
        """Set loop count (-1 for infinite, 1 for no loop)."""
        self._loops = int(loops)

    def errorString(self):
        """Return the last error message, or empty string."""
        return self._error

    def playbackState(self):
        """Return the current playback state constant."""
        return self._state


class _QtMediaPlayerAdapter(QObject):
    """Qt QMediaPlayer adapter used when neither OpenCV nor FFmpeg are available."""

    durationChanged = pyqtSignal(int)
    positionChanged = pyqtSignal(int)
    frameDisplayed = pyqtSignal(int)
    mediaStatusChanged = pyqtSignal(int)
    playbackStateChanged = pyqtSignal(int)
    playbackRateChanged = pyqtSignal(float)
    playbackLooped = pyqtSignal()

    _QT_STATUS = None
    _QT_STATE = None

    def __init__(self, parent=None):
        super().__init__(parent)
        if not _HAS_QT_MEDIA:
            raise RuntimeError("Qt multimedia is not available")

        if self._QT_STATUS is None:
            self._QT_STATUS = {
                QMediaPlayer.MediaStatus.NoMedia: NoMedia,
                QMediaPlayer.MediaStatus.LoadingMedia: LoadingMedia,
                QMediaPlayer.MediaStatus.LoadedMedia: LoadedMedia,
                QMediaPlayer.MediaStatus.StalledMedia: StalledMedia,
                QMediaPlayer.MediaStatus.BufferingMedia: BufferingMedia,
                QMediaPlayer.MediaStatus.BufferedMedia: BufferedMedia,
                QMediaPlayer.MediaStatus.EndOfMedia: EndOfMedia,
                QMediaPlayer.MediaStatus.InvalidMedia: InvalidMedia,
            }
            self._QT_STATE = {
                QMediaPlayer.PlaybackState.PlayingState: PlayingState,
                QMediaPlayer.PlaybackState.PausedState: PausedState,
                QMediaPlayer.PlaybackState.StoppedState: StoppedState,
            }

        self._player = QMediaPlayer(parent)
        self._audio = QAudioOutput(parent)
        self._player.setAudioOutput(self._audio)
        self._videoWidget = None
        self._error = ""
        self._status = NoMedia
        self._state = StoppedState
        self._hasCapture = False
        self._autoPlayWhenReady = False
        self._loops = 1
        self._muted = False
        self._rate = 1.0
        self._fmvPlaylist = None
        self._lastPositionMs = 0

        self._player.durationChanged.connect(self._emitDurationChanged)
        self._player.positionChanged.connect(self._onPositionChanged)
        self._player.mediaStatusChanged.connect(self._onMediaStatus)
        self._player.playbackStateChanged.connect(self._onPlaybackState)
        self._player.playbackRateChanged.connect(self._emitPlaybackRateChanged)
        if hasattr(self._player, "errorOccurred"):
            self._player.errorOccurred.connect(self._onError)

    def audioOutput(self):
        return self._audio

    def setVideoWidget(self, videoWidget):
        self._videoWidget = videoWidget
        sink = None
        if videoWidget is not None:
            if hasattr(videoWidget, "videoSink"):
                sink = videoWidget.videoSink()
            elif hasattr(videoWidget, "_videoSink"):
                sink = videoWidget._videoSink
        if sink is not None:
            self._player.setVideoSink(sink)

    def setAutoPlayWhenReady(self, enabled=True):
        self._autoPlayWhenReady = bool(enabled)

    def setSource(self, url):
        self._error = ""
        if not isinstance(url, QUrl):
            url = QUrl(url)
        path = _url_to_path(url)
        is_stream = path and "://" in path
        if not path or (not is_stream and not os.path.isfile(path)):
            self._status = InvalidMedia
            self._error = "File not found"
            self._hasCapture = False
            self.mediaStatusChanged.emit(self._status)
            return
        self._hasCapture = False
        self._player.setSource(url)

    def play(self):
        if self._hasCapture:
            self._player.play()
        else:
            self._autoPlayWhenReady = True

    def pause(self):
        self._player.pause()

    def stop(self):
        self._player.stop()

    def setPosition(self, ms):
        self._player.setPosition(int(ms))

    def position(self):
        return int(self._player.position())

    def duration(self):
        return int(self._player.duration())

    def setPlaybackRate(self, rate):
        self._player.setPlaybackRate(float(rate))

    def playbackRate(self):
        return float(self._player.playbackRate())

    def setMuted(self, muted):
        self._muted = bool(muted)
        self._audio.setMuted(self._muted)

    def isMuted(self):
        return self._muted

    def setLoops(self, loops):
        self._loops = int(loops)
        if hasattr(self._player, "setLoops"):
            loops_value = QMediaPlayer.Loops.Infinite if loops == -1 else max(1, loops)
            self._player.setLoops(loops_value)

    def errorString(self):
        return self._error

    def playbackState(self):
        return self._state

    def _emitDurationChanged(self, duration):
        self.durationChanged.emit(int(duration))

    def _emitPlaybackRateChanged(self, rate):
        self.playbackRateChanged.emit(float(rate))

    def _onPositionChanged(self, positionMs):
        positionMs = int(positionMs)
        if (
            self._state == PlayingState
            and self._loops == -1
            and self._lastPositionMs > 1000
            and positionMs + 1000 < self._lastPositionMs
        ):
            self.playbackLooped.emit()
        self._lastPositionMs = positionMs
        self.positionChanged.emit(positionMs)
        if self._state == PlayingState:
            self.frameDisplayed.emit(positionMs)

    def _onMediaStatus(self, status):
        self._status = self._QT_STATUS.get(status, NoMedia)
        self._hasCapture = self._status in (LoadedMedia, BufferedMedia, EndOfMedia)
        self.mediaStatusChanged.emit(self._status)
        if self._status == LoadedMedia and self._autoPlayWhenReady:
            self._autoPlayWhenReady = False
            self.play()

    def _onPlaybackState(self, state):
        self._state = self._QT_STATE.get(state, StoppedState)
        self.playbackStateChanged.emit(self._state)

    def _onError(self, _error, message=""):
        self._error = message or str(_error)
        self._status = InvalidMedia
        self._hasCapture = False
        self.mediaStatusChanged.emit(self._status)


# ---------------------------------------------------------------------------
# Factory and player utilities
# ---------------------------------------------------------------------------

def createMediaPlayer(parent=None):
    """Create a media player. FFmpeg on macOS, else OpenCV, else Qt."""
    if platform.system() == "Darwin" and _ffmpeg_available():
        log.info("Media player backend: FFmpeg (macOS)")
        return (
            OpenCvMediaPlayer(parent, decode_worker_factory=_FfmpegDecodeWorker),
            None,
        )
    if cv2 is not None:
        return OpenCvMediaPlayer(parent), None
    if _ffmpeg_available():
        return (
            OpenCvMediaPlayer(parent, decode_worker_factory=_FfmpegDecodeWorker),
            None,
        )
    if _HAS_QT_MEDIA:
        player = _QtMediaPlayerAdapter(parent)
        return player, player.audioOutput()
    player = OpenCvMediaPlayer(parent)
    return player, None


def setVideoOutput(player, videoWidget):
    """Connect the video output widget to the player."""
    player.setVideoWidget(videoWidget)


def connectStateChanged(player, slot):
    """Connect the playback-state-changed signal to *slot*."""
    player.playbackStateChanged.connect(slot)


def hasVideo(player):
    """Return True when the player has a loaded video with frames."""
    if isinstance(player, _QtMediaPlayerAdapter):
        return player._hasCapture
    return (
        player._status in (LoadedMedia, BufferedMedia, EndOfMedia)
        and player._hasCapture
    )


def setVolume(_player, _audio, value):
    """Set the audio volume (0-100 scale)."""
    if _audio is not None:
        _audio.setVolume(max(0.0, min(1.0, float(value) / 100.0)))


def getVolume(_player, _audio):
    """Return the current audio volume (0-100 scale)."""
    if _audio is not None:
        return int(round(_audio.volume() * 100))
    return 0


# ---------------------------------------------------------------------------
# Playlist
# ---------------------------------------------------------------------------

class _MediaShim(object):
    """Thin wrapper providing a ``canonicalUrl()`` for playlist compatibility."""
    def __init__(self, url):
        self._url = url

    def canonicalUrl(self):
        return self._url


PlaylistSequential = PlaylistMode.Sequential
PlaylistLoop = PlaylistMode.Loop


class FmvPlaylist(QObject):
    """Minimal playlist driving OpenCvMediaPlayer."""

    Sequential = PlaylistSequential
    Loop = PlaylistLoop

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._current = -1
        self._mode = PlaylistSequential
        self._player = None

    def setPlayer(self, player):
        """Bind the playlist to a media player instance."""
        self._player = player
        self._applyMode()

    def addMedia(self, content):
        """Append a media URL/path to the playlist."""
        self._items.append(content)
        return True

    def removeMedia(self, idx):
        """Remove the item at index *idx* from the playlist."""
        if 0 <= idx < len(self._items):
            del self._items[idx]
            if self._current >= len(self._items):
                self._current = len(self._items) - 1
            return True
        return False

    def mediaCount(self):
        """Return the number of items in the playlist."""
        return len(self._items)

    def media(self, x):
        """Return a shim wrapping the URL at index *x*."""
        if 0 <= x < len(self._items):
            return _MediaShim(self._items[x])
        return _MediaShim(QUrl())

    def currentIndex(self):
        """Return the index of the currently playing item."""
        return self._current

    def nextIndex(self):
        """Return the index of the next item, or -1 if at end."""
        if not self._items:
            return -1
        if self._mode == PlaylistLoop:
            return self._current
        nxt = self._current + 1
        return nxt if nxt < len(self._items) else -1

    def setCurrentIndex(self, row):
        """Set the current playlist index and load the media."""
        if 0 <= row < len(self._items):
            self._current = row
            if self._player is not None:
                self._player.setSource(self._items[row])

    def setPlaybackMode(self, mode):
        """Set the playback mode (Sequential or Loop)."""
        self._mode = mode
        self._applyMode()

    def _applyMode(self):
        if self._player is None:
            return
        self._player.setLoops(-1 if self._mode == PlaylistLoop else 1)


def createPlaylist(parent=None):
    """Create and return a new FmvPlaylist instance."""
    return FmvPlaylist(parent)


def attachPlaylist(player, playlist):
    """Bind *playlist* to *player* so track changes drive playback."""
    playlist.setPlayer(player)
    player._fmvPlaylist = playlist


def getPlaylist(player):
    """Return the playlist attached to *player*, or None."""
    return getattr(player, "_fmvPlaylist", None)


def mediaUrlToContent(url):
    """Return *url* as-is (compatibility shim for QMediaContent)."""
    return url





