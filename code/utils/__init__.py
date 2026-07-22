# -*- coding: utf-8 -*-
"""Shared utilities for the QGIS FMV plugin."""

__all__ = ["log", "QgsUtils"]


def __getattr__(name):
    if name == "log":
        from QGISFMV.utils.logging import log

        return log
    if name == "QgsUtils":
        from QGISFMV.utils.ui.QgsUtils import QgsUtils

        return QgsUtils
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
