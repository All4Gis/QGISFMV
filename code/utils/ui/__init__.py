# -*- coding: utf-8 -*-
"""Reusable UI helpers (messages, JSON model, plots, resources, links)."""

__all__ = ["QgsUtils"]


def __getattr__(name):
    if name == "QgsUtils":
        from QGISFMV.utils.ui.QgsUtils import QgsUtils

        return QgsUtils
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
