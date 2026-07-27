# -*- coding: utf-8 -*-
"""Download and configure YOLO ONNX models for FMV segmentation filters."""

from __future__ import annotations

import os
import shutil
import ssl
import subprocess
import sys
from typing import Callable, Optional, Tuple
from urllib.request import Request, urlopen

from QGISFMV.utils.logging import log
from QGISFMV.utils.settings.QgsFmvSettings import get, save, set_value

# Community-exported YOLOv8n ONNX (ground-level COCO).
YOLOV8N_URL = "https://huggingface.co/Kalray/yolov8/resolve/main/yolov8n.onnx"
YOLOV8N_FILENAME = "yolov8n.onnx"

# VisDrone aerial model (PyTorch weights; export to ONNX locally).
VISDRONE_PT_URL = (
    "https://huggingface.co/dronefreak/visdrone-yolov8n/resolve/main/best.pt"
)
VISDRONE_PT_FILENAME = "visdrone-yolov8n.pt"
VISDRONE_ONNX_FILENAME = "visdrone-yolov8n.onnx"

VISDRONE_CLASS_IDS = {
    "vehicle": "3,4,5,8,9",
    "person": "0,1",
}

USER_AGENT = "QGIS-FMV/1.17"


def models_dir() -> str:
    """Return the default directory for downloaded DNN models (~/.qgis-fmv-models)."""
    return os.path.join(os.path.expanduser("~"), ".qgis-fmv-models")


def default_yolov8n_path() -> str:
    """Return the default path for the YOLOv8n COCO ONNX model."""
    return os.path.join(models_dir(), YOLOV8N_FILENAME)


def default_visdrone_pt_path() -> str:
    """Return the default path for the VisDrone PyTorch model."""
    return os.path.join(models_dir(), VISDRONE_PT_FILENAME)


def default_visdrone_onnx_path() -> str:
    """Return the default path for the VisDrone ONNX model."""
    return os.path.join(models_dir(), VISDRONE_ONNX_FILENAME)


def _download(url: str, dest: str, progress: Optional[Callable[[int, int], None]] = None) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = Request(url, headers={"User-Agent": USER_AGENT})
    ctx = ssl.create_default_context()
    with urlopen(req, context=ctx, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        read = 0
        chunk_size = 256 * 1024
        tmp = dest + ".part"
        with open(tmp, "wb") as out:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if progress is not None:
                    progress(read, total)
        os.replace(tmp, dest)


def _download_model(url, dest, min_size, label, progress=None):
    """Download a model file with retry-on-corruption. Returns (ok, path_or_error)."""
    dest = dest or default_yolov8n_path()
    if os.path.isfile(dest) and os.path.getsize(dest) > min_size:
        return True, dest
    try:
        _download(url, dest, progress=progress)
        if not os.path.isfile(dest) or os.path.getsize(dest) < min_size:
            return False, f"Downloaded {label} looks too small."
        return True, dest
    except Exception as exc:
        try:
            if os.path.isfile(dest + ".part"):
                os.remove(dest + ".part")
        except OSError:
            pass
        return False, str(exc)


def download_yolov8n(
    dest: Optional[str] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bool, str]:
    """Download YOLOv8n COCO ONNX into ~/.qgis-fmv-models/. Returns (ok, message)."""
    return _download_model(YOLOV8N_URL, dest or default_yolov8n_path(),
                           1_000_000, "YOLOv8n", progress)


def download_visdrone_pt(
    dest: Optional[str] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bool, str]:
    """Download VisDrone YOLOv8n PyTorch weights. Returns (ok, path_or_error)."""
    return _download_model(VISDRONE_PT_URL, dest or default_visdrone_pt_path(),
                           500_000, "VisDrone weights", progress)


def _export_onnx_inprocess(pt_path: str, dest_onnx: str) -> Tuple[bool, str]:
    try:
        from ultralytics import YOLO
    except ImportError:
        return False, "ultralytics not installed"
    try:
        out = YOLO(pt_path).export(format="onnx", imgsz=640, opset=12, simplify=True)
        out = os.path.abspath(str(out))
        dest = os.path.abspath(dest_onnx)
        if out != dest and os.path.isfile(out):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.move(out, dest)
        if os.path.isfile(dest) and os.path.getsize(dest) > 500_000:
            return True, dest
        return False, "ONNX export produced no file"
    except Exception as exc:
        return False, str(exc)


def _export_onnx_subprocess(pt_path: str, dest_onnx: str) -> Tuple[bool, str]:
    script = (
        "import os, shutil, sys\n"
        "from ultralytics import YOLO\n"
        "pt, dest = sys.argv[1], sys.argv[2]\n"
        "out = YOLO(pt).export(format='onnx', imgsz=640, opset=12, simplify=True)\n"
        "out = os.path.abspath(str(out))\n"
        "dest = os.path.abspath(dest)\n"
        "if out != dest and os.path.isfile(out):\n"
        "    os.makedirs(os.path.dirname(dest), exist_ok=True)\n"
        "    shutil.move(out, dest)\n"
        "if not os.path.isfile(dest):\n"
        "    raise SystemExit('ONNX export produced no file')\n"
        "print(dest)\n"
    )
    errors = []
    for py in (sys.executable, "python3", "python"):
        if not py:
            continue
        try:
            proc = subprocess.run(
                [py, "-c", script, pt_path, dest_onnx],
                capture_output=True,
                text=True,
                timeout=600,
            )
            if proc.returncode == 0 and os.path.isfile(dest_onnx):
                return True, dest_onnx
            err = (proc.stderr or proc.stdout or "").strip()
            if err:
                errors.append("{}: {}".format(py, err[-400:]))
        except Exception as exc:
            errors.append("{}: {}".format(py, exc))
    return False, "; ".join(errors) if errors else "ultralytics not available"


def export_visdrone_onnx(
    pt_path: Optional[str] = None,
    dest_onnx: Optional[str] = None,
) -> Tuple[bool, str]:
    """Export VisDrone .pt to ONNX (requires ultralytics on system Python)."""
    pt_path = pt_path or default_visdrone_pt_path()
    dest_onnx = dest_onnx or default_visdrone_onnx_path()
    if os.path.isfile(dest_onnx) and os.path.getsize(dest_onnx) > 500_000:
        return True, dest_onnx
    if not os.path.isfile(pt_path):
        return False, "VisDrone weights missing — download them first."
    ok, msg = _export_onnx_inprocess(pt_path, dest_onnx)
    if ok:
        return True, msg
    ok, msg2 = _export_onnx_subprocess(pt_path, dest_onnx)
    if ok:
        return True, msg2
    return False, (
        "Could not export VisDrone ONNX automatically. Install ultralytics and run:\n"
        "  pip install ultralytics\n"
        "  yolo export model={} format=onnx imgsz=640 opset=12\n"
        "Then set onnx_model to {} in FMV Settings.".format(pt_path, dest_onnx)
    )


def apply_dnn_settings(
    *,
    enabled: bool,
    model_path: str,
    model_type: str = "yolov8",
    input_size: int = 640,
    confidence: float = 0.35,
    nms: float = 0.45,
    class_ids: Optional[dict] = None,
    model_profile: Optional[str] = None,
) -> None:
    """Write [DNN] section to settings.ini."""
    set_value("DNN", "use_dnn_detection", "true" if enabled else "false")
    set_value("DNN", "onnx_model", model_path or "")
    set_value("DNN", "onnx_model_type", model_type or "yolov8")
    set_value("DNN", "onnx_input_size", str(int(input_size)))
    set_value("DNN", "onnx_confidence", str(float(confidence)))
    set_value("DNN", "onnx_nms", str(float(nms)))
    if model_profile is not None:
        set_value("DNN", "dnn_model_profile", model_profile)
    keys = (
        "building",
        "road",
        "vehicle",
        "person",
        "fire",
        "smoke",
        "flood",
    )
    for key in keys:
        val = ""
        if class_ids and key in class_ids:
            val = class_ids[key] or ""
        set_value("DNN", "dnn_{}_class_ids".format(key), val)
    save()


def _reload_dnn_runtime() -> None:
    try:
        from QGISFMV.video.dnn.QgsFmvOnnxDetector import reset_dnn_cache

        reset_dnn_cache()
    except Exception as _exc:
        log.debug('Failed to reset DNN cache during reload: %s', _exc)
    try:
        from QGISFMV.utils.settings.QgsFmvSettings import reloadRuntime

        reloadRuntime()
    except Exception as _exc:
        log.debug('Failed to reload DNN runtime settings: %s', _exc)


def configure_default_dnn(model_path: Optional[str] = None) -> Tuple[bool, str]:
    """Enable DNN with YOLOv8n COCO (ground-level imagery)."""
    path = model_path or default_yolov8n_path()
    if not os.path.isfile(path):
        ok, msg = download_yolov8n(path)
        if not ok:
            return False, msg
        path = msg
    apply_dnn_settings(
        enabled=True,
        model_path=path,
        model_type="yolov8",
        input_size=640,
        confidence=0.25,
        nms=0.45,
        model_profile="coco",
    )
    _reload_dnn_runtime()
    return True, path


def configure_aerial_dnn(
    progress: Optional[Callable[[int, int], None]] = None,
) -> Tuple[bool, str]:
    """
    Download VisDrone YOLOv8n, export ONNX, and enable aerial class ids
    for Vehicle/Person filters (recommended for FMV / UAV video).
    """
    pt_path = default_visdrone_pt_path()
    onnx_path = default_visdrone_onnx_path()
    if not os.path.isfile(pt_path):
        ok, msg = download_visdrone_pt(pt_path, progress=progress)
        if not ok:
            return False, msg
        pt_path = msg
    if not os.path.isfile(onnx_path):
        ok, msg = export_visdrone_onnx(pt_path, onnx_path)
        if not ok:
            return False, msg
        onnx_path = msg
    apply_dnn_settings(
        enabled=True,
        model_path=onnx_path,
        model_type="yolov8",
        input_size=640,
        confidence=0.15,
        nms=0.45,
        class_ids=VISDRONE_CLASS_IDS,
        model_profile="aerial",
    )
    _reload_dnn_runtime()
    return True, onnx_path


def ensure_default_dnn_assets(quiet: bool = True) -> Tuple[bool, str]:
    """
    On first run: download VisDrone (aerial) model and enable DNN if settings
    have no model yet. Does not override an existing user configuration.
    """
    current_model = (get("DNN", "onnx_model", "") or "").strip()
    enabled_raw = str(get("DNN", "use_dnn_detection", "false")).strip().lower()
    if current_model and enabled_raw in ("1", "true", "yes", "on"):
        if os.path.isfile(current_model):
            return True, current_model
    profile = (get("DNN", "dnn_model_profile", "aerial") or "aerial").strip().lower()
    if profile in ("coco", "ground"):
        path = default_yolov8n_path()
        if not os.path.isfile(path):
            ok, msg = download_yolov8n(path)
            if not ok:
                if not quiet:
                    log.warning("YOLO model download failed: %s", msg)
                return False, msg
            path = msg
        if not current_model:
            configure_default_dnn(path)
        return True, path

    onnx_path = default_visdrone_onnx_path()
    if os.path.isfile(onnx_path):
        if not current_model:
            configure_aerial_dnn()
        return True, onnx_path
    pt_path = default_visdrone_pt_path()
    if os.path.isfile(pt_path):
        ok, msg = export_visdrone_onnx(pt_path, onnx_path)
        if ok and not current_model:
            configure_aerial_dnn()
            return True, onnx_path
        if not ok and not quiet:
            log.warning("VisDrone ONNX export skipped: %s", msg)
    if not current_model:
        ok, msg = configure_aerial_dnn()
        if ok:
            return True, msg
        if not quiet:
            log.warning("Aerial DNN setup failed: %s", msg)
        return False, msg
    return False, "No DNN model configured"
