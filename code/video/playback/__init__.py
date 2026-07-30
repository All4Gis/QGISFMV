# -*- coding: utf-8 -*-
"""OpenCV video widget, surface, state, draw/track/cursor controllers, and utilities."""

__all__ = [
    "VideoWidget",
    "VideoSinkSurface",
    "FilterState",
    "InteractionState",
    "MOUSE_MOVE_EVENT",
    "TrackLockState",
    "VideoUtils",
    "RubberBandManager",
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
    if name == "RubberBandManager":
        from QGISFMV.video.playback.QgsVideoRubberBands import RubberBandManager

        return RubberBandManager
    if name in (
        "FilterState",
        "InteractionState",
        "MOUSE_MOVE_EVENT",
        "TrackLockState",
    ):
        from QGISFMV.video.playback import QgsVideoState as _state

        return getattr(_state, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
