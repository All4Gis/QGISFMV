# -*- coding: utf-8 -*-
from enum import Enum

# Shared constant for drawing list sentinel markers
MOUSE_MOVE_EVENT = "mouseMoveEvent"


class TrackLockState(Enum):
    """Object tracking lock states."""

    IDLE = "idle"
    LOCKED = "locked"
    WEAK = "weak"
    LOST = "lost"


class InteractionState(object):
    """Tracks which drawing/measurement tool is currently active."""

    def __init__(self):
        """Initialize all interaction flags to False."""
        self.pointDrawer = False
        self.measureDistance = False
        self.measureArea = False
        self.lineDrawer = False
        self.polygonDrawer = False
        self.magnifier = False
        self.stamp = False
        self.objectTracking = False
        self.censure = False
        self.HandDraw = False
        self.militarySymbolDrawer = False

    def any_draw_active(self):
        """Return True if any drawing or measurement tool is active."""
        return (
            self.pointDrawer
            or self.polygonDrawer
            or self.lineDrawer
            or self.measureDistance
            or self.measureArea
            or self.censure
            or self.objectTracking
            or self.militarySymbolDrawer
        )

    def clear(self):
        """Reset Interaction variables"""
        self.__init__()


class FilterState(object):
    """Tracks which video filters are currently active."""

    def __init__(self):
        """Initialize all filter flags to False."""
        self.contrastFilter = False
        self.monoFilter = False
        self.MirroredHFilter = False
        self.edgeDetectionFilter = False
        self.grayColorFilter = False
        self.invertColorFilter = False
        self.brightnessContrastFilter = False
        self.claheFilter = False
        self.sharpenFilter = False
        self.motionDetectionFilter = False
        self.sobelFilter = False
        self.falseColorFilter = False
        self.exgFilter = False
        self.exrFilter = False
        self.variFilter = False
        self.nrviFilter = False
        self.backgroundSubtractionFilter = False
        self.dehazeFilter = False
        self.roadEnhanceFilter = False
        self.hotspotFilter = False
        self.buildingDetectionFilter = False
        self.roadSegmentationFilter = False
        self.vehicleSegmentationFilter = False
        self.personSegmentationFilter = False
        self.fireDetectionFilter = False
        self.smokeDetectionFilter = False
        self.floodDetectionFilter = False
        self.brightness = 0
        self.contrastLevel = 0

    def clear(self):
        """Reset Filter variables"""
        self.__init__()

    def hasFiltersSlow(self):
        """Check if video has Slow filters aplicated"""
        return any(
            (
                self.contrastFilter,
                self.edgeDetectionFilter,
                self.brightnessContrastFilter,
                self.claheFilter,
                self.sharpenFilter,
                self.sobelFilter,
                self.falseColorFilter,
                self.exgFilter,
                self.exrFilter,
                self.variFilter,
                self.nrviFilter,
                self.dehazeFilter,
                self.roadEnhanceFilter,
                self.hotspotFilter,
                self.motionDetectionFilter,
                self.backgroundSubtractionFilter,
                self.buildingDetectionFilter,
                self.roadSegmentationFilter,
                self.vehicleSegmentationFilter,
                self.personSegmentationFilter,
                self.fireDetectionFilter,
                self.smokeDetectionFilter,
                self.floodDetectionFilter,
            )
        )
