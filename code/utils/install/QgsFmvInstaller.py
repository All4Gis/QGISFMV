# -*- coding: utf-8 -*-
"""Dependency checks and optional setup for QGIS FMV (Windows / macOS / Linux)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Optional, Sequence, Tuple
from urllib.request import Request, urlopen

from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QProgressBar
from qgis.core import Qgis as QGis
from qgis.utils import iface

from QGISFMV.utils.settings.QgsFmvSettings import (
    ffmpeg_binary,
    plugin_root,
    reloadRuntime,
    repair_ffmpeg_setting,
    save,
    set_value,
)
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.logging import log

# ---------------------------------------------------------------------------
# Constants / platform
# ---------------------------------------------------------------------------

CREATE_NO_WINDOW = 0x08000000
FFMPEG_WIN_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
USER_AGENT = "QGIS-FMV/1.17"

WINDOWS = platform.system() == "Windows"
DARWIN = platform.system() == "Darwin"
LINUX = platform.system() == "Linux"

_Tr = lambda text: QCoreApplication.translate("QgsFmvInstaller", text)


# ---------------------------------------------------------------------------
# Subprocess / Python helpers
# ---------------------------------------------------------------------------

def _mac_qgis_python_candidates():
    """Return likely QGIS Python interpreters on macOS (wrapper first)."""
    app = os.environ.get("QGIS_APP", "/Applications/QGIS.app")
    return [
        os.path.join(app, "Contents", "MacOS", "python"),
        os.path.join(app, "Contents", "MacOS", "bin", "python3"),
        os.path.join(app, "Contents", "Resources", "python", "bin", "python3"),
        os.path.join(app, "Contents", "MacOS", "python3.12"),
        os.path.join(app, "Contents", "MacOS", "bin", "python3.12"),
        os.path.join(app, "Contents", "MacOS", "python3"),
    ]


def _python_executable() -> str:
    """Return the bundled Python interpreter, not qgis-bin (which relaunches QGIS)."""
    if DARWIN:
        for candidate in _mac_qgis_python_candidates():
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

    exe = sys.executable or "python"
    base = os.path.basename(exe).lower()
    if base.startswith("qgis") or base in ("qgis-bin.exe", "qgis.exe"):
        bin_dir = os.path.dirname(exe)
        for name in ("python.exe", "python3.exe", "python312.exe", "python"):
            candidate = os.path.join(bin_dir, name)
            if os.path.isfile(candidate):
                return candidate
    return exe


def _fmv_packages_dir() -> str:
    return os.path.expanduser("~/.qgis-fmv-packages")


def _subprocess_kwargs(env=None, input_bytes=None):
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": env,
    }
    if input_bytes is None:
        kwargs["text"] = True
    else:
        kwargs["input"] = input_bytes
    if WINDOWS:
        kwargs["creationflags"] = CREATE_NO_WINDOW
    return kwargs


def _pip_env(extra_pythonpath: Optional[str] = None) -> dict:
    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    pkgs = _fmv_packages_dir()
    parts = []
    if extra_pythonpath:
        parts.append(extra_pythonpath)
    if os.path.isdir(pkgs):
        parts.append(pkgs)
    if parts:
        env["PYTHONPATH"] = os.pathsep.join(parts + [env.get("PYTHONPATH", "")])
    return env


def _run_cmd(cmd: Sequence[str], env=None, input_bytes=None) -> Tuple[bool, str]:
    """Run a command; return (ok, message). Prefer stdout on success, stderr on failure."""
    try:
        proc = subprocess.run(list(cmd), **_subprocess_kwargs(env, input_bytes))
    except OSError as exc:
        return False, str(exc)

    if input_bytes is None:
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
    else:
        stdout = (proc.stdout or b"").decode(errors="replace")
        stderr = (proc.stderr or b"").decode(errors="replace")

    if proc.returncode == 0:
        out = (stdout or stderr).strip()
    else:
        out = (stderr or stdout).strip()
    return proc.returncode == 0, out


def _run_pip_env(args: Sequence[str], target: Optional[str] = None) -> Tuple[bool, str]:
    """Run ``python -m pip …`` with PYTHONNOUSERSITE; optional ``--target``."""
    cmd = [_python_executable(), "-m", "pip", *args]
    if target and "--target" not in cmd:
        cmd.extend(["--target", target])
    return _run_cmd(cmd, env=_pip_env())


def _run_pip(args: Sequence[str]) -> Tuple[bool, str]:
    return _run_pip_env(args)


def _bootstrap_python_path() -> None:
    try:
        from QGISFMV.utils.settings.python_deps_bootstrap import bootstrapPythonDepsPath

        bootstrapPythonDepsPath()
    except Exception as exc:
        log.debug("Python deps bootstrap failed: %s", exc)


def _cv2_available() -> bool:
    try:
        from QGISFMV.utils.vision.QgsObjectTracker import cv2_available

        return bool(cv2_available())
    except Exception as exc:
        log.debug("cv2 availability check failed: %s", exc)
        return False


def _try_import(module_name: str) -> Tuple[bool, str]:
    """Return (ok, version_or_empty)."""
    try:
        mod = __import__(module_name)
        return True, getattr(mod, "__version__", "") or ""
    except Exception as exc:
        log.debug("import check for %s failed: %s", module_name, exc)
        return False, ""


def _msg(title: str, text: str = "", level=QGis.MessageLevel.Info, duration: int = 6):
    qgsu.showUserAndLogMessage(title, text, level=level, duration=duration)


def _prompt_yes(title: str, question: str, detail: str = "", icon: str = "Information") -> bool:
    return qgsu.CustomMessage(title, question, detail, icon=icon) == QMessageBox.StandardButton.Yes


# ---------------------------------------------------------------------------
# Progress UI (lazy — no QWidget at import time)
# ---------------------------------------------------------------------------

_progress_bar: Optional[QProgressBar] = None


def _progress() -> QProgressBar:
    global _progress_bar
    if _progress_bar is None:
        _progress_bar = QProgressBar()
        _progress_bar.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
    return _progress_bar


def _push_progress(title: str):
    bar = iface.messageBar().createMessage("QGIS FMV", title)
    bar.layout().addWidget(_progress())
    iface.messageBar().pushWidget(bar, QGis.MessageLevel.Info)
    return bar


def _clear_progress():
    iface.messageBar().clearWidgets()
    if _progress_bar is not None:
        _progress_bar.setValue(0)


def _download(url: str, dest: str, with_progress: bool = True) -> None:
    """Download ``url`` to ``dest`` with a FMV User-Agent (no global urllib opener)."""
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req) as resp, open(dest, "wb") as out:
        total = int(resp.headers.get("Content-Length") or 0)
        read = 0
        chunk = 64 * 1024
        while True:
            data = resp.read(chunk)
            if not data:
                break
            out.write(data)
            if with_progress and total > 0:
                read += len(data)
                _progress().setValue(int(read * 100 / total))


# ---------------------------------------------------------------------------
# pip bootstrap / requirements
# ---------------------------------------------------------------------------

def _ensure_pip() -> bool:
    """Make ``python -m pip`` available (ensurepip or get-pip into packages dir)."""
    ok, _ = _run_pip(["--version"])
    if ok:
        return True

    python = _python_executable()
    env = _pip_env()
    ok, _ = _run_cmd([python, "-m", "ensurepip", "--upgrade"], env=env)
    if ok and _run_pip(["--version"])[0]:
        return True

    target = _fmv_packages_dir()
    os.makedirs(target, exist_ok=True)
    get_pip = os.path.join(tempfile.gettempdir(), "qgis_fmv_get_pip.py")
    try:
        _download(GET_PIP_URL, get_pip, with_progress=False)
        ok, _ = _run_cmd(
            [python, get_pip, "--target", target, "--no-warn-script-location"],
            env=env,
        )
    except Exception as exc:
        log.debug("get-pip download/install failed: %s", exc)
        return False
    finally:
        try:
            os.remove(get_pip)
        except OSError:
            pass

    if not ok:
        return False
    return _run_cmd(
        [python, "-m", "pip", "--version"], env=_pip_env(extra_pythonpath=target)
    )[0]


def _requirements_path() -> Optional[str]:
    path = os.path.join(plugin_root(), "requirements.txt")
    return path if os.path.isfile(path) else None


def _install_opencv_package() -> Tuple[bool, str]:
    """Install opencv-contrib-python into ~/.qgis-fmv-packages (no sudo)."""
    target = _fmv_packages_dir()
    os.makedirs(target, exist_ok=True)
    return _run_pip_env(
        ["install", "opencv-contrib-python==4.13.0.92"], target=target
    )


def _clean_mac_user_site_packages() -> None:
    """Best-effort removal of FMV wheels from ~/.local (breaks signed QGIS)."""
    packages = [
        "opencv-contrib-python",
        "opencv-python",
        "opencv-python-headless",
        "matplotlib",
        "numpy",
        "contourpy",
        "kiwisolver",
        "pillow",
    ]
    _run_pip(["uninstall", "-y", *packages])


def check_python_deps() -> Tuple[bool, str]:
    """Return ``(ok, details)``. On macOS, OpenCV is optional."""
    _bootstrap_python_path()

    pymisb_ok, _ = _try_import("pymisb")
    mpl_ok, mpl_ver = _try_import("matplotlib")
    cv2_ok = _cv2_available()
    cv2_ver = ""
    if cv2_ok:
        ok, cv2_ver = _try_import("cv2")
        cv2_ok = ok

    details = [
        "pymisb OK" if pymisb_ok else "pymisb unavailable",
        f"CV {cv2_ver}" if cv2_ok else "CV unavailable",
        f"matplotlib {mpl_ver}" if mpl_ok else "matplotlib unavailable",
    ]
    if DARWIN and not cv2_ok:
        details.append("CV optional — numpy tracking fallback")
        return pymisb_ok, ", ".join(details)

    return (pymisb_ok and cv2_ok), ", ".join(details)


def install_pymisb() -> bool:
    """Install pymisb from PyPI into the FMV packages dir."""
    target = _fmv_packages_dir()
    os.makedirs(target, exist_ok=True)
    ok, msg = _run_pip_env(["install", "pymisb==2.0.0"], target=target)
    if not ok:
        _msg(_Tr("pymisb install failed"), msg, QGis.MessageLevel.Critical)
    return ok


def _remove_numpy_from_target(target: str) -> None:
    """Remove numpy from the target dir to avoid conflicting with QGIS's own numpy."""
    for name in ("numpy", "numpy-*"):
        import glob as _glob
        for path in _glob.glob(os.path.join(target, name + ".dist-info")):
            shutil.rmtree(path, ignore_errors=True)
        pkg_dir = os.path.join(target, "numpy")
        if os.path.isdir(pkg_dir):
            shutil.rmtree(pkg_dir, ignore_errors=True)
        core_dir = os.path.join(target, "numpy.libs")
        if os.path.isdir(core_dir):
            shutil.rmtree(core_dir, ignore_errors=True)


def install_pip_requirements() -> bool:
    """Install requirements.txt into a user-writable folder (never needs sudo)."""
    req = _requirements_path()
    if not req:
        _msg(
            _Tr("requirements.txt not found in {}").format(plugin_root()),
            level=QGis.MessageLevel.Critical,
        )
        return False

    target = _fmv_packages_dir()
    os.makedirs(target, exist_ok=True)
    python = _python_executable()

    if DARWIN:
        _clean_mac_user_site_packages()

    _msg(
        _Tr("Installing dependencies"),
        _Tr(
            "Installing into {} (no admin / no write to QGIS.app).\nPython: {}"
        ).format(target, python),
        QGis.MessageLevel.Info,
        duration=8,
    )

    if not _ensure_pip():
        _msg(
            _Tr("pip is not available"),
            _Tr(
                "Could not bootstrap pip without admin rights.\n"
                "From the repo run:\n"
                "  bash scripts/install_plugin_requirements.sh"
            ),
            QGis.MessageLevel.Critical,
        )
        return False

    _run_pip_env(["install", "--upgrade", "pip", "setuptools", "wheel"], target=target)
    ok, err = _run_pip_env(["install", "-r", req], target=target)
    if not ok:
        _msg(
            _Tr("pip install failed"),
            err
            or _Tr(
                "Try from the repo (no sudo):\n"
                "  bash scripts/install_plugin_requirements.sh"
            ),
            QGis.MessageLevel.Critical,
        )
        return False

    # Remove numpy from the target dir — QGIS bundles its own version and
    # a mismatched numpy in ~/.qgis-fmv-packages breaks qgis.core imports.
    _remove_numpy_from_target(target)

    _bootstrap_python_path()
    if not _cv2_available():
        _install_opencv_package()
        _bootstrap_python_path()

    if not _cv2_available() and DARWIN:
        _msg(
            _Tr("Native CV library not loaded"),
            _Tr(
                "Packages are in {}.\n"
                "On signed macOS QGIS, CV wheels outside the app are often "
                "blocked without admin rights.\n"
                "Playback and MISB still work; object tracking uses numpy fallback."
            ).format(target),
            QGis.MessageLevel.Warning,
            duration=12,
        )
    else:
        _msg(_Tr("Dependencies installed"), target, QGis.MessageLevel.Success)

    return True


# ---------------------------------------------------------------------------
# FFmpeg
# ---------------------------------------------------------------------------

def check_ffmpeg() -> Tuple[bool, str]:
    """Return (ok, path_or_message) for the configured FFmpeg binary."""
    path = ffmpeg_binary()
    if path and os.path.isfile(path):
        return True, path
    return False, _Tr(
        "FFmpeg not found. Set the folder in Settings or install FFmpeg for your OS."
    )


def _default_ffmpeg_dir() -> str:
    if WINDOWS:
        return os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "QGISFMV", "ffmpeg"
        )
    if DARWIN:
        return os.path.join(os.path.expanduser("~"), "QGISFMV", "ffmpeg")
    return "/usr/bin"


def _save_ffmpeg_dir(bin_dir: str) -> None:
    set_value("GENERAL", "ffmpeg", bin_dir)
    save()
    reloadRuntime()


def _extract_windows_ffmpeg(zip_path: str, dest_dir: str) -> bool:
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            base = os.path.basename(name)
            if base.lower() in ("ffmpeg.exe", "ffprobe.exe"):
                target = os.path.join(dest_dir, base)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    return os.path.isfile(os.path.join(dest_dir, "ffmpeg.exe"))


def install_ffmpeg_windows() -> bool:
    """Download and extract FFmpeg binaries on Windows."""
    dest = _default_ffmpeg_dir()
    _push_progress(_Tr("Downloading FFmpeg…"))
    tmp = tempfile.mkdtemp(prefix="qgis_fmv_ffmpeg_")
    zip_path = os.path.join(tmp, "ffmpeg.zip")
    try:
        _download(FFMPEG_WIN_URL, zip_path, with_progress=True)
        if not _extract_windows_ffmpeg(zip_path, dest):
            _msg(
                _Tr("FFmpeg download failed"),
                _Tr("Could not extract ffmpeg.exe from the archive."),
                QGis.MessageLevel.Critical,
            )
            return False
        _save_ffmpeg_dir(dest)
        _msg(_Tr("FFmpeg installed"), dest, QGis.MessageLevel.Success)
        return True
    except Exception as exc:
        _msg(_Tr("FFmpeg download failed"), str(exc), QGis.MessageLevel.Critical)
        return False
    finally:
        _clear_progress()
        shutil.rmtree(tmp, ignore_errors=True)


def _brew_ffmpeg_bin_dir() -> str:
    ok, out = _run_cmd(["brew", "--prefix", "ffmpeg"])
    brew_path = out if ok and out else "/opt/homebrew"
    bin_dir = brew_path if brew_path.endswith("bin") else os.path.join(brew_path, "bin")
    if os.path.isfile(os.path.join(bin_dir, "ffmpeg")):
        return bin_dir
    for candidate in ("/opt/homebrew/bin", "/usr/local/bin"):
        if os.path.isfile(os.path.join(candidate, "ffmpeg")):
            return candidate
    return bin_dir


def install_ffmpeg_mac() -> bool:
    """Install FFmpeg on macOS via Homebrew or direct download."""
    if shutil.which("brew"):
        _push_progress(_Tr("Installing FFmpeg via Homebrew…"))
        try:
            ok, err = _run_cmd(["brew", "install", "ffmpeg"])
            if ok:
                bin_dir = _brew_ffmpeg_bin_dir()
                _save_ffmpeg_dir(bin_dir)
                _msg(
                    _Tr("FFmpeg installed via Homebrew"),
                    bin_dir,
                    QGis.MessageLevel.Success,
                )
                return True
            _msg(_Tr("Homebrew install failed"), err, QGis.MessageLevel.Warning)
        finally:
            _clear_progress()

    _msg(
        _Tr("Install FFmpeg manually"),
        _Tr(
            "Install Homebrew (https://brew.sh) and run: brew install ffmpeg\n"
            "Then set the binary folder in FMV Settings."
        ),
        QGis.MessageLevel.Info,
        duration=8,
    )
    return False


def _linux_install_cmd() -> Optional[list]:
    if shutil.which("apt-get"):
        return ["sudo", "apt-get", "install", "-y", "ffmpeg"]
    if shutil.which("dnf"):
        return ["sudo", "dnf", "install", "-y", "ffmpeg"]
    if shutil.which("pacman"):
        return ["sudo", "pacman", "-S", "--noconfirm", "ffmpeg"]
    return None


def install_ffmpeg_linux() -> bool:
    """Install FFmpeg on Linux via the system package manager."""
    found = shutil.which("ffmpeg")
    if found:
        _save_ffmpeg_dir(os.path.dirname(found))
        return True

    cmd = _linux_install_cmd()
    if cmd is None:
        _msg(
            _Tr("Install FFmpeg"),
            _Tr(
                "Install ffmpeg with your package manager, then set the path in FMV Settings."
            ),
            QGis.MessageLevel.Info,
            duration=8,
        )
        return False

    if not _prompt_yes(
        "QGIS FMV",
        _Tr("Install FFmpeg with your package manager?"),
        " ".join(cmd),
        icon="Question",
    ):
        _msg(_Tr("Run in a terminal"), " ".join(cmd), QGis.MessageLevel.Info, duration=10)
        return False

    pwd, ok = QInputDialog.getText(
        None,
        _Tr("Administrator password"),
        _Tr("Password (sudo):"),
        QLineEdit.EchoMode.Password,
    )
    if not ok or not pwd:
        return False

    ok, err = _run_cmd(["sudo", "-S", *cmd[1:]], input_bytes=pwd.encode())
    if not ok:
        _msg(_Tr("Could not install FFmpeg"), err, QGis.MessageLevel.Critical)
        return False

    _save_ffmpeg_dir("/usr/bin")
    return True


def install_ffmpeg() -> bool:
    """Install FFmpeg for the current platform (Windows, macOS, or Linux)."""
    if WINDOWS:
        return install_ffmpeg_windows()
    if DARWIN:
        return install_ffmpeg_mac()
    return install_ffmpeg_linux()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_dependency_setup(interactive: bool = True) -> bool:
    """Check and optionally install Python + FFmpeg dependencies."""
    if not interactive:
        pymisb_ok, _ = _try_import("pymisb")
        if not pymisb_ok:
            return False
        return check_python_deps()[0] and check_ffmpeg()[0]

    pymisb_ok, _ = _try_import("pymisb")
    if not pymisb_ok:
        if not _prompt_yes(
            "QGIS FMV",
            _Tr("pymisb is not installed."),
            _Tr("Install pymisb from PyPI?"),
        ):
            return False
        if not install_pymisb():
            return False

    py_ok, _ = check_python_deps()
    if not py_ok:
        if DARWIN:
            _clean_mac_user_site_packages()
        if _prompt_yes(
            "QGIS FMV",
            _Tr("Missing Python packages (pymisb / CV)."),
            _Tr(
                "Install code/requirements.txt into {} now?\n"
                "(No admin rights — does not modify QGIS.app)"
            ).format(_fmv_packages_dir()),
        ):
            if not install_pip_requirements():
                return False
        elif DARWIN:
            _msg(
                _Tr("Missing Python packages (pymisb / CV)."),
                _Tr(
                    "From the repo (no sudo):\n"
                    "  ./install_dev.sh\n"
                    "or:\n"
                    "  bash scripts/install_plugin_requirements.sh"
                ),
                QGis.MessageLevel.Warning,
                duration=12,
            )
        py_ok, _ = check_python_deps()
        if not py_ok and not DARWIN:
            return False

    repair_ffmpeg_setting()
    ff_ok, ff_msg = check_ffmpeg()
    if not ff_ok:
        if _prompt_yes(
            "QGIS FMV",
            _Tr("FFmpeg was not found."),
            ff_msg + "\n" + _Tr("Try automatic setup?"),
        ):
            install_ffmpeg()
            repair_ffmpeg_setting()
        ff_ok, _ = check_ffmpeg()

    if not ff_ok:
        _msg(
            _Tr("FFmpeg required"),
            _Tr(
                "Open FMV Settings (toolbar) and set the FFmpeg folder, "
                "or install FFmpeg manually."
            ),
            QGis.MessageLevel.Warning,
            duration=8,
        )
    return ff_ok if DARWIN else (py_ok and ff_ok)
