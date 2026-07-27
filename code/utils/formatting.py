# -*- coding: utf-8 -*-
"""Shared formatting utilities for QGISFMV."""

from datetime import datetime


def format_length(meters):
    """Format a distance in meters as a human-readable string (m or km)."""
    try:
        meters = float(meters)
    except (TypeError, ValueError):
        return "\u2014"
    if meters >= 1000.0:
        return f"{meters / 1000.0:.2f} km"
    return f"{meters:.1f} m"


def format_area(area_m2):
    """Format an area in square meters as a human-readable string (m2, ha, or km2)."""
    try:
        area_m2 = float(area_m2)
    except (TypeError, ValueError):
        return "\u2014"
    if area_m2 >= 1_000_000.0:
        return f"{area_m2 / 1_000_000.0:.2f} km\u00b2"
    if area_m2 >= 10_000.0:
        return f"{area_m2 / 10_000.0:.2f} ha"
    return f"{area_m2:.1f} m\u00b2"


def time_to_seconds(date_str):
    """Convert time string ``HH:MM:SS.ffffff`` to seconds."""
    timeval = datetime.strptime(date_str, "%H:%M:%S.%f")
    return (
        timeval.hour * 3600
        + timeval.minute * 60
        + timeval.second
        + timeval.microsecond / 1e6
    )


def seconds_to_time(sec):
    """Convert seconds to ``HH:MM:SS`` string."""
    hours, remainder = divmod(int(sec), 3600)
    minutes, seconds = divmod(remainder, 60)
    return "%02d:%02d:%02d" % (hours, minutes, seconds)
