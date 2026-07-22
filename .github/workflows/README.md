# Workflows

Quick reference — full details in [GITHUB_ACTIONS.md](../../GITHUB_ACTIONS.md).

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `ci.yml` | Push/PR → `master`, `main`, `dev` | `pytest` + `pycodestyle` |
| `transifex-sync.yml` | Daily 06:00 UTC; `code/i18n/*.ts` changes | Sync translations |
| `plugin-deploy.yml` | Tag `v*` | `build.py` + release ZIP |
| `pages.yml` | `docs/`, `README.md` | GitHub Pages |

## Secret

`TRANSIFEX_API_TOKEN` — [get token](https://www.transifex.com/user/settings/api/)

## Local commands

```bash
./install_dev.sh                    # macOS — symlink + code/requirements.txt
pip install -r requirements-dev.txt
python3 build.py                    # UI + resources + i18n
python -m pytest code/tests         # tests
pycodestyle --ignore=E501 code/ --exclude=code/gui
python3 deploy/plugin_zip.py        # release ZIP
./transifex-sync.sh sync            # translations (needs TX_TOKEN)
```
