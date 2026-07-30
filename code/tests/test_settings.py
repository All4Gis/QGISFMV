# -*- coding: utf-8 -*-
"""Tests for settings.ini helpers (no QGIS runtime)."""

import os
import types
from code.tests.support import load_plugin_module


def _load_settings_module(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    settings = load_plugin_module("utils/settings/QgsFmvSettings.py")
    monkeypatch.setattr(
        settings, "SETTINGS_PATH", str(tmp_path / "settings.ini"), raising=False
    )
    settings._loaded = False
    settings._parser.clear()
    return settings


class TestQgsFmvSettings:
    def test_get_returns_default_when_missing(self, tmp_path, monkeypatch):
        settings = _load_settings_module(tmp_path, monkeypatch)
        assert settings.get("GENERAL", "missing_key", fallback="x") == "x"

    def test_default_reads_factory_values(self, tmp_path, monkeypatch):
        settings = _load_settings_module(tmp_path, monkeypatch)
        assert settings.default("LAYERS", "platform_lyr") == "Platform"
        assert settings.get_layer("symbol_lyr") == "Military Symbols"
        assert settings.get_layer("objecttrack_lyr") == "Object Track"
        assert settings.get_layer("objectposition_lyr") == "Object Position"

    def test_set_and_get_roundtrip(self, tmp_path, monkeypatch):
        settings = _load_settings_module(tmp_path, monkeypatch)
        settings.set_value("GENERAL", "ffmpeg", "/opt/ffmpeg")
        assert settings.get("GENERAL", "ffmpeg") == "/opt/ffmpeg"

    def test_creates_settings_file_on_load(self, tmp_path, monkeypatch):
        settings = _load_settings_module(tmp_path, monkeypatch)
        settings.load()
        assert os.path.isfile(str(tmp_path / "settings.ini"))

    def test_repair_ffmpeg_does_not_run_on_get(self, tmp_path, monkeypatch):
        settings = _load_settings_module(tmp_path, monkeypatch)
        settings.set_value("GENERAL", "ffmpeg", "/opt/ffmpeg")
        called = []
        monkeypatch.setattr(
            settings, "repair_ffmpeg_setting", lambda persist=True: called.append(1)
        )
        assert settings.get("GENERAL", "ffmpeg") == "/opt/ffmpeg"
        assert called == []

    def test_reload_runtime_syncs_cached_modules(self, tmp_path, monkeypatch):
        import sys

        settings = _load_settings_module(tmp_path, monkeypatch)

        fmv_stub = types.SimpleNamespace(
            dtm_data=[],
            dtm_transform=None,
            dtm_colLowerBound=0,
            dtm_rowLowerBound=0,
            ffmpeg_path="",
            ffprobe_path="",
            parser=None,
            ffmpegConf="",
            frames_g="",
            Reverse_geocoding_url="",
            min_buffer_size=5,
            MOSAIC_MIN_INTERVAL_SEC=0,
            MOSAIC_MIN_MOVE_METERS=0,
            MOSAIC_MAX_FRAME_DIMENSION=0,
            MOSAIC_FEATHER_PX=0,
            MOSAIC_MAX_OUTPUT_SIZE=0,
            MOSAIC_FOOTPRINT_GROW_RATIO=0,
            MOSAIC_FOOTPRINT_GROW_METERS=0,
            Platform_lyr="",
            Beams_lyr="",
            Footprint_lyr="",
            FrameCenter_lyr="",
            FrameAxis_lyr="",
            Point_lyr="",
            Symbol_lyr="",
            Line_lyr="",
            Polygon_lyr="",
            ObjectTrack_lyr="",
            ObjectPosition_lyr="",
            Trajectory_lyr="",
            dtm_buffer=2000,
        )
        layers_stub = types.SimpleNamespace(
            parser=None,
            Platform_lyr="",
            Beams_lyr="",
            Footprint_lyr="",
            FrameCenter_lyr="",
            FrameAxis_lyr="",
            Point_lyr="",
            Symbol_lyr="",
            Line_lyr="",
            Polygon_lyr="",
            ObjectTrack_lyr="",
            ObjectPosition_lyr="",
            frames_g="",
            Trajectory_lyr="",
            epsg="",
        )
        sys.modules["QGISFMV.utils.core.QgsFmvUtils"] = fmv_stub
        sys.modules["QGISFMV.utils.layers.QgsFmvLayers"] = layers_stub

        settings.set_value("GENERAL", "dtm_buffer_size", "3000")
        settings.set_value("GENERAL", "ffmpeg", "/custom/ffmpeg/bin")
        settings.set_value("LAYERS", "platform_lyr", "My Platform")
        settings.save()

        assert fmv_stub.dtm_buffer == 3000
        assert fmv_stub.ffmpegConf == "/custom/ffmpeg/bin"
        assert fmv_stub.Platform_lyr == "My Platform"
        assert layers_stub.Platform_lyr == "My Platform"
