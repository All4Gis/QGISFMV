# -*- coding: utf-8 -*-
"""Military symbol catalog and bundled SVG assets."""

import os

import pytest

pytest.importorskip("qgis")

from QGISFMV.player.dialogs.QgsFmvMilitarySymbols import (
    MILITARY_SYMBOLS,
    symbol_svg_path,
    symbols_dir,
)


class TestMilitarySymbols:
    def test_symbols_directory_exists(self):
        assert os.path.isdir(symbols_dir())

    def test_all_catalog_svgs_exist(self):
        missing = []
        for entry in MILITARY_SYMBOLS:
            path = symbol_svg_path(entry["file"])
            if not os.path.isfile(path):
                missing.append(entry["file"])
        assert not missing, f"Missing SVGs: {missing}"

    def test_catalog_not_empty(self):
        assert len(MILITARY_SYMBOLS) > 0
