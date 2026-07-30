# -*- coding: utf-8 -*-
"""Drawing-tool toggles: magnifier, stamp, drawers, measures, military symbols."""

from qgis.PyQt.QtCore import Qt

from QGISFMV.utils.media.QgsFmvMultimedia import PausedState, PlayingState, StoppedState
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.video.playback.QgsVideoState import MOUSE_MOVE_EVENT


class DrawToolsController:
    """Own mutually-exclusive draw-tool toggles and measure/military helpers."""

    _UNCHECKABLE_TOOLS = [
        "actionMagnifying_glass",
        "actionDraw_Pinpoint",
        "actionDraw_Line",
        "actionDraw_Polygon",
        "actionObject_Tracking",
        "actionMeasureDistance",
        "actionMeasureArea",
        "actionCensure",
        "actionStamp",
        "actionMilitary_Symbols",
    ]

    def __init__(self, player):
        self.player = player

    def _setupMilitarySymbolTool(self):
        """Wire military symbol picker dialog (toolbar action is in ui_FmvPlayer.ui)."""
        from QGISFMV.player.dialogs.QgsFmvMilitarySymbols import MilitarySymbolDialog

        player = self.player
        player._milSymbolDialog = MilitarySymbolDialog(player)
        player._milSymbolDialog.symbolSelected.connect(self._onMilitarySymbolSelected)
        player._milSymbolDialog.focusVideoRequested.connect(
            self._focusVideoForMilitarySymbol
        )
        player._milSymbolDialog.placementFinished.connect(
            self._finishMilitarySymbolPlacement
        )
        player._milSymbolDialog.btn_removeLast.clicked.connect(
            self._removeLastMilitarySymbol
        )
        player._milSymbolDialog.btn_removeAll.clicked.connect(
            self._removeAllMilitarySymbols
        )

    def magnifier(self, value):
        """Magnifier Glass Utils"""
        player = self.player
        self.UncheckUtils(player.sender(), value)
        player.videoWidget.SetMagnifier(value)
        player.videoWidget.UpdateSurface()

    def stamp(self, value):
        """Stamp Utils"""
        player = self.player
        self.UncheckUtils(player.sender(), value)
        player.videoWidget.SetStamp(value)
        player.videoWidget.UpdateSurface()

    def pointDrawer(self, value):
        """Draw Point"""
        player = self.player
        self.UncheckUtils(player.sender(), value)
        player.videoWidget.SetPointDrawer(value)
        player.videoWidget.UpdateSurface()

    def militarySymbolDrawer(self, value):
        """Place military symbols on the georeferenced video."""
        player = self.player
        self.UncheckUtils(player.sender(), value)
        dialog = getattr(player, "_milSymbolDialog", None)
        if value and dialog is not None:
            from QGISFMV.utils.core.QgsFmvUtils import GetGCPGeoTransform

            symbol_id, unit_name = dialog.current_symbol()
            player.videoWidget.setSelectedMilitarySymbol(symbol_id, unit_name)
            dialog.set_georeferenced(GetGCPGeoTransform() is not None)
            dialog.set_placed_count(len(player.videoWidget.drawMilSymbols))
            dialog.show()
            dialog.raise_()
            player.videoWidget.setFocus(Qt.FocusReason.OtherFocusReason)
        elif dialog is not None:
            dialog.hide()
        player.videoWidget.SetMilitarySymbolDrawer(value)
        player.videoWidget.UpdateSurface()

    def _finishMilitarySymbolPlacement(self):
        player = self.player
        if hasattr(player, "actionMilitary_Symbols"):
            player.actionMilitary_Symbols.setChecked(False)
        player.videoWidget.SetMilitarySymbolDrawer(False)
        player.videoWidget.UpdateSurface()

    def _removeLastMilitarySymbol(self):
        player = self.player
        player.videoWidget.removeLastMilitarySymbol()
        dialog = getattr(player, "_milSymbolDialog", None)
        if dialog is not None:
            dialog.set_placed_count(len(player.videoWidget.drawMilSymbols))

    def _removeAllMilitarySymbols(self):
        player = self.player
        player.videoWidget.removeAllMilitarySymbols()
        dialog = getattr(player, "_milSymbolDialog", None)
        if dialog is not None:
            dialog.set_placed_count(0)

    def _onMilitarySymbolSelected(self, symbol_id, unit_name):
        player = self.player
        player.videoWidget.setSelectedMilitarySymbol(symbol_id, unit_name)
        dialog = getattr(player, "_milSymbolDialog", None)
        if dialog is not None:
            from QGISFMV.utils.core.QgsFmvUtils import GetGCPGeoTransform

            dialog.set_georeferenced(GetGCPGeoTransform() is not None)

    def _focusVideoForMilitarySymbol(self):
        player = self.player
        player.videoWidget.setFocus(Qt.FocusReason.OtherFocusReason)
        player.videoWidget.flashMilitarySymbolPlacementHint()

    def _refreshMilSymbolPlacedCount(self):
        player = self.player
        dialog = getattr(player, "_milSymbolDialog", None)
        if dialog is not None:
            dialog.set_placed_count(len(player.videoWidget.drawMilSymbols))

    def lineDrawer(self, value):
        """Draw Line"""
        player = self.player
        self.UncheckUtils(player.sender(), value)
        player.videoWidget.SetLineDrawer(value)
        player.videoWidget.UpdateSurface()

    def polygonDrawer(self, value):
        """Draw Polygon"""
        player = self.player
        self.UncheckUtils(player.sender(), value)
        player.videoWidget.SetPolygonDrawer(value)
        player.videoWidget.UpdateSurface()

    def objectTracking(self, value):
        """Object Tracking
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        player.videoWidget.rubbers.track_canvas.reset()

        self.UncheckUtils(player.sender(), value)
        if value:
            player.ensurePlaying()
            if player.player.playbackRate() != player.playbackRateSlow:
                player.sdv = player.player.position()
                player.player.setPlaybackRate(player.playbackRateSlow)
        elif player.player.playbackRate() == player.playbackRateSlow:
            player.player.setPlaybackRate(1.0)

        player.videoWidget.SetObjectTracking(value)
        player.videoWidget.update()

    def VideoMeasureDistance(self, value):
        """Video Measure Distance
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        self.CommonPauseTool(value)
        player.videoWidget.UpdateSurface()

        player.toolBtn_Measure.setDefaultAction(player.actionMeasureDistance)
        self.UncheckUtils(player.sender(), value)
        # Exclusive vs area (UncheckUtils already clears drawers; enforce flag).
        if value:
            player.videoWidget.SetMeasureArea(False)
        player.videoWidget.SetMeasureDistance(value)
        player.staticDraw = value

    def VideoMeasureArea(self, value):
        """Video Measure Area
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        self.CommonPauseTool(value)
        player.videoWidget.UpdateSurface()

        player.toolBtn_Measure.setDefaultAction(player.actionMeasureArea)
        self.UncheckUtils(player.sender(), value)
        if value:
            player.videoWidget.SetMeasureDistance(False)
        player.videoWidget.SetMeasureArea(value)
        player.staticDraw = value

    def _removeLastMeasurePoint(self, draw_list, sync_fn):
        """Remove last measurement point from *draw_list* and sync to map."""
        if not draw_list:
            return
        # Remove trailing mouseMoveEvent entry if present
        if draw_list[-1][-1] == MOUSE_MOVE_EVENT:
            draw_list.pop()
        if draw_list:
            draw_list.pop()
        sync_fn()
        self.player.videoWidget.UpdateSurface()

    def removeLastMeasureDistance(self):
        """Remove last distance measurement point."""
        player = self.player
        self._removeLastMeasurePoint(
            player.videoWidget.drawMeasureDistance,
            player.videoWidget._syncMeasureDistanceMap,
        )

    def removeAllMeasureDistance(self):
        """Remove all distance measurements."""
        player = self.player
        player.videoWidget.ResetDrawMeasureDistance()
        player.videoWidget.UpdateSurface()

    def removeLastMeasureArea(self):
        """Remove last area measurement point."""
        player = self.player
        self._removeLastMeasurePoint(
            player.videoWidget.drawMeasureArea,
            player.videoWidget._syncMeasureAreaMap,
        )

    def removeAllMeasureArea(self):
        """Remove all area measurements."""
        player = self.player
        player.videoWidget.ResetDrawMeasureArea()
        player.videoWidget.UpdateSurface()

    def VideoHandDraw(self, value):
        """Video Free Hand Draw
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        player.videoWidget.SetHandDraw(value)
        self.CommonPauseTool(value)
        player.videoWidget.UpdateSurface()

    def CommonPauseTool(self, value):
        """Static draw common function
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        qgsu.showUserAndLogMessage("", "CommonPauseTool:" + str(value), onlyLog=True)
        if value:
            if player.playerState == PlayingState:
                player.playbackController.pauseAt(player.player.position())
                player.btn_play.setIcon(player.playIcon)
                player.videoWidget.update()
        else:
            if player.playerState in (StoppedState, PausedState):
                player.player.play()
                player.btn_play.setIcon(player.pauseIcon)

    def VideoCensure(self, value):
        """Censure Video Parts
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        self.UncheckUtils(player.sender(), value)
        player.videoWidget.SetCensure(value)
        player.videoWidget.UpdateSurface()

    def UncheckUtils(self, sender, value):
        """Uncheck Utils Video
        @type value: bool
        @param value: Button checked state
        """
        player = self.player
        for name in self._UNCHECKABLE_TOOLS:
            action = getattr(player, name, None)
            if action is None or action is sender:
                continue
            # Block signals so sibling tools do not re-enter their slots
            # (e.g. MeasureArea(False) must not resume playback while
            # MeasureDistance is being activated).
            action.blockSignals(True)
            action.setChecked(False)
            action.blockSignals(False)

        dialog = getattr(player, "_milSymbolDialog", None)
        if dialog is not None:
            dialog.hide()

        player.videoWidget.RestoreDrawer()

        if (
            not value
            and sender is not None
            and player.player.playbackRate() == player.playbackRateSlow
            and sender.objectName() == "actionObject_Tracking"
            and not player.videoWidget._filterSatate.hasFiltersSlow()
        ):
            player.sdv = player.player.position()
            player.player.setPlaybackRate(1.0)

        if sender is not None:
            sender.blockSignals(True)
            sender.setChecked(value)
            sender.blockSignals(False)

    def UncheckFilters(self, sender, value):
        """Uncheck Filters Video"""
        self.player.filterManager.uncheckFilters(sender, value)

    def RemoveMeasures(self):
        """Remove video measurements"""
        player = self.player
        # Remove Measure when video is playing
        # Uncheck Measure Distance
        player.videoWidget.ResetDrawMeasureDistance()
        player.actionMeasureDistance.setChecked(False)
        player.videoWidget.SetMeasureDistance(False)
        # Uncheck Measure Area
        player.videoWidget.ResetDrawMeasureArea()
        player.actionMeasureArea.setChecked(False)
        player.videoWidget.SetMeasureArea(False)

        player.staticDraw = False
