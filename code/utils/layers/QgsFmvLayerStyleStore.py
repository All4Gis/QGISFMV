# -*- coding: utf-8 -*-
"""Persist FMV map layer symbology in QGIS user settings."""

from qgis.PyQt.QtCore import QSettings
from qgis.core import QgsMapLayerStyle

_SUPPRESS = set()
_WATCHED = {}


def _settings_key(style_key):
    """Return the full QSettings path for a layer style key."""
    from QGISFMV.utils.core.QgsFmvUtils import getNameSpace

    return f"{getNameSpace()}/LayerStyles/{style_key}"


def save(layer, style_key):
    """Serialize the current layer renderer to QSettings."""
    if layer is None or not style_key:
        return False
    style = QgsMapLayerStyle()
    if not style.readFromLayer(layer):
        return False
    xml = style.xmlData()
    if not xml:
        return False
    QSettings().setValue(_settings_key(style_key), xml)
    return True


def apply_saved(layer, style_key):
    """Restore a previously saved renderer, if any."""
    if layer is None or not style_key:
        return False
    xml = QSettings().value(_settings_key(style_key))
    if not xml:
        return False
    style = QgsMapLayerStyle()
    if not style.readXml(xml):
        return False
    _SUPPRESS.add(layer.id())
    try:
        return style.applyToLayer(layer)
    finally:
        _SUPPRESS.discard(layer.id())


def ensure_watch(layer, style_key):
    """Listen for user symbology edits and persist them."""
    if layer is None or not style_key:
        return
    layer_id = layer.id()
    if layer_id in _WATCHED:
        return

    def _on_style_changed():
        if layer_id in _SUPPRESS:
            return
        save(layer, style_key)

    layer.styleChanged.connect(_on_style_changed)
    _WATCHED[layer_id] = style_key


def apply_or_default(layer, style_key, default_fn, *args, **kwargs):
    """Use saved symbology when present, otherwise apply plugin defaults."""
    if layer is None or not style_key:
        return
    _SUPPRESS.add(layer.id())
    try:
        if not apply_saved(layer, style_key):
            default_fn(layer, *args, **kwargs)
    finally:
        _SUPPRESS.discard(layer.id())
    ensure_watch(layer, style_key)


def clear(style_key=None):
    """Drop one or all saved layer styles (defaults apply again)."""
    from QGISFMV.utils.core.QgsFmvUtils import getNameSpace

    settings = QSettings()
    if style_key:
        settings.remove(_settings_key(style_key))
        return
    group = f"{getNameSpace()}/LayerStyles"
    settings.beginGroup(group)
    for key in settings.childKeys():
        settings.remove(key)
    settings.endGroup()
