"""Filesystem resource paths for plugin icons.

``player/``, ``misc/``, ``status/``, ``export/``, etc.

Resources are loaded directly from the filesystem because compiled Qt
resources are no longer supported in Qt6.
"""

from pathlib import Path


# Plugin root directory
_PLUGIN_DIR = Path(__file__).resolve().parent.parent.parent

# Physical directory containing the plugin images
_IMAGES_DIR = _PLUGIN_DIR / "images"


def r(*parts):
    """Build an absolute filesystem path from path segments."""
    return str(_IMAGES_DIR.joinpath(*parts))


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