"""Runtime Python environment tweaks for QGIS FMV.

On macOS, guards against broken user-site wheels in signed QGIS builds.
Adds ``~/.qgis-fmv-packages`` to ``sys.path`` when present.

QGIS Plugin Manager only extracts the plugin zip — it does not install pip
packages. ``ensurePymisb`` runs from ``classFactory`` (blocking, small).
The rest of ``requirements.txt`` is installed in a QgsTask after the plugin
UI is up.
"""

from __future__ import annotations

import json
import os
import platform
import sys

DEFAULT_PYMISB_SPEC = "pymisb==2.0.2"
FMV_PACKAGES_DIRNAME = ".qgis-fmv-packages"
STAMP_NAME = ".fmv-requirements.json"

# Heavy / ABI-sensitive wheels. Do not pin-upgrade a copy QGIS already ships.
# Putting a mismatched numpy next to QGIS Python can break the app.
HEAVY_PIP_PACKAGES = frozenset(
    {
        "opencv-contrib-python",
        "opencv-python",
        "opencv-python-headless",
        "matplotlib",
        "numpy",
    }
)

DIST_TO_MODULE = {
    "opencv-contrib-python": "cv2",
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
}


def fmvPackagesDir():
    """User-writable folder for FMV pip packages (no admin / no QGIS.app)."""
    return os.path.join(os.path.expanduser("~"), FMV_PACKAGES_DIRNAME)


def stampPath():
    return os.path.join(fmvPackagesDir(), STAMP_NAME)


def parseSpec(spec):
    """Return ``(distribution_name, pinned_version_or_None)`` from a pip spec."""
    spec = (spec or "").split("#", 1)[0].strip()
    if not spec:
        return "", None
    for sep in ("==", ">=", "<=", "~=", "!="):
        if sep in spec:
            name, ver = spec.split(sep, 1)
            pinned = ver.strip() if sep == "==" else None
            return name.split("[")[0].strip(), pinned
    return spec.split("[")[0].strip(), None


def parseRequirementSpecs(requirementsPath, excludeHeavy=True):
    """Return pip requirement specs from ``requirements.txt``.

    Skips comments/blank lines. When ``excludeHeavy`` is true, omits OpenCV,
    matplotlib, and numpy so first-run (classFactory) stays small.
    """
    specs = []
    try:
        with open(requirementsPath, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return [DEFAULT_PYMISB_SPEC]

    for raw in lines:
        spec = raw.split("#", 1)[0].strip()
        if not spec:
            continue
        name, _pinned = parseSpec(spec)
        if excludeHeavy and name.lower() in HEAVY_PIP_PACKAGES:
            continue
        specs.append(spec)
    return specs or [DEFAULT_PYMISB_SPEC]


def installedDistVersion(distName):
    """Installed distribution version, or None if missing."""
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:
        return None
    try:
        return version(distName)
    except PackageNotFoundError:
        return None
    except Exception:
        return None


def distImportable(distName):
    """True when the import name for ``distName`` can be imported."""
    mod = DIST_TO_MODULE.get(distName.lower(), distName.replace("-", "_"))
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


def specsNeedingInstall(specs, versionOf=None, importable=None):
    """Return specs that are missing, or (for light packages) pinned wrongly.

    Heavy packages (OpenCV / matplotlib) are installed only when they cannot
    be imported — a QGIS-bundled copy at another version is accepted.
    Numpy is never installed into the FMV target dir.
    """
    versionOf = versionOf or installedDistVersion
    importable = importable or distImportable
    needed = []
    for spec in specs:
        name, pinned = parseSpec(spec)
        if not name:
            continue
        key = name.lower()
        if key == "numpy":
            continue
        if key in HEAVY_PIP_PACKAGES:
            if importable(name):
                continue
            needed.append(spec)
            continue
        have = versionOf(name)
        if have is None:
            needed.append(spec)
        elif pinned and have != pinned:
            needed.append(spec)
    return needed


def readInstallStamp():
    path = stampPath()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def writeInstallStamp(specs):
    os.makedirs(fmvPackagesDir(), exist_ok=True)
    with open(stampPath(), "w", encoding="utf-8") as fh:
        json.dump({"specs": list(specs)}, fh)


def stampMatches(specs):
    data = readInstallStamp()
    if not data:
        return False
    return list(data.get("specs") or []) == list(specs)


def bootstrapPythonDepsPath():
    """Guard macOS user-site issues and add optional local package path."""

    local_pkgs = fmvPackagesDir()
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


def ensurePymisb():
    """Blocking first-run install of pymisb (and other light pins).

    Returns ``(ok, error_detail)``. Safe to call from ``classFactory``.
    """
    bootstrapPythonDepsPath()
    try:
        from QGIS_FMV.utils.install.QgsFmvInstaller import ensure_pymisb_blocking

        return ensure_pymisb_blocking()
    except Exception as exc:
        try:
            import pymisb  # noqa: F401

            return True, ""
        except ImportError:
            return False, str(exc)


def ensureRequiredPackages():
    """Back-compat wrapper: True when pymisb is importable after startup install."""
    ok, _err = ensurePymisb()
    return ok
