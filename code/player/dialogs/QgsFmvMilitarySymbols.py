# -*- coding: utf-8 -*-
"""NATO APP-6D inspired military symbol picker for FMV video annotations."""

import os

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QListWidgetItem

from QGISFMV.gui.ui_FmvMilitarySymbols import Ui_FmvMilitarySymbols
from QGISFMV.utils.settings.QgsFmvSettings import plugin_root

MILITARY_SYMBOLS = (
    ("f_inf", "Friendly Infantry", "friendly", "infantry.svg"),
    ("f_arm", "Friendly Armour", "friendly", "armour.svg"),
    ("f_eng", "Friendly Engineer", "friendly", "engineer.svg"),
    ("f_art", "Friendly Artillery", "friendly", "artillery.svg"),
    ("f_log", "Friendly Logistics", "friendly", "logistics.svg"),
    ("f_hq", "Friendly Headquarters", "friendly", "headquarter.svg"),
    ("h_inf", "Hostile Infantry", "hostile", "infantry.svg"),
    ("h_arm", "Hostile Armour", "hostile", "armour.svg"),
    ("h_unk", "Hostile Unknown", "hostile", "unknown.svg"),
    ("n_unit", "Neutral Unit", "neutral", "unit.svg"),
    ("s_mine", "Minefield", "special", "minefield.svg"),
    ("s_obs", "Obstacle", "special", "obstacle.svg"),
    ("s_bri", "Bridge", "special", "bridge.svg"),
    ("s_chk", "Checkpoint", "special", "checkpoint.svg"),
)

_CATEGORY_ITEM_DATA = ("", "friendly", "hostile", "neutral", "special")

_SYMBOL_LOOKUP = {entry[0]: entry for entry in MILITARY_SYMBOLS}
_SVG_CACHE = {}


def symbols_dir():
    """Return the filesystem path to the bundled military SVG icons."""
    return os.path.join(plugin_root(), "images", "military")


def symbol_svg_path(symbol_id):
    """Return the full SVG path for *symbol_id*, or None if not found."""
    entry = _SYMBOL_LOOKUP.get(symbol_id)
    if entry is None:
        return None
    _sid, _name, category, filename = entry
    return os.path.join(symbols_dir(), category, filename)


def _render_svg_pixmap(svg_path, size):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    if not svg_path or not os.path.isfile(svg_path):
        return pixmap
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        return pixmap
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap


def symbol_icon(symbol_id, size=32):
    """Return a cached QIcon for the given military symbol SVG."""
    path = symbol_svg_path(symbol_id)
    if not path or not os.path.isfile(path):
        return QIcon()
    cache_key = (symbol_id, size)
    if cache_key not in _SVG_CACHE:
        _SVG_CACHE[cache_key] = QIcon(_render_svg_pixmap(path, size))
    return _SVG_CACHE[cache_key]


class MilitarySymbolDialog(QDialog, Ui_FmvMilitarySymbols):
    """Pick a military symbol and place it by clicking on the georeferenced video."""

    symbolSelected = pyqtSignal(str, str)
    placementFinished = pyqtSignal()
    focusVideoRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._current_id = MILITARY_SYMBOLS[0][0]
        self._placed_count = 0
        self._georeferenced = True

        for index, data in enumerate(_CATEGORY_ITEM_DATA):
            self.cmb_category.setItemData(index, data)

        ok_btn = self.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText(self.tr("Done"))
            ok_btn.setDefault(True)

        self._refresh_list()
        if self.lst_symbols.count():
            self.lst_symbols.setCurrentRow(0)
        self._update_status(georeferenced=True)

    def showEvent(self, event):
        """Handle dialog show — display placement steps and focus the video widget."""
        super().showEvent(event)
        self._update_steps()
        self._focus_video()

    def set_georeferenced(self, georeferenced):
        """Update the georeferenced state (affects placement mode)."""
        self._georeferenced = bool(georeferenced)
        self._update_status(georeferenced=self._georeferenced)

    def set_placed_count(self, count):
        """Update the placed-symbol counter in the UI."""
        self._placed_count = count
        self.lbl_placed.setText(
            self.tr("Placed on video/map: {count}").format(count=count)
        )

    def current_symbol(self):
        """Return (symbol_id, unit_name) for the currently selected symbol."""
        return self._current_id, self.ln_unitName.text().strip()

    def refreshSymbolList(self, *_args):
        """Rebuild the symbol list widget."""
        self._refresh_list()

    def onSymbolItemChanged(self, current, _previous):
        """Slot: selection changed in the symbol list."""
        self._on_item_changed(current, None)

    def onSymbolActivated(self, item):
        """Slot: symbol double-clicked — select and focus the video."""
        if item is None:
            return
        self._on_item_changed(item, None)
        self._focus_video()

    def emitSymbolSelection(self, *_args):
        """Emit the symbolSelected signal with the current selection."""
        self._emit_selection()

    def requestVideoClick(self):
        """Enter placement mode — prompt the user to click on the video."""
        self._request_video_click()

    def finishPlacement(self):
        """Finalize placement and return to the symbol picker."""
        self._finish_placement()

    def _symbol_name(self, symbol_id):
        entry = _SYMBOL_LOOKUP.get(symbol_id)
        if entry is None:
            return symbol_id
        return self.tr(entry[1])

    def _update_steps(self):
        self.lbl_steps.setText(
            "<b>"
            + self.tr("How to place symbols")
            + "</b><br>"
            + "1. "
            + self.tr("Pick a symbol from the list below")
            + "<br>"
            + "2. "
            + self.tr("Optionally type a unit label")
            + "<br>"
            + "3. "
            + self.tr(
                "Press the green button below, then click on the <b>video image</b> "
                "(the player panel, not this dialog)"
            )
            + "<br>"
            + "<span style='color:#607d8b;'>"
            + self.tr(
                "Selecting a symbol in the list only chooses it — it does not place it. "
                "Same as drawing points: the video must have MISB georeferencing."
            )
            + "</span>"
        )

    def _update_status(self, georeferenced=True):
        self.btn_clickVideo.setEnabled(georeferenced)
        if not georeferenced:
            self.lbl_status.setText(
                "<span style='color:#e65100; font-weight:bold;'>"
                + self.tr("Video not georeferenced — play a MISB video first.")
                + "</span>"
            )
            return
        name = self._symbol_name(self._current_id)
        label = self.ln_unitName.text().strip()
        extra = f" ({label})" if label else ""
        self.lbl_status.setText(
            "<span style='color:#2e7d32; font-weight:bold;'>"
            + self.tr("Ready:")
            + "</span> "
            + self.tr("Click on the video to place <b>{symbol}</b>{extra}.").format(
                symbol=name, extra=extra
            )
        )

    def _focus_video(self):
        player = self.parent()
        if player is not None and hasattr(player, "videoWidget"):
            player.videoWidget.setFocus(Qt.FocusReason.OtherFocusReason)
            if hasattr(player.videoWidget, "flashMilitarySymbolPlacementHint"):
                player.videoWidget.flashMilitarySymbolPlacementHint()

    def _request_video_click(self):
        self._focus_video()
        self.focusVideoRequested.emit()

    def _finish_placement(self):
        self.placementFinished.emit()
        self.hide()

    def _refresh_list(self):
        category = self.cmb_category.currentData()
        previous = self._current_id
        self.lst_symbols.blockSignals(True)
        self.lst_symbols.clear()
        for symbol_id, name, cat, filename in MILITARY_SYMBOLS:
            if category and cat != category:
                continue
            item = QListWidgetItem(symbol_icon(symbol_id), self._symbol_name(symbol_id))
            item.setData(Qt.ItemDataRole.UserRole, symbol_id)
            item.setToolTip(
                self.tr(
                    "Click on the video to place this symbol. "
                    "Double-click to focus the video."
                )
            )
            self.lst_symbols.addItem(item)
            if symbol_id == previous:
                self.lst_symbols.setCurrentItem(item)
        self.lst_symbols.blockSignals(False)
        if self.lst_symbols.currentItem() is None and self.lst_symbols.count():
            self.lst_symbols.setCurrentRow(0)
        self._on_item_changed(self.lst_symbols.currentItem(), None)

    def _on_item_changed(self, current, _previous):
        if current is None:
            return
        symbol_id = current.data(Qt.ItemDataRole.UserRole)
        self._current_id = symbol_id
        path = symbol_svg_path(symbol_id)
        if path:
            pixmap = _render_svg_pixmap(path, 96)
            self.lbl_preview.setPixmap(
                pixmap.scaled(
                    96,
                    96,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.lbl_preview.clear()
        self._emit_selection()

    def _emit_selection(self, *_args):
        self.symbolSelected.emit(self._current_id, self.ln_unitName.text().strip())
        self._update_status(georeferenced=self._georeferenced)
