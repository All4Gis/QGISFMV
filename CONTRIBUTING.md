# Contributing

Thanks for improving QGIS FMV. This guide covers setup, conventions, and how to land changes.

<p align="center">
  <a href="README.md">README</a> ·
  <a href="USAGE.md">Usage</a> ·
  <a href="ARCHITECTURE.md">Architecture</a> ·
  <a href="CODING_STANDARDS.md">Coding standards</a>
</p>

---

## How to help

| Channel | Link |
|---------|------|
| Bug reports & features | [GitHub Issues](https://github.com/All4Gis/QGISFMV/issues) |
| Community Q&A | [Discussions](https://github.com/All4Gis/QGISFMV/discussions) |
| Code & docs | Pull requests |
| Translations | [Transifex](https://www.transifex.com/all4gis/QGISFMV/) |
| Screenshots | [assets/README.md](assets/README.md) — QGIS 4 captures welcome |

---

## Development setup

### 1. Clone

```bash
git clone https://github.com/YOUR_USERNAME/QGISFMV.git
cd QGISFMV
```

### 2. Install & link (recommended)

| OS | Command | What it does |
|----|---------|--------------|
| **macOS** | `./install_dev.sh` | Symlink plugin + deps into `~/.qgis-fmv-packages` (no sudo) |
| **macOS** | `./debug_qgis.sh` | Start QGIS with `FRAN_DEBUG=1` for Cursor attach |
| **Windows** | `install_dev.bat` | Junction + install requirements |

Deps-only (no symlink):

```bash
bash scripts/install_plugin_requirements.sh
```

### 3. Python dependencies

| File | Purpose | Installed by |
|------|---------|--------------|
| `code/requirements.txt` | **Runtime** in QGIS: pymisb, OpenCV, matplotlib | `install_dev.sh` / FMV Settings |
| `requirements-dev.txt` | Tests, lint, **PyQt6 + PySide6** (build) | Your system `pip` (outside QGIS) |

Manual install into QGIS Python (macOS example):

```bash
QGIS_PY="/Applications/QGIS.app/Contents/MacOS/python3.12"
$QGIS_PY -m pip install -r code/requirements.txt
$QGIS_PY -m pip install -r requirements-dev.txt   # optional, for build tools only
```

> Do **not** use `pip --user` for OpenCV on macOS — it breaks signed QGIS. Use QGIS bundled Python (as `install_dev.sh` does).

### 4. Build UI & resources (outside QGIS)

```bash
pip install -r requirements-dev.txt
python3 build.py
```

`build.py` compiles all `code/ui/*.ui` (manager, player, metadata, settings, military symbols, multiplexer, streams, about, brightness/contrast), `resources.qrc`, and `code/i18n/*.ts`. It finds `pyuic6`, `pyside6-rcc`, and `pyside6-lrelease` even when pip script folders are not on `PATH`. On Linux you can alternatively install `qt6-tools-dev` / `pyqt6-dev-tools`.

### 5. Reload in QGIS

Enable **Plugin Reloader** → reload **QGIS FMV** after code changes.

### 6. Run tests

No QGIS GUI required:

```bash
python -m pytest code/tests
# Windows: code\tests\run_tests.bat
```

Covers pymisb integration, KLV reader, settings, ffmpeg runner, video session lifecycle, mosaic helpers, **video filters / AI detection** (`test_video_filters.py`, `test_onnx_detector.py`).

### 7. Settings

- Runtime file: **`code/settings.ini`** at plugin root (auto-created; gitignored)
- Templates: **`code/settings.sample.ini`** (`[DNN]`, `[FILTERS]`, `[MOSAIC]`, …)
- Code API: **`code/utils/settings/QgsFmvSettings.py`**
- UI: **FMV Settings** dialog — prefer over hand-editing INI
- Never commit machine-specific paths

---

## Project layout

See [ARCHITECTURE.md](ARCHITECTURE.md) for session/controllers/paint pipeline details.

```
code/
├── QgsFmv.py               # Plugin entry (classFactory)
├── manager/                # Video manager, multiplexer, streams
├── player/
│   ├── QgsFmvPlayer.py     # Player dock (composition root)
│   ├── dialogs/            # Settings, metadata, reports, military symbols
│   ├── overlays/           # HUD, mini map, sensor cone, distance rings
│   ├── drawing/            # On-video draw toolbar
│   └── features/           # Controllers: playback, record, export, close, menus, mosaic, …
├── video/
│   ├── playback/           # QgsVideo, paint pipeline, surface, state
│   ├── filters/            # VideoFilters, detection, FilterWorker, brightness dialog
│   └── dnn/                # QgsFmvOnnxDetector, QgsFmvModelSetup
├── utils/
│   ├── settings/           # QgsFmvSettings, python_deps bootstrap
│   ├── layers/             # QgsFmvLayers, DrawLayers, styles, export
│   ├── media/              # Multimedia, FfmpegRunner, probe, KLV, streams
│   ├── core/               # VideoSession, QgsFmvUtils, georef, mosaic
│   ├── ui/                 # QgsUtils, JSON model, plots, resources
│   ├── logging/            # `from QGISFMV.utils.logging import log`
│   ├── install/            # QgsFmvInstaller
│   └── vision/             # Object tracker
├── geo/                    # Geodesy (QgsGeoUtils)
├── about/                  # About dialog
├── settings.ini            # Runtime config (gitignored; use FMV Settings UI)
├── settings.sample.ini     # Template with comments
├── gui/                    # Generated PyQt6 — do not hand-edit
├── ui/                     # Qt Designer .ui — edit these
├── images/                 # Icons (bundled via resources.qrc)
├── i18n/                   # Translations (.ts → .qm via build.py)
└── requirements.txt        # Runtime deps for QGIS Python
```

Root `QGISFMV` → symlink to `code/` (QGIS plugin name). Edit/lint `code/` only.

**UI workflow:** edit `code/ui/*.ui` → `python3 build.py` → never edit `code/gui/ui_*.py` directly.
Prefer Designer for dialog chrome; Python only for dynamic/custom-painted widgets.

`build.py` post-patches `pyuic6` output for QGIS 4 / PyQt6 (`qgis.PyQt` imports, `QDockWidget.DockWidgetFeature`, `QToolButton` menus instead of invalid `addSeparator()`).

### Icons

- Toolbar PNGs: `code/images/`
- Platform SVGs: `code/images/platforms/`
- Military symbols: `code/images/military/`
- Bundle: `code/ui/resources.qrc` → `python3 build.py`

---

## Making changes

### Branches

| Prefix | Use |
|--------|-----|
| `feature/` | New functionality |
| `fix/` | Bug fixes |
| `docs/` | Documentation & screenshots |
| `refactor/` | Internal restructuring |

### Commits

[Conventional Commits](https://www.conventionalcommits.org/) preferred:

```text
feat(player): add mini map PiP overlay
fix(layers): split trajectory on playback loop
docs: refresh USAGE for QGIS 4
```

### Lint

```bash
pycodestyle --ignore=E501 code/ --exclude=code/gui
```

Optional: `black`, `isort`, `flake8` (see `requirements-dev.txt`).

---

## Pull request checklist

- [ ] `python3 build.py` succeeds (if UI/i18n/resources changed)
- [ ] `pytest code/tests` passes
- [ ] Lint clean on touched Python files
- [ ] Manual test in QGIS 4 (load video, play, multiplexer if relevant)
- [ ] Docs updated for behavior/UI changes
- [ ] Screenshots updated in `assets/` when UI changed — see [assets/README.md](assets/README.md)
- [ ] No secrets or local paths in committed files

**Template:** [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md)

---

## Bug reports

Include:

- QGIS version & OS
- Plugin version (`code/metadata.txt`)
- Steps to reproduce
- Expected vs actual
- File type (no classified media)

**Template:** [bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md)

---

## Translations

Sources: `code/i18n/qgisfmv_*.ts`

```bash
export TX_TOKEN="your-token"
./transifex-sync.sh sync
```

---

## License

Contributions are **GPL v3**, consistent with QGIS plugin requirements — [LICENSE](LICENSE).
