# -*- coding: utf-8 -*-
"""Background frame decode workers (OpenCV VideoCapture and FFmpeg pipe)."""

try:
    import cv2
except ImportError:
    cv2 = None

from qgis.PyQt.QtCore import QObject, pyqtSignal, pyqtSlot
from qgis.PyQt.QtGui import QImage

from QGISFMV.utils.logging import log
from QGISFMV.utils.media.QgsFmvMediaProbe import (
    _ffmpeg_available,
    _ffmpeg_popen,
    _probe_video_info,
    _probeDurationMs,
    _read_bytes,
    _validateMediaPath,
)


class FrameDecodeWorker(QObject):
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


class FfmpegDecodeWorker(QObject):
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


# Private aliases matching the former Multimedia module names.
_FrameDecodeWorker = FrameDecodeWorker
_FfmpegDecodeWorker = FfmpegDecodeWorker
