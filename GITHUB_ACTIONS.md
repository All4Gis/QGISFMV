# GitHub Actions

CI/CD for QGIS FMV. Workflows live in `.github/workflows/`.

<p align="center">
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="README.md">README</a>
</p>

---

## Secrets

| Secret | Used by | How to get |
|--------|---------|------------|
| `TRANSIFEX_API_TOKEN` | Translation sync | [Transifex API settings](https://www.transifex.com/user/settings/api/) |

**Settings → Secrets and variables → Actions**

---

## Workflows

### CI — `ci.yml`

| | |
|---|---|
| **Trigger** | Push / PR to `master`, `main`, `dev` |
| **Runs** | `pytest`, `pycodestyle` |
| **Purpose** | Minimum merge bar |

---

### Transifex — `transifex-sync.yml`

| | |
|---|---|
| **Trigger** | Daily 06:00 UTC; changes to `code/i18n/*.ts` |
| **Runs** | Push/pull `.ts` sources via Transifex CLI |

```bash
gh workflow run transifex-sync.yml -f command=sync

# Local
export TX_TOKEN="your-token"
./transifex-sync.sh sync
```

---

### Plugin deploy — `plugin-deploy.yml`

| | |
|---|---|
| **Trigger** | Tags `v*` (e.g. `v1.17`) |
| **Runs** | `build.py` → `deploy/plugin_zip.py` → GitHub Release |

```bash
git tag v1.18
git push origin v1.18
```

> **Note:** Workflow should install `PyQt6` + `PySide6` (or `qt6-tools-dev` on Ubuntu) before `build.py`. Qt5 packages in older workflow steps are legacy and should be updated.

---

### GitHub Pages — `pages.yml`

| | |
|---|---|
| **Trigger** | Changes to `docs/`, `_config.yml`, `README.md` |
| **Runs** | Publish docs site |

Live: [all4gis.github.io/QGISFMV](https://all4gis.github.io/QGISFMV/)

---

## Local equivalents

```bash
# Dev setup (macOS) — symlink plugin + runtime deps into QGIS Python
./install_dev.sh

# Full build (UI + resources + i18n) — outside QGIS
pip install -r requirements-dev.txt
python3 build.py

# Tests + lint (same as CI)
python -m pytest code/tests
pycodestyle --ignore=E501 code/ --exclude=code/gui

# Release ZIP
python3 deploy/plugin_zip.py
```

| File | Installed where |
|------|-----------------|
| `code/requirements.txt` | QGIS bundled Python (`install_dev.sh` / FMV Settings) |
| `requirements-dev.txt` | System / venv Python (build, pytest, lint) |

---

## Adding workflows

- Keep jobs fast — no QGIS GUI in default CI
- Cache pip when possible
- Document new secrets here

See [.github/workflows/README.md](.github/workflows/README.md) for a quick reference table.
