# -*- coding: utf-8 -*-
from qgis.PyQt.QtGui import QColor, qRgba


def _sensor_style(color, outline, width="1.8"):
    """Create a sensor footprint style dict."""
    return {
        "COLOR": color,
        "OUTLINE_COLOR": outline,
        "OUTLINE_STYLE": "solid",
        "OUTLINE_WIDTH": width,
    }


def _platform_style(svg_name, outline="255, 255, 255, 220", size="20"):
    """Create a platform symbol style dict."""
    return {
        "NAME": f":/imgFMV/images/platforms/{svg_name}",
        "OUTLINE": outline,
        "OUTLINE_WIDTH": "0.8",
        "SIZE": size,
    }


class FmvLayerStyles(object):

    # ── Sensor styles (ImageSourceSensor) ──
    S = {
        "DEFAULT":          _sensor_style("0, 188, 212, 55", "#00bcd4"),
        "IR":               _sensor_style("255, 87, 34, 55", "#ff5722"),
        "EOW":              _sensor_style("0, 188, 212, 55", "#00bcd4"),
        "BLEND":            _sensor_style("158, 158, 158, 45", "#78909c", "1.6"),
        "EON_SWIR":         _sensor_style("255, 152, 0, 55", "#ff9800"),
        "EON":              _sensor_style("255, 193, 7, 55", "#ffc107"),
        "FLIR SS380-HD HDIR": _sensor_style("255, 87, 34, 55", "#ff5722"),
        "SP":               _sensor_style("205, 220, 57, 55", "#cddc39"),
    }

    # ── Platform styles ──
    P = {
        "DEFAULT":         _platform_style("platform_default.svg"),
        "Super Puma TH06": _platform_style("plat_super_puma.svg"),
        "N97826":          _platform_style("plat_N97826.svg"),
        "VH-ZXX":          _platform_style("plat_VH-ZXX.svg"),
        "ADS15":           _platform_style("plat_ADS15.svg"),
    }

    # ── Trajectory ──
    T = {"DEFAULT": {
        "NAME": "dash cyan", "COLOR": "#26c6da", "WIDTH": "2.2",
        "customdash": "4;3", "use_custom_dash": "1",
    }}

    # ── Beam ──
    B = {"DEFAULT": {"COLOR": qRgba(176, 190, 197, 140)}}

    # ── Frame Center ──
    F = {"DEFAULT": {
        "NAME": "diamond", "LINE_COLOR": "#ff4081",
        "LINE_WIDTH": "0.35", "SIZE": "4.5",
    }}

    # ── Frame Axis ──
    FA = {"DEFAULT": {"OUTLINE_WIDTH": "1.6", "OUTLINE_STYLE": "dash"}}

    # ── Drawing Point ──
    DP = {"DEFAULT": {
        "NAME": "circle", "COLOR": "#ff7043", "LINE_COLOR": "#ffffff",
        "LINE_WIDTH": "0.9", "SIZE": "5",
        "LABEL_FONT": "Segoe UI", "LABEL_FONT_SIZE": 10,
        "LABEL_FONT_COLOR": "#ffffff", "LABEL_SIZE": 10,
        "LABEL_BUFFER_COLOR": "#37474f", "LABEL_BUFFER_SIZE": 1.4,
        "LABEL_OFFSET_X": 2.0, "LABEL_OFFSET_Y": -2.0,
    }}

    # ── Drawing Line ──
    DL = {"DEFAULT": {"COLOR": QColor.fromRgb(255, 213, 79), "WIDTH": 1.4}}

    # ── Drawing Polygon ──
    DPL = {"DEFAULT": {
        "COLOR": "255, 213, 79, 90", "OUTLINE_COLOR": "#ffd54f",
        "OUTLINE_STYLE": "solid", "OUTLINE_WIDTH": "1.2",
    }}

    # ── Object Track ──
    OT = {"DEFAULT": {
        "COLOR": "#ff9100", "WIDTH": "2.6",
        "customdash": "1;0", "use_custom_dash": "0",
    }}

    # ── Object Position ──
    OP = {"DEFAULT": {
        "NAME": "circle", "COLOR": "#ff9100", "LINE_COLOR": "#ffffff",
        "LINE_WIDTH": "1.0", "SIZE": "7", "LABEL_FONT": "Segoe UI",
        "LABEL_FONT_SIZE": 9, "LABEL_FONT_COLOR": "#ffffff",
        "LABEL_BUFFER_COLOR": "#e65100", "LABEL_BUFFER_SIZE": 1.2,
    }}

    # ── Measure Distance ──
    MD = {"DEFAULT": {"COLOR": "#00bcd4", "WIDTH": "2.2"}}

    # ── Measure Area ──
    MA = {"DEFAULT": {
        "COLOR": "255, 193, 7, 90", "OUTLINE_COLOR": "#ffc107",
        "OUTLINE_STYLE": "solid", "OUTLINE_WIDTH": "1.6",
    }}

    # ── Unified getter (new code should prefer this) ──
    _categories = {
        "sensor": S, "platform": P, "trajectory": T, "beam": B,
        "frame_center": F, "frame_axis": FA,
        "drawing_point": DP, "drawing_line": DL, "drawing_polygon": DPL,
        "object_track": OT, "object_position": OP,
        "measure_distance": MD, "measure_area": MA,
    }

    @classmethod
    def get(cls, category, name="DEFAULT"):
        """Return a style dict by category and optional variant name."""
        cat = cls._categories.get(category, {})
        return cat.get(name, cat.get("DEFAULT", {}))

    # ── Backward-compatible accessors ──
    @staticmethod
    def getPlatform(name):
        return FmvLayerStyles.P.get(name, FmvLayerStyles.P["DEFAULT"])

    @staticmethod
    def getSensor(name):
        return FmvLayerStyles.S.get(name, FmvLayerStyles.S["DEFAULT"])

    @staticmethod
    def getTrajectory(name):
        return FmvLayerStyles.T.get(name, FmvLayerStyles.T["DEFAULT"])

    @staticmethod
    def getBeam(name):
        return FmvLayerStyles.B.get(name, FmvLayerStyles.B["DEFAULT"])

    @staticmethod
    def getDrawingPoint():
        return FmvLayerStyles.DP["DEFAULT"]

    @staticmethod
    def getFrameCenterPoint():
        return FmvLayerStyles.F["DEFAULT"]

    @staticmethod
    def getFrameAxis():
        return FmvLayerStyles.FA["DEFAULT"]

    @staticmethod
    def getDrawingLine():
        return FmvLayerStyles.DL["DEFAULT"]

    @staticmethod
    def getDrawingPolygon():
        return FmvLayerStyles.DPL["DEFAULT"]

    @staticmethod
    def getObjectTrack():
        return FmvLayerStyles.OT["DEFAULT"]

    @staticmethod
    def getObjectPosition():
        return FmvLayerStyles.OP["DEFAULT"]

    @staticmethod
    def getMeasureDistance():
        return FmvLayerStyles.MD["DEFAULT"]

    @staticmethod
    def getMeasureArea():
        return FmvLayerStyles.MA["DEFAULT"]
