"""Tests for first-run pip requirement parsing (no QGIS)."""

from pathlib import Path

from code.tests.support import load_plugin_module

ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS = ROOT / "code" / "requirements.txt"


def _boot():
    return load_plugin_module(
        "utils/settings/python_deps_bootstrap.py",
        "QGIS_FMV.utils.settings.python_deps_bootstrap",
    )


class TestParseRequirementSpecs:
    def test_skips_comments_and_heavy_packages(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text(
            "# comment\n"
            "pymisb==2.0.2\n"
            "defusedxml==0.7.1\n"
            "mgrs==1.5.4\n"
            "matplotlib==3.11.2\n"
            "opencv-contrib-python==4.13.0.92\n"
            "numpy==2.0.0\n",
            encoding="utf-8",
        )
        boot = _boot()
        specs = boot.parseRequirementSpecs(str(req), excludeHeavy=True)
        assert specs == ["pymisb==2.0.2", "defusedxml==0.7.1", "mgrs==1.5.4"]

    def test_includes_heavy_when_requested(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("pymisb==2.0.2\nmatplotlib==3.11.2\n", encoding="utf-8")
        boot = _boot()
        specs = boot.parseRequirementSpecs(str(req), excludeHeavy=False)
        assert "matplotlib==3.11.2" in specs

    def test_missing_file_falls_back_to_pymisb(self, tmp_path):
        boot = _boot()
        specs = boot.parseRequirementSpecs(str(tmp_path / "missing.txt"))
        assert specs == [boot.DEFAULT_PYMISB_SPEC]

    def test_real_requirements_keep_pymisb(self):
        boot = _boot()
        specs = boot.parseRequirementSpecs(str(REQUIREMENTS), excludeHeavy=True)
        assert "pymisb==2.0.2" in specs
        assert boot.DEFAULT_PYMISB_SPEC == "pymisb==2.0.2"
        assert not any("opencv" in s for s in specs)
        assert not any(s.startswith("matplotlib") for s in specs)

    def test_real_requirements_full_list(self):
        boot = _boot()
        specs = boot.parseRequirementSpecs(str(REQUIREMENTS), excludeHeavy=False)
        assert "pymisb==2.0.2" in specs
        assert any(s.startswith("matplotlib==") for s in specs)
        assert any(s.startswith("opencv-contrib-python==") for s in specs)
        assert any(s.startswith("defusedxml==") for s in specs)
        assert any(s.startswith("mgrs==") for s in specs)


class TestParseSpec:
    def test_exact_pin(self):
        boot = _boot()
        assert boot.parseSpec("pymisb==2.0.2") == ("pymisb", "2.0.2")

    def test_ignores_comment(self):
        boot = _boot()
        assert boot.parseSpec("mgrs==1.5.4  # coords")[0] == "mgrs"


class TestSpecsNeedingInstall:
    def test_missing_light_package(self):
        boot = _boot()
        needed = boot.specsNeedingInstall(
            ["pymisb==2.0.2"],
            versionOf=lambda name: None,
            importable=lambda name: False,
        )
        assert needed == ["pymisb==2.0.2"]

    def test_wrong_pymisb_version(self):
        boot = _boot()
        needed = boot.specsNeedingInstall(
            ["pymisb==2.0.2"],
            versionOf=lambda name: "2.0.1",
            importable=lambda name: True,
        )
        assert needed == ["pymisb==2.0.2"]

    def test_matching_pin_skipped(self):
        boot = _boot()
        needed = boot.specsNeedingInstall(
            ["pymisb==2.0.2"],
            versionOf=lambda name: "2.0.2",
            importable=lambda name: True,
        )
        assert needed == []

    def test_qgis_matplotlib_accepted(self):
        boot = _boot()
        needed = boot.specsNeedingInstall(
            ["matplotlib==3.11.2"],
            versionOf=lambda name: "3.8.0",
            importable=lambda name: True,
        )
        assert needed == []

    def test_missing_matplotlib_installed(self):
        boot = _boot()
        needed = boot.specsNeedingInstall(
            ["matplotlib==3.11.2"],
            versionOf=lambda name: None,
            importable=lambda name: False,
        )
        assert needed == ["matplotlib==3.11.2"]

    def test_never_installs_numpy(self):
        boot = _boot()
        needed = boot.specsNeedingInstall(
            ["numpy==2.0.0"],
            versionOf=lambda name: None,
            importable=lambda name: False,
        )
        assert needed == []


class TestInstallStamp:
    def test_roundtrip(self, tmp_path, monkeypatch):
        boot = _boot()
        monkeypatch.setattr(boot, "fmvPackagesDir", lambda: str(tmp_path))
        specs = ["pymisb==2.0.2", "mgrs==1.5.4"]
        boot.writeInstallStamp(specs)
        assert boot.stampMatches(specs)
        assert not boot.stampMatches(["pymisb==2.0.1"])


class TestEnsureRequiredPackages:
    def test_true_when_pymisb_already_importable(self):
        boot = _boot()
        try:
            import pymisb  # noqa: F401
        except ImportError:
            return
        assert boot.ensureRequiredPackages() is True
