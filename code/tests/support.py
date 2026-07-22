# -*- coding: utf-8 -*-
"""Test helpers (import paths, plugin module loader)."""

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "code"

# Subpackages under code/ that tests may import directly.
_SUBPACKAGES = (
    "utils",
    "utils.core",
    "utils.settings",
    "utils.layers",
    "utils.media",
    "utils.ui",
    "utils.install",
    "utils.vision",
    "utils.logging",
    "geo",
    "about",
    "manager",
    "gui",
    "player",
    "player.overlays",
    "player.dialogs",
    "player.drawing",
    "player.features",
    "video",
    "video.playback",
    "video.filters",
    "video.dnn",
)

# Packages whose real ``__init__.py`` must be loaded (not empty stubs).
_LOAD_INIT = frozenset(
    {
        "QGISFMV.utils.logging",
    }
)


def _ensure_subpackage(name, path):
    """Ensure an intermediate sub-package exists in sys.modules."""
    if name in sys.modules:
        return
    init_py = path / "__init__.py"
    if name in _LOAD_INIT and init_py.is_file():
        spec = importlib.util.spec_from_file_location(
            name, init_py, submodule_search_locations=[str(path)]
        )
        pkg = importlib.util.module_from_spec(spec)
        pkg.__path__ = [str(path)]
        pkg.__package__ = name
        sys.modules[name] = pkg
        spec.loader.exec_module(pkg)
        return
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(path)]
    pkg.__package__ = name
    sys.modules[name] = pkg


def ensure_qgis_fmv_package():
    if "QGISFMV" in sys.modules:
        # Ensure logging init is loaded even if an older stub was cached.
        logging_name = "QGISFMV.utils.logging"
        logging_path = CODE / "utils" / "logging"
        if logging_name in sys.modules and not hasattr(
            sys.modules[logging_name], "log"
        ):
            del sys.modules[logging_name]
            _ensure_subpackage(logging_name, logging_path)
        return

    pkg = types.ModuleType("QGISFMV")
    pkg.__path__ = [str(CODE)]
    pkg.__package__ = "QGISFMV"
    sys.modules["QGISFMV"] = pkg

    for rel in _SUBPACKAGES:
        parts = rel.split(".")
        name = "QGISFMV." + rel
        path = CODE.joinpath(*parts)
        if path.is_dir():
            _ensure_subpackage(name, path)


def ensure_pymisb_installed():
    """Skip the calling test if pymisb is not importable in this environment."""
    import pytest

    return pytest.importorskip("pymisb")


def load_plugin_module(relative_path, module_name=None):
    """Load a plugin module by file path under ``code/``."""
    ensure_qgis_fmv_package()
    if module_name is None:
        rel = relative_path.replace("\\", "/")
        if rel.endswith(".py"):
            rel = rel[:-3]
        module_name = "QGISFMV." + rel.replace("/", ".")
    file_path = CODE / relative_path
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {file_path} as {module_name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
