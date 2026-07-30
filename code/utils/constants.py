# -*- coding: utf-8 -*-
"""Project-wide named constants for QGISFMV.

Replaces magic numbers scattered across the codebase with readable,
searchable names.  Import from here instead of hard-coding values.
"""

# ── Player ────────────────────────────────────────────────────────────
SKIP_INTERVAL_MS = 10_000  # forward / rewind step (10 s)
SLOW_PLAYBACK_RATE = 0.7
MAX_VIDEOS_IN_MANAGER = 5
INSTANT_REPLAY_SEC = 3.0  # rewind on alert / sentinel
INSTANT_REPLAY_COOLDOWN_MS = 5000
CINEMATIC_FOLLOW_ALPHA = 0.28  # lerp factor for smooth map follow (0–1)
PLACE_LABEL_MIN_MOVE_M = 120.0  # re-geocode when frame-center moves this far
PLACE_LABEL_MIN_INTERVAL_MS = 8000
DETECTION_TRAIL_MAX_POINTS = 2500
TARGET_PIN_ALERT_COOLDOWN_MS = 8000  # FOV-enter alert debounce for pinned target

# ── Object tracking ───────────────────────────────────────────────────
TRACK_MAX_MISSES = 8
TRACK_TIMER_INTERVAL_MS = 100
TRACK_WEAK_THRESHOLD = 3  # misses before state becomes "weak"

# ── Detection filters – confidence overlay blending ────────────────────
CONFIDENCE_BASE_BRIGHTNESS = 0.45
CONFIDENCE_TINT_RANGE = 0.40
CONFIDENCE_TINT_INTENSITY = 0.78

# ── Live mosaic capture / blending ─────────────────────────────────────
MOSAIC_MIN_INTERVAL_SEC = 2.0
MOSAIC_MIN_MOVE_METERS = 30.0
MOSAIC_MAX_FRAME_DIMENSION = 960
MOSAIC_FEATHER_PX = 56
MOSAIC_MAX_OUTPUT_SIZE = 2048
MOSAIC_MAX_KEPT_FRAMES = 80
MOSAIC_FOOTPRINT_GROW_RATIO = 1.12
MOSAIC_FOOTPRINT_GROW_METERS = 35.0
