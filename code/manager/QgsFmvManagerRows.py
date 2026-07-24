# -*- coding: utf-8 -*-
"""Row-id / row-metadata lookups and active-row status text for the Manager table.

The manager table's column 0 holds the row id (hidden), which keys into the
manager's ``_row_data`` dict of per-video metadata (playable flag, initial
point, cached KLV reader). This module centralizes that lookup logic plus the
"Playing"/"Ready" status-cell toggling.
"""
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QTableWidgetItem


class ManagerRowStore:
    """Resolve manager table rows to their row-id-keyed metadata dict, and
    toggle the status text ("Playing"/"Ready"/...) shown in the table.
    """

    def __init__(self, manager):
        self._m = manager

    def normalize_row_id(self, row_id):
        """Coerce *row_id* to int, returning the original value on failure."""
        try:
            return int(row_id)
        except (TypeError, ValueError):
            return row_id

    def row_id_at(self, row_index):
        """Return the integer row ID stored in column 0 at *row_index*."""
        item = self._m.VManager.item(row_index, 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except (TypeError, ValueError):
            return None

    def row_entry(self, row_index, create=False):
        """Return the metadata dict for the row, optionally creating it."""
        manager = self._m
        row_id = self.row_id_at(row_index)
        if row_id is None:
            return {}
        row_id = self.normalize_row_id(row_id)
        if create:
            return manager._row_data.setdefault(
                row_id,
                {"playable": False, "initialPt": [], "metaReader": None},
            )
        entry = manager._row_data.get(row_id)
        if entry is None:
            legacy = manager._row_data.get(str(row_id))
            if legacy is not None:
                manager._row_data[row_id] = legacy
                del manager._row_data[str(row_id)]
                entry = legacy
        return entry or {}

    def is_playable(self, row_index):
        """True when the row at *row_index* has been verified as playable."""
        return bool(self.row_entry(row_index).get("playable"))

    def toggle_active_from_title(self):
        """Toggle Active video status"""
        manager = self._m
        column = 2
        for row in range(manager.VManager.rowCount()):
            if manager.VManager.item(row, column) is not None:
                v = manager.VManager.item(row, column).text()
                if v == "Playing":
                    self.toggle_active_row(row, value="Ready")
                    return

    def toggle_active_row(self, row, value="Playing"):
        """Toggle Active row manager video status"""
        manager = self._m
        manager.VManager.setItem(
            row, 2, QTableWidgetItem(QCoreApplication.translate("ManagerDock", value))
        )
