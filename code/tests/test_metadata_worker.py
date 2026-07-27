# -*- coding: utf-8 -*-
"""Metadata worker coalescing — exercises the real class with Qt stubs."""

import sys
import types

import pytest

from code.tests.support import (
    ensure_qgis_fmv_package,
    load_plugin_module,
    qgis_stub_keys,
    restore_modules,
    snapshot_modules,
)


def _install_qt_stub():
    ensure_qgis_fmv_package()
    keys = qgis_stub_keys(
        "pymisb",
        "pymisb.klvdata",
        "pymisb.klvdata.streamparser",
        "pymisb.klvdata.element",
    )
    saved = snapshot_modules(keys)

    for name in ("qgis", "qgis.PyQt", "qgis.PyQt.QtCore"):
        sys.modules.setdefault(name, types.ModuleType(name))
    qgis = sys.modules["qgis"]
    pyqt = sys.modules["qgis.PyQt"]
    qgis.PyQt = pyqt
    qtcore = sys.modules["qgis.PyQt.QtCore"]

    class QObject:
        def __init__(self, *a, **k):
            pass

    def pyqtSignal(*args):
        class _Signal:
            def connect(self, slot):
                self._slot = slot

            def emit(self, *a, **k):
                return None

        return _Signal()

    def pyqtSlot(*args, **kwargs):
        def decorator(fn):
            return fn

        return decorator

    qtcore.QObject = QObject
    qtcore.pyqtSignal = pyqtSignal
    qtcore.pyqtSlot = pyqtSlot

    if "pymisb.klvdata.streamparser" not in sys.modules or not hasattr(
        sys.modules.get("pymisb.klvdata.streamparser", object), "StreamParser"
    ):
        sp = types.ModuleType("pymisb.klvdata.streamparser")
        sp.StreamParser = lambda raw: []
        sys.modules["pymisb"] = types.ModuleType("pymisb")
        sys.modules["pymisb.klvdata"] = types.ModuleType("pymisb.klvdata")
        sys.modules["pymisb.klvdata.streamparser"] = sp
        el = types.ModuleType("pymisb.klvdata.element")

        class UnknownElement:
            pass

        el.UnknownElement = UnknownElement
        sys.modules["pymisb.klvdata.element"] = el

    return saved


@pytest.fixture
def worker_mod():
    saved = _install_qt_stub()
    try:
        mod = load_plugin_module(
            "utils/media/QgsFmvMetadataWorker.py",
            "QGISFMV.utils.media.QgsFmvMetadataWorker",
        )
    except Exception as exc:
        restore_modules(saved)
        pytest.skip(f"Cannot load MetadataParseWorker: {exc}")
    try:
        yield mod
    finally:
        restore_modules(saved)
        sys.modules.pop("QGISFMV.utils.media.QgsFmvMetadataWorker", None)


class TestMetadataParseWorkerCoalesce:
    def test_keeps_latest_while_busy(self, worker_mod):
        worker = worker_mod.MetadataParseWorker()
        worker._busy = True
        worker._parsePacket(b"a", 1, 0)
        worker._parsePacket(b"b", 5, 0)
        worker._parsePacket(b"c", 3, 0)
        assert worker._pending == (b"b", 5, 0)

    def test_clear_pending(self, worker_mod):
        worker = worker_mod.MetadataParseWorker()
        worker._pending = (b"x", 1, 0)
        worker.clearPending()
        assert worker._pending is None
