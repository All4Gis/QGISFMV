# -*- coding: utf-8 -*-
"""
Advanced visual regression tests for QGIS FMV.

Tests specific UI scenarios:
- Opening/closing dialogs
- Toggling overlays
- Drawing tools
- Filter activation
- Metadata panel

Each test captures a screenshot and compares against a baseline.
First run creates baselines; subsequent runs compare.

Run inside QGIS::

    import pytest; pytest.main(["-xvs", "QGISFMV/tests/test_visual_regression.py"])
"""

import os
import sys
import pytest

_qgis_available = False
try:
    from qgis.core import QgsApplication
    _qgis_available = QgsApplication.instance() is not None
except ImportError:
    pass

pytestmark = pytest.mark.skipif(
    not _qgis_available,
    reason="QGIS runtime not available"
)


@pytest.fixture
def harness():
    from QGISFMV.tests.gui_test_harness import GUITestHarness
    h = GUITestHarness()
    h.start()
    yield h
    h.stop()


class TestManagerVisual:
    """Manager dock visual regression."""

    def test_manager_default(self, harness):
        """Manager in its default state."""
        harness.screenshot("vis_manager_default")
        harness.assert_screenshot_matches("vis_manager_default")

    def test_manager_with_selection(self, harness):
        """Manager with a row selected (if any rows exist)."""
        mgr = harness.get_manager()
        table = harness.find_widget("VManager", parent=mgr)
        if table is None or table.rowCount() == 0:
            pytest.skip("No rows in manager")
        table.selectRow(0)
        harness.process_events_for(0.5)
        harness.screenshot("vis_manager_selected")
        harness.assert_screenshot_matches("vis_manager_selected")


class TestPlayerVisual:
    """Player window visual regression."""

    def test_player_default(self, harness):
        """Player in its default state (no video loaded)."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        harness.screenshot("vis_player_default")
        harness.assert_screenshot_matches("vis_player_default")

    def test_player_controls_visible(self, harness):
        """Player control buttons should be visible."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        for btn_name in ["btn_play", "btn_stop", "btn_volume"]:
            btn = harness.find_widget(btn_name, parent=player)
            if btn is not None:
                assert btn.isVisible(), f"{btn_name} should be visible"

    def test_player_slider_range(self, harness):
        """Duration slider should have a valid range."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        slider = harness.find_widget("sliderDuration", parent=player)
        if slider is not None:
            assert slider.maximum() >= 0, "Slider maximum should be ≥ 0"


class TestToolbarVisual:
    """Drawing toolbar visual regression."""

    def test_toolbar_exists(self, harness):
        """Player should have a DrawToolBar."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        toolbar = harness.find_widget("DrawToolBar", parent=player)
        assert toolbar is not None, "DrawToolBar not found"
        harness.screenshot("vis_toolbar")
        harness.assert_screenshot_matches("vis_toolbar")

    def test_toolbar_has_actions(self, harness):
        """DrawToolBar should have drawing actions."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        toolbar = harness.find_widget("DrawToolBar", parent=player)
        if toolbar is not None:
            actions = toolbar.actions()
            assert len(actions) >= 5, f"Toolbar should have ≥5 actions, got {len(actions)}"


class TestOverlayVisual:
    """C2 overlay visual regression."""

    def test_sensor_cone_toggle(self, harness):
        """Toggling Sensor Cone should not crash."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        action = harness.find_action("actionToggle_SensorCone", parent=player)
        if action is None:
            pytest.skip("Sensor Cone action not found")
        action.setChecked(True)
        harness.process_events_for(1.0)
        harness.screenshot("vis_sensor_cone_on")
        harness.assert_screenshot_matches("vis_sensor_cone_on")
        action.setChecked(False)
        harness.process_events_for(0.5)

    def test_distance_rings_toggle(self, harness):
        """Toggling Distance Rings should not crash."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        action = harness.find_action("actionToggle_DistanceRings", parent=player)
        if action is None:
            pytest.skip("Distance Rings action not found")
        action.setChecked(True)
        harness.process_events_for(1.0)
        harness.screenshot("vis_distance_rings_on")
        harness.assert_screenshot_matches("vis_distance_rings_on")
        action.setChecked(False)
        harness.process_events_for(0.5)


class TestFilterVisual:
    """Video filter visual regression."""

    def test_filter_actions_exist(self, harness):
        """All filter actions should exist in the player."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        filter_actions = [
            "actionGray", "actionInvert_Color", "actionMono_Filter",
            "actionCanny_edge_detection", "actionAuto_Contrast_Filter",
            "actionMirroredH", "actionBrightness_Contrast",
        ]
        for name in filter_actions:
            action = harness.find_action(name, parent=player)
            assert action is not None, f"Filter action '{name}' not found"
            assert action.isCheckable(), f"Filter action '{name}' should be checkable"
