# -*- coding: utf-8 -*-
"""Real-time video filters (classic + AI/CV detection façade/pipeline/scores)."""

__all__ = [
    "VideoFilters",
    "opencv_available",
    "opencv_status_text",
    "reset_temporal_filter_state",
]

_CORE_EXPORTS = frozenset(
    {"opencv_available", "opencv_status_text", "reset_temporal_filter_state"}
)


def __getattr__(name):
    if name == "VideoFilters":
        from QGISFMV.video.filters.QgsVideoFilters import VideoFilters

        return VideoFilters
    if name in _CORE_EXPORTS:
        from QGISFMV.video.filters import QgsFmvFilterCore as _core

        return getattr(_core, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
