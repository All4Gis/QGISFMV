# -*- coding: utf-8 -*-
"""Cross-platform path helper tests (Mac / Linux / Windows)."""

import os
import platform
from code.tests.support import load_plugin_module


class TestDefaultFfmpegFolder:
    def test_windows_uses_localappdata(self, tmp_path, monkeypatch):
        settings = load_plugin_module("utils/settings/QgsFmvSettings.py")
        monkeypatch.setattr(settings.platform, "system", lambda: "Windows")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData"))
        folder = settings._default_ffmpeg_folder()
        assert folder == os.path.join(str(tmp_path / "AppData"), "QGISFMV", "ffmpeg")

    def test_windows_falls_back_to_home(self, tmp_path, monkeypatch):
        settings = load_plugin_module("utils/settings/QgsFmvSettings.py")
        monkeypatch.setattr(settings.platform, "system", lambda: "Windows")
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
        monkeypatch.setattr(
            settings.os.path, "expanduser", lambda p: str(tmp_path / "home")
        )
        folder = settings._default_ffmpeg_folder()
        assert folder == os.path.join(str(tmp_path / "home"), "QGISFMV", "ffmpeg")
        # Must not start with a bare separator from empty LOCALAPPDATA.
        assert not folder.startswith(os.sep + "QGISFMV")

    def test_windows_whitespace_localappdata_falls_back(self, tmp_path, monkeypatch):
        settings = load_plugin_module("utils/settings/QgsFmvSettings.py")
        monkeypatch.setattr(settings.platform, "system", lambda: "Windows")
        monkeypatch.setenv("LOCALAPPDATA", "   ")
        monkeypatch.setattr(
            settings.os.path, "expanduser", lambda p: str(tmp_path / "home")
        )
        folder = settings._default_ffmpeg_folder()
        assert folder == os.path.join(str(tmp_path / "home"), "QGISFMV", "ffmpeg")

    def test_linux_prefers_which(self, tmp_path, monkeypatch):
        settings = load_plugin_module("utils/settings/QgsFmvSettings.py")
        monkeypatch.setattr(settings.platform, "system", lambda: "Linux")
        fake = tmp_path / "bin" / "ffmpeg"
        fake.parent.mkdir(parents=True)
        fake.write_text("x")
        monkeypatch.setattr(
            settings.shutil,
            "which",
            lambda name: str(fake) if name == "ffmpeg" else None,
        )
        folder = settings._default_ffmpeg_folder()
        assert folder == str(fake.parent)

    def test_darwin_prefers_which(self, tmp_path, monkeypatch):
        settings = load_plugin_module("utils/settings/QgsFmvSettings.py")
        monkeypatch.setattr(settings.platform, "system", lambda: "Darwin")
        fake = tmp_path / "homebrew" / "bin" / "ffmpeg"
        fake.parent.mkdir(parents=True)
        fake.write_text("x")
        monkeypatch.setattr(
            settings.shutil,
            "which",
            lambda name: str(fake) if name == "ffmpeg" else None,
        )
        folder = settings._default_ffmpeg_folder()
        assert folder == str(fake.parent)


class TestBootstrapPackagesPath:
    def test_uses_os_path_join(self, tmp_path, monkeypatch):
        boot = load_plugin_module(
            "utils/settings/python_deps_bootstrap.py",
            "QGISFMV.utils.settings.python_deps_bootstrap",
        )
        home = tmp_path / "home"
        pkg = home / ".qgis-fmv-packages"
        pkg.mkdir(parents=True)
        monkeypatch.setattr(
            boot.os.path, "expanduser", lambda p: str(home) if p == "~" else p
        )
        monkeypatch.setattr(boot.platform, "system", lambda: "Linux")
        # Ensure append happens with joined path.
        before = list(boot.sys.path)
        boot.bootstrapPythonDepsPath()
        expected = os.path.join(str(home), ".qgis-fmv-packages")
        assert expected in boot.sys.path
        # Restore path for other tests.
        boot.sys.path[:] = before
