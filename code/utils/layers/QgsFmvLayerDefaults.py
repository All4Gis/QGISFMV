# -*- coding: utf-8 -*-
"""Default layer symbology, extracted from QgsFmvLayers.py.

Owns every ``SetDefault*Style`` function (2D + 3D), the data-driven style
registry that backs the 2D ones, and the 3D-renderer bookkeeping
(``ensure_fmv_3d_renderers`` / ``RestoreDefaultLayerStyles``).

Layer-name constants and ``groupName`` still live in QgsFmvLayers.py (they
are refreshed live by QgsFmvSettings.reloadRuntime via ``setattr``), so this
module reads them through a module reference (``_base()``) instead of
importing them by value — mirrors the pattern already used by
QgsFmvDrawLayers.py.
"""
import os

from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import QPointF
from qgis.core import (
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsMarkerSymbol,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsRuleBasedRenderer,
    QgsSymbol,
    QgsWkbTypes,
    QgsProject,
    QgsUnitTypes,
    Qgis,
)

from qgis.utils import iface
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.layers.QgsFmvStyles import FmvLayerStyles as S

try:
    from qgis._3d import (
        QgsPhongMaterialSettings,
        QgsVectorLayer3DRenderer,
        QgsLine3DSymbol,
        QgsPoint3DSymbol,
        QgsPolygon3DSymbol,
    )
    _HAS_3D = True
except ImportError:
    QgsPhongMaterialSettings = None
    QgsVectorLayer3DRenderer = None
    QgsLine3DSymbol = None
    QgsPoint3DSymbol = None
    QgsPolygon3DSymbol = None
    _HAS_3D = False


def _base():
    """Lazily resolve QgsFmvLayers to dodge the circular import at load time.

    QgsFmvLayers.py re-exports this module's functions for backward
    compatibility, so importing QgsFmvLayers eagerly here (at module scope)
    could fail if this module happens to load first. Deferring the import
    to call time guarantees both modules are fully initialized.
    """
    import QGISFMV.utils.layers.QgsFmvLayers as _mod
    return _mod


def _refresh_layer_tree_style(layer):
    """Refresh map and layer-tree legend after a symbol change."""
    if layer is None:
        return
    layer.triggerRepaint()
    try:
        if iface is not None:
            iface.layerTreeView().refreshLayerSymbology(layer.id())
    except Exception as exc:
        log.debug("Layer tree symbology refresh failed: %s", exc)


# ---------------------------------------------------------------------------
# Data-driven style registry
# ---------------------------------------------------------------------------

# kwargs mappers: style dict -> QgsSymbol.createSimple kwargs


def _fill_kwargs(style):
    return {
        "color": style["COLOR"],
        "outline_color": style["OUTLINE_COLOR"],
        "outline_style": style["OUTLINE_STYLE"],
        "outline_width": style["OUTLINE_WIDTH"],
    }


def _line_kwargs(style):
    return {
        "color": style["COLOR"],
        "width": style["WIDTH"],
        "customdash": style.get("customdash", "0"),
        "use_custom_dash": style.get("use_custom_dash", "0"),
    }


def _marker_kwargs(style):
    return {
        "name": style["NAME"],
        "color": style.get("COLOR", style["LINE_COLOR"]),
        "outline_color": style["LINE_COLOR"],
        "outline_width": style["LINE_WIDTH"],
        "size": style["SIZE"],
    }


def _frame_center_kwargs(style):
    return {
        "name": style["NAME"],
        "line_color": style["LINE_COLOR"],
        "line_width": style["LINE_WIDTH"],
        "size": style["SIZE"],
    }


def _beams_kwargs(style):
    c = QColor.fromRgba(style["COLOR"])
    return {
        "color": f"{c.red()},{c.green()},{c.blue()},{c.alpha()}",
        "width": "0.7",
        "line_style": "dash",
        "customdash": "5;4",
        "use_custom_dash": "1",
    }


def _frame_axis_style(sensor="DEFAULT"):
    """Merge sensor and frame-axis style dicts for the frame axis line."""
    sensor_style = S.getSensor(sensor)
    frame_axis = S.getFrameAxis()
    return {
        "OUTLINE_COLOR": sensor_style["OUTLINE_COLOR"],
        "OUTLINE_WIDTH": sensor_style["OUTLINE_WIDTH"],
        "OUTLINE_STYLE": frame_axis["OUTLINE_STYLE"],
    }


def _frame_axis_kwargs(style):
    return {
        "color": style["OUTLINE_COLOR"],
        "width": style["OUTLINE_WIDTH"],
        "outline_style": style["OUTLINE_STYLE"],
    }


def _measure_distance_kwargs(style):
    return {
        "color": style["COLOR"],
        "width": style["WIDTH"],
        "line_style": "solid",
        "capstyle": "round",
        "joinstyle": "round",
    }


# Labeling helpers


def _label_object_position(layer, style):
    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()
    text_format.setFont(
        QFont(style["LABEL_FONT"], style["LABEL_FONT_SIZE"], QFont.Weight.Bold)
    )
    text_format.setSize(style["LABEL_FONT_SIZE"])
    text_format.setColor(QColor(style["LABEL_FONT_COLOR"]))
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(style["LABEL_BUFFER_SIZE"])
    buffer_settings.setColor(QColor(style["LABEL_BUFFER_COLOR"]))
    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)
    layer_settings.fieldName = "'TRACK ' || coalesce(\"track_id\", '')"
    layer_settings.isExpression = True
    layer_settings.placement = QgsPalLayerSettings.Placement.OverPoint
    layer.setLabeling(QgsVectorLayerSimpleLabeling(layer_settings))
    layer.setLabelsEnabled(True)


def _label_point(layer, style):
    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()
    text_format.setFont(
        QFont(
            style["LABEL_FONT"],
            style["LABEL_FONT_SIZE"],
            QFont.Weight.Bold,
        )
    )
    text_format.setColor(QColor(style["LABEL_FONT_COLOR"]))
    text_format.setSize(style["LABEL_SIZE"])

    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(float(style.get("LABEL_BUFFER_SIZE", 1.4)))
    buffer_settings.setColor(QColor(style["LABEL_BUFFER_COLOR"]))

    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)

    layer_settings.fieldName = "number"
    layer_settings.placement = QgsPalLayerSettings.Placement.OverPoint
    layer_settings.enabled = True
    layer_settings.dist = 0
    layer_settings.offsetType = QgsPalLayerSettings.OffsetType.FromPoint
    layer_settings.offset = QPointF(
        float(style.get("LABEL_OFFSET_X", 2.0)),
        float(style.get("LABEL_OFFSET_Y", -2.0)),
    )
    layer_settings.offsetUnit = QgsUnitTypes.RenderMillimeters

    quadrant = getattr(QgsPalLayerSettings, "QuadrantAboveRight", None)
    if quadrant is None and hasattr(QgsPalLayerSettings, "QuadrantOffset"):
        quadrant = QgsPalLayerSettings.QuadrantOffset.QuadrantAboveRight
    if quadrant is not None:
        layer_settings.quadrantOffset = quadrant

    layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
    layer.setLabelsEnabled(True)
    layer.setLabeling(layer_settings)


# Custom apply functions for non-standard symbol types


def _apply_military_symbol(layer):
    """Rule-based SVG renderer for NATO military symbols."""
    from QGISFMV.player.dialogs.QgsFmvMilitarySymbols import (
        MILITARY_SYMBOLS,
        symbol_svg_path,
    )

    default_sym = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
    renderer = QgsRuleBasedRenderer(default_sym)
    root = renderer.rootRule()
    root.removeChildAt(0)

    for symbol_id, _name, _category, _filename in MILITARY_SYMBOLS:
        svg_path = symbol_svg_path(symbol_id)
        if not svg_path or not os.path.isfile(svg_path):
            continue
        svg_layer = QgsSvgMarkerSymbolLayer(svg_path)
        svg_layer.setSize(8)
        svg_layer.setSizeUnit(QgsUnitTypes.RenderMillimeters)
        point_symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
        point_symbol.deleteSymbolLayer(0)
        point_symbol.appendSymbolLayer(svg_layer)
        rule = QgsRuleBasedRenderer.Rule(point_symbol)
        rule.setFilterExpression(f'"symbol_id" = \'{symbol_id}\'')
        rule.setActive(True)
        root.appendChild(rule)

    layer.setRenderer(renderer)

    layer_settings = QgsPalLayerSettings()
    layer_settings.fieldName = "unit_name"
    layer_settings.enabled = True
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial", 8, QFont.Weight.Bold))
    text_format.setColor(QColor("#000000"))
    layer_settings.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(layer_settings))
    layer.setLabelsEnabled(True)


def _apply_line_modify(layer):
    """Modify the existing line renderer symbol in place."""
    style = S.getDrawingLine()
    symbol = layer.renderer().symbol()
    symbol.setColor(style["COLOR"])
    symbol.setWidth(style["WIDTH"])


# Style registry: maps config keys to style configurations.
#
# Each entry:
#   "symbol_type" : "fill" | "line" | "marker" | "svg_marker" | "custom" | "modify"
#   "get_style"   : callable(*args) -> dict   (ignored for "custom" / "modify")
#   "map_kwargs"  : callable(style_dict) -> dict for createSimple
#   "default_args": tuple of default positional args for get_style
#   "labeling"    : optional callable(layer, style_dict)
#   "refresh"     : bool -- refresh layer tree style after applying

_STYLE_REGISTRY = {
    "footprint": {
        "symbol_type": "fill",
        "get_style": S.getSensor,
        "map_kwargs": _fill_kwargs,
        "default_args": ("DEFAULT",),
    },
    "beams": {
        "symbol_type": "line",
        "get_style": S.getBeam,
        "map_kwargs": _beams_kwargs,
        "default_args": ("DEFAULT",),
    },
    "trajectory": {
        "symbol_type": "line",
        "get_style": S.getTrajectory,
        "map_kwargs": _line_kwargs,
        "default_args": ("DEFAULT",),
    },
    "object_track": {
        "symbol_type": "line",
        "get_style": S.getObjectTrack,
        "map_kwargs": _line_kwargs,
        "default_args": (),
        "refresh": True,
    },
    "object_position": {
        "symbol_type": "marker",
        "get_style": S.getObjectPosition,
        "map_kwargs": _marker_kwargs,
        "default_args": (),
        "labeling": _label_object_position,
        "refresh": True,
    },
    "platform": {
        "symbol_type": "svg_marker",
        "get_style": S.getPlatform,
        "default_args": ("DEFAULT",),
        "refresh": True,
    },
    "frame_center": {
        "symbol_type": "marker",
        "get_style": S.getFrameCenterPoint,
        "map_kwargs": _frame_center_kwargs,
        "default_args": (),
    },
    "frame_axis": {
        "symbol_type": "line",
        "get_style": _frame_axis_style,
        "map_kwargs": _frame_axis_kwargs,
        "default_args": ("DEFAULT",),
    },
    "military_symbol": {
        "symbol_type": "custom",
        "apply_fn": _apply_military_symbol,
    },
    "point": {
        "symbol_type": "marker",
        "get_style": S.getDrawingPoint,
        "map_kwargs": _marker_kwargs,
        "default_args": (),
        "labeling": _label_point,
    },
    "line": {
        "symbol_type": "modify",
        "apply_fn": _apply_line_modify,
    },
    "polygon": {
        "symbol_type": "fill",
        "get_style": S.getDrawingPolygon,
        "map_kwargs": _fill_kwargs,
        "default_args": (),
    },
    "measure_distance": {
        "symbol_type": "line",
        "get_style": S.getMeasureDistance,
        "map_kwargs": _measure_distance_kwargs,
        "default_args": (),
        "labeling": lambda layer, s: _apply_measure_labeling(
            layer, "label", "#e0f7fa", line=True
        ),
        "refresh": True,
    },
    "measure_area": {
        "symbol_type": "fill",
        "get_style": S.getMeasureArea,
        "map_kwargs": _fill_kwargs,
        "default_args": (),
        "labeling": lambda layer, s: _apply_measure_labeling(
            layer, "label", "#fff8e1", line=False
        ),
        "refresh": True,
    },
}


def _apply_style(layer, config_key, *args):
    """Apply a default style to *layer* using the style registry.

    *args* override the entry's ``default_args`` when provided.
    """
    config = _STYLE_REGISTRY[config_key]
    symbol_type = config["symbol_type"]

    # Custom: delegate entirely to the apply_fn
    if symbol_type in ("custom", "modify"):
        config["apply_fn"](layer)
        return

    # Standard symbol creation
    effective_args = args if args else config["default_args"]
    style_dict = config["get_style"](*effective_args)
    map_fn = config.get("map_kwargs")
    kwargs = map_fn(style_dict) if map_fn else {}

    if symbol_type == "fill":
        symbol = QgsFillSymbol.createSimple(kwargs)
    elif symbol_type == "line":
        symbol = QgsLineSymbol.createSimple(kwargs)
    elif symbol_type == "marker":
        symbol = QgsMarkerSymbol.createSimple(kwargs)
    elif symbol_type == "svg_marker":
        svg_layer = QgsSvgMarkerSymbolLayer.create(style_dict)
        symbol = QgsMarkerSymbol([svg_layer])
    else:
        raise ValueError(f"Unknown symbol_type: {symbol_type}")

    layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    labeling_fn = config.get("labeling")
    if labeling_fn:
        labeling_fn(layer, style_dict)

    if config.get("refresh"):
        _refresh_layer_tree_style(layer)


# ---------------------------------------------------------------------------
# Backward-compatible thin wrappers
# ---------------------------------------------------------------------------


def SetDefaultFootprintStyle(layer, sensor="DEFAULT"):
    """Footprint Symbol"""
    _apply_style(layer, "footprint", sensor)


def SetDefaultFootprint3DStyle(layer):
    """Footprint 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(0, 188, 212, 180))
    material.setAmbient(QColor(0, 151, 167))
    symbol = QgsPolygon3DSymbol()
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)
    if hasattr(symbol, "setHeight"):
        symbol.setHeight(2.0)

    _apply_vector_layer_3d_renderer(layer, symbol)


_FM3D_RENDERER_SYMBOLS = {}


def _fmv_3d_layer_styles():
    base = _base()
    return [
        (base.Footprint_lyr, SetDefaultFootprint3DStyle),
        (base.Beams_lyr, SetDefaultBeams3DStyle),
        (base.Trajectory_lyr, SetDefaultTrajectory3DStyle),
        (base.FrameAxis_lyr, SetDefaultFrameAxis3DStyle),
        (base.Platform_lyr, SetDefaultPlatform3DStyle),
        (base.FrameCenter_lyr, SetDefaultFrameCenter3DStyle),
    ]


def _apply_vector_layer_3d_renderer(layer, symbol):
    """Apply a 3D symbol without replacing an existing renderer (QGIS SIP crash)."""
    renderer = layer.renderer3D()
    if renderer is None or not isinstance(renderer, QgsVectorLayer3DRenderer):
        renderer = QgsVectorLayer3DRenderer()
        renderer.setLayer(layer)
        layer.setRenderer3D(renderer)
    _FM3D_RENDERER_SYMBOLS[layer.id()] = (renderer, symbol)
    renderer.setSymbol(symbol)


def ensure_fmv_3d_renderers(group_name=None, force=False):
    """Ensure FMV layers have 3D renderers using absolute Z from telemetry."""
    if not _HAS_3D:
        return []
    key = group_name if group_name is not None else _base().groupName
    if not key:
        return []
    ready = []
    for lyr_name, style_fn in _fmv_3d_layer_styles():
        layer = qgsu.selectLayerByName(lyr_name, key)
        if layer is None:
            continue
        if not force and isinstance(layer.renderer3D(), QgsVectorLayer3DRenderer):
            ready.append(layer)
            continue
        try:
            style_fn(layer)
            if hasattr(layer, "trigger3DUpdate"):
                layer.trigger3DUpdate()
            ready.append(layer)
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                "",
                "3D renderer setup failed for %s: %s" % (lyr_name, exc),
                onlyLog=True,
            )
    return ready


def SetDefaultTrajectoryStyle(layer):
    """Trajectory Symbol"""
    _apply_style(layer, "trajectory")


def SetDefaultObjectTrackStyle(layer):
    """Object tracking path style (amber, distinct from platform trajectory)."""
    _apply_style(layer, "object_track")


def SetDefaultObjectPositionStyle(layer):
    """Live tracked-object marker style."""
    _apply_style(layer, "object_position")


def SetDefaultPlatformStyle(layer, platform="DEFAULT"):
    """Platform Symbol"""
    _apply_style(layer, "platform", platform)


def SetDefaultPlatform3DStyle(layer):
    """Platform 3D Symbol — simple sphere (stable across QGIS SIP ownership)."""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 255, 255))
    material.setAmbient(QColor(200, 220, 235))
    symbol = QgsPoint3DSymbol()
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)
    symbol.setShape(Qgis.Point3DShape.Sphere)
    symbol.setShapeProperties({"radius": 25})

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultTrajectory3DStyle(layer):
    """Trajectory 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(38, 198, 218))
    material.setAmbient(QColor(0, 151, 167))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(5)
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultFrameAxis3DStyle(layer):
    """Frame Axis 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 64, 129))
    material.setAmbient(QColor(194, 24, 91))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(3)
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultBeams3DStyle(layer):
    """Beams 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 235, 59))
    material.setAmbient(QColor(255, 193, 7))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(5)
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultFrameCenterStyle(layer):
    """Frame Center Symbol"""
    _apply_style(layer, "frame_center")


def SetDefaultFrameCenter3DStyle(layer):
    """Frame Center 3D Symbol"""
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 64, 129))
    material.setAmbient(QColor(194, 24, 91))
    symbol = QgsPoint3DSymbol()
    symbol.setAltitudeClamping(Qgis.AltitudeClamping.Absolute)
    symbol.setMaterialSettings(material)
    symbol.setShape(Qgis.Point3DShape.Sphere)
    symbol.setShapeProperties({"radius": 8})

    _apply_vector_layer_3d_renderer(layer, symbol)


def SetDefaultFrameAxisStyle(layer, sensor="DEFAULT"):
    """Line Symbol"""
    _apply_style(layer, "frame_axis", sensor)


def SetDefaultMilitarySymbolStyle(layer):
    """Rule-based SVG renderer for NATO military symbols."""
    _apply_style(layer, "military_symbol")


def SetDefaultPointStyle(layer):
    """Point Symbol"""
    _apply_style(layer, "point")


def SetDefaultLineStyle(layer):
    """Line Symbol"""
    _apply_style(layer, "line")


def SetDefaultPolygonStyle(layer):
    """Polygon Symbol"""
    _apply_style(layer, "polygon")


def _apply_measure_labeling(layer, field_name="label", color="#ffffff", line=True):
    """Bold buffered labels for measure layers."""
    settings = QgsPalLayerSettings()
    settings.fieldName = field_name
    settings.isExpression = False
    settings.enabled = True
    placement = QgsPalLayerSettings.Placement
    if line:
        settings.placement = getattr(placement, "Line", placement.AroundPoint)
    else:
        settings.placement = getattr(placement, "Centroid", placement.AroundPoint)
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
    text_format.setSize(9)
    text_format.setColor(QColor(color))
    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(1.2)
    buffer_settings.setColor(QColor(20, 30, 40, 220))
    text_format.setBuffer(buffer_settings)
    settings.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)


def SetDefaultMeasureDistanceStyle(layer):
    """Cyan dashed line + length labels for measure distance."""
    _apply_style(layer, "measure_distance")


def SetDefaultMeasureAreaStyle(layer):
    """Amber translucent fill + area labels for measure area."""
    _apply_style(layer, "measure_area")


def SetDefaultBeamsStyle(layer, beam="DEFAULT"):
    """Beams Symbol"""
    _apply_style(layer, "beams", beam)


def RestoreDefaultLayerStyles():
    """Clear saved symbology and re-apply plugin defaults on open FMV layers."""
    from QGISFMV.utils.layers.QgsFmvLayerStyleStore import clear, ensure_watch
    from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get

    clear()
    base = _base()

    defaults = {
        settings_get("LAYERS", "footprint_lyr", base.Footprint_lyr): (
            SetDefaultFootprintStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "beams_lyr", base.Beams_lyr): (
            SetDefaultBeamsStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "trajectory_lyr", base.Trajectory_lyr): (
            SetDefaultTrajectoryStyle,
            (),
        ),
        settings_get("LAYERS", "frameaxis_lyr", base.FrameAxis_lyr): (
            SetDefaultFrameAxisStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "platform_lyr", base.Platform_lyr): (
            SetDefaultPlatformStyle,
            ("DEFAULT",),
        ),
        settings_get("LAYERS", "point_lyr", base.Point_lyr): (SetDefaultPointStyle, ()),
        settings_get("LAYERS", "symbol_lyr", base.Symbol_lyr): (SetDefaultMilitarySymbolStyle, ()),
        settings_get("LAYERS", "framecenter_lyr", base.FrameCenter_lyr): (
            SetDefaultFrameCenterStyle,
            (),
        ),
        settings_get("LAYERS", "line_lyr", base.Line_lyr): (SetDefaultLineStyle, ()),
        settings_get("LAYERS", "polygon_lyr", base.Polygon_lyr): (
            SetDefaultPolygonStyle,
            (),
        ),
        settings_get("LAYERS", "objecttrack_lyr", base.ObjectTrack_lyr): (
            SetDefaultObjectTrackStyle,
            (),
        ),
        settings_get("LAYERS", "objectposition_lyr", base.ObjectPosition_lyr): (
            SetDefaultObjectPositionStyle,
            (),
        ),
        settings_get("LAYERS", "measuredistance_lyr", base.MeasureDistance_lyr): (
            SetDefaultMeasureDistanceStyle,
            (),
        ),
        settings_get("LAYERS", "measurearea_lyr", base.MeasureArea_lyr): (
            SetDefaultMeasureAreaStyle,
            (),
        ),
    }

    restored = 0
    layer_registry = QgsProject.instance()
    for layer in layer_registry.mapLayers().values():
        entry = defaults.get(layer.name())
        if entry is None:
            continue
        fn, args = entry
        fn(layer, *args)
        ensure_watch(layer, layer.name())
        layer.triggerRepaint()
        restored += 1

    if iface is not None:
        for layer in layer_registry.mapLayers().values():
            if layer.name() in defaults:
                try:
                    iface.layerTreeView().refreshLayerSymbology(layer.id())
                except Exception as exc:
                    log.debug(
                        "Layer tree refresh failed for %s: %s", layer.name(), exc
                    )
    return restored
