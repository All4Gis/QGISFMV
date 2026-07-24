# -*- coding: utf-8 -*-
"""Center-on-map action group: keep the canvas following platform/footprint/target."""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QActionGroup

from QGISFMV.utils.core.QgsFmvUtils import centerCanvasOnLayer
from QGISFMV.utils.layers.QgsFmvLayers import (
    Footprint_lyr,
    FrameCenter_lyr,
    Platform_lyr,
)


class MapCenterController:
    """Manage the center-on-platform/footprint/target action group and mode."""

    def __init__(self, player):
        self.player = player
        self._actionGroup = None

    def setup(self):
        """Wire the mutually-exclusive center actions and apply the saved mode."""
        player = self.player
        self._actionGroup = QActionGroup(player)
        self._actionGroup.setExclusive(False)
        for action in (
            player.actionCenter_on_Platform,
            player.actionCenter_on_Footprint,
            player.actionCenter_Target,
        ):
            self._actionGroup.addAction(action)
            action.setToolTip(
                action.text()
                + " — "
                + QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Keep the map following this object while playing. "
                    "Uncheck for free panning.",
                )
            )

        if player.actionCenter_on_Platform.isChecked():
            player.session.setCenterMode(1)
        elif player.actionCenter_on_Footprint.isChecked():
            player.session.setCenterMode(2)
        elif player.actionCenter_Target.isChecked():
            player.session.setCenterMode(3)
        else:
            # UI unchecked → free panning (do not keep a stale session mode).
            player.session.setCenterMode(0)

    def centerMapAction(self, checked, mode, layer_name):
        """Shared logic for center-on actions: uncheck siblings, set mode, center."""
        player = self.player
        sender = player.sender()
        for other in (
            player.actionCenter_on_Platform,
            player.actionCenter_on_Footprint,
            player.actionCenter_Target,
        ):
            if other is sender:
                continue
            # Block signals so unchecking Platform (default) does not re-enter
            # centerMapPlatform(False) and clear the newly checked action.
            other.blockSignals(True)
            other.setChecked(False)
            other.blockSignals(False)
        if checked:
            # Ensure the activated action stays checked (defensive).
            if sender is not None and not sender.isChecked():
                sender.blockSignals(True)
                sender.setChecked(True)
                sender.blockSignals(False)
            player.session.setCenterMode(mode)
            centerCanvasOnLayer(player.iface, layer_name, player._videoGroupName())
        else:
            player.session.setCenterMode(0)

    def centerMapPlatform(self, checked):
        """Center map on Platform"""
        self.centerMapAction(checked, 1, Platform_lyr)

    def centerMapFootprint(self, checked):
        """Center Map on Footprint"""
        self.centerMapAction(checked, 2, Footprint_lyr)

    def centerMapTarget(self, checked):
        """Center Map on Target (Frame Center layer)"""
        self.centerMapAction(checked, 3, FrameCenter_lyr)
