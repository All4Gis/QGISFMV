# -*- coding: utf-8 -*-
"""Pure spatial helpers + mission/bookmark geo enrichment (no QGIS GUI)."""

from __future__ import annotations

import csv
import sys
import types
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from code.tests.support import (
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


class TestSpatialHelpers:
    def test_point_in_ring_and_nearest(self):
        spatial = load_plugin_module("geo/QgsFmvSpatial.py")
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        assert spatial.point_in_ring(5, 5, square) is True
        assert spatial.point_in_ring(20, 5, square) is False
        samples = [(0.0, 0.0, 1.0), (1.0, 0.0, 2.0), (2.0, 0.0, 3.0)]
        near = spatial.nearest_sample(1.05, 0.01, samples)
        assert near[2] == 2.0
        assert spatial.box_center((0, 0, 10, 20)) == (5.0, 10.0)
        assert spatial.metadata_lat_lon(
            {
                0: ["Frame Center Latitude", "40.1"],
                1: ["Frame Center Longitude", "-3.2"],
            }
        ) == (40.1, -3.2)
        hits = spatial.detections_inside_ring(
            {
                "vehicle": [{"lon": 5.0, "lat": 5.0}, {"lon": 50.0, "lat": 50.0}],
                "person": [{"lon": 1.0, "lat": 1.0}],
            },
            square,
        )
        assert len(hits) == 2
        assert {h[0] for h in hits} == {"vehicle", "person"}

        ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        samples = [
            (1.0, 1.0, 10.0, ring),
            (1.0, 1.0, 11.0, ring),  # same cluster
            (1.0, 1.0, 20.0, ring),
            (50.0, 50.0, 30.0, [(40, 40), (60, 40), (60, 60), (40, 60)]),
        ]
        lb = spatial.lookback_samples(5.0, 5.0, samples, cluster_dt=2.0)
        assert [s[2] for s in lb] == [10.0, 20.0]
        brng = spatial.initial_bearing_deg((-3.7, 40.4), (-3.7, 41.4))
        assert 0.0 <= brng < 10.0  # roughly north
        assert "km" in spatial.format_distance_m(1500)
        cue = spatial.target_cue_state(
            5.0, 5.0, 0.0, 0.0, 0.0, samples=samples, footprint_ring=None
        )
        assert cue["distance_m"] > 0 and "TGT" in cue["label"]
        cue_in = spatial.target_cue_state(
            5.0, 5.0, 0.0, 0.0, 0.0, samples=[], footprint_ring=ring
        )
        assert cue_in["in_fov"] is True and "IN FOV" in cue_in["label"]
        nxt = spatial.next_lookback_after(5.0, 5.0, samples, after_sec=12.0)
        assert nxt is not None and nxt[2] == 20.0


class TestGeofenceRule:
    def test_enter_transition(self):
        ensure_qgis_fmv_package()
        keys = qgis_stub_keys(
            "qgis.PyQt.QtWidgets",
            "qgis.core",
            "QGISFMV.utils.ui.QgsUtils",
            "QGISFMV.utils.logging",
        )
        saved = snapshot_modules(keys)
        try:
            for name in keys:
                sys.modules.setdefault(name, types.ModuleType(name))
            qtcore = sys.modules["qgis.PyQt.QtCore"]
            qtcore.QCoreApplication = types.SimpleNamespace(
                translate=lambda *a, **k: a[-1] if a else ""
            )
            core = sys.modules["qgis.core"]
            core.Qgis = types.SimpleNamespace(
                MessageLevel=types.SimpleNamespace(Warning=1, Info=0)
            )
            ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]

            class QgsUtils:
                @staticmethod
                def showUserAndLogMessage(*a, **k):
                    return None

                @staticmethod
                def selectLayerByName(*a, **k):
                    return None

            ui.QgsUtils = QgsUtils
            logmod = sys.modules["QGISFMV.utils.logging"]
            logmod.log = types.SimpleNamespace(debug=lambda *a, **k: None)

            mod = load_plugin_module(
                "player/features/QgsFmvGeofence.py",
                "QGISFMV.player.features.QgsFmvGeofence",
            )
            ring = [(0, 0), (10, 0), (10, 10), (0, 10)]
            rule = mod.GeofenceRule(ring, label="AOI", mode="enter")
            # First sample outside — no alert
            ok, _ = rule.check_transition(-1, -1)
            assert ok is False
            # Enter
            ok, detail = rule.check_transition(5, 5)
            assert ok is True
            assert "entered" in detail
            # Stay inside — no re-trigger
            ok, _ = rule.check_transition(6, 6)
            assert ok is False

            # Detection Sentinel
            player = MagicMock()
            player.alertManager = MagicMock()
            player.hudOverlay = MagicMock()
            player._videoGroupName = MagicMock(return_value="g")
            ctrl = mod.GeofenceController(player)
            ctrl.set_ring(ring, label="AOI")
            ctrl._cooldown_ms = 0
            msg = ctrl.checkDetections(
                {"vehicle": [{"lon": 5.0, "lat": 5.0, "track_id": 1}]}
            )
            assert msg and "SENTINEL" in msg
            player.alertManager.alertTriggered.emit.assert_called()
            # Outside — no hit
            ctrl._last_alert_ms = 0
            assert (
                ctrl.checkDetections(
                    {"vehicle": [{"lon": 50.0, "lat": 50.0, "track_id": 2}]}
                )
                is None
            )
        finally:
            restore_modules(saved)


class TestGeoTimeIndex:
    def test_index_throttle_and_nearest(self):
        ensure_qgis_fmv_package()
        keys = qgis_stub_keys(
            "qgis.PyQt.QtWidgets",
            "qgis.core",
            "QGISFMV.utils.ui.QgsUtils",
            "QGISFMV.utils.logging",
        )
        saved = snapshot_modules(keys)
        try:
            for name in keys:
                sys.modules.setdefault(name, types.ModuleType(name))
            ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]
            ui.QgsUtils = types.SimpleNamespace(
                showUserAndLogMessage=lambda *a, **k: None
            )
            logmod = sys.modules["QGISFMV.utils.logging"]
            logmod.log = types.SimpleNamespace(debug=lambda *a, **k: None)

            mod = load_plugin_module(
                "player/features/QgsFmvMapSeekController.py",
                "QGISFMV.player.features.QgsFmvMapSeekController",
            )
            idx = mod.GeoTimeIndex(min_step_m=1.0, min_dt_sec=0.0)
            ring = [(0.0, 0.0), (0.01, 0.0), (0.01, 0.01), (0.0, 0.01)]
            assert idx.add(0.0, 0.0, 0.0, footprint=ring)
            assert idx.add(0.01, 0.0, 1.0, footprint=ring)  # ~1km
            sample = idx.nearest(0.009, 0.0)
            assert sample[2] == 1.0
            assert sample[3] is not None

            player = MagicMock()
            player.currentInfo = 1.0
            player.playbackController = MagicMock()
            player.iface = None
            ctrl = mod.MapSeekController(player)
            ctrl.index = idx
            t = ctrl.seekNearest(0.009, 0.0)
            assert t == 1.0
            player.playbackController.seek.assert_called_with(1.0)
            # Time Machine scrub (no canvas → ghost skipped)
            ctrl._scrub_min_ms = 0
            ctrl._scrub_min_dt = 0
            assert ctrl.scrubNearest(0.009, 0.0) == 1.0

            # Lookback via footprint containment
            hits = ctrl.index.lookback(0.005, 0.005)
            assert len(hits) >= 1
            # Avoid GUI dialog in unit test — call seek helper directly
            ctrl._lookback_hits = hits
            assert ctrl.seekLookbackIndex(0) == hits[0][2]
        finally:
            restore_modules(saved)


class TestDetectionGeo:
    def test_boxes_to_geo_points(self):
        import numpy as np

        mod = load_plugin_module(
            "video/filters/QgsFmvDetectionMap.py",
            "QGISFMV.video.filters.QgsFmvDetectionMap",
        )
        # Identity-ish: lat=y, lon=x (homography with scalar 1)
        gt = np.array([[0, 1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        points = mod.detections_to_geo_points(
            [(0, 0, 10, 20)], track_ids=[7], scores=[0.9], gt=gt
        )
        assert len(points) == 1
        assert points[0]["track_id"] == 7
        assert points[0]["lat"] == pytest.approx(10.0)
        assert points[0]["lon"] == pytest.approx(5.0)


class TestMissionPackageHelpers:
    def test_csv_and_zip_builders(self, tmp_path):
        ensure_qgis_fmv_package()
        keys = qgis_stub_keys(
            "qgis.PyQt.QtWidgets",
            "qgis.core",
            "QGISFMV.utils.ui.QgsUtils",
            "QGISFMV.utils.core.QgsFmvUtils",
            "QGISFMV.utils.logging",
            "QGISFMV.utils.layers.QgsFmvExport",
            "QGISFMV.video.filters.QgsFmvDetectionMap",
        )
        saved = snapshot_modules(keys)
        try:
            for name in keys:
                sys.modules.setdefault(name, types.ModuleType(name))
            qtcore = sys.modules["qgis.PyQt.QtCore"]
            qtcore.QCoreApplication = types.SimpleNamespace(
                translate=lambda *a, **k: a[-1] if a else ""
            )

            class QObject:
                def __init__(self, parent=None, *a, **k):
                    self._parent = parent

            qtcore.QObject = QObject
            core = sys.modules["qgis.core"]
            core.Qgis = types.SimpleNamespace(
                MessageLevel=types.SimpleNamespace(Warning=1, Info=0)
            )
            ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]
            ui.QgsUtils = types.SimpleNamespace(
                showUserAndLogMessage=lambda *a, **k: None
            )
            utils = sys.modules["QGISFMV.utils.core.QgsFmvUtils"]
            utils.askForFiles = lambda *a, **k: None
            logmod = sys.modules["QGISFMV.utils.logging"]
            logmod.log = types.SimpleNamespace(
                debug=lambda *a, **k: None, error=lambda *a, **k: None
            )
            det = sys.modules["QGISFMV.video.filters.QgsFmvDetectionMap"]
            det.last_detections = lambda: {
                "vehicle": [{"track_id": 1, "lon": -3.0, "lat": 40.0, "score": 0.8}]
            }

            # Bookmark writers need QtGui for alert path; stub lightly.
            sys.modules.setdefault("qgis.PyQt.QtGui", types.ModuleType("QtGui"))
            sys.modules["qgis.PyQt.QtGui"].QColor = object

            mod = load_plugin_module(
                "player/features/QgsFmvMissionPackage.py",
                "QGISFMV.player.features.QgsFmvMissionPackage",
            )
            geo_p = tmp_path / "geo.csv"
            assert mod.write_geotime_csv(str(geo_p), [(1.0, 2.0, 3.5)]) == 1
            text = geo_p.read_text(encoding="utf-8")
            assert "time_sec" in text and "3.5" in text

            class Ev:
                def __init__(self):
                    self.time_sec = 1.0
                    self.label = "B"
                    self.lat = 40.0
                    self.lon = -3.0
                    self.alt = 100.0

            class TL:
                def events(self):
                    return [Ev()]

            class Idx:
                samples = [(-3.0, 40.0, 1.0)]

            player = MagicMock()
            player.fileName = "/tmp/demo.ts"
            player.timeline = TL()
            player.bookmarkController = MagicMock()
            player.mapSeekController = MagicMock(index=Idx())
            player.mosaic = MagicMock(active_path=None)
            player.geofenceController = MagicMock(rules=lambda: [])
            player._videoGroupName = MagicMock(return_value="g")

            # Stub silent kml to no-op
            mod._write_group_kml_silent = lambda *a, **k: None

            zpath = tmp_path / "mission.zip"
            out = mod.build_mission_package(player, str(zpath))
            assert out == str(zpath)
            assert zpath.is_file()
            with zipfile.ZipFile(zpath) as zf:
                names = set(zf.namelist())
            assert "MANIFEST.txt" in names
            assert "bookmarks.csv" in names
            assert "geotime_index.csv" in names
            assert "ai_detections.csv" in names
        finally:
            restore_modules(saved)


class TestSpatialBookmarksExport:
    def test_csv_kml_include_coords(self, tmp_path):
        ensure_qgis_fmv_package()
        keys = qgis_stub_keys(
            "qgis.PyQt.QtGui",
            "qgis.PyQt.QtWidgets",
            "qgis.core",
            "QGISFMV.utils.ui.QgsUtils",
            "QGISFMV.utils.core.QgsFmvUtils",
            "QGISFMV.utils.logging",
        )
        saved = snapshot_modules(keys)
        try:
            for name in keys:
                sys.modules.setdefault(name, types.ModuleType(name))
            qtcore = sys.modules["qgis.PyQt.QtCore"]
            qtcore.QCoreApplication = types.SimpleNamespace(
                translate=lambda *a, **k: a[-1] if a else ""
            )

            class QObject:
                def __init__(self, parent=None, *a, **k):
                    self._parent = parent

            qtcore.QObject = QObject
            qtgui = sys.modules["qgis.PyQt.QtGui"]
            qtgui.QColor = object
            core = sys.modules["qgis.core"]
            core.Qgis = types.SimpleNamespace(
                MessageLevel=types.SimpleNamespace(Warning=1, Info=0)
            )
            ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]
            ui.QgsUtils = types.SimpleNamespace(
                showUserAndLogMessage=lambda *a, **k: None
            )
            utils = sys.modules["QGISFMV.utils.core.QgsFmvUtils"]
            utils.askForFiles = lambda *a, **k: None
            utils.GetFrameCenter = lambda: (40.4, -3.7, 500.0)
            logmod = sys.modules["QGISFMV.utils.logging"]
            logmod.log = types.SimpleNamespace(
                debug=lambda *a, **k: None, error=lambda *a, **k: None
            )

            mod = load_plugin_module(
                "player/features/QgsFmvBookmarkController.py",
                "QGISFMV.player.features.QgsFmvBookmarkController",
            )

            class Ev:
                def __init__(self):
                    self.time_sec = 2.5
                    self.label = "Mark"
                    self.lat = 40.4
                    self.lon = -3.7
                    self.alt = 500.0

            csv_p = tmp_path / "b.csv"
            kml_p = tmp_path / "b.kml"
            mod.write_bookmarks_csv(str(csv_p), [Ev()])
            mod.write_bookmarks_kml(str(kml_p), [Ev()], "x.ts")
            rows = list(csv.reader(csv_p.open(encoding="utf-8")))
            assert rows[0] == ["index", "time_sec", "label", "lat", "lon", "alt"]
            assert "40.4" in rows[1]
            kml = kml_p.read_text(encoding="utf-8")
            assert "-3.7,40.4,500" in kml
        finally:
            restore_modules(saved)


class TestDetectionTrailFlags:
    def test_trail_toggle(self):
        mod = load_plugin_module(
            "video/filters/QgsFmvDetectionMap.py",
            "QGISFMV.video.filters.QgsFmvDetectionMap",
        )
        assert mod.set_trail_enabled(True) is True
        assert mod.is_trail_enabled() is True
        assert mod.set_trail_enabled(False) is False
        assert mod.is_trail_enabled() is False


class TestInstantReplayController:
    def test_disabled_noop_and_enabled_rewinds(self):
        ensure_qgis_fmv_package()
        keys = qgis_stub_keys("QGISFMV.utils.ui.QgsUtils")
        saved = snapshot_modules(keys)
        try:
            for name in keys:
                sys.modules.setdefault(name, types.ModuleType(name))
            ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]
            ui.QgsUtils = types.SimpleNamespace(
                showUserAndLogMessage=lambda *a, **k: None
            )

            mod = load_plugin_module(
                "player/features/QgsFmvInstantReplay.py",
                "QGISFMV.player.features.QgsFmvInstantReplay",
            )
            player = MagicMock()
            player.player.position.return_value = 10_000
            player.playbackController = None
            ctrl = mod.InstantReplayController(player, seconds=3.0)
            assert ctrl.onAlert("x") is False
            ctrl.setEnabled(True)
            assert ctrl.onAlert("SENTINEL") is True
            player.player.setPosition.assert_called_with(7000)
            player.player.pause.assert_called()
        finally:
            restore_modules(saved)


class TestCinematicFollowFlag:
    def test_set_cinematic_follow(self):
        ensure_qgis_fmv_package()
        keys = qgis_stub_keys("QGISFMV.utils.ui.QgsUtils")
        saved = snapshot_modules(keys)
        try:
            for name in keys:
                sys.modules.setdefault(name, types.ModuleType(name))
            ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]
            ui.QgsUtils = types.SimpleNamespace()
            # Stub qgis.core types used at import
            core = sys.modules.setdefault("qgis.core", types.ModuleType("qgis.core"))
            for attr in (
                "QgsCoordinateTransform",
                "QgsCoordinateReferenceSystem",
                "QgsProject",
                "QgsPointXY",
                "QgsWkbTypes",
            ):
                setattr(core, attr, object)
            mod = load_plugin_module(
                "utils/core/QgsFmvMapCenter.py",
                "QGISFMV.utils.core.QgsFmvMapCenter",
            )
            assert mod.set_cinematic_follow(True) is True
            assert mod.is_cinematic_follow() is True
            assert mod.set_cinematic_follow(False) is False
        finally:
            restore_modules(saved)


class TestPlaceLabelController:
    def test_enable_clears_on_disable(self):
        mod = load_plugin_module(
            "player/features/QgsFmvPlaceLabel.py",
            "QGISFMV.player.features.QgsFmvPlaceLabel",
        )
        player = MagicMock()
        hud = MagicMock()
        player.hudOverlay = hud
        ctrl = mod.PlaceLabelController(player)
        assert ctrl.setEnabled(True) is True
        assert ctrl.setEnabled(False) is False
        hud.setPlaceLabel.assert_called_with("")


class TestTargetPinController:
    def test_set_pin_and_cue_update(self):
        ensure_qgis_fmv_package()
        keys = qgis_stub_keys(
            "QGISFMV.utils.ui.QgsUtils",
            "QGISFMV.player.features.QgsFmvGeofence",
        )
        saved = snapshot_modules(keys)
        try:
            for name in keys:
                sys.modules.setdefault(name, types.ModuleType(name))
            ui = sys.modules["QGISFMV.utils.ui.QgsUtils"]
            ui.QgsUtils = types.SimpleNamespace(
                showUserAndLogMessage=lambda *a, **k: None
            )
            geo = sys.modules["QGISFMV.player.features.QgsFmvGeofence"]
            ring = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
            geo.footprint_ring_from_session = lambda *a, **k: ring

            mod = load_plugin_module(
                "player/features/QgsFmvTargetPin.py",
                "QGISFMV.player.features.QgsFmvTargetPin",
            )
            player = MagicMock()
            player.iface = None
            player.currentInfo = 1.0
            player.hudOverlay = MagicMock()
            player.mapSeekController = MagicMock()
            player.mapSeekController.index.samples = [
                (1.0, 1.0, 5.0, ring),
            ]
            player.alertManager = MagicMock()
            player.alertManager.alertTriggered = MagicMock()
            player.alertManager.alertTriggered.emit = MagicMock()

            ctrl = mod.TargetPinController(player)
            assert ctrl.setPin(5.0, 5.0) is True
            assert ctrl.hasPin() is True
            state = ctrl.updateFromMetadata(
                {
                    0: ["Frame Center Latitude", "1.0"],
                    1: ["Frame Center Longitude", "1.0"],
                }
            )
            assert state["in_fov"] is True
            assert "IN FOV" in state["label"]
            player.hudOverlay.setTargetCue.assert_called()
            player.alertManager.alertTriggered.emit.assert_called()
            ctrl.clear()
            assert ctrl.hasPin() is False
        finally:
            restore_modules(saved)
