# -*- coding: utf-8 -*-
"""
GUI tests for QgsFmvPlayer — the video player window.

These tests open QGIS, load a video, and verify that the player UI
behaves correctly: buttons toggle, overlays appear, menus work, etc.

Run via::

    # From QGIS Python console:
    import pytest; pytest.main(["-xvs", "QGISFMV/tests/test_gui_player.py"])

    # Or via pytest (requires QGIS runtime):
    cd QGISFMV && python -m pytest tests/test_gui_player.py -v
"""

import os
import sys

import pytest

# ---------------------------------------------------------------------------
# Skip if QGIS runtime is not available
# ---------------------------------------------------------------------------
_qgis_available = False
try:
    from qgis.core import QgsApplication

    _qgis_available = QgsApplication.instance() is not None
except ImportError:
    pass

pytestmark = pytest.mark.skipif(
    not _qgis_available,
    reason="QGIS runtime not available (run inside QGIS or via qgis --code)",
)


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def harness():
    """Create and start a GUITestHarness, yield it, then tear down."""
    from QGISFMV.tests.gui_test_harness import GUITestHarness

    h = GUITestHarness()
    h.start()
    yield h
    h.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestPlayerLifecycle:
    """Verify the player window can be opened and closed."""

    def test_manager_opens(self, harness):
        """The Manager dock widget should be accessible after plugin load."""
        mgr = harness.get_manager()
        assert mgr is not None, "Manager not created"

    def test_manager_has_video_table(self, harness):
        """Manager should have a VManager table widget."""
        mgr = harness.get_manager()
        assert mgr is not None
        table = harness.find_widget("VManager", parent=mgr)
        assert table is not None, "VManager table not found"
        assert table.columnCount() >= 5, "VManager should have ≥5 columns"


class TestPlayerControls:
    """Verify player control buttons exist and are interactive."""

    def test_play_button_exists(self, harness):
        """Player should have a btn_play button."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        btn = harness.find_widget("btn_play", parent=player)
        assert btn is not None, "btn_play not found"

    def test_stop_button_exists(self, harness):
        """Player should have a btn_stop button."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        btn = harness.find_widget("btn_stop", parent=player)
        assert btn is not None, "btn_stop not found"

    def test_slider_duration_exists(self, harness):
        """Player should have a sliderDuration widget."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        slider = harness.find_widget("sliderDuration", parent=player)
        assert slider is not None, "sliderDuration not found"

    def test_volume_slider_exists(self, harness):
        """Player should have a volumeSlider widget."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        slider = harness.find_widget("volumeSlider", parent=player)
        assert slider is not None, "volumeSlider not found"


class TestPlayerMenus:
    """Verify player menu structure."""

    def test_tools_menu_exists(self, harness):
        """Player should have a menuTools menu."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        menu = harness.find_widget("menuTools", parent=player)
        assert menu is not None, "menuTools not found"

    def test_has_center_actions(self, harness):
        """Player should have Platform/Footprint/Target center actions."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        for name in [
            "actionCenter_on_Platform",
            "actionCenter_on_Footprint",
            "actionCenter_Target",
        ]:
            action = harness.find_action(name, parent=player)
            assert action is not None, f"{name} not found"


class TestPlayerOverlays:
    """Verify C2 overlay actions exist in the player."""

    def test_sensor_cone_action_exists(self, harness):
        """Player should have a Sensor Coverage Cone toggle action."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        action = harness.find_action("actionToggle_SensorCone", parent=player)
        assert action is not None, "Sensor Cone action not found"
        assert action.isCheckable(), "Sensor Cone action should be checkable"

    def test_distance_rings_action_exists(self, harness):
        """Player should have a Distance Rings toggle action."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        action = harness.find_action("actionToggle_DistanceRings", parent=player)
        assert action is not None, "Distance Rings action not found"
        assert action.isCheckable(), "Distance Rings action should be checkable"

    def test_hud_action_exists(self, harness):
        """Player should have a HUD toggle action."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open yet")
        action = harness.find_action("actionToggle_HUD", parent=player)
        assert action is not None, "HUD action not found"


class TestPlayerVisualRegression:
    """Screenshot-based visual regression tests."""

    def test_manager_screenshot(self, harness):
        """Capture the Manager dock and compare against baseline."""
        mgr = harness.get_manager()
        if mgr is None:
            pytest.skip("No manager")
        harness.screenshot("manager_default")
        match, sim = harness.assert_screenshot_matches("manager_default")
        assert match, f"Manager screenshot differs (similarity={sim:.2%})"

    def test_player_screenshot(self, harness):
        """Capture the Player window and compare against baseline."""
        player = harness.get_player()
        if player is None:
            pytest.skip("No player open")
        harness.screenshot("player_default")
        match, sim = harness.assert_screenshot_matches("player_default")
        assert match, f"Player screenshot differs (similarity={sim:.2%})"
