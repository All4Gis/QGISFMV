"""OpenCV video widget, surface, state, draw/track/cursor controllers, and utilities."""

__all__ = [
    "MOUSE_MOVE_EVENT",
    "FilterState",
    "InteractionState",
    "RubberBandManager",
    "TrackLockState",
    "VideoSinkSurface",
    "VideoUtils",
    "VideoWidget",
]


def __getattr__(name):
    if name == "VideoWidget":
        from QGIS_FMV.video.playback.QgsVideo import VideoWidget

        return VideoWidget
    if name == "VideoSinkSurface":
        from QGIS_FMV.video.playback.QgsVideoSurface import VideoSinkSurface

        return VideoSinkSurface
    if name == "VideoUtils":
        from QGIS_FMV.video.playback.QgsVideoUtils import VideoUtils

        return VideoUtils
    if name == "RubberBandManager":
        from QGIS_FMV.video.playback.QgsVideoRubberBands import RubberBandManager

        return RubberBandManager
    if name in (
        "FilterState",
        "InteractionState",
        "MOUSE_MOVE_EVENT",
        "TrackLockState",
    ):
        from QGIS_FMV.video.playback import QgsVideoState as _state

        return getattr(_state, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
