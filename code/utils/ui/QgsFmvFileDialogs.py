# -*- coding: utf-8 -*-
"""File/folder picker dialogs, extracted from QgsFmvUtils.py.

Remembers the last-used path per dialog-owning widget class in QSettings
(``pluginSetting`` / ``setPluginSetting``), used only by ``askForFiles`` and
``askForFolder`` below.
"""
import os

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import QFileDialog


def _base():
    """Lazily resolve QgsFmvUtils to dodge the circular import at load time.

    QgsFmvUtils.py re-exports this module's functions for backward
    compatibility, so importing it eagerly here (at module scope) could
    fail if this module happens to load first. Deferring the import to
    call time guarantees both modules are fully initialized.
    """
    import QGISFMV.utils.core.QgsFmvUtils as _mod
    return _mod


def pluginSetting(name, namespace=None, typ=str):
    """Read a plugin setting from QSettings."""
    namespace = namespace or _base().getNameSpace()
    full_name = namespace + "/" + name
    return QSettings().value(full_name, None, type=typ)


def setPluginSetting(name, value, namespace=None):
    """Set plugin name in QGIS settings"""
    namespace = namespace or _base().getNameSpace()
    QSettings().setValue(namespace + "/" + name, value)


def askForFiles(parent, msg=None, isSave=False, allowMultiple=False, exts="*"):
    """dialog for save or load files"""
    msg = msg or "Select file"
    name = "/".join(["LAST_PATH", parent.__class__.__name__])
    namespace = _base().getNameSpace()
    path = pluginSetting(name, namespace)
    f = None
    if not isinstance(exts, list):
        exts = [exts]
    extString = ";; ".join(
        [
            (
                " %s files (*.%s *.%s)" % (e.upper(), e, e.upper())
                if e != "*"
                else "All files (*.*)"
            )
            for e in exts
        ]
    )

    dlg = QFileDialog()

    if allowMultiple:
        ret = dlg.getOpenFileNames(parent, msg, path, extString)
        if ret:
            f = ret[0]
        else:
            f = ret = None
    else:
        if isSave:
            ret = dlg.getSaveFileName(parent, msg, path, extString) or None
            if ret[0] != "":
                _file_stem, ext = os.path.splitext(ret[0])
                if not ext:
                    ret[0] += "." + exts[0]  # Default extension
        else:
            ret = dlg.getOpenFileName(parent, msg, path, extString) or None
        f = ret

    if f is not None:
        setPluginSetting(name, os.path.dirname(f[0]), namespace)

    return ret


def askForFolder(parent, msg=None, options=QFileDialog.Option.ShowDirsOnly):
    """dialog for save or load folder"""
    msg = msg or "Select folder"
    name = "/".join(["LAST_PATH", parent.__class__.__name__])
    namespace = _base().getNameSpace()
    path = pluginSetting(name, namespace)
    folder = QFileDialog.getExistingDirectory(parent, msg, path, options)
    if folder:
        setPluginSetting(name, folder, namespace)
    return folder
