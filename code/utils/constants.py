# -*- coding: utf-8 -*-
"""Project-wide named constants for QGISFMV.

Replaces magic numbers scattered across the codebase with readable,
searchable names.  Import from here instead of hard-coding values.
"""

# ── Player ────────────────────────────────────────────────────────────
SKIP_INTERVAL_MS = 10_000       # forward / rewind step (10 s)
SLOW_PLAYBACK_RATE = 0.7
MAX_VIDEOS_IN_MANAGER = 5

# ── Object tracking ───────────────────────────────────────────────────
TRACK_MAX_MISSES = 8
TRACK_TIMER_INTERVAL_MS = 100
TRACK_WEAK_THRESHOLD = 3        # misses before state becomes "weak"

# ── Detection filters – confidence overlay blending ────────────────────
CONFIDENCE_BASE_BRIGHTNESS = 0.45
CONFIDENCE_TINT_RANGE = 0.40
CONFIDENCE_TINT_INTENSITY = 0.78
