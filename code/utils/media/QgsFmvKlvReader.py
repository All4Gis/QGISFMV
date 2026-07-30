# -*- coding: utf-8 -*-
import bisect
import threading
import time
from collections import deque
from datetime import datetime

from QGISFMV.utils.logging import log
from QGISFMV.utils.core.QgsFmvUtils import (
    _time_to_seconds,
    _spawn,
    KLV_HEADER_0601,
    KLV_HEADER_EG0104,
)
from pymisb.klvdata.streamparser import StreamParser

STREAM_PACKET_CACHE = 600
STREAM_READ_CHUNK = 65536


def _bisect_nearest(sorted_list, target):
    """Return the index of the nearest value in *sorted_list* to *target*."""
    if not sorted_list:
        return None
    idx = bisect.bisect_left(sorted_list, target)
    if idx <= 0:
        return 0
    if idx >= len(sorted_list):
        return len(sorted_list) - 1
    before = idx - 1
    if abs(sorted_list[before] - target) <= abs(sorted_list[idx] - target):
        return before
    return idx


def _extractKlvPackets(rawData):
    """Split raw KLV stream data into individual packets."""
    if isinstance(rawData, bytearray):
        rawData = bytes(rawData)
    packets = []
    pos = 0
    dataLen = len(rawData)
    while pos < dataLen:
        idx0601 = rawData.find(KLV_HEADER_0601, pos)
        idx0104 = rawData.find(KLV_HEADER_EG0104, pos)

        if idx0601 == -1 and idx0104 == -1:
            break
        if idx0601 == -1:
            start = idx0104
        elif idx0104 == -1:
            start = idx0601
        else:
            start = min(idx0601, idx0104)

        next0601 = rawData.find(KLV_HEADER_0601, start + 14)
        next0104 = rawData.find(KLV_HEADER_EG0104, start + 14)
        candidates = [h for h in (next0601, next0104) if h != -1]
        end = min(candidates) if candidates else dataLen

        packet = rawData[start:end]
        if len(packet) > 14:
            packets.append(packet)
        pos = end

    return packets


_extractKlvPackets._logOnce = True


def _parseTimestampFromKlv(packet):
    """Extract Precision Time Stamp (tag 2) from a MISB 0601 KLV packet."""
    try:
        for parsed in StreamParser(packet):
            item = parsed.items.get(b"\x02")
            if item is None:
                continue
            value = getattr(item, "value", None)
            if hasattr(value, "value") and not isinstance(value, datetime):
                value = value.value
            if isinstance(value, datetime):
                return value.timestamp()
            if value is not None and hasattr(value, "timestamp"):
                return value.timestamp()
    except Exception as exc:
        log.debug("KLV timestamp parse failed: %s", exc)
    return None


class LocalFileMetaReader:
    """Pre-reads metadata from a local MISB video via a single ffmpeg process."""

    def __init__(self, videoPath, klvIndex=0, preload=True):
        self.videoPath = videoPath
        self.klvIndex = klvIndex
        self._offsets = []
        self._packets = []
        self._rawPacketCount = 0
        self._videoStart = None
        self._loaded = False
        self._loadError = None
        self._stop = False
        self._loadThread = None
        if preload:
            self._loadThread = threading.Thread(target=self._loadAll, daemon=True)
            self._loadThread.start()
        else:
            self._loadAll()

    def _loadAll(self):
        try:
            proc = _spawn(
                [
                    "-i",
                    self.videoPath,
                    "-map",
                    "0:d:" + str(self.klvIndex),
                    "-f",
                    "data",
                    "-",
                ]
            )
            rawData, _ = proc.communicate(timeout=120)

            if not rawData:
                log.info("LocalFileMetaReader: no KLV data found.")
                self._loaded = True
                return

            packets = _extractKlvPackets(rawData)
            self._rawPacketCount = len(packets)
            log.info("LocalFileMetaReader: extracted %d KLV packets.", len(packets))

            self._videoStart = self._getVideoStartTime()

            entries = []
            for packet in packets:
                if self._stop:
                    break
                ts = _parseTimestampFromKlv(packet)
                if ts is not None:
                    entries.append((self._timestampToOffset(ts), packet))

            if not entries and packets:
                duration = self._getMediaDuration() or float(len(packets))
                step = duration / max(len(packets), 1)
                for index, packet in enumerate(packets):
                    entries.append((index * step, packet))

            entries = self._finalizeEntries(entries)
            self._offsets = [item[0] for item in entries]
            self._packets = [item[1] for item in entries]
            self._loaded = True
            log.info(
                "LocalFileMetaReader: indexed {} metadata entries (span {:.2f}s).".format(
                    len(self._packets),
                    (
                        (self._offsets[-1] - self._offsets[0])
                        if len(self._offsets) > 1
                        else 0.0
                    ),
                )
            )

        except Exception as exc:
            self._loadError = str(exc)
            log.error("LocalFileMetaReader load failed: %s", exc)
            self._loaded = True

    def _timestampToOffset(self, unixTs):
        if self._videoStart is not None:
            offsetSec = unixTs - self._videoStart
            if offsetSec < 0:
                offsetSec = 0
            return offsetSec
        return float(unixTs)

    def _finalizeEntries(self, entries):
        """Map packet timestamps onto the video timeline (seconds from t=0)."""
        if not entries:
            return entries

        entries = sorted(entries, key=lambda item: item[0])
        duration = self._getMediaDuration()

        if self._videoStart is None and entries:
            base = entries[0][0]
            entries = [(max(0.0, float(off) - base), pkt) for off, pkt in entries]

        if duration and len(entries) > 1:
            span = entries[-1][0] - entries[0][0]
            if span <= 0 or span > duration * 1.5 or entries[-1][0] > duration * 1.5:
                step = duration / max(len(entries) - 1, 1)
                entries = [(i * step, pkt) for i, (_, pkt) in enumerate(entries)]

        return entries

    def isReady(self):
        """Return True when the KLV file has finished loading."""
        return self._loaded

    def loadError(self):
        """Return the exception string if loading failed, else None."""
        return self._loadError

    def waitUntilLoaded(self, timeout=None):
        """Block until loading completes or *timeout* seconds elapse."""
        if self._loadThread is not None:
            self._loadThread.join(timeout=timeout)
        return self._loaded

    def packetCount(self):
        """Return the number of parsed KLV packets."""
        return len(self._packets)

    def rawPacketCount(self):
        """Return the raw packet count from the probe output."""
        return self._rawPacketCount or len(self._packets)

    def hasTelemetry(self):
        """True when at least one KLV packet was found."""
        return self.rawPacketCount() > 0

    def firstPacket(self):
        """Return the first raw KLV packet, or b'' if none."""
        if self._packets:
            return self._packets[0]
        return b""

    def _getMediaDuration(self):
        try:
            from QGISFMV.utils.media.QgsFfmpegProbe import probe_json
            import json

            data = probe_json(self.videoPath)
            if not data:
                return None
            info = json.loads(data.decode("utf-8", errors="replace"))
            duration = float(info.get("format", {}).get("duration") or 0.0)
            return duration if duration > 0 else None
        except Exception as _exc:
            log.debug("media duration probe failed: %s", _exc)
            return None

    def _getVideoStartTime(self):
        try:
            proc = _spawn(
                [
                    "-i",
                    self.videoPath,
                    "-show_entries",
                    "format_tags=creation_time",
                    "-v",
                    "quiet",
                    "-of",
                    "csv=p=0",
                ],
                t="probe",
            )
            out, _ = proc.communicate(timeout=15)
            if out:
                text = out.decode("utf-8", errors="replace").strip()
                if text:
                    for fmt in (
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                        "%Y-%m-%dT%H:%M:%S.%f",
                        "%Y-%m-%dT%H:%M:%SZ",
                        "%Y-%m-%dT%H:%M:%S",
                    ):
                        try:
                            dt = datetime.strptime(text.split("\n")[0].strip(), fmt)
                            return dt.timestamp()
                        except ValueError:
                            continue
        except Exception as exc:
            from QGISFMV.utils.logging import log

            log.debug("Metadata timestamp parse failed: %s", exc)
        return None

    def _lookupOffset(self, targetSec):
        return _bisect_nearest(self._offsets, targetSec)

    def get(self, t):
        """Return the KLV packet nearest to time *t*, or b'' if unavailable."""
        if not self._loaded:
            return "BUFFERING"
        if not self._packets:
            return b""
        try:
            targetSec = _time_to_seconds(t)
        except Exception as _exc:
            log.debug("KLV time conversion failed: %s", _exc)
            return b""
        idx = self._lookupOffset(targetSec)
        if idx is None:
            return b""
        return self._packets[idx]

    def getSnapshot(self, targetSec):
        """Return ``(packetIndex, packet)`` for the telemetry entry at *targetSec*."""
        if not self._loaded:
            return -1, b""
        if not self._packets:
            return -1, b""
        try:
            targetSec = float(targetSec)
        except (TypeError, ValueError):
            try:
                targetSec = _time_to_seconds(targetSec)
            except Exception as _exc:
                log.debug("KLV snapshot time conversion failed: %s", _exc)
                return -1, b""
        idx = self._lookupOffset(targetSec)
        if idx is None:
            return -1, b""
        return idx, self._packets[idx]

    def getSize(self, t):
        """Return the total number of loaded KLV packets."""
        return len(self._packets)

    def dispose(self):
        """Stop loading, release resources, and clear packet data."""
        if getattr(self, "_disposed", False):
            return
        self._disposed = True
        self._stop = True
        if self._loadThread is not None:
            self._loadThread.join(timeout=1.0)
            self._loadThread = None
        self._offsets.clear()
        self._packets.clear()
        self._loaded = False


class StreamMetaReader:
    """Read KLV telemetry from a live FFmpeg stream (UDP/TCP/RTP/RTSP)."""

    def __init__(self, source, connectTimeout=5.0):
        self.source = source
        self._lock = threading.Lock()
        self._offsets = deque(maxlen=STREAM_PACKET_CACHE)
        self._packets = deque(maxlen=STREAM_PACKET_CACHE)
        self._latest = b""
        self._latestSeq = 0
        self._loaded = False
        self._loadError = None
        self._stop = False
        self._startMono = time.monotonic()
        self._proc = None
        log.info("StreamMetaReader: connecting to %s", source)
        self._thread = threading.Thread(
            target=self._readLoop, daemon=True, name="fmv-stream-klv"
        )
        self._thread.start()

        deadline = time.monotonic() + max(1.0, float(connectTimeout))
        while time.monotonic() < deadline and not self._stop:
            with self._lock:
                if self._latest:
                    self._loaded = True
                    log.info(
                        "StreamMetaReader: first KLV packet received from %s", source
                    )
                    break
            time.sleep(0.02)
        if not self._loaded:
            log.warning(
                "StreamMetaReader: no KLV data received from %s within %ss",
                source,
                connectTimeout,
            )

    def _readLoop(self):
        try:
            self._proc = _spawn(
                [
                    "-fflags",
                    "+nobuffer",
                    "-analyzeduration",
                    "2000000",
                    "-probesize",
                    "32",
                    "-i",
                    self.source,
                    "-map",
                    "0:d",
                    "-c",
                    "copy",
                    "-f",
                    "data",
                    "-",
                ]
            )
            log.info(
                f"StreamMetaReader: ffmpeg KLV process started (pid={self._proc.pid})"
            )
            buf = bytearray()
            no_data_count = 0
            while not self._stop and self._proc and self._proc.poll() is None:
                chunk = (
                    self._proc.stdout.read(STREAM_READ_CHUNK)
                    if self._proc.stdout
                    else b""
                )
                if not chunk:
                    no_data_count += 1
                    if no_data_count > 200:
                        log.warning(
                            f"StreamMetaReader: no data received for 1s, "
                            f"stream may not contain a data PID. "
                            f"Source: {self.source}"
                        )
                        break
                    time.sleep(0.005)
                    continue
                no_data_count = 0
                buf.extend(chunk)
                if len(buf) > STREAM_READ_CHUNK * 4:
                    buf = buf[-STREAM_READ_CHUNK * 2 :]
                packets = _extractKlvPackets(buf)
                if not packets:
                    continue
                keep_from = (
                    buf.rfind(packets[-1][:16]) if len(packets[-1]) >= 16 else -1
                )
                if keep_from >= 0:
                    del buf[:keep_from]

                now = time.monotonic()
                with self._lock:
                    for packet in packets:
                        if self._stop:
                            break
                        offset = now - self._startMono
                        self._offsets.append(offset)
                        self._packets.append(packet)
                        self._latest = packet
                        self._latestSeq += 1
                        self._loaded = True
                if self._latestSeq % 10 == 1:
                    log.info(
                        f"StreamMetaReader: {self._latestSeq} KLV packets received from {self.source}"
                    )
            if self._proc and self._proc.poll() is not None:
                stderr_out = ""
                try:
                    stderr_out = self._proc.stderr.read().decode(
                        "utf-8", errors="replace"
                    )
                except Exception as exc:
                    log.debug("KLV process stderr read failed: %s", exc)
                log.warning(
                    f"StreamMetaReader: ffmpeg exited with code {self._proc.returncode}: {stderr_out[:500]}"
                )
            if not self._loaded and not self._loadError:
                self._loadError = (
                    f"No KLV data found in stream. "
                    f"Ensure VLC sends a data PID alongside video. "
                    f"Source: {self.source}"
                )
                log.warning("StreamMetaReader: %s", self._loadError)
        except Exception as exc:
            self._loadError = str(exc)
            log.error("StreamMetaReader failed: %s", exc)
        finally:
            self._releaseProc()

    def _releaseProc(self):
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception as exc:
                try:
                    self._proc.kill()
                except Exception as kill_exc:
                    log.debug("KLV process kill failed: %s", kill_exc)
                log.debug("KLV process terminate failed: %s", exc)
            self._proc = None

    def isReady(self):
        """Return True when the stream reader has received at least one packet."""
        return self._loaded

    def loadError(self):
        """Return the error string if the stream process failed, else None."""
        return self._loadError

    def waitUntilLoaded(self, timeout=None):
        """Block until a packet arrives or *timeout* seconds elapse."""
        if timeout is None:
            return self._loaded
        deadline = time.monotonic() + float(timeout)
        while time.monotonic() < deadline and not self._loaded and not self._stop:
            time.sleep(0.05)
        return self._loaded

    def packetCount(self):
        """Return the number of KLV packets received so far."""
        with self._lock:
            return len(self._packets)

    def rawPacketCount(self):
        """Return the raw packet count (same as packetCount for streams)."""
        return self.packetCount()

    def hasTelemetry(self):
        """True when at least one KLV packet or latest frame exists."""
        with self._lock:
            return bool(self._packets) or bool(self._latest)

    def firstPacket(self):
        """Return the first KLV packet, or the latest frame if none queued."""
        with self._lock:
            if self._packets:
                return self._packets[0]
            return self._latest or b""

    def _lookupOffset(self, targetSec):
        with self._lock:
            return _bisect_nearest(self._offsets, targetSec)

    def getLatest(self):
        """Return the most recent KLV packet (live streams)."""
        with self._lock:
            return self._latest or b""

    def getLatestSeq(self):
        """Monotonic counter; changes whenever a new KLV packet arrives."""
        with self._lock:
            return self._latestSeq

    def getLatestSnapshot(self):
        """Return ``(seq, packet)`` under one lock acquisition."""
        with self._lock:
            return self._latestSeq, (self._latest or b"")

    def getSnapshot(self, targetSec):
        """Return ``(packetIndex, packet)`` aligned to playback time."""
        with self._lock:
            if not self._loaded:
                return -1, b""
            if not self._packets and not self._latest:
                return -1, b""
            if not self._offsets:
                return self._latestSeq, (self._latest or b"")
            try:
                targetSec = float(targetSec)
            except (TypeError, ValueError):
                try:
                    targetSec = _time_to_seconds(targetSec)
                except Exception as _exc:
                    log.debug("stream snapshot time conversion failed: %s", _exc)
                    return self._latestSeq, (self._latest or b"")
            if not self._offsets:
                return self._latestSeq, (self._latest or b"")
            packetIdx = _bisect_nearest(self._offsets, targetSec)
            if packetIdx is None:
                return self._latestSeq, (self._latest or b"")
            return packetIdx, self._packets[packetIdx]

    def markPlaybackStart(self):
        """Align stream telemetry clock with video playback start."""
        with self._lock:
            self._startMono = time.monotonic()

    def get(self, t):
        """Return the KLV packet nearest to time *t*, or the latest frame."""
        if not self._loaded:
            return "BUFFERING"
        with self._lock:
            if not self._packets and not self._latest:
                return b""
            if self._latest and not self._packets:
                return self._latest
            try:
                targetSec = _time_to_seconds(t)
            except Exception as _exc:
                log.debug("stream KLV time conversion failed: %s", _exc)
                return self._latest or b""
            if not self._offsets:
                return self._latest or b""
            packetIdx = _bisect_nearest(self._offsets, targetSec)
            if packetIdx is None:
                return self._latest or b""
            return self._packets[packetIdx]

    def getSize(self, _t):
        """Return the total number of received KLV packets."""
        return self.packetCount()

    def dispose(self):
        """Stop the stream reader process and release all resources."""
        if getattr(self, "_disposed", False):
            return
        self._disposed = True
        self._stop = True
        self._releaseProc()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        with self._lock:
            self._offsets.clear()
            self._packets.clear()
            self._latest = b""
            self._latestSeq = 0
            self._loaded = False


# Legacy snake_case names removed — use camelCase API above.
