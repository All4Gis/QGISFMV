# -*- coding: utf-8 -*-
"""Pytest fixtures for QGIS FMV tests."""

import importlib.util
import os
import sys

import pytest

# Load support.py directly by path to avoid the 'code' package name conflict.
_support_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "support.py")
_spec = importlib.util.spec_from_file_location("qgsfmv_test_support", _support_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_load_plugin_module = _mod.load_plugin_module


@pytest.fixture
def plugin_module():
    """Return the plugin module loader helper."""

    def _loader(relative_path, module_name=None):
        return _load_plugin_module(relative_path, module_name)

    return _loader
