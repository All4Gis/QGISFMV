"""The release zip must ship requirements.txt for first-run pip."""

from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _plugin_zip():
    import importlib.util

    path = ROOT / "deploy" / "plugin_zip.py"
    spec = importlib.util.spec_from_file_location("qgis_fmv_plugin_zip", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPluginZipRequirements:
    def test_requirements_txt_not_excluded(self):
        zipmod = _plugin_zip()
        assert not any(
            fnmatch("requirements.txt", pattern) for pattern in zipmod.EXCLUDE_PATTERNS
        )

    def test_required_files_include_requirements(self):
        zipmod = _plugin_zip()
        assert "requirements.txt" in zipmod.REQUIRED_IN_ZIP
        for name in zipmod.REQUIRED_IN_ZIP:
            assert (ROOT / "code" / name).is_file(), name
