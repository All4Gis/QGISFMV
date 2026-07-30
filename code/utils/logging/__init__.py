# -*- coding: utf-8 -*-
"""
Centralized logging for QGIS FMV (stdlib ``logging`` — no extra pip package).

Usage::

    from QGISFMV.utils.logging import log
    log.info("video loaded")
    log.error("parse failed", exc_info=True)

Rotating file: ``~/.qgis-fmv/logs/qgis_fmv.log`` (10 MB × 5).
Console (WARNING+): QGIS Log Messages panel via stderr.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys

__all__ = ["log"]

log = logging.getLogger("qgis_fmv")
log.setLevel(logging.DEBUG)

if not log.handlers:
    _fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")

    try:
        _log_dir = os.path.join(os.path.expanduser("~"), ".qgis-fmv", "logs")
        os.makedirs(_log_dir, exist_ok=True)
        _fh = logging.handlers.RotatingFileHandler(
            os.path.join(_log_dir, "qgis_fmv.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        _fh.setFormatter(_fmt)
        _fh.setLevel(logging.DEBUG)
        log.addHandler(_fh)
    except Exception as _exc:
        print(
            "[QGISFMV] Warning: could not create log file: {}".format(_exc),
            file=sys.stderr,
        )

    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)
    _ch.setLevel(logging.WARNING)
    log.addHandler(_ch)

    log.info("----------------- Start Log -----------------")
