# -*- coding: utf-8 -*-
"""
Centralized logging for QGIS FMV.

Provides a module-level ``log`` object backed by Python's stdlib ``logging``
with a rotating file handler (~/.qgis-fmv/logs/qgis_fmv.log) and a console
handler for WARNING+ messages (visible in QGIS Log Messages panel).

Usage::

    from QGISFMV.utils.logging.QgsFmvLog import log
    log.info("video loaded")
    log.error("parse failed", exc_info=True)

The logger auto-initializes on first import — no manual ``initLogging()``
call is needed.
"""

import logging
import logging.handlers
import os

# Module-level logger — import as ``from QGISFMV.utils.logging.QgsFmvLog import log``
log = logging.getLogger("qgis_fmv")
log.setLevel(logging.DEBUG)

# Prevent duplicate handlers on re-import
if not log.handlers:
    _fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")

    # Rotating file: 10 MB × 5 backups stored in ~/.qgis-fmv/logs/
    try:
        _log_dir = os.path.join(
            os.path.expanduser("~"), ".qgis-fmv", "logs"
        )
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
    except Exception:
        pass  # non-critical — console-only fallback

    # Console handler (visible in QGIS Log Messages panel via stderr)
    _ch = logging.StreamHandler()
    _ch.setFormatter(_fmt)
    _ch.setLevel(logging.WARNING)
    log.addHandler(_ch)

    log.info("----------------- Start Log -----------------")
