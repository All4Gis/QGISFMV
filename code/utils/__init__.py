"""Shared utilities for the QGIS FMV plugin."""

__all__ = ["QgsUtils", "log"]


def __getattr__(name):
    if name == "log":
        from QGIS_FMV.utils.logging import log

        return log
    if name == "QgsUtils":
        from QGIS_FMV.utils.ui.QgsUtils import QgsUtils

        return QgsUtils
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
