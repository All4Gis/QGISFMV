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
| Player features | `code/player/features/` | Controllers (record, metadata, mosaic, map center, …) |
| Player dialogs | `code/player/dialogs/` | Settings, metadata dock, military symbols, reports |
| Overlays | `code/player/overlays/` | HUD, minimap, sensor cone, distance rings |
| Drawing toolbar | `code/player/drawing/` | Draw tools painted on video |
| Video widget | `code/video/playback/` | Decode surface, interaction, paint pipeline |
| Filters / DNN | `code/video/filters/`, `code/video/dnn/` | Classic + AI filters |
| Session state | `code/utils/core/QgsFmvVideoSession.py` | Per-video telemetry / geo state |
| Georef / mosaic | `code/utils/core/QgsFmvGeoReferencing.py`, `QgsFmvMosaic.py` | GCP math, mosaic frames |
| Layers | `code/utils/layers/` | Map layers + draw/measure layer helpers |
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
(`QgsFmvMultimedia`) call the runner directly.

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
| `QgsFmvLayers.py` | Platform/footprint/beams/trajectory updates, group creation, styles |
| `QgsFmvDrawLayers.py` | Draw point/line/polygon/military + measure sync |
| `QgsFmvExport.py` | KML/GPX/track export |
| `QgsFmvStyles.py` / `QgsFmvLayerStyleStore.py` | Symbology |

`QgsFmvLayers` re-exports draw helpers for backward-compatible imports.

---

## Metadata / reports

| Module | Role |
|--------|------|
| `QgsFmvMetadata.py` | Metadata dock widget (table UI) |
| `QgsFmvReportGenerator.py` | PDF report generation |

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
