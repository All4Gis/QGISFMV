# -*- coding: utf-8 -*-
"""Picture-in-picture mini map overlay on the video widget."""

from math import radians, sin, cos

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRasterLayer,
    QgsRectangle,
)
from qgis.gui import QgsMapCanvas
from qgis.PyQt.QtCore import Qt, QPointF, QRectF
from qgis.PyQt.QtGui import QColor, QPainter, QPen, QBrush, QFont, QLinearGradient
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout

from QGISFMV.geo.QgsGeoUtils import distance as _geo_distance
from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


def create_osm_basemap(name="MiniMap OSM"):
    """Return a lightweight XYZ OpenStreetMap raster layer, or None."""
    urls = (
        "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0",
        "type=xyz&url=http://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0",
    )
    for uri in urls:
        layer = QgsRasterLayer(uri, name, "wms")
        if layer.isValid():
            return layer
    return None


def _fmt_coord(value, decimals=4):
    if value is None:
        return "—"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _nice_scale_length(meters):
    """Pick a round scale-bar length (m) for the current map span."""
    if meters is None or meters <= 0:
        return None
    candidates = (5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)
    target = meters / 4.0
    for length in candidates:
        if length >= target:
            return length
    return candidates[-1]


class MiniMapOverlay(QWidget):
    """Live map preview with OSM basemap and FMV telemetry layers."""

    MARGIN = 14
    SIZE = 236

    def __init__(self, parent=None, iface=None):
        super().__init__(parent)
        self._iface = iface
        self._visible = False
        self._group_name = None
        self._heading = None
        self._sensor_lat = None
        self._sensor_lon = None
        self._mgrs = ""
        self._footprint_span_m = None
        self._scale_length_m = None
        self._basemap = create_osm_basemap()

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._canvas = QgsMapCanvas(self)
        self._canvas.setCanvasColor(QColor(30, 34, 42))
        if hasattr(self._canvas, "enableAntiAliasing"):
            self._canvas.enableAntiAliasing(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(self._canvas)

        self.hide()

    def toggle(self):
        """Toggle mini-map visibility and refresh layers when shown."""
        self._visible = not self._visible
        self.setVisible(self._visible)
        if self._visible:
            self.reposition()
            self.refresh_layers()
        return self._visible

    def set_group(self, group_name):
        """Set the layer-tree group name for map layer filtering."""
        self._group_name = group_name
        if self._visible:
            self.refresh_layers()

    def reposition(self):
        """Move the mini-map to the top-right corner of the parent widget."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.setGeometry(
            parent.width() - self.SIZE - self.MARGIN,
            self.MARGIN,
            self.SIZE,
            self.SIZE,
        )
        self.raise_()

    def _destination_crs(self):
        authid = settings_get("LAYERS", "epsg", "EPSG:4326")
        crs = QgsCoordinateReferenceSystem(authid)
        if crs.isValid():
            return crs
        return QgsCoordinateReferenceSystem("EPSG:4326")

    def _vector_layer_names(self):
        """FMV vector layers for the mini map (bottom -> top draw order)."""
        return [
            settings_get("LAYERS", "trajectory_lyr", "Trajectory"),
            settings_get("LAYERS", "footprint_lyr", "Footprint"),
            settings_get("LAYERS", "beams_lyr", "Beams"),
            settings_get("LAYERS", "frameaxis_lyr", "Frame Axis"),
            settings_get("LAYERS", "platform_lyr", "Platform"),
            settings_get("LAYERS", "framecenter_lyr", "Frame Center"),
            settings_get("LAYERS", "polygon_lyr", "Drawings Polygon"),
            settings_get("LAYERS", "line_lyr", "Drawings Line"),
            settings_get("LAYERS", "point_lyr", "Drawings Point"),
            settings_get("LAYERS", "symbol_lyr", "Military Symbols"),
            settings_get("LAYERS", "objecttrack_lyr", "Object Track"),
            settings_get("LAYERS", "objectposition_lyr", "Object Position"),
        ]

    def _set_canvas_crs(self, crs):
        if hasattr(self._canvas, "setDestinationCrs"):
            self._canvas.setDestinationCrs(crs)
        elif hasattr(self._canvas, "setCrs"):
            self._canvas.setCrs(crs)

    def _collect_group_layers(self):
        if not self._group_name:
            return {}

        project = QgsProject.instance()
        group = project.layerTreeRoot().findGroup(self._group_name)
        if group is None:
            return {}

        by_name = {}
        for child in group.findLayers():
            layer = child.layer()
            if layer is None or not layer.isValid():
                continue
            by_name[layer.name()] = layer
        return by_name

    def refresh_layers(self):
        """Rebuild the canvas layer stack: OSM basemap + telemetry vectors."""
        by_name = self._collect_group_layers()
        if not by_name and self._basemap is None:
            return

        crs = self._destination_crs()
        for layer in by_name.values():
            if layer.crs().isValid():
                crs = layer.crs()
                break

        self._set_canvas_crs(crs)

        # QgsMapCanvas draws the first layer on top; basemap goes last.
        canvas_layers = []
        for name in reversed(self._vector_layer_names()):
            layer = by_name.get(name)
            if layer is not None:
                canvas_layers.append(layer)

        if self._basemap is not None and self._basemap.isValid():
            canvas_layers.append(self._basemap)

        if not canvas_layers:
            return

        self._canvas.setLayers(canvas_layers)
        self._canvas.refresh()

    def _footprint_span_meters(self, gv):
        corners = [
            gv.getCornerUL(),
            gv.getCornerUR(),
            gv.getCornerLR(),
            gv.getCornerLL(),
        ]
        if any(c is None or None in c for c in corners):
            return None
        try:
            lats = [float(c[0]) for c in corners]
            lons = [float(c[1]) for c in corners]
        except (TypeError, ValueError):
            return None
        center = (sum(lons) / 4.0, sum(lats) / 4.0)
        return max(_geo_distance(center, (float(c[1]), float(c[0]))) for c in corners)

    def _extent_from_state(self, gv):
        if gv is None:
            return None

        rect = QgsRectangle()
        points = []

        for corner in (
            gv.getCornerUL(),
            gv.getCornerUR(),
            gv.getCornerLR(),
            gv.getCornerLL(),
        ):
            if corner is None or None in corner:
                continue
            points.append((float(corner[1]), float(corner[0])))

        lat = gv.getSensorLatitude()
        lon = gv.getSensorLongitude()
        if lat is not None and lon is not None:
            points.append((float(lon), float(lat)))

        fc_lat = gv.getFrameCenterLat()
        fc_lon = gv.getFrameCenterLon()
        if fc_lat is not None and fc_lon is not None:
            points.append((float(fc_lon), float(fc_lat)))

        if not points:
            return None

        for x, y in points:
            if rect.isNull():
                rect = QgsRectangle(x, y, x, y)
            else:
                rect.combineExtentWith(QgsRectangle(x, y, x, y))

        pad = max(rect.width(), rect.height()) * 0.45
        if pad <= 0:
            pad = 0.0015
        return rect.buffered(pad)

    def _update_scale_from_extent(self, extent):
        self._scale_length_m = None
        if extent is None or extent.isNull() or extent.isEmpty():
            return
        center_lat = (extent.yMinimum() + extent.yMaximum()) / 2.0
        try:
            span_m = _geo_distance(
                (extent.xMinimum(), center_lat),
                (extent.xMaximum(), center_lat),
            )
        except Exception as _exc:
            log.debug("MiniMap scale span calculation failed: %s", _exc)
            return
        self._scale_length_m = _nice_scale_length(span_m)

    def _update_heading(self):
        platform_name = settings_get("LAYERS", "platform_lyr", "Platform")
        layer = qgsu.selectLayerByName(platform_name, self._group_name)
        if layer is None or layer.renderer() is None:
            self._heading = None
            return
        try:
            self._heading = float(layer.renderer().symbol().angle())
        except Exception as _exc:
            log.debug("MiniMap heading read failed: %s", _exc)
            self._heading = None

    def _update_mgrs(self):
        self._mgrs = ""
        if self._sensor_lat is None or self._sensor_lon is None:
            return
        try:
            import mgrs

            self._mgrs = mgrs.MGRS().toMgrs(
                float(self._sensor_lat), float(self._sensor_lon)
            )
        except Exception as _exc:
            log.debug("MiniMap MGRS conversion failed: %s", _exc)
            self._mgrs = ""

    def update_from_state(self, gv):
        """Refresh mini-map layers when the global state changes."""
        if not self._visible:
            return
        self.refresh_layers()

        if gv is not None:
            self._sensor_lat = gv.getSensorLatitude()
            self._sensor_lon = gv.getSensorLongitude()
            self._footprint_span_m = self._footprint_span_meters(gv)
            self._update_mgrs()

        extent = self._extent_from_state(gv)
        if extent is not None and not extent.isNull():
            self._canvas.setExtent(extent)
            self._canvas.refresh()
            self._update_scale_from_extent(extent)
        self._update_heading()
        self.update()

    def _draw_header(self, painter):
        gradient = QLinearGradient(0, 0, 0, 34)
        gradient.setColorAt(0, QColor(8, 16, 24, 210))
        gradient.setColorAt(1, QColor(8, 16, 24, 40))
        painter.fillRect(QRectF(4, 4, self.width() - 8, 30), gradient)

        title_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.setPen(QPen(QColor(220, 255, 230, 230)))
        painter.drawText(QPointF(10, 16), "MINI MAP")

        coord_font = QFont("Consolas", 7)
        painter.setFont(coord_font)
        painter.setPen(QPen(QColor(180, 220, 255, 210)))
        coord_text = f"{_fmt_coord(self._sensor_lat)}  {_fmt_coord(self._sensor_lon)}"
        painter.drawText(QPointF(10, 28), coord_text)

    def _draw_north_arrow(self, painter):
        cx = self.width() - 22
        cy = 22
        painter.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
        painter.setBrush(QBrush(QColor(255, 255, 255, 40)))
        painter.drawEllipse(QPointF(cx, cy), 11, 11)
        painter.drawLine(QPointF(cx, cy + 6), QPointF(cx, cy - 7))
        painter.drawLine(QPointF(cx, cy - 7), QPointF(cx - 3, cy - 2))
        painter.drawLine(QPointF(cx, cy - 7), QPointF(cx + 3, cy - 2))
        north_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(north_font)
        painter.setPen(QPen(QColor(255, 255, 255, 230)))
        painter.drawText(QPointF(cx - 4, cy - 10), "N")

    def _draw_scale_bar(self, painter):
        if self._scale_length_m is None:
            return
        extent = self._canvas.extent()
        if extent is None or extent.isNull() or extent.isEmpty():
            return

        map_rect = self._canvas.rect()
        if map_rect.width() <= 0:
            return

        center_lat = (extent.yMinimum() + extent.yMaximum()) / 2.0
        try:
            span_m = _geo_distance(
                (extent.xMinimum(), center_lat),
                (extent.xMaximum(), center_lat),
            )
        except Exception as _exc:
            log.debug("MiniMap scale bar span calculation failed: %s", _exc)
            return
        if span_m <= 0:
            return

        bar_px = max(24, int(map_rect.width() * (self._scale_length_m / span_m)))
        bar_px = min(bar_px, int(self.width() * 0.45))
        x0 = 12
        y0 = self.height() - 28

        painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
        painter.drawLine(x0, y0, x0 + bar_px, y0)
        painter.drawLine(x0, y0 - 3, x0, y0 + 3)
        painter.drawLine(x0 + bar_px, y0 - 3, x0 + bar_px, y0 + 3)

        label = (
            f"{int(self._scale_length_m)} m"
            if self._scale_length_m < 1000
            else f"{self._scale_length_m / 1000:.1f} km"
        )
        scale_font = QFont("Segoe UI", 6)
        painter.setFont(scale_font)
        painter.setPen(QPen(QColor(240, 240, 240, 220)))
        painter.drawText(QPointF(x0, y0 - 5), label)

    def _draw_footer_info(self, painter):
        info_parts = []
        if self._heading is not None:
            info_parts.append(f"HDG {self._heading:.0f}°")
        if self._footprint_span_m is not None:
            if self._footprint_span_m >= 1000:
                info_parts.append(f"FP ~{self._footprint_span_m / 1000:.1f} km")
            else:
                info_parts.append(f"FP ~{self._footprint_span_m:.0f} m")
        if self._mgrs:
            info_parts.append(self._mgrs[:15])

        if not info_parts:
            return

        footer_font = QFont("Segoe UI", 6)
        painter.setFont(footer_font)
        painter.setPen(QPen(QColor(200, 255, 220, 200)))
        painter.drawText(
            QPointF(10, self.height() - 10),
            "  ·  ".join(info_parts),
        )

    def _draw_heading_arrow(self, painter):
        if self._heading is None:
            return
        cx = self.width() / 2.0
        cy = self.height() - 18
        radius = 10
        angle = radians(self._heading - 90)
        tip = QPointF(cx + radius * cos(angle), cy + radius * sin(angle))
        left = QPointF(
            cx + radius * 0.45 * cos(angle + 2.4),
            cy + radius * 0.45 * sin(angle + 2.4),
        )
        right = QPointF(
            cx + radius * 0.45 * cos(angle - 2.4),
            cy + radius * 0.45 * sin(angle - 2.4),
        )
        painter.setBrush(QBrush(QColor(255, 193, 7, 220)))
        painter.setPen(QPen(QColor(255, 255, 255, 180), 1))
        painter.drawPolygon([tip, left, right])

    def _draw_legend(self, painter):
        items = (
            (QColor(0, 188, 212, 230), "Footprint"),
            (QColor(255, 193, 7, 230), "Platform"),
            (QColor(255, 112, 67, 230), "Drawings"),
            (QColor(156, 204, 101, 230), "Mil sym"),
        )
        x = self.width() - 58
        y = 40
        legend_font = QFont("Segoe UI", 6)
        painter.setFont(legend_font)
        for color, label in items:
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
            painter.drawRect(QRectF(x, y - 7, 7, 7))
            painter.setPen(QPen(QColor(230, 230, 230, 200)))
            painter.drawText(QPointF(x + 10, y), label)
            y += 11

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._visible:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QPen(QColor(0, 255, 120, 200), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(1.5, 1.5, self.width() - 3, self.height() - 3), 8, 8
        )

        self._draw_header(painter)
        self._draw_north_arrow(painter)
        self._draw_legend(painter)
        self._draw_scale_bar(painter)
        self._draw_heading_arrow(painter)
        self._draw_footer_info(painter)

        if self._basemap is not None and self._basemap.isValid():
            attrib_font = QFont("Segoe UI", 6)
            painter.setFont(attrib_font)
            painter.setPen(QPen(QColor(210, 210, 210, 170)))
            painter.drawText(QPointF(self.width() - 40, self.height() - 5), "© OSM")

        painter.end()
