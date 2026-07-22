# -*- coding: utf-8 -*-
"""Root conftest — prevent the local ``code/`` package from shadowing
Python's stdlib ``code`` module (used by ``pdb`` and ``_pytest.debugging``).

Strategy: use ``importlib.util.find_spec`` to locate the stdlib ``code``
module by absolute path, bypassing sys.path which includes our ``code/`` dir.
"""

import importlib.util
import sys
import sysconfig
import types


def _ensure_stdlib_code():
    """Import the real stdlib ``code`` module before pytest can be confused."""
    # Already correct? Check for InteractiveConsole which only exists in stdlib.
    existing = sys.modules.get("code")
    if existing is not None and hasattr(existing, "InteractiveConsole"):
        return

    # Find stdlib code module by path — immune to sys.path ordering.
    stdlib_path = sysconfig.get_paths()["stdlib"]
    spec = importlib.util.spec_from_file_location(
        "code", f"{stdlib_path}/code.py",
        submodule_search_locations=[],
    )
    if spec is None or spec.origin is None:
        return  # best-effort; don't crash pytest

    real_code = importlib.util.module_from_spec(spec)
    sys.modules["code"] = real_code
    spec.loader.exec_module(real_code)


_ensure_stdlib_code()
