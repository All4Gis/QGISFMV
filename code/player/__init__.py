# -*- coding: utf-8 -*-
"""FMV video player package."""

__all__ = ["QgsFmvPlayer"]


def __getattr__(name):
    if name == "QgsFmvPlayer":
        from QGISFMV.player.QgsFmvPlayer import QgsFmvPlayer

        return QgsFmvPlayer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
