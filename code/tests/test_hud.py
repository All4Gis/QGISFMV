# -*- coding: utf-8 -*-
"""Tests for HUD overlay widget (no QGIS runtime)."""

import pytest


class TestHudOverlay:
    """Test the HudOverlay class without QGIS runtime."""

    @pytest.fixture
    def hud_class(self):
        """Import HudOverlay class without requiring QGIS."""
        try:
            from qgis.PyQt.QtWidgets import QApplication

            from QGISFMV.player.overlays.QgsFmvHud import HudOverlay

            return HudOverlay
        except ImportError:
            pytest.skip("QGIS runtime not available")

    @pytest.fixture
    def app(self):
        """Create QApplication if needed."""
        try:
            from qgis.PyQt.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            return app
        except ImportError:
            pytest.skip("QGIS runtime not available")

    def test_initial_visible_false(self, hud_class, app):
        hud = HudOverlay()
        assert hud._visible is False

    def test_toggle_sets_visible(self, hud_class, app):
        hud = HudOverlay()
        result = hud.toggle()
        assert result is True
        assert hud._visible is True

    def test_double_toggle_hides(self, hud_class, app):
        hud = HudOverlay()
        hud.toggle()
        result = hud.toggle()
        assert result is False
        assert hud._visible is False

    def test_set_timestamp(self, hud_class, app):
        hud = HudOverlay()
        hud.setTimestamp("2024-01-15 12:30:45")
        assert hud._timestamp == "2024-01-15 12:30:45"

    def test_update_from_state_none(self, hud_class, app):
        hud = HudOverlay()
        hud.updateFromState(None)
        assert hud._lat is None

    def test_update_from_state_with_values(self, hud_class, app):
        from QGISFMV.utils.core.QgsFmvUtilsState import globalVariablesState

        hud = HudOverlay()
        gv = globalVariablesState()
        gv.setSensorLatitude(40.4168)
        gv.setSensorLongitude(-3.7038)
        gv.setSensorTrueAltitude([1000.0])

        hud.updateFromState(gv)
        assert hud._lat == 40.4168
        assert hud._lon == -3.7038
        assert hud._alt == 1000.0

    def test_update_from_state_empty_altitude(self, hud_class, app):
        from QGISFMV.utils.core.QgsFmvUtilsState import globalVariablesState

        hud = HudOverlay()
        gv = globalVariablesState()
        gv.setSensorTrueAltitude([])

        hud.updateFromState(gv)
        assert hud._alt is None

    def test_set_video_size(self, hud_class, app):
        hud = HudOverlay()
        hud.setVideoSize(1920, 1080)
        assert hud._video_size == (1920, 1080)
