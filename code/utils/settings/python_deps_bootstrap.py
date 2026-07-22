# -*- coding: utf-8 -*-
"""Runtime Python environment tweaks for QGIS FMV.

On macOS, guards against broken user-site wheels in signed QGIS builds.
Optionally adds ``~/.qgis-fmv-packages`` to ``sys.path`` when present.
Runtime deps are installed via ``code/requirements.txt`` into QGIS Python
(``install_dev.sh`` / FMV Settings), not a local ``python_deps/`` folder.
"""

import os
import platform
import sys


def bootstrapPythonDepsPath():
    """Guard macOS user-site issues and add optional local package path."""

    local_pkgs = os.path.expanduser("~/.qgis-fmv-packages")
    if os.path.isdir(local_pkgs) and local_pkgs not in sys.path:
        # Append (do not insert): wheels here must never shadow QGIS's numpy.
        # A bad install (wrong CPython ABI / Team ID) would otherwise break QGIS.
        sys.path.append(local_pkgs)

    if platform.system() != "Darwin":
        return

    # QGIS.app is code-signed; wheels in ~/.local cannot be loaded (Team ID mismatch).
    sys.path[:] = [path for path in sys.path if ".local/lib/python" not in path]

    if os.environ.get("PYTHONNOUSERSITE", "").strip() not in ("1", "true", "yes"):
        os.environ["PYTHONNOUSERSITE"] = "1"

    try:
        import site

        site.ENABLE_USER_SITE = False
    except ImportError:
        pass
