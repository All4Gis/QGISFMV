# -*- coding: utf-8 -*-
"""Tests for QGISFMV.utils.formatting shared utilities."""

from code.tests.support import ensure_qgis_fmv_package, load_plugin_module

ensure_qgis_fmv_package()
mod = load_plugin_module("utils/formatting.py")


class TestFormatLength:
    def test_meters(self):
        assert mod.format_length(500) == "500.0 m"

    def test_one_meter(self):
        assert mod.format_length(1) == "1.0 m"

    def test_zero(self):
        assert mod.format_length(0) == "0.0 m"

    def test_kilometers(self):
        assert mod.format_length(1500) == "1.50 km"

    def test_large_km(self):
        assert mod.format_length(10000) == "10.00 km"

    def test_exact_threshold(self):
        assert mod.format_length(1000) == "1.00 km"

    def test_below_threshold(self):
        assert mod.format_length(999.9) == "999.9 m"

    def test_float_input(self):
        assert mod.format_length(1234.5) == "1.23 km"

    def test_negative(self):
        assert mod.format_length(-500) == "-500.0 m"

    def test_none_returns_dash(self):
        assert mod.format_length(None) == "\u2014"

    def test_string_number(self):
        assert mod.format_length("750") == "750.0 m"

    def test_invalid_string_returns_dash(self):
        assert mod.format_length("abc") == "\u2014"

    def test_empty_string_returns_dash(self):
        assert mod.format_length("") == "\u2014"


class TestFormatArea:
    def test_small_area(self):
        assert mod.format_area(500) == "500.0 m\u00b2"

    def test_hectares(self):
        assert mod.format_area(50000) == "5.00 ha"

    def test_exact_hectare_threshold(self):
        assert mod.format_area(10000) == "1.00 ha"

    def test_below_hectare_threshold(self):
        assert mod.format_area(9999) == "9999.0 m\u00b2"

    def test_square_kilometers(self):
        assert mod.format_area(2000000) == "2.00 km\u00b2"

    def test_exact_km2_threshold(self):
        assert mod.format_area(1000000) == "1.00 km\u00b2"

    def test_zero(self):
        assert mod.format_area(0) == "0.0 m\u00b2"

    def test_float_input(self):
        assert mod.format_area(1234567.89) == "1.23 km\u00b2"

    def test_none_returns_dash(self):
        assert mod.format_area(None) == "\u2014"

    def test_invalid_string_returns_dash(self):
        assert mod.format_area("xyz") == "\u2014"

    def test_negative_area(self):
        assert mod.format_area(-100) == "-100.0 m\u00b2"

    def test_large_hectares(self):
        assert mod.format_area(500000) == "50.00 ha"
