# -*- coding: utf-8 -*-
"""Unit tests for per-group layer cache reset helpers."""

from code.tests.support import load_plugin_module as _load_plugin_module

import pytest


@pytest.fixture
def layers_mod():
    try:
        from qgis.PyQt.QtGui import QColor  # noqa: F401
    except ImportError:
        pytest.skip("QGIS runtime not available")
    return _load_plugin_module(
        "utils/layers/QgsFmvLayers.py", "QGISFMV.utils.layers.QgsFmvLayers"
    )


def test_reset_layer_caches_scoped(layers_mod):
    layers_mod._trajectory_active_feature["video_a"] = 1
    layers_mod._trajectory_active_feature["video_b"] = 2
    layers_mod._object_track_active_feature["video_a"] = 3
    layers_mod._beam_feature_ids["video_a"] = [1, 2, 3, 4]
    layers_mod._beam_feature_ids["video_b"] = [5, 6, 7, 8]

    layers_mod.resetLayerCaches("video_a")

    assert "video_a" not in layers_mod._trajectory_active_feature
    assert layers_mod._trajectory_active_feature["video_b"] == 2
    assert "video_a" not in layers_mod._object_track_active_feature
    assert "video_a" not in layers_mod._beam_feature_ids
    assert layers_mod._beam_feature_ids["video_b"] == [5, 6, 7, 8]


def test_reset_layer_caches_all(layers_mod):
    layers_mod._trajectory_active_feature["video_a"] = 1
    layers_mod._object_track_active_feature["video_a"] = 2
    layers_mod._beam_feature_ids["video_a"] = [1, 2, 3, 4]
    layers_mod.groupName = None

    layers_mod.resetLayerCaches(None)

    assert layers_mod._trajectory_active_feature == {}
    assert layers_mod._object_track_active_feature == {}
    assert layers_mod._beam_feature_ids == {}
