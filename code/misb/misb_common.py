# -*- coding: utf-8 -*-
r"""
misb_common.py
==============

MISB/CSV core used by misb_ffmpeg.py:
    - MISB ST0601 encoder (raw bytes, no external dependencies).
    - DJI telemetry CSV parsing into timed KLV packets.
    - Small path/config helpers.

Why not use the 'klvdata' library to ENCODE here?
    klvdata is primarily a *parser*. Its writing support is partial:
      - Individual element values can be encoded (e.g. PlatformHeadingAngle(45.0)),
      - but PrecisionTimeStamp(datetime) raises (it expects bytes), and
      - UASLocalMetadataSet only parses bytes -> items; it cannot assemble items
        back into a packet, so it builds neither the 16-byte universal key, the
        total BER length, nor the BCC-16 checksum.
    We would still have to write the key/length/checksum/timestamp by hand, and
    it would add a hard dependency to the generator (which today runs on the
    Python standard library alone). So the encoder below stays self-contained.
    (klvdata IS used, as intended, to DECODE/verify the result in misb_check.py.)
"""

from __future__ import annotations

import os
import csv
import struct
from math import tan, cos, sin, radians, degrees
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Output naming
# ---------------------------------------------------------------------------
# Suffix appended to the original video name for the output (e.g.
# DJI_0047.mp4 -> DJI_0047_MISB.ts) when --out is not given.
OUT_SUFFIX = "_MISB"


def default_output(video_path: str) -> str:
    """Output next to the video, same name + OUT_SUFFIX and .ts extension."""
    base = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(os.path.dirname(video_path) or ".", base + OUT_SUFFIX + ".ts")


# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------
# Camera field of view (degrees). Adjust to your DJI camera/lens.
HFOV_DEG = 81.0
VFOV_DEG = 66.0

EARTH_MEAN_RADIUS = 6378137.0  # meters (WGS-84)
ST0601_VERSION = 11            # Tag 65: UAS LS version number

# Universal key (16 bytes) of the UAS Datalink Local Set (MISB ST0601)
UAS_LS_KEY = bytes(
    [0x06, 0x0E, 0x2B, 0x34, 0x02, 0x0B, 0x01, 0x01,
     0x0E, 0x01, 0x03, 0x01, 0x01, 0x00, 0x00, 0x00]
)


# ===========================================================================
# 1. MISB ST0601 ENCODER  (RAW bytes, no external dependencies)
# ===========================================================================
def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _u(value: float, vmin: float, vmax: float, nbytes: int) -> int:
    """Map value in [vmin, vmax] to an unsigned integer of nbytes."""
    value = _clamp(value, vmin, vmax)
    full = (1 << (8 * nbytes)) - 1
    return int(round((value - vmin) / (vmax - vmin) * full))


def _s(value: float, vabs: float, nbytes: int) -> int:
    """Map value in [-vabs, vabs] to a signed integer of nbytes (two's complement)."""
    value = _clamp(value, -vabs, vabs)
    half = (1 << (8 * nbytes - 1)) - 1
    return int(round(value / vabs * half))


def _tlv(tag: int, value: bytes) -> bytes:
    """Tag-Length-Value of a local set element (1-byte tag and length)."""
    return bytes([tag, len(value)]) + value


def _ber_length(n: int) -> bytes:
    """Encode a length in BER (short or long form)."""
    if n < 128:
        return bytes([n])
    out = b""
    while n > 0:
        out = bytes([n & 0xFF]) + out
        n >>= 8
    return bytes([0x80 | len(out)]) + out


def _bcc_16(data: bytes) -> int:
    """ST0601 16-bit checksum (sum weighted by even/odd position)."""
    s = 0
    for i, b in enumerate(data):
        s += b << (8 * ((i + 1) % 2))
    return s & 0xFFFF


def build_st0601_packet(values: dict) -> bytes:
    """
    Build a complete ST0601 packet from a dict of quantities.
    Returns the RAW bytes of the packet (key + BER length + TLVs + checksum).
    """
    payload = b""

    # Tag 2 - Precision Time Stamp (UNIX UTC microseconds, uint64)
    if "timestamp_us" in values:
        payload += _tlv(2, struct.pack(">Q", int(values["timestamp_us"])))

    # Tag 65 - UAS LS Version Number
    payload += _tlv(65, bytes([ST0601_VERSION]))

    # Tag 5 - Platform Heading Angle (0..360, uint16)
    if "platform_heading" in values:
        payload += _tlv(5, struct.pack(">H", _u(values["platform_heading"], 0, 360, 2)))

    # Tag 6 - Platform Pitch Angle (-20..20, int16)
    if "platform_pitch" in values:
        payload += _tlv(6, struct.pack(">h", _s(values["platform_pitch"], 20, 2)))

    # Tag 7 - Platform Roll Angle (-50..50, int16)
    if "platform_roll" in values:
        payload += _tlv(7, struct.pack(">h", _s(values["platform_roll"], 50, 2)))

    # Tag 13 - Sensor Latitude (-90..90, int32)
    if "sensor_lat" in values:
        payload += _tlv(13, struct.pack(">i", _s(values["sensor_lat"], 90, 4)))

    # Tag 14 - Sensor Longitude (-180..180, int32)
    if "sensor_lon" in values:
        payload += _tlv(14, struct.pack(">i", _s(values["sensor_lon"], 180, 4)))

    # Tag 15 - Sensor True Altitude (-900..19000 m, uint16)
    if "sensor_alt" in values:
        payload += _tlv(15, struct.pack(">H", _u(values["sensor_alt"], -900, 19000, 2)))

    # Tag 16 - Sensor Horizontal FOV (0..180, uint16)
    payload += _tlv(16, struct.pack(">H", _u(HFOV_DEG, 0, 180, 2)))
    # Tag 17 - Sensor Vertical FOV (0..180, uint16)
    payload += _tlv(17, struct.pack(">H", _u(VFOV_DEG, 0, 180, 2)))

    # Tag 18 - Sensor Relative Azimuth Angle (0..360, uint32)
    if "sensor_rel_az" in values:
        payload += _tlv(18, struct.pack(">I", _u(values["sensor_rel_az"], 0, 360, 4)))
    # Tag 19 - Sensor Relative Elevation Angle (-180..180, int32)
    if "sensor_rel_el" in values:
        payload += _tlv(19, struct.pack(">i", _s(values["sensor_rel_el"], 180, 4)))
    # Tag 20 - Sensor Relative Roll Angle (0..360, uint32)
    if "sensor_rel_roll" in values:
        payload += _tlv(20, struct.pack(">I", _u(values["sensor_rel_roll"], 0, 360, 4)))

    # Tag 21 - Slant Range (0..5000000 m, uint32)
    if "slant_range" in values:
        payload += _tlv(21, struct.pack(">I", _u(values["slant_range"], 0, 5_000_000, 4)))
    # Tag 22 - Target Width (0..10000 m, uint16)
    if "target_width" in values:
        payload += _tlv(22, struct.pack(">H", _u(values["target_width"], 0, 10_000, 2)))

    # Tag 23 - Frame Center Latitude (-90..90, int32)
    if "fc_lat" in values:
        payload += _tlv(23, struct.pack(">i", _s(values["fc_lat"], 90, 4)))
    # Tag 24 - Frame Center Longitude (-180..180, int32)
    if "fc_lon" in values:
        payload += _tlv(24, struct.pack(">i", _s(values["fc_lon"], 180, 4)))
    # Tag 25 - Frame Center Elevation (-900..19000 m, uint16)
    if "fc_elev" in values:
        payload += _tlv(25, struct.pack(">H", _u(values["fc_elev"], -900, 19000, 2)))

    # Total local set length = payload + checksum TLV (tag 1, len 2, value 2)
    total_len = len(payload) + 4
    pre_checksum = UAS_LS_KEY + _ber_length(total_len) + payload + bytes([0x01, 0x02])
    checksum = _bcc_16(pre_checksum)
    return pre_checksum + struct.pack(">H", checksum)


# ===========================================================================
# 2. DJI TELEMETRY CSV PARSING
# ===========================================================================
def _to_float(text: str):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_dji_time(text: str) -> datetime:
    """DJI writes 'YYYY/MM/DD HH:MM:SS.fff' (sometimes without milliseconds)."""
    for fmt in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date format: {text!r}")


def _compute_geometry(row_vals: dict) -> dict:
    """
    Compute slant range, target width and frame center from the pose.
    It's an approximation (like QGISFMV), good enough to draw the footprint.
    """
    out = {}
    lat = row_vals.get("sensor_lat")
    lon = row_vals.get("sensor_lon")
    alt = row_vals.get("sensor_alt")
    yaw = row_vals.get("platform_heading")
    pitch = row_vals.get("platform_pitch", 0.0) or 0.0
    gimbal_pitch = row_vals.get("_gimbal_pitch", 0.0) or 0.0

    if None in (lat, lon, alt) or yaw is None:
        return out

    # Total depression angle (platform + gimbal)
    depression = pitch + gimbal_pitch
    angle = 180.0 + depression
    cos_a = cos(radians(angle))
    if abs(cos_a) < 1e-6:
        cos_a = 1e-6
    slant = abs(alt / cos_a)
    out["slant_range"] = slant
    out["target_width"] = 2.0 * slant * tan(radians(HFOV_DEG / 2.0))

    # Frame center projected onto the ground
    ground_angle = 90.0 + depression
    tg_dist = alt * tan(radians(ground_angle))
    dy = tg_dist * cos(radians(yaw))
    dx = tg_dist * sin(radians(yaw))
    fc_lat = lat + degrees(dy / EARTH_MEAN_RADIUS)
    cos_lat = cos(radians(lat)) or 1e-6
    fc_lon = lon + degrees(dx / EARTH_MEAN_RADIUS) / cos_lat
    out["fc_lat"] = fc_lat
    out["fc_lon"] = fc_lon
    out["fc_elev"] = 0.0
    return out


def build_klv_packets(csv_path: str, only_recording: bool = True):
    """
    Read the DJI CSV and return a list of tuples (t_rel_seconds, packet_bytes).
    t_rel is the time relative to the start of the recorded segment (KLV PTS).
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(csv_path)

    packets = []
    t0 = None

    with open(csv_path, newline="", encoding="utf-8", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            is_video = (row.get("CUSTOM.isVideo") or "").strip()
            if only_recording and not is_video:
                continue

            time_str = (row.get("CUSTOM.updateTime") or "").strip()
            if not time_str:
                continue
            t = _parse_dji_time(time_str)
            if t0 is None:
                t0 = t
            t_rel = (t - t0).total_seconds()
            if t_rel < 0:
                continue

            vals = {"timestamp_us": int(t.timestamp() * 1_000_000)}

            yaw = _to_float(row.get("OSD.yaw"))
            if yaw is not None:
                vals["platform_heading"] = yaw + 360.0 if yaw < 0 else yaw
            pitch = _to_float(row.get("OSD.pitch"))
            if pitch is not None:
                vals["platform_pitch"] = pitch
            roll = _to_float(row.get("OSD.roll"))
            if roll is not None:
                vals["platform_roll"] = roll

            lat = _to_float(row.get("OSD.latitude"))
            if lat is not None:
                vals["sensor_lat"] = lat
            lon = _to_float(row.get("OSD.longitude"))
            if lon is not None:
                vals["sensor_lon"] = lon
            alt = _to_float(row.get("OSD.altitude [m]"))
            if alt is not None:
                vals["sensor_alt"] = alt

            g_yaw = _to_float(row.get("GIMBAL.yaw"))
            if g_yaw is not None:
                vals["sensor_rel_az"] = g_yaw + 360.0 if g_yaw < 0 else g_yaw
            g_pitch = _to_float(row.get("GIMBAL.pitch"))
            if g_pitch is not None:
                vals["sensor_rel_el"] = g_pitch
                vals["_gimbal_pitch"] = g_pitch
            g_roll = _to_float(row.get("GIMBAL.roll"))
            if g_roll is not None:
                vals["sensor_rel_roll"] = g_roll + 360.0 if g_roll < 0 else g_roll

            vals.update(_compute_geometry(vals))
            vals.pop("_gimbal_pitch", None)

            packets.append((t_rel, build_st0601_packet(vals)))

    if not packets:
        raise RuntimeError(
            "No KLV packet was generated. Does the CSV have rows with "
            "CUSTOM.isVideo = 'Recording'? Try --all-rows."
        )
    return packets


def write_klv_stream(packets, out_path: str) -> str:
    """Write the packets as a BINARY KLV elementary stream (raw bytes)."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as fh:
        for _, pkt in packets:
            fh.write(pkt)
    return out_path
