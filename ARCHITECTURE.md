# QGIS FMV — Architecture

This document describes the plugin layout after the session / controller refactor.
The installable package lives in [`code/`](code/). The root `QGISFMV` path is a
**symlink to `code/`** for QGIS plugin discovery — do not edit or lint through
that symlink (tools may double-count files).

<p align="center">
  <a href="CODING_STANDARDS.md">Coding standards</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="README.md">README</a>
</p>

---

## Package map

| Area | Path | Role |
|------|------|------|
| Plugin entry | `code/QgsFmv.py`, `code/__init__.py` | QGIS plugin class, menu/toolbar |
| Manager | `code/manager/` | Video list dock, open stream, multiplexer |
| Player | `code/player/QgsFmvPlayer.py` | Dock shell; wires controllers + UI |
| Player features | `code/player/features/` | Controllers (record, metadata, mosaic, map seek / Time Machine, geofence, bookmarks, mission package, …) |
| Player dialogs | `code/player/dialogs/` | Settings, metadata dock, military symbols, reports |
| Overlays | `code/player/overlays/` | HUD (incl. alert banner), minimap, sensor cone, distance rings |
| Spatial helpers | `code/geo/QgsFmvSpatial.py` | Pure point-in-polygon, nearest sample, image→lat/lon (no QGIS) |
| AI → map | `code/video/filters/QgsFmvDetectionMap.py` | Georeferenced detection points + listener hooks (Sentinel) |
| Drawing toolbar | `code/player/drawing/` | Draw tools painted on video |
| Video widget | `code/video/playback/` | Decode surface, interaction, paint pipeline |
| Filters / DNN | `code/video/filters/`, `code/video/dnn/` | Classic + AI filters |
| Session state | `code/utils/core/QgsFmvVideoSession.py` | Per-video telemetry / geo state |
| Georef / mosaic | `code/utils/core/QgsFmvGeoReferencing.py`, `QgsFmvCornerEstimation.py`, `QgsFmvMosaic.py` | GCP math, footprint corner estimation, mosaic frames |
| Map center | `code/utils/core/QgsFmvMapCenter.py` | Follow platform/footprint/frame-center canvas centering |
| File dialogs | `code/utils/ui/QgsFmvFileDialogs.py` | Open/save file & folder pickers (last-path memory) |
| Layers | `code/utils/layers/` | Map layers, telemetry updates, default styles, draw/measure helpers |
| Media I/O | `code/utils/media/` | KLV readers, ffmpeg runner/probe, Qt multimedia |
| Settings | `code/utils/settings/QgsFmvSettings.py` | `settings.ini` access + `reloadRuntime()` |
| UI sources | `code/ui/*.ui` | Qt Designer sources (compile via `build.py`) |
| Generated UI | `code/gui/ui_*.py` | **Do not hand-edit** |

---

## VideoSession (replaces global `gv`)

Telemetry and georeferencing state is owned by a [`VideoSession`](code/utils/core/QgsFmvVideoSession.py)
instance on the player (`player.session`).

```
QgsFmvPlayer.__init__
    → session = VideoSession(iface)
    → session.activate()          # process-wide active session
playFile / mosaic enable
    → session.activate()
close cleanup
    → ResetData(group)            # layer caches + session.reset_telemetry()
    → session.deactivate()
```

| API | Use |
|-----|-----|
| `player.session` | Preferred inside player / controllers |
| `get_active_session()` | Helpers that do not have a player ref |
| `ensure_session(iface)` | Create-if-missing (mosaic / utils) |
| `QgsFmvUtils.gv` | **Legacy alias** of the active session — avoid in new code |

`MapCenterController` mutates `player.session.setCenterMode()` in place. Do **not**
call `setCenterMode()` from `QgsFmvUtils` when a player session already exists —
that helper recreates a session and would wipe live telemetry.

---

## Player controllers

`QgsFmvPlayer` (~1100 lines) is a composition root. Domain logic lives in
feature controllers under `code/player/features/`:

| Controller | Module | Responsibility |
|------------|--------|----------------|
| `PlaybackController` | `QgsFmvPlaybackController.py` | Open file, seek, play/pause, status |
| `RecordController` | `QgsFmvRecordController.py` | Record button animation + ffmpeg trim |
| `MetadataPipelineController` | `QgsFmvMetadataPipeline.py` | KLV worker thread, packet apply |
| `MapCenterController` | `QgsFmvMapCenterController.py` | Center-on platform/footprint/target |
| `MosaicController` | `QgsFmvMosaicController.py` | Georeferenced mosaic build |
| `ExportController` | `QgsFmvExportController.py` | Frames, geo capture, convert, bitrate, KML/GPX |
| `CloseController` | `QgsFmvCloseController.py` | Teardown / QThread shutdown |
| `TaskResultsController` | `QgsFmvTaskResults.py` | QgsTask completion dispatcher |
| `ContextMenuController` | `QgsFmvContextMenus.py` | Video / menu-bar context menus |
| `DrawToolsController` | `QgsFmvDrawToolsController.py` | Draw/measure/track/military toggles |
| `AutoSnapshot` / `AlertManager` | existing | Snapshots, telemetry alerts |
| `TimelineWidget` | `QgsFmvTimeline.py` | Custom paint; **placed in** `ui_FmvPlayer.ui` |

Qt Designer slots that must remain on `PlayerWindow` (connected from
`ui_FmvPlayer.ui`) stay as one-line delegates on the player.

---

## Paint pipeline

`VideoWidget.paintEvent` delegates to
[`VideoPaintPipeline`](code/video/playback/QgsVideoPaintPipeline.py)
in fixed z-order:

1. Background  
2. Decoded frame (`VideoSinkSurface`)  
3. User drawings  
4. Military symbol preview  
5. Object-tracking HUD  
6. Magnifier  
7. Stamp  
8. Tool placement hint  
9. Telemetry HUD overlay  

Minimap is a separate child `QWidget`, not painted inside `paintEvent`.

---

## FFmpeg subprocesses

All ffmpeg/ffprobe launches go through
[`QgsFfmpegRunner`](code/utils/media/QgsFfmpegRunner.py):

- Binary resolution from settings / PATH  
- Windows `CREATE_NO_WINDOW`  
- Optional `-preset ultrafast` for encodes  

`QgsFmvUtils._spawn()` is a thin compatibility wrapper. Multimedia fallbacks
(`QgsFmvMultimedia` / decode workers) call the runner directly.

---

## Multimedia split

| Module | Contents |
|--------|----------|
| `QgsFmvMultimedia.py` | Public façade: `createMediaPlayer`, volume/output helpers, re-exports |
| `QgsFmvMediaTypes.py` | `PlaybackState` / `MediaStatus` / `PlaylistMode` + aliases |
| `QgsFmvMediaProbe.py` | Path/duration/stream-info helpers (`probe_video_info`, …) |
| `QgsFmvDecodeWorkers.py` | `FrameDecodeWorker` (OpenCV) + `FfmpegDecodeWorker` (pipe) |
| `QgsFmvOpenCvPlayer.py` | `OpenCvMediaPlayer` QMediaPlayer-compatible backend |
| `QgsFmvQtMediaAdapter.py` | Qt multimedia last-resort adapter |
| `QgsFmvPlaylist.py` | `FmvPlaylist` + attach/get helpers |

Prefer importing from `QgsFmvMultimedia` for public API stability.

---

## UI policy

1. **Prefer `.ui` files** under `code/ui/` for dialogs and static layouts.  
2. After editing `.ui` / `.qrc` / `.ts`: run `python3 build.py` from the repo root.  
3. Python may create widgets only when they are dynamic (tables, custom paint,
   runtime overlays) or cannot be expressed in Designer.  
4. **Never hand-edit `code/gui/ui_*.py`** — regenerate from `.ui` only.  
5. Alert rules dialog: `ui_FmvAlertRule.ui` + `player/dialogs/QgsFmvAlertRule.py`.  
6. Timeline is a promoted custom widget in `ui_FmvPlayer.ui` (`TimelineWidget`).  

Sizes / geometry for Metadata and Video Info live in their `.ui` files — do not
`resize()` / `setMinimumSize()` those dialogs from Python.

---

## Layers split

| Module | Contents |
|--------|----------|
| `QgsFmvLayers.py` | Group/layer creation (`CreateVideoLayers`, `LayerFactory`, …), object tracking, platform-icon handling, generic layer helpers (`CommonLayer`, caches) |
| `QgsFmvTelemetryLayers.py` | Per-KLV-packet `Update*Data` functions (footprint, beams, trajectory, frame axis/center, platform) + their per-group caches |
| `QgsFmvLayerDefaults.py` | All `SetDefault*Style` functions (2D + 3D), the data-driven style registry, `ensure_fmv_3d_renderers`, `RestoreDefaultLayerStyles` |
| `QgsFmvDrawLayers.py` | Draw point/line/polygon/military + measure sync |
| `QgsFmvExport.py` | KML/GPX/track export |
| `QgsFmvStyles.py` / `QgsFmvLayerStyleStore.py` | Symbology |

`QgsFmvLayers` re-exports the Telemetry/Defaults/Draw helpers for
backward-compatible imports. Layer-name constants and `groupName` stay on
`QgsFmvLayers` (refreshed live by `QgsFmvSettings.reloadRuntime()` via
`setattr`); Telemetry/Defaults/Draw read them back through a lazy
`_base()` module reference to avoid a circular import at load time.

---

## Metadata / reports

| Module | Role |
|--------|------|
| `QgsFmvMetadata.py` | Metadata dock widget (table UI) |
| `QgsFmvReportGenerator.py` | PDF orchestration façade (`ReportGenerator`) |
| `QgsFmvReportMetadata.py` | Metadata leaf walk, grouping, summary fields |
| `QgsFmvReportGeo.py` | Footprint/sensor/map extent helpers |
| `QgsFmvReportPdfLayout.py` | Page metrics / image scale / PDF color constants |

---

## Video widget split

| Module | Contents |
|--------|----------|
| `QgsVideo.py` | `VideoWidget` façade (Qt events + public Set*/remove* API) |
| `QgsVideoPaintPipeline.py` | Z-order paint for overlays/drawings |
| `QgsVideoSurface.py` | Frame sink + filter apply |
| `QgsVideoState.py` | `InteractionState`, `FilterState`, `TrackLockState` |
| `QgsVideoUtils.py` | Screen↔geo math helpers |
| `QgsVideoRubberBands.py` | `RubberBandManager` |
| `QgsVideoDrawController.py` | Draw-list mutations, tool toggles, measure sync |
| `QgsVideoObjectTracking.py` | OpenCV object-tracking controller |
| `QgsVideoCursor.py` | Georeferenced cursor / MGRS labels |

---

## Detection filters split

| Module | Contents |
|--------|----------|
| `QgsFmvDetectionFilters.py` | Public `FmvDetectionFilters.*Filter` façade |
| `QgsFmvDetectionGeometry.py` | IoU/NMS/track IDs + temporal state |
| `QgsFmvDetectionPipeline.py` | Shared OpenCV/fallback detection engine (+ map notify) |
| `QgsFmvDetectionScores.py` | Per-class scorers (building/road/vehicle/…) |
| `QgsFmvDetectionMap.py` | Pixel boxes → WGS84 layer; heat trail; listener API for Sentinel |

---

## Geo-intelligence controllers

| Module | Role |
|--------|------|
| `QgsFmvMapSeekController.py` | GeoTimeIndex; Click-to-seek; **Map Time Machine**; **Lookback** (FOV revisits) |
| `QgsFmvTargetPin.py` | **Target Pin/Cue** — range, bearing, next FOV, enter alert |
| `QgsFmvGeofence.py` | AOI from footprint; frame-center enter alerts; **Detection Sentinel** |
| `QgsFmvBookmarkController.py` | Timeline markers + spatial CSV/KML export |
| `QgsFmvInstantReplay.py` | Rewind+pause on alert / sentinel |
| `QgsFmvPlaceLabel.py` | Throttled reverse geocode → HUD `PLACE` |
| `QgsFmvStoryboard.py` | Silent GeoTIFF captures on bookmark / alert |
| `QgsFmvMissionPackage.py` | After-action ZIP bundle (incl. storyboard/) |
| `QgsFmvMapCenter.py` | Follow modes + optional cinematic lerp |
| `QgsFmvSpatial.py` | Pure helpers: PIP, nearest sample, image→lat/lon |

User-facing docs: [USAGE.md § Geo-intelligence](USAGE.md#geo-intelligence).

---

## Manager / drawing splits

| Module | Contents |
|--------|----------|
| `QgsManager.py` | `FmvManager` dock façade (UI slots) |
| `QgsFmvManagerBgLoad.py` | Background media/KLV probe worker |
| `QgsFmvManagerPlaylistController.py` | Play / setup / create player |
| `QgsFmvManagerRows.py` | Row-id store + active status toggles |
| `QgsFmvDrawToolBar.py` | `DrawToolBar.drawOnVideo` façade |
| `QgsFmvDrawingConfig.py` | Pens/brushes/`setValues` / stamp |
| `QgsFmvDrawShapes.py` | Point/line/polygon/military/censure |
| `QgsFmvDrawMeasure.py` | Measure distance/area overlays |
| `QgsFmvDrawHud.py` | Tracking HUD, magnifier, stamp paint |

---

## What the plugin must not do

- Mutate global QGIS preferences (`/qgis/parallel_rendering`, OpenCL, etc.) on load  
- Keep a second copy of “current group” out of sync with `session.groupName`  
  (layer module still mirrors `groupName` today — prefer session going forward)  
- Duplicate ffmpeg `Popen` wiring outside `QgsFfmpegRunner`  
- Leave unused dialogs that build widgets in Python when a `.ui` already exists  

---

## Tests

```bash
pytest code/tests/ -v --tb=short
```

Session / runner coverage: `test_video_session.py`, `test_ffmpeg_runner.py`.
Lifecycle-sensitive paths (QThread teardown on quit) are covered by player/manager
GUI tests where the harness is available.
