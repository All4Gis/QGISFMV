# -*- coding: utf-8 -*-
"""Network stream URI helpers for FMV live playback."""

import os


def isStreamUri(value):
    """Return True when *value* looks like a network media URI."""
    if not value:
        return False
    text = str(value).strip()
    if "://" not in text:
        return False
    scheme = text.split("://", 1)[0].lower()
    return scheme in ("udp", "tcp", "rtp", "rtsp", "rtmp", "http", "https")


def streamDisplayName(uri):
    """Short label for manager rows and window titles."""
    text = str(uri).strip()
    if not isStreamUri(text):
        return os.path.basename(text) or text
    scheme, rest = text.split("://", 1)
    return f"{scheme.upper()} {rest}"


def buildStreamUri(protocol, host, port, path=""):
    """Build an FFmpeg-compatible URI for UDP/TCP/RTP/RTSP sources."""
    proto = (protocol or "UDP").strip().lower()
    host = (host or "127.0.0.1").strip()
    port = str(port or "").strip()
    if not port:
        raise ValueError("Port is required")

    if proto == "udp":
        if host in ("", "0.0.0.0", "127.0.0.1", "localhost"):
            return f"udp://@:{port}"
        return f"udp://{host}:{port}"

    if proto == "tcp":
        # Passive listen — suitable for VLC "stream to TCP" or ffmpeg listeners.
        return f"tcp://{host}:{port}?listen=1"

    if proto == "rtp":
        return f"rtp://{host}:{port}"

    if proto == "rtsp":
        route = (path or "/stream").strip()
        if not route.startswith("/"):
            route = "/" + route
        auth_host = host
        return f"rtsp://{auth_host}:{port}{route}"

    return f"{proto}://{host}:{port}"


def validateStreamEndpoint(protocol, host, port):
    """Validate dialog fields before connecting."""
    if not str(port or "").strip().isdigit():
        return False, "Port must be a number."
    port_num = int(port)
    if port_num < 1 or port_num > 65535:
        return False, "Port must be between 1 and 65535."
    if protocol.upper() == "RTSP" and host.strip() == "":
        return False, "Host is required for RTSP."
    return True, ""


def vlcHintText(protocol):
    """Detailed hint shown in the open-stream dialog."""
    proto = (protocol or "UDP").upper()
    if proto == "UDP":
        return (
            "VLC: Media → Stream → Next.\n"
            "1) Destination: select UDP (127.0.0.1), enter the same port number.\n"
            "2) Transcoding Options: Profile = MPEG-TS, Encapsulation = MPEG-TS.\n"
            "3) Keep Transcode active and set Video/Audio Codec to 'Copy' "
            "(do NOT re-encode — KLV data is lost on re-encode).\n"
            "4) Click Stream to start sending.\n"
            "\n"
            "Or use FFmpeg directly from a terminal:\n"
            "ffmpeg -stream_loop -1 -re -i input.mpg -map 0 -c copy "
            "-f mpegts udp://127.0.0.1:PORT\n"
            "\n"
            "Note: KLV metadata must already exist in the source file "
            "(recorded by STANAG 4609 devices). VLC/FFmpeg cannot create KLV."
        )
    if proto == "TCP":
        return (
            "VLC: Media → Stream → Next → Destination: TCP.\n"
            "Enter: 127.0.0.1 and the port number.\n"
            "Transcoding: MPEG-TS, Video/Audio Codec = Copy.\n"
            "\n"
            "Or use FFmpeg directly:\n"
            "ffmpeg -stream_loop -1 -re -i input.mpg -map 0 -c copy "
            "-f mpegts tcp://127.0.0.1:PORT?listen=1\n"
            "\n"
            "Note: KLV is preserved only if you use stream copy, not re-encode."
        )
    if proto == "RTP":
        return (
            "VLC: Media → Stream → Next → Destination: RTP/UDP.\n"
            "Enter the same host and port as configured here.\n"
            "Transcoding: MPEG-TS, Video/Audio Codec = Copy.\n"
            "\n"
            "Or use FFmpeg directly:\n"
            "ffmpeg -stream_loop -1 -re -i input.mpg -map 0 -c copy "
            "-f rtp rtp://127.0.0.1:PORT"
        )
    if proto == "RTSP":
        return (
            "Enter the camera RTSP host, port and path (e.g. /stream).\n"
            "No VLC setup needed — FMV connects directly to the camera."
        )
    return ""
