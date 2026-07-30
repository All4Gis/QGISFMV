# -*- coding: utf-8 -*-
"""Unified FFmpeg / ffprobe subprocess launcher.

All plugin code that shells out to FFmpeg should go through this module so
binary resolution, Windows ``CREATE_NO_WINDOW``, and pipe defaults stay
consistent.
"""

import os
import platform
import shutil
import subprocess

try:
    from QGISFMV.utils.logging import log
except ImportError:
    import logging

    log = logging.getLogger("qgis_fmv")

_windows = platform.system() == "Windows"
_ffmpeg_path = "ffmpeg.exe" if _windows else "ffmpeg"
_ffprobe_path = "ffprobe.exe" if _windows else "ffprobe"


def ensure_paths():
    """Refresh cached ffmpeg/ffprobe paths from settings or PATH."""
    global _ffmpeg_path, _ffprobe_path

    if (
        _ffmpeg_path
        and os.path.isfile(_ffmpeg_path)
        and _ffprobe_path
        and os.path.isfile(_ffprobe_path)
    ):
        return _ffmpeg_path, _ffprobe_path

    try:
        from QGISFMV.utils.settings.QgsFmvSettings import (
            ffmpeg_binary,
            ffprobe_binary,
        )

        ff_bin = ffmpeg_binary()
        fp_bin = ffprobe_binary()
    except Exception as exc:
        log.debug("FFmpeg settings lookup failed: %s", exc)
        ff_bin = None
        fp_bin = None

    if ff_bin and os.path.isfile(ff_bin):
        _ffmpeg_path = ff_bin
    elif not os.path.isfile(_ffmpeg_path or ""):
        found = shutil.which("ffmpeg.exe" if _windows else "ffmpeg")
        if found:
            _ffmpeg_path = found

    if fp_bin and os.path.isfile(fp_bin):
        _ffprobe_path = fp_bin
    elif not os.path.isfile(_ffprobe_path or ""):
        found = shutil.which("ffprobe.exe" if _windows else "ffprobe")
        if found:
            _ffprobe_path = found

    return _ffmpeg_path, _ffprobe_path


def ffmpeg_path():
    """Return the resolved ffmpeg binary path."""
    ensure_paths()
    return _ffmpeg_path


def ffprobe_path():
    """Return the resolved ffprobe binary path."""
    ensure_paths()
    return _ffprobe_path


def invalidate_paths():
    """Force re-resolution on next spawn (after settings change)."""
    global _ffmpeg_path, _ffprobe_path
    _ffmpeg_path = "ffmpeg.exe" if _windows else "ffmpeg"
    _ffprobe_path = "ffprobe.exe" if _windows else "ffprobe"


def _popen_kwargs(
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    bufsize=0,
):
    kwargs = {
        "stdin": stdin,
        "stdout": stdout,
        "stderr": stderr,
        "bufsize": bufsize,
        "shell": False,
    }
    if _windows:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    else:
        kwargs["close_fds"] = True
    return kwargs


def spawn(
    cmds,
    t="ffmpeg",
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    bufsize=0,
    inject_ultrafast=True,
):
    """Spawn ffmpeg or ffprobe with *cmds* (without the binary prefix).

    Parameters
    ----------
    cmds : list
        Argument list (binary is prepended).
    t : str
        ``"ffmpeg"`` or ``"probe"`` / ``"ffprobe"``.
    inject_ultrafast : bool
        When encoding with ``-c:v``, insert ``-preset ultrafast`` if missing.
    """
    ensure_paths()
    cmds = list(cmds)
    if t in ("probe", "ffprobe"):
        cmds.insert(0, _ffprobe_path)
    else:
        cmds.insert(0, _ffmpeg_path)
        if inject_ultrafast and "-c:v" in cmds and "-preset" not in cmds:
            try:
                idx = cmds.index("-c:v") + 2
                cmds.insert(idx, "-preset")
                cmds.insert(idx + 1, "ultrafast")
            except ValueError:
                pass

    return subprocess.Popen(
        cmds,
        **_popen_kwargs(stdin=stdin, stdout=stdout, stderr=stderr, bufsize=bufsize),
    )


def popen_ffmpeg(
    args,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    bufsize=0,
):
    """Spawn ffmpeg with common pipe defaults used by multimedia fallbacks."""
    ensure_paths()
    if not _ffmpeg_path or not os.path.isfile(_ffmpeg_path):
        # Allow bare name on PATH for environments that resolve at exec time.
        if not shutil.which(_ffmpeg_path):
            raise RuntimeError("FFmpeg is not configured")
    return subprocess.Popen(
        [_ffmpeg_path] + list(args),
        **_popen_kwargs(stdin=stdin, stdout=stdout, stderr=stderr, bufsize=bufsize),
    )


def available():
    """Return True when an ffmpeg binary can be resolved."""
    try:
        path, _ = ensure_paths()
        return bool(path and (os.path.isfile(path) or shutil.which(path)))
    except Exception as exc:
        log.debug("ffmpeg availability check failed: %s", exc)
        return False
