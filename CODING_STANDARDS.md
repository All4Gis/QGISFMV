# Coding Standards

Python conventions for QGIS FMV. PEP 8 base with QGIS/PyQt habits used in this repo.

<p align="center">
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="README.md">README</a>
</p>

---

## Tooling

```bash
# CI-aligned linter (never lint via the QGISFMV→code symlink)
pycodestyle --ignore=E203,E501,W503 code/ --exclude=code/gui,code/QGISFMV
pycodestyle --ignore=E203,E501,W503,W504 deploy/

# Optional
black code/ --exclude code/gui
isort code/ --skip code/gui
flake8 code/ --exclude code/gui
pytest code/tests
```

| Rule | Policy |
|------|--------|
| Line length | Prefer ≤ 100 chars; E501 ignored in CI |
| Indentation | 4 spaces |
| Generated code | `code/gui/*` — never lint or hand-edit |

---

## Naming

| Element | Style | Example |
|---------|--------|---------|
| Functions / methods | **camelCase** | `playFile()`, `updateLayers()` |
| Variables / attributes | **camelCase** | `self.metaReader`, `videoPath` |
| Classes | `PascalCase` | `QgsFmvPlayer`, `LocalFileMetaReader` |
| Constants | `UPPER_SNAKE_CASE` | `KLV_HEADER_0601`, `DEFAULT_TARGET_WIDTH` |
| Private helpers | `_` + camelCase | `_spawn()`, `_videoGroupName()` |
| Module files | Historical `Qgs*.py` names | Keep existing filenames |

Match the **file you edit**. Prefer camelCase when touching legacy snake_case.

Do **not** rename Qt Designer slots without updating the matching `.ui` file.

---

## Imports

```python
import os
from datetime import datetime

from qgis.core import QgsTask
from qgis.PyQt.QtCore import QCoreApplication

from pymisb.klvdata.streamparser import StreamParser

from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.settings.QgsFmvSettings import get, get_layer
from QGISFMV.utils.logging import log
```

Order: stdlib → third-party → QGIS/PyQt → `QGISFMV.*`

Plugin namespace: **`QGISFMV`** (`code/metadata.txt` → `internal_name`).

---

## PyQt / UI

| Topic | Rule |
|-------|------|
| Toolkit | **QGIS 4 / PyQt6** (`qgis.PyQt`) |
| UI source | `code/ui/*.ui` only |
| Build | `python3 build.py` from repo root → compiles `code/ui/*.ui`, `resources.qrc`, `code/i18n/*.ts` |
| i18n | `QCoreApplication.translate("Context", "text")` |
| Signals | Connect in `.ui` or `__init__` — stay consistent per dialog |

---

## Settings

| What | Where |
|------|--------|
| User-editable values | `code/settings.ini` at plugin root (gitignored) |
| Factory defaults | `QgsFmvSettings.DEFAULTS` in `code/utils/settings/QgsFmvSettings.py` |
| UI editor | **FMV Settings** dialog (`code/player/dialogs/QgsFmvSettings.py`, `code/ui/ui_FmvSettings.ui`) |
| Runtime cache | `QgsFmvUtils` / `QgsFmvLayers` module attrs — refreshed by `reloadRuntime()` |

Rules:

- Do **not** duplicate layer names or paths in new modules — use `QgsFmvSettings.get()` / `get_layer()`
- Do not read INI at import time in new modules unless via `QgsFmvSettings` helpers
- Fixed geodesy constants live in `code/geo/QgsGeoUtils.py` (not settings)
- Do **not** write global QGIS prefs (`/qgis/parallel_rendering`, OpenCL, thread caps) from the plugin

---

## Video session state

| What | Where |
|------|--------|
| Per-video telemetry / GCP state | `VideoSession` in `code/utils/core/QgsFmvVideoSession.py` |
| Owner | `QgsFmvPlayer.session` (activate on open, deactivate on close) |
| Legacy alias | `QgsFmvUtils.gv` → active session (avoid in new code) |

Prefer `player.session` or `get_active_session()`. See [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Player controllers

Domain logic belongs in `code/player/features/` (`RecordController`,
`MetadataPipelineController`, `MapCenterController`, `MosaicController`, …).
Keep `QgsFmvPlayer` as a thin composition root + Qt Designer slot delegates.

---

## UI policy

1. Static dialog layouts live in `code/ui/*.ui` — not built in Python.
2. Python may create widgets only for dynamic / custom-painted content.
3. After `.ui` / `.qrc` / `.ts` changes: `python3 build.py`.
4. **Never hand-edit `code/gui/ui_*.py`** — regenerate from `.ui` only.
5. The root `QGISFMV` symlink points at `code/` — exclude it from lint/tools.
6. Prefer Designer properties for size/geometry; avoid `resize()` / `setMinimumSize()` in Python for dialogs that already define them in `.ui`.

---

## Shared utilities

| Module | Purpose |
|--------|---------|
| `code/utils/formatting.py` | `format_length()` / `format_area()` — shared by DrawToolBar and Layers |
| `code/utils/constants.py` | Named constants (`SKIP_INTERVAL_MS`, `TRACK_MAX_MISSES`, etc.) — import instead of hard-coding |

- Use `QGISFMV.utils.constants` for numeric thresholds instead of inline magic numbers
- Use `QGISFMV.utils.formatting` for distance/area formatting instead of duplicating logic

---

## Docstrings

Public classes and non-obvious functions:

```python
def probeJson(path):
    """Return ffprobe JSON as bytes, or None on failure."""
```

Use Args / Returns for complex APIs.

---

## Error handling

- Catch **specific** exceptions
- User messages: `QgsUtils.showUserAndLogMessage()` + `Qgis.MessageLevel`
- Background work → signals to main thread; never block GUI on ffmpeg
- Internal logging: `from QGISFMV.utils.logging import log`

---

## FFmpeg / subprocess

- Binaries via `QgsFmvSettings.ffmpeg_binary()` / `ffprobe_binary()`
- **All** `Popen` launches: `code/utils/media/QgsFfmpegRunner.py`
- Probes: `code/utils/media/QgsFfmpegProbe.py`
- Legacy wrapper: `QgsFmvUtils._spawn()` → runner

---

## Video paint pipeline

- Widget: `code/video/playback/QgsVideo.py`
- Z-order painting: `code/video/playback/QgsVideoPaintPipeline.py` (`VideoPaintPipeline.paint`)
- Do not pile new overlay drawing into `paintEvent` — extend the pipeline module

---

## MISB / telemetry

| Task | Module |
|------|--------|
| Mux / demux / parse | **pymisb** (PyPI) — do not duplicate KLV in `code/` |
| Playback cache | `LocalFileMetaReader` in `code/utils/media/QgsFmvKlvReader.py` |
| Layer updates | `code/utils/layers/QgsFmvLayers.py` |

Parse and mux via **pymisb** only — do not reintroduce a local KLV parser under `code/`.

---

## Video filters & AI detection

| Module | Role |
|--------|------|
| `video/playback/QgsVideo.py` | Main video widget (OpenCV decode, interaction) |
| `video/playback/QgsVideoSurface.py` | QVideoSink surface + filter worker hook |
| `video/playback/QgsVideoState.py` | Filter / interaction state snapshots |
| `video/filters/QgsVideoFilters.py` | Classic filters; delegates detection to `FmvDetectionFilters` |
| `video/filters/QgsFmvFilterCore.py` | OpenCV bootstrap + shared image primitives |
| `video/filters/QgsFmvDetectionFilters.py` | AI/CV detection pipelines |
| `video/filters/QgsFmvFilterTuning.py` | `[FILTERS]` settings profile (aerial FMV) |
| `video/dnn/QgsFmvOnnxDetector.py` | YOLO ONNX via OpenCV DNN |
| `video/dnn/QgsFmvModelSetup.py` | VisDrone download / ONNX export |

- Player menu labels live in `code/ui/ui_FmvPlayer.ui` (**Filters → AI Detection**).
- DNN/model UI: `code/ui/ui_FmvSettings.ui` (**AI Detection** tab) + `code/player/dialogs/QgsFmvSettings.py`.
- After `.ui` changes: `python3 build.py`.
- Tunable defaults documented in `code/settings.sample.ini` (`[DNN]`, `[FILTERS]`).

---

## Python dependencies

- Runtime list: `code/requirements.txt`
- Dev install: `./install_dev.sh` (QGIS Python) + `pip install -r requirements-dev.txt` (build/tests)
- Do not ship a `code/python_deps/` vendor folder

---

## Git hygiene

- Focused commits; no drive-by refactors
- Never commit: `.pyc`, `__pycache__`, `settings.ini`, `python_deps/`, secrets
- User-visible releases: update `code/metadata.txt` changelog

---

## References

- [QGIS Plugin Guidelines](https://plugins.qgis.org/plugins/instructions/)
- [Contributing](CONTRIBUTING.md)
- [pymisb on PyPI](https://pypi.org/project/pymisb/)
