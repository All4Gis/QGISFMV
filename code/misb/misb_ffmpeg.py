# -*- coding: utf-8 -*-
r"""
misb_ffmpeg.py
==============

Creates a MISB / STANAG 4609 video (MPEG-TS) with VIDEO + AUDIO (if present) + a
TIMED KLV data channel (MISB ST0601), from a DJI video and its telemetry log
exported to CSV. The result opens in QGISFMV.

FFmpeg path (recommended on Windows):
    - FFmpeg builds the video/audio TS by copying the streams (no re-encoding).
    - This script injects, in Python, a KLV PID with one PES packet per sample and
      its PTS (90 kHz clock), and rewrites the PMT to advertise it as KLV metadata
      (stream_type 0x15, "KLVA" descriptor).
    - Result: 'Data: klv (KLVA)' with per-packet timestamps.

Only needs Python (standard library) and FFmpeg.

Author: Fran Raga (2026 rewrite). Based on QGISFMV/QgsMultiplexor.
"""

from __future__ import annotations

import os
import sys
import struct
import shutil
import argparse
import subprocess

from QGIS_FMV.misb.misb_common import (
    default_output,
    build_klv_packets, write_klv_stream,
)


# ===========================================================================
# 1. MPEG-TS PRIMITIVES  (PES with PTS, PCR, PSI tables)
# ===========================================================================
def _crc32_mpeg(data: bytes) -> int:
    """CRC-32 for MPEG PSI tables (poly 0x04C11DB7, MSB-first)."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte << 24
        for _ in range(8):
            crc = ((crc << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if crc & 0x80000000 else (crc << 1) & 0xFFFFFFFF
    return crc


def _encode_pts(pts: int) -> bytes:
    """Encode a 33-bit PTS into the 5 PES header bytes (prefix 0010)."""
    pts &= 0x1FFFFFFFF
    return bytes([
        0x21 | ((pts >> 29) & 0x0E),
        (pts >> 22) & 0xFF,
        0x01 | ((pts >> 14) & 0xFE),
        (pts >> 7) & 0xFF,
        0x01 | ((pts << 1) & 0xFE),
    ])


def _encode_pcr(pcr_base: int) -> bytes:
    """48-bit PCR (33-bit base at 90 kHz + 6 reserved + 9-bit extension)."""
    val = ((pcr_base & 0x1FFFFFFFF) << 15) | (0x3F << 9) | 0
    return val.to_bytes(6, "big")


def _build_pes(payload: bytes, pts: int) -> bytes:
    """Wrap a KLV unit in a private_stream_1 (0xBD) PES packet with PTS."""
    body = bytes([0x80, 0x80, 0x05]) + _encode_pts(pts) + payload
    return b"\x00\x00\x01\xBD" + struct.pack(">H", len(body)) + body


def _packetize_pes(pid: int, pes: bytes, pcr: int, cc: int, with_pcr: bool = True):
    """Split a PES into 188-byte TS packets (optional PCR in the first one)."""
    out = bytearray()
    data = pes
    first = True
    while data or first:
        pkt = bytearray([0x47, ((0x40 if first else 0x00) | ((pid >> 8) & 0x1F)), pid & 0xFF])
        if first and with_pcr:
            # Adaptation field with PCR + stuffing to fit the payload exactly
            payload_space = 184 - 1 - 7  # 1 AFL byte + (flags+PCR = 7)
            chunk = data[:payload_space]
            stuffing = payload_space - len(chunk)
            afl = 7 + stuffing
            pkt.append(0x30 | (cc & 0x0F))
            pkt.append(afl)
            pkt.append(0x10)               # PCR_flag
            pkt += _encode_pcr(pcr)
            pkt += b"\xFF" * stuffing
            pkt += chunk
            data = data[len(chunk):]
        elif len(data) >= 184:
            pkt.append(0x10 | (cc & 0x0F))
            pkt += data[:184]
            data = data[184:]
        else:
            # Last packet: pad with an adaptation field of stuffing
            pkt.append(0x30 | (cc & 0x0F))
            afl = 183 - len(data)
            pkt.append(afl)
            if afl > 0:
                pkt.append(0x00)           # no flags
                pkt += b"\xFF" * (afl - 1)
            pkt += data
            data = b""
        cc = (cc + 1) & 0x0F
        first = False
        out += bytes(pkt)
    return bytes(out), cc


# ===========================================================================
# 2. KLV PID INJECTION INTO AN EXISTING TS  (per-packet PTS, in Python)
# ===========================================================================
# When COPYING a KLV stream, FFmpeg drops the PTS (it treats it as asynchronous).
# So we don't let FFmpeg touch the KLV: FFmpeg only produces the video/audio TS
# and here, in Python, we insert a new PID with the KLV packets and their PTS,
# rewriting the PMT to advertise it as synchronous KLV metadata.

def _pid_of(pkt: bytes) -> int:
    return ((pkt[1] & 0x1F) << 8) | pkt[2]


def _read_pcr(pkt: bytes):
    """Return the PCR base (90 kHz) of a TS packet, or None if it has none."""
    afc = (pkt[3] >> 4) & 0x03
    if afc in (2, 3) and pkt[4] > 0 and (pkt[5] & 0x10):
        b = pkt[6:12]
        return (b[0] << 25) | (b[1] << 17) | (b[2] << 9) | (b[3] << 1) | (b[4] >> 7)
    return None


def _parse_pat_pmt_pid(pkt: bytes):
    """Return the PMT PID from a PAT packet."""
    ptr = pkt[4]
    t = pkt[5 + ptr:]
    section_length = ((t[1] & 0x0F) << 8) | t[2]
    section = t[3:3 + section_length]
    entries = section[5:section_length - 4]   # after tsid/ver/sec/last
    for i in range(0, len(entries), 4):
        program = (entries[i] << 8) | entries[i + 1]
        pid = ((entries[i + 2] & 0x1F) << 8) | entries[i + 3]
        if program != 0:
            return pid
    return None


def _merged_pmt_table(pmt_pkt: bytes, klv_pid: int) -> bytes:
    """Rebuild the PMT table adding the KLV ES (stream_type 0x15)."""
    meta_desc = bytes([0x26, 0x09, 0x01, 0x00, 0xFF]) + b"KLVA" + bytes([0x00, 0x00])
    meta_std = bytes([0x27, 0x09, 0xC0, 0x00, 0x00, 0xC0, 0x00, 0x00, 0xC0, 0x00, 0x00])
    desc = meta_desc + meta_std
    new_es = (bytes([0x15]) + struct.pack(">H", 0xE000 | (klv_pid & 0x1FFF))
              + struct.pack(">H", 0xF000 | (len(desc) & 0x0FFF)) + desc)

    ptr = pmt_pkt[4]
    t = pmt_pkt[5 + ptr:]
    section_length = ((t[1] & 0x0F) << 8) | t[2]
    section = t[3:3 + section_length]
    body = section[:-4]                        # program..last ES (without CRC)
    new_body = body + new_es
    new_len = len(new_body) + 4
    table = bytes([0x02, 0xB0 | ((new_len >> 8) & 0x0F), new_len & 0xFF]) + new_body
    return table + struct.pack(">I", _crc32_mpeg(table))


def _all_pids(pkts) -> set:
    return {_pid_of(p) for p in pkts if len(p) == 188 and p[0] == 0x47}


def inject_klv_into_ts(video_ts: str, packets, out_ts: str) -> str:
    """Insert a timed KLV PID (PTS at 90 kHz) into a video/audio TS."""
    with open(video_ts, "rb") as fh:
        raw = fh.read()
    pkts = [raw[i:i + 188] for i in range(0, len(raw), 188)]

    pmt_pid = None
    for p in pkts:
        if _pid_of(p) == 0x0000 and (p[1] & 0x40):
            pmt_pid = _parse_pat_pmt_pid(p)
            break
    if pmt_pid is None:
        raise RuntimeError("PMT not found in the video TS.")

    used = _all_pids(pkts)
    klv_pid = next(pid for pid in range(0x0100, 0x1FFE) if pid not in used and pid != pmt_pid)

    new_pmt_table = None
    for p in pkts:
        if _pid_of(p) == pmt_pid and (p[1] & 0x40):
            new_pmt_table = _merged_pmt_table(p, klv_pid)
            break

    # Pre-build the KLV PES packets (one per sample) with their PTS
    klv_items = []
    for t_rel, kdata in packets:
        pts = int(round(t_rel * 90000)) & 0x1FFFFFFFF
        klv_items.append((t_rel, _build_pes(kdata, pts)))

    out = bytearray()
    klv_cc = 0
    ki = 0
    last_t = 0.0
    for p in pkts:
        if len(p) != 188 or p[0] != 0x47:
            continue
        pcr = _read_pcr(p)
        if pcr is not None:
            last_t = pcr / 90000.0
        if _pid_of(p) == pmt_pid and (p[1] & 0x40):
            payload = b"\x00" + new_pmt_table
            p = bytes([0x47, p[1], p[2], 0x10 | (p[3] & 0x0F)]) + payload
            p = p + b"\xFF" * (188 - len(p))
        # Insert the KLV packets whose PTS has already arrived (per the video PCR)
        while ki < len(klv_items) and klv_items[ki][0] <= last_t:
            pts = int(round(klv_items[ki][0] * 90000))
            chunk, klv_cc = _packetize_pes(klv_pid, klv_items[ki][1], pts, klv_cc, with_pcr=False)
            out += chunk
            ki += 1
        out += p

    while ki < len(klv_items):                 # flush the remaining KLV packets
        pts = int(round(klv_items[ki][0] * 90000))
        chunk, klv_cc = _packetize_pes(klv_pid, klv_items[ki][1], pts, klv_cc, with_pcr=False)
        out += chunk
        ki += 1

    with open(out_ts, "wb") as fh:
        fh.write(bytes(out))
    return out_ts


# ===========================================================================
# 3. MUXING WITH FFMPEG  (FFmpeg makes the video/audio TS; Python adds the KLV)
# ===========================================================================
def _resolve_ffmpeg(ffmpeg_bin=None):
    """Return a usable ffmpeg path. Prefer the explicit one, then the PATH."""
    if ffmpeg_bin and os.path.isfile(ffmpeg_bin):
        return ffmpeg_bin
    found = shutil.which("ffmpeg")
    if found:
        return found
    if ffmpeg_bin:
        # Last resort: trust the provided name even if not found by isfile
        return ffmpeg_bin
    raise RuntimeError("'ffmpeg' not found (PATH or plugin configuration).")


def _no_window_kwargs():
    """Avoid a flashing console window on Windows when spawning ffmpeg."""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return {"startupinfo": startupinfo, "creationflags": creationflags}


def mux_with_ffmpeg(video_path: str, packets, out_path: str, ffmpeg_bin=None) -> None:
    ffmpeg = _resolve_ffmpeg(ffmpeg_bin)

    tmp_ts = os.path.splitext(out_path)[0] + ".video.ts"
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-map", "0:v", "-map", "0:a?",
        "-c", "copy",
        "-muxpreload", "0", "-muxdelay", "0",
        "-f", "mpegts",
        tmp_ts,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         **_no_window_kwargs())
    if res.returncode != 0:
        err = (res.stderr or b"").decode("utf-8", "replace")[-800:]
        raise RuntimeError("ffmpeg failed to create the video/audio TS.\n" + err)

    inject_klv_into_ts(tmp_ts, packets, out_path)
    try:
        os.remove(tmp_ts)
    except OSError:
        pass


# ===========================================================================
# 4. MAIN  (CLI, kept for standalone use / debugging)
# ===========================================================================
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a MISB/STANAG 4609 video (video + audio + KLV) with FFmpeg.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--video", help="DJI video path (.mp4). Required unless --klv-only")
    parser.add_argument("--csv", required=True, help="DJI telemetry CSV")
    parser.add_argument("--out", default=None,
                        help="MPEG-TS output (.ts). Default: <video_name>_MISB.ts. "
                             "Required when using --klv-only without --video")
    parser.add_argument("--all-rows", action="store_true",
                        help="Don't filter by CUSTOM.isVideo=Recording (use all rows)")
    parser.add_argument("--klv-only", action="store_true",
                        help="Only generate the .klv stream (no muxing)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.csv):
        print(f"[ERROR] CSV does not exist: {args.csv}", file=sys.stderr)
        return 2

    if not args.klv_only and not args.video:
        print("[ERROR] --video is required (or use --klv-only to only build the .klv).",
              file=sys.stderr)
        return 2

    if args.out is None:
        if not args.video:
            print("[ERROR] --out is required when using --klv-only without --video.",
                  file=sys.stderr)
            return 2
        args.out = default_output(args.video)

    print(f"[1/2] Generating ST0601 KLV from {args.csv} ...")
    packets = build_klv_packets(args.csv, only_recording=not args.all_rows)
    dur = packets[-1][0] - packets[0][0]
    print(f"      {len(packets)} KLV packets  (~{dur:.1f}s, "
          f"{len(packets) / dur if dur else 0:.1f} Hz)")

    if args.klv_only:
        klv_path = os.path.splitext(args.out)[0] + ".klv"
        write_klv_stream(packets, klv_path)
        print(f"      KLV stream written to {klv_path}")
        return 0

    if not os.path.isfile(args.video):
        print(f"[ERROR] Video does not exist: {args.video}", file=sys.stderr)
        print("        (use --klv-only if you only want to generate the .klv)")
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    print(f"[2/2] Muxing (ffmpeg) -> {args.out} ...")
    mux_with_ffmpeg(args.video, packets, args.out)

    print(f"\n[OK] MISB video created: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
