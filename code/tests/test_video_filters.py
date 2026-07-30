# # -*- coding: utf-8 -*-
# """Tests for video filter pure-numpy implementations (no QGIS runtime)."""

# import numpy as np
# import pytest


# class TestSnapshotFilterState:
#     def test_copies_new_analysis_filters(self):
#         from code.tests.support import load_plugin_module, has_real_qgis_qt

#         if not has_real_qgis_qt():
#             pytest.skip("Qt / QGIS runtime not available")

#         worker = load_plugin_module(
#             "video/filters/QgsFilterWorker.py", "QGISFMV.video.filters.QgsFilterWorker"
#         )
#         state_mod = load_plugin_module(
#             "video/playback/QgsVideoState.py", "QGISFMV.video.playback.QgsVideoState"
#         )
#         state = state_mod.FilterState()
#         state.claheFilter = True
#         state.sharpenFilter = True
#         state.sobelFilter = True
#         state.falseColorFilter = True
#         state.exgFilter = True
#         state.exrFilter = True
#         state.variFilter = True
#         state.nrviFilter = True
#         state.dehazeFilter = True
#         state.roadEnhanceFilter = True
#         state.hotspotFilter = True
#         state.motionDetectionFilter = True
#         state.backgroundSubtractionFilter = True
#         state.buildingDetectionFilter = True
#         state.roadSegmentationFilter = True
#         state.vehicleSegmentationFilter = True
#         state.personSegmentationFilter = True
#         state.fireDetectionFilter = True
#         state.smokeDetectionFilter = True
#         state.floodDetectionFilter = True
#         state.edgeDetectionFilter = True

#         snap = worker.snapshot_filter_state(state)
#         assert snap.claheFilter is True
#         assert snap.sharpenFilter is True
#         assert snap.sobelFilter is True
#         assert snap.falseColorFilter is True
#         assert snap.exgFilter is True
#         assert snap.exrFilter is True
#         assert snap.variFilter is True
#         assert snap.nrviFilter is True
#         assert snap.dehazeFilter is True
#         assert snap.roadEnhanceFilter is True
#         assert snap.hotspotFilter is True
#         assert snap.motionDetectionFilter is True
#         assert snap.backgroundSubtractionFilter is True
#         assert snap.buildingDetectionFilter is True
#         assert snap.roadSegmentationFilter is True
#         assert snap.vehicleSegmentationFilter is True
#         assert snap.personSegmentationFilter is True
#         assert snap.fireDetectionFilter is True
#         assert snap.smokeDetectionFilter is True
#         assert snap.floodDetectionFilter is True
#         assert snap.edgeDetectionFilter is True


# class TestGaussianKernel:
#     @pytest.fixture
#     def filters(self):
#         from code.tests.support import load_plugin_module

#         return load_plugin_module(
#             "video/filters/QgsFmvFilterCore.py", "QGISFMV.video.filters.QgsFmvFilterCore"
#         )

#     def test_shape_5x5(self, filters):
#         k = filters._gaussian_kernel(5, 1.0)
#         assert k.shape == (5, 5)

#     def test_sums_to_one(self, filters):
#         k = filters._gaussian_kernel(5, 1.0)
#         assert k.sum() == pytest.approx(1.0, abs=1e-6)

#     def test_center_is_peak(self, filters):
#         k = filters._gaussian_kernel(7, 1.0)
#         center = k[3, 3]
#         assert center == k.max()

#     def test_smaller_sigma_sharper(self, filters):
#         k1 = filters._gaussian_kernel(5, 0.5)
#         k2 = filters._gaussian_kernel(5, 2.0)
#         assert k1[2, 2] > k2[2, 2]


# class TestBuildingRoadScores:
#     @pytest.fixture
#     def scores(self):
#         from code.tests.support import load_plugin_module

#         return load_plugin_module(
#             "video/filters/QgsFmvDetectionScores.py",
#             "QGISFMV.video.filters.QgsFmvDetectionScores",
#         )

#     def test_road_score_prefers_gray_strip(self, scores):
#         rgb = np.zeros((120, 160, 3), dtype=np.uint8)
#         rgb[:] = (40, 100, 40)
#         rgb[50:70, 10:150] = (110, 110, 115)
#         score = scores._road_surface_score(rgb)
#         assert float(score[50:70].mean()) > float(score[:40].mean())

#     def test_building_score_reacts_to_structure(self, scores):
#         rgb = np.zeros((120, 160, 3), dtype=np.uint8)
#         rgb[:] = (40, 100, 40)
#         rgb[10:40, 20:60] = (170, 165, 160)
#         # Hard edges around the rectangle
#         rgb[10, 20:60] = (20, 20, 20)
#         rgb[39, 20:60] = (20, 20, 20)
#         rgb[10:40, 20] = (20, 20, 20)
#         rgb[10:40, 59] = (20, 20, 20)
#         score = scores._building_structure_score(rgb)
#         assert float(score[10:40, 20:60].mean()) > float(score[70:100, 20:60].mean())

#     def test_vehicle_score_finds_aerial_parking_lot(self, scores, monkeypatch):
#         """Many small light/dark cars on gray pavement should score above background."""
#         from code.tests.support import load_plugin_module

#         geom = load_plugin_module(
#             "video/filters/QgsFmvDetectionGeometry.py",
#             "QGISFMV.video.filters.QgsFmvDetectionGeometry",
#         )
#         geom.reset_detection_state()
#         try:
#             tuning = load_plugin_module(
#                 "video/filters/QgsFmvFilterTuning.py",
#                 "QGISFMV.video.filters.QgsFmvFilterTuning",
#             )
#             monkeypatch.setattr(tuning, "is_aerial_profile", lambda: True)
#         except Exception:
#             pass

#         rgb = np.zeros((240, 320, 3), dtype=np.uint8)
#         rgb[:] = (115, 115, 118)
#         cars = [
#             (30, 40, 44, 58, (35, 35, 40)),
#             (30, 90, 44, 108, (210, 210, 215)),
#             (30, 140, 44, 158, (50, 50, 55)),
#             (30, 190, 44, 208, (195, 195, 200)),
#             (80, 60, 94, 78, (40, 40, 45)),
#             (80, 120, 94, 138, (205, 205, 210)),
#             (80, 180, 94, 198, (55, 55, 60)),
#             (130, 50, 144, 68, (200, 200, 205)),
#             (130, 110, 144, 128, (45, 45, 50)),
#             (130, 170, 144, 188, (190, 190, 195)),
#         ]
#         for y0, x0, y1, x1, color in cars:
#             rgb[y0:y1, x0:x1] = color
#         score = scores._vehicle_blob_score(rgb)
#         bg = float(score[0:20, 0:40].mean())
#         fg = float(score[30:44, 40:58].mean())
#         assert fg > bg
#         assert float(score.max()) > bg
#         assert float(score.max()) > 0.05


# class TestConv2d:
#     @pytest.fixture
#     def filters(self):
#         from code.tests.support import load_plugin_module

#         return load_plugin_module(
#             "video/filters/QgsFmvFilterCore.py", "QGISFMV.video.filters.QgsFmvFilterCore"
#         )

#     def test_identity_kernel(self, filters):
#         img = np.random.rand(32, 32).astype(np.float32)
#         kernel = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]], dtype=np.float32)
#         result = filters._conv2d(img, kernel)
#         np.testing.assert_allclose(result, img, atol=1e-5)

#     def test_blur_kernel_smooths(self, filters):
#         img = np.zeros((32, 32), dtype=np.float32)
#         img[16, 16] = 1.0
#         kernel = np.ones((3, 3), dtype=np.float32) / 9.0
#         result = filters._conv2d(img, kernel)
#         # Center should be less than 1.0 after blur
#         assert result[16, 16] < 1.0
#         # Surrounding pixels should have non-zero values
#         assert result[15, 16] > 0.0

#     def test_preserves_shape(self, filters):
#         img = np.random.rand(64, 48).astype(np.float32)
#         kernel = np.ones((5, 5), dtype=np.float32) / 25.0
#         result = filters._conv2d(img, kernel)
#         assert result.shape == img.shape

#     def test_large_kernel(self, filters):
#         img = np.random.rand(100, 100).astype(np.float32)
#         kernel = np.ones((11, 11), dtype=np.float32) / 121.0
#         result = filters._conv2d(img, kernel)
#         assert result.shape == img.shape


# class TestFilterExports:
#     def test_opencv_status_text_is_string(self):
#         from code.tests.support import load_plugin_module

#         filters_pkg = load_plugin_module(
#             "video/filters/__init__.py", "QGISFMV.video.filters"
#         )
#         text = filters_pkg.opencv_status_text()
#         assert isinstance(text, str)
#         assert text
