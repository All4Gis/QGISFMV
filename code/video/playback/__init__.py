# -*- coding: utf-8 -*-
"""OpenCV video widget, surface, state, and utilities."""

from QGISFMV.video.playback.QgsVideoState import FilterState, InteractionState, MOUSE_MOVE_EVENT

__all__ = [
    "VideoWidget",
    "VideoSinkSurface",
    "FilterState",
    "InteractionState",
    "MOUSE_MOVE_EVENT",
    "VideoUtils",
]


def __getattr__(name):
    if name == "VideoWidget":
        from QGISFMV.video.playback.QgsVideo import VideoWidget

        return VideoWidget
    if name == "VideoSinkSurface":
        from QGISFMV.video.playback.QgsVideoSurface import VideoSinkSurface

        return VideoSinkSurface
    if name == "VideoUtils":
        from QGISFMV.video.playback.QgsVideoUtils import VideoUtils

        return VideoUtils
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
