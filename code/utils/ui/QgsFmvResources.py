# -*- coding: utf-8 -*-
"""Qt resource paths for plugin icons (prefix ``:/imgFMV/images/``).

Source files are listed in ``ui/resources.qrc`` under subfolders:
``player/``, ``misc/``, ``status/``, ``export/``, etc.
"""

_PREFIX = ":/imgFMV/images"


def r(*parts):
    """Build a resource URL from path segments, e.g. ``r('misc', 'icon.png')``."""
    return f"{_PREFIX}/{'/'.join(parts)}"


# --- Plugin chrome ---
ICON_PLUGIN = r("misc", "icon.png")
ICON_OPTIONS = r("misc", "custom-options.png")
ICON_ABOUT = r("status", "Information.png")

# --- Message boxes (QgsUtils) ---
ICON_QUESTION = r("status", "Question.png")
ICON_INFORMATION = r("status", "Information.png")
ICON_WARNING = r("status", "Warning.png")
ICON_CRITICAL = r("status", "Critical.png")

# --- Player toolbar / transport ---
ICON_PLAY = r("player", "play-arrow.png")
ICON_PAUSE = r("player", "pause.png")
ICON_VOLUME = r("player", "volume_up.png")
RECORD_GIF = r("misc", "record.gif")
ICON_RECORD = r("misc", "record.png")

# --- Player actions ---
ICON_CAPTURE_FRAMES = r("misc", "capture_all_frames.png")
ICON_SCREENSHOT = r("misc", "screenshot.png")
ICON_METADATA = r("export", "show-metadata.png")
ICON_TRACKING = r("misc", "object-tracking.png")
ICON_MOSAIC = r("misc", "mosaic.png")

# --- Manager ---
ICON_DELETE = r("misc", "delete.png")

# --- PDF report ---
ICON_HEADER_LOGO = r("misc", "header_logo.png")
