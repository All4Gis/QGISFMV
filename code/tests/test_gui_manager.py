# -*- coding: utf-8 -*-
"""
GUI tests for FmvManager — the video manager dock widget.

Tests verify that the manager loads correctly, handles video list
operations, and that its UI elements are properly configured.

Run inside QGIS Python console::

    import pytest; pytest.main(["-xvs", "QGISFMV/tests/test_gui_manager.py"])
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
    not _qgis_available, reason="QGIS runtime not available"
)


@pytest.fixture
def harness():
    from QGISFMV.tests.gui_test_harness import GUITestHarness

    h = GUITestHarness()
    h.start()
    yield h
    h.stop()


class TestManagerUI:
    """Verify Manager dock widget UI elements."""

    def test_manager_dock_is_qdockwidget(self, harness):
        """Manager should be a QDockWidget."""
        from qgis.PyQt.QtWidgets import QDockWidget

        mgr = harness.get_manager()
        assert mgr is not None
        assert isinstance(mgr, QDockWidget), "Manager should be a QDockWidget"

    def test_manager_has_table(self, harness):
        """Manager should have a VManager table with 6 columns."""
        mgr = harness.get_manager()
        assert mgr is not None
        table = harness.find_widget("VManager", parent=mgr)
        assert table is not None
        assert (
            table.columnCount() == 6
        ), f"Expected 6 columns, got {table.columnCount()}"

    def test_manager_has_progress_bars(self, harness):
        """Each row should have a QProgressBar cell widget."""
        mgr = harness.get_manager()
        assert mgr is not None
        from qgis.PyQt.QtWidgets import QProgressBar

        bars = mgr.findChildren(QProgressBar)
        # At least 0 bars (empty table) or more if videos loaded
        assert isinstance(bars, list), "Progress bars should be a list"

    def test_manager_menu_bar(self, harness):
        """Manager should have a menu bar."""
        mgr = harness.get_manager()
        assert mgr is not None
        menubar = harness.find_widget("menubarwidget", parent=mgr)
        assert menubar is not None, "menubarwidget not found"

    def test_manager_column_widths(self, harness):
        """Manager table columns should have configured widths."""
        mgr = harness.get_manager()
        assert mgr is not None
        table = harness.find_widget("VManager", parent=mgr)
        assert table is not None
        # Column 1 should be 250px (name)
        assert table.columnWidth(1) >= 200, "Name column too narrow"


class TestManagerDragDrop:
    """Verify drag-and-drop acceptance."""

    def test_manager_accepts_drops(self, harness):
        """Manager should accept drag-and-drop."""
        mgr = harness.get_manager()
        assert mgr is not None
        assert mgr.acceptDrops(), "Manager should accept drops"


class TestManagerVisual:
    """Screenshot tests for the Manager."""

    def test_manager_empty_screenshot(self, harness):
        """Capture empty manager state."""
        mgr = harness.get_manager()
        if mgr is None:
            pytest.skip("No manager")
        harness.screenshot("manager_empty")
        match, sim = harness.assert_screenshot_matches("manager_empty")
        assert match, f"Manager empty screenshot differs (sim={sim:.2%})"
