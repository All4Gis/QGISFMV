# -*- coding: utf-8 -*-
"""Manages video filter toggles, unchecking other filters when one is activated."""

from QGISFMV.video.filters.QgsBrightnessContrast import BrightnessContrastDialog

# Filter name -> (widget method name, description) for the 20+ trivial _setFilter calls.
_FILTER_DISPATCH = {
    "grayFilter": ("SetGray", "Gray Video Filter"),
    "MirrorHorizontalFilter": ("SetMirrorH", "Mirror Horizontal Video Filter"),
    "edgeFilter": ("SetEdgeDetection", "Edge Detection Video Filter"),
    "invertColorFilter": ("SetInvertColor", "Invert Color Video Filter"),
    "autoContrastFilter": ("SetAutoContrastFilter", "Auto Contrast Video Filter"),
    "monoFilter": ("SetMonoFilter", "Filter Mono Video"),
    "claheFilter": ("claheFilter", "CLAHE adaptive contrast filter"),
    "sharpenFilter": ("sharpenFilter", "Sharpen (unsharp mask) filter"),
    "sobelFilter": ("sobelFilter", "Sobel edge detection filter"),
    "roadEnhanceFilter": ("roadEnhanceFilter", "Road & structure enhancement filter"),
    "motionDetectionFilter": ("motionDetectionFilter", "Motion detection filter"),
    "backgroundSubtractionFilter": (
        "backgroundSubtractionFilter",
        "Background subtraction (MOG2) filter",
    ),
    "hotspotFilter": ("hotspotFilter", "Hotspot detection filter"),
    "falseColorFilter": ("falseColorFilter", "False color (Turbo LUT) filter"),
    "exgFilter": ("exgFilter", "Excess Green (ExG = 2G − R − B) filter"),
    "exrFilter": ("exrFilter", "Excess Red (ExR = 1.4R − G) filter"),
    "variFilter": ("variFilter", "VARI vegetation index filter"),
    "dehazeFilter": ("dehazeFilter", "Dehaze (CLAHE enhancement) filter"),
    "nrviFilter": ("nrviFilter", "NRVI vegetation index (RGB approx) filter"),
    "buildingDetectionFilter": (
        "buildingDetectionFilter",
        "Building Segmentation (classical CV) filter",
    ),
    "roadSegmentationFilter": (
        "roadSegmentationFilter",
        "Road Segmentation (classical CV) filter",
    ),
    "vehicleSegmentationFilter": (
        "vehicleSegmentationFilter",
        "Vehicle Segmentation filter",
    ),
    "personSegmentationFilter": (
        "personSegmentationFilter",
        "Person Segmentation filter",
    ),
    "fireDetectionFilter": ("fireDetectionFilter", "Fire Segmentation filter"),
    "smokeDetectionFilter": ("smokeDetectionFilter", "Smoke Segmentation filter"),
    "floodDetectionFilter": ("floodDetectionFilter", "Flood Segmentation filter"),
}


class FilterManager:
    """Manages video filter toggles for the FMV player.

    Holds brightness/contrast dialog state and provides toggle methods
    that uncheck all other filters when one is activated.
    """

    def __init__(self, player):
        """
        Args:
            player: The QgsFmvPlayer instance (provides .videoWidget, .action*, .player).
        """
        self._player = player
        self._brightness_val = 0
        self._contrast_val = 0
        self._bc_dialog = None
        self._all_filter_actions = None

    # ── Trivial filter toggles (generated from _FILTER_DISPATCH) ──

    def toggle(self, filter_name, value):
        """Generic toggle: uncheck all other filters, then apply *filter_name*."""
        self._uncheck_filters(getattr(self._player, "_sender", None), value)
        method_name, _ = _FILTER_DISPATCH[filter_name]
        vw = self._player.videoWidget
        # Some filters use Set* methods, others use _setFilter
        if method_name.startswith("Set"):
            getattr(vw, method_name)(value)
        else:
            vw._setFilter(method_name, value)

    # ── Individual filter slot methods (connected to QAction.toggled) ──

    def grayFilter(self, value):
        self._apply_simple("SetGray", value)

    def MirrorHorizontalFilter(self, value):
        self._apply_simple("SetMirrorH", value)

    def edgeFilter(self, value):
        self._apply_simple("SetEdgeDetection", value)

    def invertColorFilter(self, value):
        self._apply_simple("SetInvertColor", value)

    def autoContrastFilter(self, value):
        self._apply_simple("SetAutoContrastFilter", value)

    def monoFilter(self, value):
        self._apply_simple("SetMonoFilter", value)

    def claheFilter(self, value):
        self._apply_setFilter("claheFilter", value)

    def sharpenFilter(self, value):
        self._apply_setFilter("sharpenFilter", value)

    def sobelFilter(self, value):
        self._apply_setFilter("sobelFilter", value)

    def roadEnhanceFilter(self, value):
        self._apply_setFilter("roadEnhanceFilter", value)

    def motionDetectionFilter(self, value):
        self._apply_setFilter("motionDetectionFilter", value)

    def backgroundSubtractionFilter(self, value):
        self._apply_setFilter("backgroundSubtractionFilter", value)

    def hotspotFilter(self, value):
        self._apply_setFilter("hotspotFilter", value)

    def falseColorFilter(self, value):
        self._apply_setFilter("falseColorFilter", value)

    def exgFilter(self, value):
        self._apply_setFilter("exgFilter", value)

    def exrFilter(self, value):
        self._apply_setFilter("exrFilter", value)

    def variFilter(self, value):
        self._apply_setFilter("variFilter", value)

    def dehazeFilter(self, value):
        self._apply_setFilter("dehazeFilter", value)

    def nrviFilter(self, value):
        self._apply_setFilter("nrviFilter", value)

    def buildingDetectionFilter(self, value):
        self._apply_setFilter("buildingDetectionFilter", value)

    def roadSegmentationFilter(self, value):
        self._apply_setFilter("roadSegmentationFilter", value)

    def vehicleSegmentationFilter(self, value):
        self._apply_setFilter("vehicleSegmentationFilter", value)

    def personSegmentationFilter(self, value):
        self._apply_setFilter("personSegmentationFilter", value)

    def fireDetectionFilter(self, value):
        self._apply_setFilter("fireDetectionFilter", value)

    def smokeDetectionFilter(self, value):
        self._apply_setFilter("smokeDetectionFilter", value)

    def floodDetectionFilter(self, value):
        self._apply_setFilter("floodDetectionFilter", value)

    # ── Brightness/Contrast special filter ──

    def brightnessContrastFilter(self, value):
        """Manual brightness/contrast filter with dialog."""
        self._uncheck_filters(getattr(self._player, "_sender", None), value)
        self._player.videoWidget.SetBrightnessContrastFilter(value)
        if value:
            self._bc_dialog = BrightnessContrastDialog(self._player)
            self._bc_dialog.brightnessChanged.connect(self.setBrightness)
            self._bc_dialog.contrastChanged.connect(self.setContrastLevel)
            self._bc_dialog.finished.connect(self._onBCDialogClosed)
            self._bc_dialog.show()
            self._player.videoWidget.SetBrightness(self._brightness_val)
            self._player.videoWidget.SetContrastLevel(self._contrast_val)
        else:
            self._closeBCDialog()

    def setBrightness(self, value):
        self._brightness_val = value
        vw = self._player.videoWidget
        if getattr(vw._filterSatate, "brightnessContrastFilter", False):
            vw.SetBrightness(value)

    def setContrastLevel(self, value):
        self._contrast_val = value
        vw = self._player.videoWidget
        if getattr(vw._filterSatate, "brightnessContrastFilter", False):
            vw.SetContrastLevel(value)

    def _onBCDialogClosed(self):
        self._bc_dialog = None
        self._player.actionBrightness_Contrast.setChecked(False)
        self._player.videoWidget.SetBrightnessContrastFilter(False)

    def _closeBCDialog(self):
        if self._bc_dialog is not None:
            self._bc_dialog.close()
            self._bc_dialog = None

    # ── Uncheck / Restore ──

    def uncheckFilters(self, sender, value):
        """Uncheck all other filter actions, then check *sender*."""
        if self._all_filter_actions is None:
            self._all_filter_actions = tuple(
                getattr(self._player, name)
                for name in (
                    "actionGray",
                    "actionInvert_Color",
                    "actionMono_Filter",
                    "actionCanny_edge_detection",
                    "actionAuto_Contrast_Filter",
                    "actionMirroredH",
                    "actionBrightness_Contrast",
                    "actionCLAHE",
                    "actionSharpen",
                    "actionSobel",
                    "actionRoad_Enhance",
                    "actionMotion_Detection",
                    "actionBackground_Subtraction",
                    "actionHotspot",
                    "actionFalse_Color",
                    "actionExG",
                    "actionExR",
                    "actionVARI",
                    "actionNRVI",
                    "actionDehaze",
                    "actionBuilding_Detection",
                    "actionRoad_Segmentation",
                    "actionVehicle_Segmentation",
                    "actionPerson_Segmentation",
                    "actionFire_Detection",
                    "actionSmoke_Detection",
                    "actionFlood_Detection",
                )
                if hasattr(self._player, name)
            )
        for action in self._all_filter_actions:
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)

        self._player.videoWidget.RestoreFilters()

        if sender is not None:
            sender.blockSignals(True)
            sender.setChecked(value)
            sender.blockSignals(False)

    def restoreFilters(self):
        """Remove and restore all video filters."""
        self._player.videoWidget.RestoreFilters()

    def resetState(self):
        """Reset filter state (call on video close/switch)."""
        self._brightness_val = 0
        self._contrast_val = 0
        self._closeBCDialog()

    # ── Internal helpers ──

    def _apply_simple(self, method_name, value):
        """Apply a filter via a Set* method on videoWidget."""
        self._uncheck_filters(getattr(self._player, "_sender", None), value)
        getattr(self._player.videoWidget, method_name)(value)

    def _apply_setFilter(self, filter_attr, value):
        """Apply a filter via _setFilter on videoWidget."""
        self._uncheck_filters(getattr(self._player, "_sender", None), value)
        self._player.videoWidget._setFilter(filter_attr, value)

    def _uncheck_filters(self, sender, value):
        """Delegate to uncheckFilters (kept as internal alias)."""
        self.uncheckFilters(sender, value)
