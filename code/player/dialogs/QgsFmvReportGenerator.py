# -*- coding: utf-8 -*-
"""PDF report generation, extracted from QgsFmvMetadata.py.

Owns all metadata-formatting helpers and the ReportGenerator class used to
render the multi-section FMV analysis PDF report.
"""
import html
import os
from datetime import datetime

from qgis.PyQt.QtCore import Qt, QCoreApplication, QSize, QPointF, QUrl
from qgis.PyQt.QtGui import (
    QFont,
    QTextCursor,
    QTextDocument,
    QTextBlockFormat,
    QTextImageFormat,
    QColor,
    QImage,
    QPainter,
    QPen,
    QPolygonF,
    QTextFormat,
    QPageSize,
    QPageLayout,
)
from qgis.PyQt.QtPrintSupport import QPrinter
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsMapSettings,
    QgsMapRendererSequentialJob,
    QgsProject,
    QgsRectangle,
)

from QGISFMV.utils.logging import log
from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get
from QGISFMV.utils.ui.QgsFmvResources import ICON_HEADER_LOGO
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.player.overlays.QgsFmvMiniMap import create_osm_basemap


# ── PDF report palette (FMV branding) ──
_PDF_COLORS = {
    "primary": "#1a2332",
    "header_bg": "#ffffff",
    "header_border": "#cfd8dc",
    "header_text": "#546e7a",
    "accent": "#00bcd4",
    "accent_dark": "#00838f",
    "text": "#263238",
    "muted": "#78909c",
    "border": "#cfd8dc",
    "surface": "#f5f7fa",
    "category": "#37474f",
    "classified": "#c62828",
}

# ~12.7 mm — consistent margins for all PDF sections (points, 72 pt = 1 inch).
_PDF_MARGIN_PT = 36.0


def _pdf_page_metrics(printer):
    """Page and content dimensions in points for QTextDocument layout."""
    page_rect = printer.pageLayout().paintRect(QPageLayout.Unit.Point)
    page_width = float(page_rect.width())
    margin = _PDF_MARGIN_PT
    content_width = max(280.0, page_width - (2.0 * margin))
    dpi = float(printer.resolution())
    return {
        "page_size": page_rect.size(),
        "page_width": page_width,
        "content_width": content_width,
        "margin": margin,
        "dpi": dpi,
        "pt_to_px": dpi / 72.0,
    }


def _scale_image_for_pdf(image, max_width_pt, max_height_pt, pt_to_px):
    """Scale a QImage to fit PDF content box (points → device pixels)."""
    if image is None or image.isNull():
        return None
    max_w_px = max(1, int(max_width_pt * pt_to_px))
    max_h_px = max(1, int(max_height_pt * pt_to_px))
    return image.scaled(
        max_w_px,
        max_h_px,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def _metadata_table_headers(VManager):
    """Column titles for the metadata table (defaults Key / Name / Value)."""
    defaults = (
        QCoreApplication.translate("QgsFmvMetadata", "Key"),
        QCoreApplication.translate("QgsFmvMetadata", "Name"),
        QCoreApplication.translate("QgsFmvMetadata", "Value"),
    )
    if VManager is None:
        return list(defaults)
    headers = []
    for column in range(min(VManager.columnCount(), 3)):
        item = VManager.horizontalHeaderItem(column)
        headers.append(item.text() if item is not None else defaults[column])
    while len(headers) < 3:
        headers.append(defaults[len(headers)])
    return headers


def _build_grouped_metadata_html(data, VManager):
    """HTML metadata table with fixed column widths (reliable in QTextDocument)."""
    headers = _metadata_table_headers(VManager)
    col_widths = ("22%", "28%", "50%")
    groups = _group_metadata_fields(data)
    if not groups:
        empty_t = QCoreApplication.translate(
            "QgsFmvMetadata", "No metadata available for this frame."
        )
        return (
            f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt;'>"
            f"{_html_escape(empty_t)}</p>"
        )

    parts = [
        "<table width='100%' cellpadding='0' cellspacing='0' "
        f"style='border-collapse:collapse; table-layout:fixed; "
        f"border:1px solid {_PDF_COLORS['border']};'>"
    ]

    parts.append("<tr>")
    for index, header in enumerate(headers):
        parts.append(
            f"<td width='{col_widths[index]}' "
            f"style='background:{_PDF_COLORS['primary']}; color:white; "
            f"font-weight:bold; font-size:8pt; padding:6px 8px; "
            f"border:1px solid {_PDF_COLORS['border']};'>"
            f"{_html_escape(header)}</td>"
        )
    parts.append("</tr>")

    data_row = 0
    for group_name, keys in groups:
        parts.append(
            f"<tr><td colspan='3' "
            f"style='background:{_PDF_COLORS['category']}; color:white; "
            f"font-weight:bold; font-size:8pt; padding:6px 8px; "
            f"border:1px solid {_PDF_COLORS['border']};'>"
            f"{_html_escape(group_name)}</td></tr>"
        )
        for key in keys:
            entry = data.get(key, ["", ""])
            label = entry[0] if len(entry) > 0 else ""
            value = entry[1] if len(entry) > 1 else ""
            bg = _PDF_COLORS["surface"] if data_row % 2 else "#ffffff"
            parts.append(f"<tr style='background:{bg};'>")
            for col_index, cell in enumerate((str(key), str(label), str(value))):
                mono = (
                    "font-family:monospace; font-size:7.5pt;"
                    if col_index == 2
                    else ""
                )
                parts.append(
                    f"<td style='padding:5px 8px; font-size:8pt; vertical-align:top; "
                    f"border:1px solid {_PDF_COLORS['border']}; "
                    f"word-wrap:break-word; overflow-wrap:break-word; {mono}'>"
                    f"{_html_escape(cell)}</td>"
                )
            parts.append("</tr>")
            data_row += 1

    parts.append("</table>")
    return "".join(parts)


_METADATA_GROUPS = (
    (
        "Platform & Mission",
        ("platform", "mission", "tail", "designation", "flight", "callsign"),
    ),
    (
        "Sensor & Position",
        (
            "sensor",
            "latitude",
            "longitude",
            "altitude",
            "elevation",
            "heading",
            "pitch",
            "roll",
            "yaw",
            "ground",
        ),
    ),
    (
        "Frame & Imagery",
        (
            "frame",
            "corner",
            "fov",
            "slant",
            "image",
            "target",
            "footprint",
            "width",
            "height",
            "source",
        ),
    ),
    (
        "Timing & Navigation",
        ("time", "stamp", "utc", "checkpoint", "date"),
    ),
    (
        "Security & System",
        ("security", "classification", "version", "checksum", "uuid", "unique"),
    ),
)

_SUMMARY_SPECS = (
    ("Platform", ("platform", "designation")),
    ("Heading", ("platform", "heading")),
    ("Sensor Latitude", ("sensor", "latitude")),
    ("Sensor Longitude", ("sensor", "longitude")),
    ("Sensor Altitude", ("sensor", "true", "altitude")),
    ("Image Sensor", ("image", "source", "sensor")),
    ("Frame Center Lat", ("frame", "center", "latitude")),
    ("Frame Center Lon", ("frame", "center", "longitude")),
    ("Slant Range", ("slant", "range")),
    ("Ground Range", ("ground", "range")),
    ("Precision Time", ("precision", "time")),
    ("Classification", ("security", "classification")),
)


def _html_escape(value):
    return html.escape(str(value) if value is not None else "")


def _normalize_key(key):
    return str(key).lower().replace("_", " ").replace("-", " ")


def _metadata_entry_leaves(key_hint, entry):
    """Yield scalar MISB labels/values, recursing nested local sets."""
    if not entry:
        return
    label = str(entry[0]) if len(entry) > 0 else str(key_hint)
    if len(entry) >= 4 and isinstance(entry[-1], dict):
        for sub_key, sub_entry in entry[-1].items():
            yield from _metadata_entry_leaves(f"{label} {sub_key}", sub_entry)
        return
    if len(entry) >= 2:
        value = entry[1]
        if value is not None and not isinstance(value, dict):
            text = str(value).strip()
            if text and text != "None":
                yield label, text
                yield str(key_hint), text


def _metadata_leaf_entries(data):
    if not data:
        return
    for key, entry in data.items():
        yield from _metadata_entry_leaves(key, entry)


def _find_metadata_value(data, *required_tokens):
    """Find a metadata value by matching tokens against field keys and labels."""
    if not data:
        return "—"
    required = [token.lower() for token in required_tokens]
    for label, value in _metadata_leaf_entries(data):
        key_lower = _normalize_key(label)
        if all(token in key_lower for token in required):
            return value
    return "—"


_PACKET_FIELD_NAMES = {
    ("platform", "designation"): "PlatformDesignation",
    ("platform", "heading"): "PlatformHeadingAngle",
    ("sensor", "latitude"): "SensorLatitude",
    ("sensor", "longitude"): "SensorLongitude",
    ("sensor", "true", "altitude"): "SensorTrueAltitude",
    ("image", "source", "sensor"): "ImageSourceSensor",
    ("frame", "center", "latitude"): "FrameCenterLatitude",
    ("frame", "center", "longitude"): "FrameCenterLongitude",
    ("slant", "range"): "SlantRange",
    ("ground", "range"): "GroundRange",
    ("precision", "time"): "PrecisionTimeStamp",
}


def _packet_attribute_for_tokens(player, tokens):
    if player is None:
        return None
    packet = getattr(player, "_lastMetadataPacket", None)
    if packet is None:
        return None
    attr = _PACKET_FIELD_NAMES.get(tuple(token.lower() for token in tokens))
    if not attr:
        return None
    try:
        value = getattr(packet, attr)
    except AttributeError:
        return None
    if value is None:
        return None
    if hasattr(value, "value"):
        value = value.value
    return value


def _gv_value_for_summary(tokens):
    """Fallback executive-summary values from live FMV state."""
    try:
        from QGISFMV.utils.core.QgsFmvUtils import gv
    except Exception as exc:
        log.debug("gv import failed for summary: %s", exc)
        return None

    token_key = tuple(token.lower() for token in tokens)
    direct = {
        ("sensor", "latitude"): gv.getSensorLatitude(),
        ("sensor", "longitude"): gv.getSensorLongitude(),
        ("frame", "center", "latitude"): gv.getFrameCenterLat(),
        ("frame", "center", "longitude"): gv.getFrameCenterLon(),
    }
    if token_key in direct:
        value = direct[token_key]
        return value if value is not None else None

    if token_key == ("sensor", "true", "altitude"):
        altitude = gv.getSensorTrueAltitude()
        if isinstance(altitude, (list, tuple)):
            altitude = next((v for v in altitude if v is not None), None)
        return altitude

    return None


def _summary_field_value(data, tokens, player=None):
    value = _find_metadata_value(data, *tokens)
    if value != "—":
        return value
    packet_value = _packet_attribute_for_tokens(player, tokens)
    if packet_value is not None:
        return str(packet_value)
    gv_value = _gv_value_for_summary(tokens)
    if gv_value is not None:
        return str(gv_value)
    if player is not None:
        precision_ts = getattr(player, "PrecisionTimeStamp", "") or ""
        if ("precision", "time") == tuple(t.lower() for t in tokens) and precision_ts:
            return precision_ts
    return "—"


def _metadata_dict_from_table(table):
    data = {}
    if table is None:
        return data
    for row in range(table.rowCount()):
        key_item = table.item(row, 0)
        if key_item is None:
            continue
        label_item = table.item(row, 1)
        value_item = table.item(row, 2)
        data[key_item.text()] = [
            label_item.text() if label_item is not None else "",
            value_item.text() if value_item is not None else "",
        ]
    return data


def _corners_from_footprint_feature(feature):
    """Extract footprint corners as (lon, lat) tuples from a layer feature."""
    field_names = feature.fields().names()
    corners = []
    for idx in range(1, 5):
        lon_field = f"clon{idx}"
        lat_field = f"clat{idx}"
        if lon_field not in field_names or lat_field not in field_names:
            continue
        try:
            lon = float(feature[lon_field])
            lat = float(feature[lat_field])
        except (TypeError, ValueError):
            continue
        corners.append((lon, lat))
    if len(corners) >= 3:
        return corners

    geometry = feature.geometry()
    if geometry is None or geometry.isEmpty():
        return []

    try:
        polygon = geometry.asPolygon()
        if polygon and polygon[0]:
            return [(pt.x(), pt.y()) for pt in polygon[0]]
    except Exception as exc:
        log.debug("Footprint asPolygon failed: %s", exc)

    try:
        for part in geometry.asMultiPolygon():
            if part and part[0]:
                return [(pt.x(), pt.y()) for pt in part[0]]
    except Exception as exc:
        log.debug("Footprint asMultiPolygon failed: %s", exc)

    try:
        const = geometry.constGet()
        if const is not None and hasattr(const, "exteriorRing"):
            ring = const.exteriorRing()
            if ring is not None:
                return [
                    (ring.pointN(i).x(), ring.pointN(i).y())
                    for i in range(ring.numPoints())
                ]
    except Exception as exc:
        log.debug("Footprint exteriorRing failed: %s", exc)

    try:
        vertices = []
        for vertex in geometry.vertices():
            vertices.append((vertex.x(), vertex.y()))
        if len(vertices) >= 3:
            if vertices[0] == vertices[-1]:
                vertices = vertices[:-1]
            return vertices
    except Exception as exc:
        log.debug("Footprint vertices iteration failed: %s", exc)
    return []


def _footprint_corners_for_report(data, group_name):
    """Collect footprint corners from QGIS layer, metadata, or live gv state."""
    # Source 1: QGIS footprint layer
    layer_name = settings_get("LAYERS", "footprint_lyr", "Footprint")
    layer = qgsu.selectLayerByName(layer_name, group_name) if group_name else None
    if layer is not None and layer.featureCount() > 0:
        for feature in layer.getFeatures():
            corners = _corners_from_footprint_feature(feature)
            if len(corners) >= 3:
                return corners

    # Source 2: MISB metadata corner/point fields
    corners = []
    for point_idx in range(1, 5):
        lat = lon = None
        point_token = str(point_idx)
        for label, value in _metadata_leaf_entries(data):
            key_lower = _normalize_key(label)
            if point_token not in key_lower:
                continue
            if "corner" not in key_lower and "point" not in key_lower:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if "latitude" in key_lower:
                lat = numeric
            elif "longitude" in key_lower:
                lon = numeric
        if lat is not None and lon is not None:
            corners.append((lon, lat))
    if len(corners) >= 3:
        return corners

    # Source 3: live gv state
    try:
        from QGISFMV.utils.core.QgsFmvUtils import gv
    except Exception as exc:
        log.debug("gv import failed for footprint corners: %s", exc)
        return []

    corners = []
    for getter in (gv.getCornerUL, gv.getCornerUR, gv.getCornerLR, gv.getCornerLL):
        point = getter()
        if point is None or len(point) < 2:
            continue
        lat, lon = float(point[0]), float(point[1])
        corners.append((lon, lat))
    return corners


def _sensor_position_from_layer(group_name):
    if not group_name:
        return None, None
    platform_name = settings_get("LAYERS", "platform_lyr", "Platform")
    layer = qgsu.selectLayerByName(platform_name, group_name)
    if layer is None or layer.featureCount() == 0:
        return None, None

    for feature in layer.getFeatures():
        lat = lon = None
        field_names = feature.fields().names()
        if "latitude" in field_names and "longitude" in field_names:
            try:
                lat = float(feature["latitude"])
                lon = float(feature["longitude"])
            except (TypeError, ValueError):
                pass
        if lat is None or lon is None:
            geometry = feature.geometry()
            if geometry is not None and not geometry.isEmpty():
                try:
                    point = geometry.asPoint()
                    lon, lat = point.x(), point.y()
                except Exception as exc:
                    try:
                        point = geometry.constGet()
                        if point is not None:
                            lon, lat = point.x(), point.y()
                    except Exception as nested_exc:
                        log.debug(
                            "Platform geometry parse failed: %s / %s",
                            exc,
                            nested_exc,
                        )
        if lat is not None and lon is not None:
            return lat, lon
    return None, None


def _sensor_position_for_report(data):
    lat = lon = None
    lat_text = _find_metadata_value(data, "sensor", "latitude")
    lon_text = _find_metadata_value(data, "sensor", "longitude")
    if lat_text == "—":
        lat_text = _find_metadata_value(data, "platform", "latitude")
    if lon_text == "—":
        lon_text = _find_metadata_value(data, "platform", "longitude")

    for raw, target in ((lat_text, "lat"), (lon_text, "lon")):
        if raw == "—":
            continue
        try:
            if target == "lat":
                lat = float(raw)
            else:
                lon = float(raw)
        except (TypeError, ValueError):
            pass

    if lat is None or lon is None:
        try:
            from QGISFMV.utils.core.QgsFmvUtils import gv

            if gv is not None:
                if lat is None:
                    lat = gv.getSensorLatitude()
                if lon is None:
                    lon = gv.getSensorLongitude()
                if lat is not None:
                    lat = float(lat)
                if lon is not None:
                    lon = float(lon)
        except Exception as exc:
            log.debug("Sensor position from gv failed: %s", exc)

    return lat, lon


def _sensor_position_for_report_with_group(data, group_name=None, player=None):
    lat, lon = _sensor_position_for_report(data)
    if lat is not None and lon is not None:
        return lat, lon

    if group_name:
        lat, lon = _sensor_position_from_layer(group_name)
        if lat is not None and lon is not None:
            return lat, lon

    packet = getattr(player, "_lastMetadataPacket", None) if player else None
    if packet is not None:
        try:
            if lat is None and packet.SensorLatitude is not None:
                lat = float(packet.SensorLatitude)
            if lon is None and packet.SensorLongitude is not None:
                lon = float(packet.SensorLongitude)
        except (TypeError, ValueError, AttributeError):
            pass
    return lat, lon


def _classification_level(data):
    level = _find_metadata_value(data, "security", "classification")
    if level == "—":
        level = _find_metadata_value(data, "classification")
    return level


def _is_classified(level):
    if not level or level == "—":
        return False
    upper = level.upper().strip()
    return upper not in ("UNCLASSIFIED", "U", "NONE", "N/A", "UNKNOWN", "")


def _sorted_metadata_keys(keys):
    """Sort metadata keys safely (MISB may mix int tags and str names)."""
    return sorted(keys, key=lambda key: str(key))


def _group_metadata_fields(data):
    if not isinstance(data, dict):
        try:
            data = dict(data)
        except (TypeError, ValueError):
            data = {}
    assigned = set()
    groups = []
    for group_name, tokens in _METADATA_GROUPS:
        items = []
        for key in _sorted_metadata_keys(data.keys()):
            if key in assigned:
                continue
            key_lower = _normalize_key(key)
            if any(token in key_lower for token in tokens):
                items.append(key)
                assigned.add(key)
        if items:
            groups.append((group_name, items))

    remaining = [
        key for key in _sorted_metadata_keys(data.keys()) if key not in assigned
    ]
    if remaining:
        groups.append(
            (
                QCoreApplication.translate("QgsFmvMetadata", "Additional Fields"),
                remaining,
            )
        )
    return groups


def _create_osm_basemap_layer():
    """Temporary OSM XYZ layer for report map rendering."""
    return create_osm_basemap("OSM-report")


def _extent_from_corners(corners):
    if len(corners) < 3:
        return None
    extent = QgsRectangle()
    for lon, lat in corners:
        extent.combineExtentWith(QgsRectangle(lon, lat, lon, lat))
    if extent.isNull() or extent.isEmpty():
        return None
    return extent


def _padded_map_extent(extent, padding_factor=0.4, minimum_span=0.0003):
    if extent is None or extent.isNull() or extent.isEmpty():
        return extent
    span = max(extent.width(), extent.height(), minimum_span)
    pad = span * padding_factor
    return QgsRectangle(
        extent.xMinimum() - pad,
        extent.yMinimum() - pad,
        extent.xMaximum() + pad,
        extent.yMaximum() + pad,
    )


def _geo_to_pixel(lon, lat, extent, width_px, height_px):
    if extent.width() <= 0 or extent.height() <= 0:
        return 0.0, 0.0
    x = (lon - extent.xMinimum()) / extent.width() * width_px
    y = (1.0 - (lat - extent.yMinimum()) / extent.height()) * height_px
    return x, y


# ---------------------------------------------------------------------------
# ReportGenerator — owns PDF rendering, separated from the dock widget
# ---------------------------------------------------------------------------

class ReportGenerator:
    """Generates professional multi-section FMV analysis PDF reports."""

    def __init__(self, player=None):
        self.player = player

    # ── public entry point ──────────────────────────────────────────────

    def generate(
        self,
        task,
        out,
        timestamp,
        data,
        frame,
        rows,
        columns,
        fileName,
        VManager,
        frame_clean=None,
    ):
        """Create a professional multi-section FMV analysis PDF report."""
        if not data:
            data = self._report_metadata()

        font_normal = QFont("Helvetica", 8, QFont.Weight.Normal)
        font_section = QFont("Helvetica", 11, QFont.Weight.Bold)

        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setOutputFileName(out)
        printer.setFullPage(True)

        metrics = _pdf_page_metrics(printer)
        document = QTextDocument()
        document.setDefaultFont(font_normal)
        document.setPageSize(metrics["page_size"])
        document.setDocumentMargin(int(metrics["margin"]))
        content_width = metrics["content_width"]
        frame_max_height_pt = min(420.0, metrics["page_size"].height() * 0.55)
        map_max_height_pt = min(300.0, metrics["page_size"].height() * 0.38)

        cursor = QTextCursor(document)
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        video_name = os.path.basename(fileName) if fileName else "—"
        classification = _classification_level(data)
        precision_ts = ""
        if self.player is not None:
            precision_ts = getattr(self.player, "PrecisionTimeStamp", "") or ""

        self._insert_cover(
            cursor,
            video_name=video_name,
            file_path=fileName,
            timestamp=timestamp,
            precision_ts=precision_ts,
            generated_at=generated_at,
            classification=classification,
        )
        self._insert_summary(cursor, data)

        try:
            map_img = self._render_map(data, width_px=420, height_px=320)
        except Exception as exc:
            log.warning("PDF footprint mini map skipped: %s", exc)
            map_img = None
        if map_img is not None and not map_img.isNull():
            self._page_break(cursor)
            map_title = QCoreApplication.translate(
                "QgsFmvMetadata", "Frame Footprint Map"
            )
            self._insert_section_header(
                cursor, map_title, font_section, _PDF_COLORS["accent_dark"]
            )

            caption_t = QCoreApplication.translate(
                "QgsFmvMetadata",
                "Mini map with OpenStreetMap basemap and the current frame footprint",
            )
            group_name = None
            if self.player is not None and hasattr(self.player, "_videoGroupName"):
                group_name = self.player._videoGroupName()
            lat, lon = _sensor_position_for_report_with_group(
                data, group_name, self.player
            )
            lat_text = f"{lat:.6f}" if lat is not None else "—"
            lon_text = f"{lon:.6f}" if lon is not None else "—"
            coord_t = QCoreApplication.translate("QgsFmvMetadata", "Sensor position")
            cursor.insertHtml(
                f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt; margin:0 0 8px 0;'>"
                f"{_html_escape(caption_t)}<br>"
                f"<strong>{_html_escape(coord_t)}:</strong> "
                f"{_html_escape(lat_text)}, {_html_escape(lon_text)}</p>"
            )

            self._insert_framed_image(
                cursor,
                map_img,
                metrics=metrics,
                max_width_pt=content_width,
                max_height_pt=map_max_height_pt,
                document=document,
            )
            self._insert_footprint_map_legend(cursor)

        self._page_break(cursor)
        metadata_title = QCoreApplication.translate(
            "QgsFmvMetadata", "Metadata Details"
        )
        self._insert_section_header(
            cursor, metadata_title, font_section, _PDF_COLORS["accent_dark"]
        )
        subtitle = QCoreApplication.translate(
            "QgsFmvMetadata",
            "MISB metadata fields grouped by category for the current frame.",
        )
        cursor.insertHtml(
            f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt; margin:0 0 10px 0;'>"
            f"{_html_escape(subtitle)}</p>"
        )
        self._insert_metadata_table(cursor, data, VManager)

        # Annotated frame — own page so the caption is not cut off
        self._page_break(cursor)
        annotated_t = QCoreApplication.translate(
            "QgsFmvMetadata", "Video Frame with Drawings"
        )
        self._insert_section_header(
            cursor, annotated_t, font_section, _PDF_COLORS["accent_dark"]
        )
        frame_note = QCoreApplication.translate(
            "QgsFmvMetadata",
            "Current video frame with user drawings burned in. Timestamp: {0}",
        ).format(timestamp)
        cursor.insertHtml(
            f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt; "
            f"margin:4px 0 12px 0;'>{_html_escape(frame_note)}</p>"
        )
        if frame is not None and not frame.isNull():
            self._insert_framed_image(
                cursor,
                frame,
                metrics=metrics,
                max_width_pt=content_width,
                max_height_pt=frame_max_height_pt,
                caption=timestamp,
                document=document,
            )

        # Clean frame — separate page, never stacked on the annotated one
        if frame_clean is not None and not frame_clean.isNull():
            self._page_break(cursor)
            clean_t = QCoreApplication.translate(
                "QgsFmvMetadata", "Video Frame without Annotations"
            )
            self._insert_section_header(
                cursor, clean_t, font_section, _PDF_COLORS["accent_dark"]
            )
            clean_note = QCoreApplication.translate(
                "QgsFmvMetadata",
                "Same video frame without drawings or overlays. Timestamp: {0}",
            ).format(timestamp)
            cursor.insertHtml(
                f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt; "
                f"margin:4px 0 12px 0;'>{_html_escape(clean_note)}</p>"
            )
            self._insert_framed_image(
                cursor,
                frame_clean,
                metrics=metrics,
                max_width_pt=content_width,
                max_height_pt=frame_max_height_pt,
                caption=timestamp,
                document=document,
            )

        self._insert_footer(cursor, generated_at)

        document.print(printer)

        if task is not None and task.isCanceled():
            return None
        return {
            "task": task.description() if task is not None else "Save PDF Report Task"
        }

    # ── metadata helper ─────────────────────────────────────────────────

    def _report_metadata(self):
        """Metadata dict for exports, falling back to the visible table."""
        data = {}
        if self.player is not None:
            packet_data = self.player.GetPacketData()
            if packet_data:
                data = dict(packet_data)
        table = getattr(self.player, "VManager", None) if self.player else None
        table_data = _metadata_dict_from_table(table)
        if table_data:
            if not data:
                data = table_data
            else:
                for key, entry in table_data.items():
                    if key not in data:
                        data[key] = entry
                        continue
                    current = data.get(key)
                    if (
                        current
                        and len(current) > 1
                        and str(current[1]).strip() in ("", "None")
                        and len(entry) > 1
                        and str(entry[1]).strip() not in ("", "None")
                    ):
                        data[key] = entry
        return data

    # ── cover page ──────────────────────────────────────────────────────

    @staticmethod
    def _build_cover_html(
        video_name, file_path, timestamp, precision_ts, generated_at, classification
    ):
        """Return the full HTML string for the report cover block."""
        title_t = QCoreApplication.translate("QgsFmvMetadata", "FMV Analysis Report")
        subtitle_t = QCoreApplication.translate(
            "QgsFmvMetadata",
            "Geospatial Full Motion Video intelligence document",
        )
        video_t = QCoreApplication.translate("QgsFmvMetadata", "Video file")
        path_t = QCoreApplication.translate("QgsFmvMetadata", "Source path")
        time_t = QCoreApplication.translate("QgsFmvMetadata", "Playback time")
        precision_t = QCoreApplication.translate(
            "QgsFmvMetadata", "Precision timestamp"
        )
        generated_t = QCoreApplication.translate("QgsFmvMetadata", "Generated")
        report_id_t = QCoreApplication.translate("QgsFmvMetadata", "Report ID")
        report_id = datetime.now().strftime("FMV-%Y%m%d-%H%M%S")

        classification_html = ""
        if _is_classified(classification):
            class_t = QCoreApplication.translate("QgsFmvMetadata", "Classification")
            classification_html = (
                f"<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:0;'>"
                f"<tr><td style='background:{_PDF_COLORS['classified']}; color:white; "
                f"text-align:center; font-weight:bold; font-size:11pt; padding:8px;'>"
                f"{_html_escape(class_t)}: {_html_escape(classification)}"
                f"</td></tr></table>"
            )

        return f"""
        <table width='100%' cellpadding='0' cellspacing='0' style='margin-bottom:16px;'>
          <tr>
            <td style='background:{_PDF_COLORS['header_bg']}; padding:14px 20px;
                       border:1px solid {_PDF_COLORS['header_border']};
                       border-bottom:3px solid {_PDF_COLORS['accent']};'>
              <table width='100%' cellpadding='0' cellspacing='0'>
                <tr>
                  <td>
                    <img src='{ICON_HEADER_LOGO}' height='28' />
                  </td>
                  <td align='right' style='color:{_PDF_COLORS['header_text']};
                             font-size:10pt; font-weight:bold;'>
                    QGISFMV
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
        {classification_html}
        <h1 style='color:{_PDF_COLORS['primary']}; font-size:22pt; margin:18px 0 4px 0;'>
          {_html_escape(title_t)}
        </h1>
        <p style='color:{_PDF_COLORS['muted']}; font-size:10pt; margin:0 0 14px 0;'>
          {_html_escape(subtitle_t)}
        </p>
        <hr style='border:none; border-top:3px solid {_PDF_COLORS['accent']}; margin:0 0 16px 0;'/>
        <table width='100%' cellpadding='0' cellspacing='0'
               style='border:1px solid {_PDF_COLORS['border']}; border-collapse:collapse;
                      table-layout:fixed; margin-bottom:12px;'>
          <tr>
            <td colspan='2' style='background:{_PDF_COLORS['primary']}; color:white;
                font-weight:bold; padding:8px 10px; font-size:9pt;'>
              {_html_escape(QCoreApplication.translate("QgsFmvMetadata", "Source"))}
            </td>
          </tr>
          <tr style='background:{_PDF_COLORS['surface']};'>
            <td style='padding:7px 10px; font-weight:bold; width:32%;
                       border-bottom:1px solid {_PDF_COLORS['border']};'>
              {_html_escape(video_t)}
            </td>
            <td style='padding:7px 10px; border-bottom:1px solid {_PDF_COLORS['border']};
                       word-wrap:break-word; overflow-wrap:break-word;'>
              {_html_escape(video_name)}
            </td>
          </tr>
          <tr>
            <td style='padding:7px 10px; font-weight:bold;
                       border-bottom:1px solid {_PDF_COLORS['border']};'>
              {_html_escape(path_t)}
            </td>
            <td style='padding:7px 10px; border-bottom:1px solid {_PDF_COLORS['border']};
                       font-size:7.5pt; color:{_PDF_COLORS['text']};
                       word-wrap:break-word; overflow-wrap:break-word;'>
              {_html_escape(file_path or "—")}
            </td>
          </tr>
          <tr style='background:{_PDF_COLORS['surface']};'>
            <td style='padding:7px 10px; font-weight:bold;'>
              {_html_escape(report_id_t)}
            </td>
            <td style='padding:7px 10px; font-family:monospace;'>
              {_html_escape(report_id)}
            </td>
          </tr>
        </table>
        <table width='100%' cellpadding='0' cellspacing='0'
               style='border:1px solid {_PDF_COLORS['border']}; border-collapse:collapse;
                      table-layout:fixed;'>
          <tr>
            <td colspan='2' style='background:{_PDF_COLORS['accent_dark']}; color:white;
                font-weight:bold; padding:8px 10px; font-size:9pt;'>
              {_html_escape(QCoreApplication.translate("QgsFmvMetadata", "Timing"))}
            </td>
          </tr>
          <tr style='background:{_PDF_COLORS['surface']};'>
            <td style='padding:7px 10px; font-weight:bold; width:32%;
                       border-bottom:1px solid {_PDF_COLORS['border']};'>
              {_html_escape(time_t)}
            </td>
            <td style='padding:7px 10px; border-bottom:1px solid {_PDF_COLORS['border']};
                       font-family:monospace;'>
              {_html_escape(timestamp)}
            </td>
          </tr>
          <tr>
            <td style='padding:7px 10px; font-weight:bold;
                       border-bottom:1px solid {_PDF_COLORS['border']};'>
              {_html_escape(precision_t)}
            </td>
            <td style='padding:7px 10px; border-bottom:1px solid {_PDF_COLORS['border']};
                       font-family:monospace; word-wrap:break-word; overflow-wrap:break-word;'>
              {_html_escape(precision_ts or "—")}
            </td>
          </tr>
          <tr style='background:{_PDF_COLORS['surface']};'>
            <td style='padding:7px 10px; font-weight:bold;'>
              {_html_escape(generated_t)}
            </td>
            <td style='padding:7px 10px; font-family:monospace;'>
              {_html_escape(generated_at)}
            </td>
          </tr>
        </table>
        <br/>
        """

    def _insert_cover(
        self,
        cursor,
        video_name,
        file_path,
        timestamp,
        precision_ts,
        generated_at,
        classification,
    ):
        """Cover block with branding, document info and classification banner."""
        cursor.insertHtml(
            self._build_cover_html(
                video_name, file_path, timestamp, precision_ts, generated_at, classification
            )
        )

    # ── executive summary ───────────────────────────────────────────────

    def _insert_summary(self, cursor, data):
        """Key telemetry snapshot in a compact grid."""
        summary_t = QCoreApplication.translate(
            "QgsFmvMetadata", "Executive Summary"
        )
        cursor.insertHtml(
            f"<h2 style='color:{_PDF_COLORS['primary']}; font-size:13pt; "
            f"border-bottom:2px solid {_PDF_COLORS['accent']}; padding-bottom:4px; "
            f"margin:18px 0 10px 0;'>{_html_escape(summary_t)}</h2>"
        )

        cells = []
        for label, tokens in _SUMMARY_SPECS:
            value = _summary_field_value(data, tokens, self.player)
            cells.append(
                f"<td width='50%' style='padding:6px 8px; border:1px solid {_PDF_COLORS['border']}; "
                f"vertical-align:top; word-wrap:break-word; overflow-wrap:break-word;'>"
                f"<div style='color:{_PDF_COLORS['muted']}; font-size:7pt; "
                f"text-transform:uppercase; letter-spacing:0.4px;'>{_html_escape(label)}</div>"
                f"<div style='color:{_PDF_COLORS['text']}; font-size:9pt; "
                f"font-family:monospace; margin-top:2px;'>{_html_escape(value)}</div>"
                f"</td>"
            )

        rows_html = []
        for index in range(0, len(cells), 2):
            row_cells = cells[index : index + 2]
            while len(row_cells) < 2:
                row_cells.append(
                    f"<td width='50%' style='border:1px solid {_PDF_COLORS['border']};'></td>"
                )
            rows_html.append("<tr>" + "".join(row_cells) + "</tr>")

        cursor.insertHtml(
            "<table width='100%' cellpadding='0' cellspacing='0' "
            f"style='border-collapse:collapse; table-layout:fixed; background:white;'>"
            f"{''.join(rows_html)}</table><br/>"
        )

    # ── mini map ────────────────────────────────────────────────────────

    def _footprint_report_layers(self, group_name):
        """Collect footprint and platform layers for the PDF mini map."""
        if not group_name:
            return []

        layers = []
        for setting_key in ("footprint_lyr", "platform_lyr"):
            layer_name = settings_get("LAYERS", setting_key, "")
            if not layer_name:
                continue
            layer = qgsu.selectLayerByName(layer_name, group_name)
            if layer is None or not layer.isValid():
                continue
            if layer.featureCount() == 0:
                continue
            layers.append(layer)
        return layers

    def _footprint_extent_for_report(self, data, group_name):
        """Extent for the current-frame footprint mini map."""
        corners = _footprint_corners_for_report(data, group_name)
        extent = _extent_from_corners(corners)
        if extent is not None:
            return _padded_map_extent(extent)

        footprint_name = settings_get("LAYERS", "footprint_lyr", "Footprint")
        footprint_layer = (
            qgsu.selectLayerByName(footprint_name, group_name) if group_name else None
        )
        if footprint_layer is not None and footprint_layer.featureCount() > 0:
            for feature in footprint_layer.getFeatures():
                geometry = feature.geometry()
                if geometry is None or geometry.isEmpty():
                    continue
                bbox = geometry.boundingBox()
                if not bbox.isNull() and not bbox.isEmpty():
                    return _padded_map_extent(bbox)

        lat, lon = _sensor_position_for_report_with_group(
            data, group_name, self.player
        )
        if lat is None or lon is None:
            return None

        buffer_deg = 0.01
        return QgsRectangle(
            lon - buffer_deg,
            lat - buffer_deg,
            lon + buffer_deg,
            lat + buffer_deg,
        )

    def _render_map(self, data, width_px=420, height_px=320):
        """Render a mini map with OSM and the current frame footprint."""
        group_name = None
        if self.player is not None and hasattr(self.player, "_videoGroupName"):
            group_name = self.player._videoGroupName()

        extent = self._footprint_extent_for_report(data, group_name)
        if extent is None or extent.isNull() or extent.isEmpty():
            return None

        osm_layer = _create_osm_basemap_layer()
        fmv_layers = self._footprint_report_layers(group_name)

        render_layers = []
        if osm_layer is not None:
            render_layers.append(osm_layer)
        render_layers.extend(fmv_layers)
        if not render_layers:
            return None

        project = QgsProject.instance()
        map_settings = QgsMapSettings()
        map_settings.setLayers(render_layers)
        map_settings.setExtent(extent)
        map_settings.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
        transform_context = project.transformContext()
        if hasattr(map_settings, "setTransformContext"):
            map_settings.setTransformContext(transform_context)
        elif hasattr(map_settings, "setCrsTransformContext"):
            map_settings.setCrsTransformContext(transform_context)
        map_settings.setOutputSize(QSize(width_px, height_px))
        map_settings.setFlag(QgsMapSettings.Flag.Antialiasing, True)
        map_settings.setFlag(QgsMapSettings.Flag.UseRenderingOptimization, True)
        map_settings.setBackgroundColor(QColor(30, 34, 42))

        renderer = QgsMapRendererSequentialJob(map_settings)
        renderer.start()
        renderer.waitForFinished()

        image = None
        if hasattr(renderer, "renderedImage"):
            image = renderer.renderedImage()

        if image is None or image.isNull():
            image = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
            image.fill(QColor(30, 34, 42))
        elif image.size() != QSize(width_px, height_px):
            image = image.scaled(
                width_px,
                height_px,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        corners = _footprint_corners_for_report(data, group_name)
        if len(corners) >= 3:
            if len(corners) > 1 and corners[0] == corners[-1]:
                corners = corners[:-1]
            polygon = QPolygonF(
                [
                    QPointF(*_geo_to_pixel(lon, lat, extent, width_px, height_px))
                    for lon, lat in corners
                ]
            )
            if not polygon.isEmpty():
                fill = QColor(0, 188, 212, 70)
                outline = QColor(0, 188, 212, 230)
                painter.setBrush(fill)
                painter.setPen(QPen(outline, 3))
                painter.drawPolygon(polygon)

        lat, lon = _sensor_position_for_report_with_group(
            data, group_name, self.player
        )
        if lat is not None and lon is not None:
            px, py = _geo_to_pixel(lon, lat, extent, width_px, height_px)
            painter.setBrush(QColor(255, 255, 255, 230))
            painter.setPen(QPen(QColor(26, 35, 50), 2))
            painter.drawEllipse(int(px) - 6, int(py) - 6, 12, 12)

        painter.end()
        return image

    # ── metadata table ──────────────────────────────────────────────────

    def _insert_metadata_table(self, cursor, data, VManager):
        """Metadata table with category section headers (HTML for stable layout)."""
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(_build_grouped_metadata_html(data, VManager))
        cursor.insertBlock()

    # ── frame images ────────────────────────────────────────────────────

    def _insert_framed_image(
        self,
        cursor,
        image,
        metrics,
        max_width_pt,
        max_height_pt,
        caption=None,
        document=None,
    ):
        """Insert a centered image sized to the PDF content area."""
        if image is None or image.isNull() or metrics is None:
            return

        scaled = _scale_image_for_pdf(
            image, max_width_pt, max_height_pt, metrics["pt_to_px"]
        )
        if scaled is None or scaled.isNull():
            return

        cursor.movePosition(QTextCursor.MoveOperation.End)
        display_w = float(scaled.width()) / metrics["pt_to_px"]
        display_h = float(scaled.height()) / metrics["pt_to_px"]

        resource_name = "fmv_img_%d.png" % abs(id(scaled))
        if document is not None:
            document.addResource(
                QTextDocument.ResourceType.ImageResource,
                QUrl(resource_name),
                scaled,
            )
            image_fmt = QTextImageFormat()
            image_fmt.setName(resource_name)
            image_fmt.setWidth(display_w)
            image_fmt.setHeight(display_h)
            self._center_block(cursor)
            cursor.insertImage(image_fmt)
        else:
            self._center_block(cursor)
            cursor.insertImage(scaled)

        if caption:
            cap_fmt = QTextBlockFormat()
            cap_fmt.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            cap_fmt.setTopMargin(6)
            cap_fmt.setBottomMargin(14)
            cursor.insertBlock(cap_fmt)
            cursor.insertHtml(
                f"<span style='color:{_PDF_COLORS['muted']}; font-size:7.5pt;'>"
                f"{_html_escape(caption)}</span>"
            )
        else:
            spacer = QTextBlockFormat()
            spacer.setBottomMargin(12)
            cursor.insertBlock(spacer)

    # ── footer ──────────────────────────────────────────────────────────

    def _insert_footer(self, cursor, generated_at):
        """Document footer with disclaimer and attribution."""
        disclaimer = QCoreApplication.translate(
            "QgsFmvMetadata",
            "This report was automatically generated from MISB metadata and the "
            "current video frame. Verify classification and coordinates before "
            "operational use.",
        )
        generated_label = QCoreApplication.translate("QgsFmvMetadata", "Generated on")
        cursor.insertHtml(
            f"<br/><hr style='border:none; border-top:1px solid {_PDF_COLORS['border']};'/>"
            f"<p style='color:{_PDF_COLORS['muted']}; font-size:7pt; margin-top:8px;'>"
            f"{_html_escape(disclaimer)}<br/>"
            f"{_html_escape(generated_label)}: {_html_escape(generated_at)} · "
            f"QGISFMV</p>"
        )

    # ── layout helpers ──────────────────────────────────────────────────

    def _insert_section_header(self, cursor, text, font, color):
        """Insert a section title with accent underline."""
        cursor.movePosition(QTextCursor.MoveOperation.End)
        size_pt = font.pointSize() if font.pointSize() > 0 else 11
        cursor.insertHtml(
            f"<h2 style='color:{_html_escape(color)}; font-size:{size_pt}pt; "
            f"font-weight:bold; margin:12px 0 6px 0; padding-bottom:4px; "
            f"border-bottom:2px solid {_PDF_COLORS['accent']};'>"
            f"{_html_escape(text)}</h2>"
        )
        cursor.insertBlock()

    def _insert_footprint_map_legend(self, cursor):
        """Legend for the frame footprint mini map."""
        legend_t = QCoreApplication.translate("QgsFmvMetadata", "Legend")
        footprint_t = QCoreApplication.translate(
            "QgsFmvMetadata", "Current frame footprint"
        )
        platform_t = QCoreApplication.translate(
            "QgsFmvMetadata", "Platform position"
        )
        basemap_t = QCoreApplication.translate(
            "QgsFmvMetadata", "OpenStreetMap basemap"
        )
        cursor.insertHtml(
            f"<table width='100%' cellpadding='6' cellspacing='0' "
            f"style='margin-top:8px; border:1px solid {_PDF_COLORS['border']}; "
            f"table-layout:fixed; background:{_PDF_COLORS['surface']};'>"
            f"<tr><td style='font-size:8pt; color:{_PDF_COLORS['text']}; "
            f"word-wrap:break-word; overflow-wrap:break-word;'>"
            f"<strong>{_html_escape(legend_t)}</strong> &nbsp; "
            f"<span style='color:#00bcd4;'>■</span> {_html_escape(footprint_t)} &nbsp;|&nbsp; "
            f"<span style='color:#ffffff; border:1px solid #1a2332;'>●</span> "
            f"{_html_escape(platform_t)} &nbsp;|&nbsp; "
            f"<span style='color:#78909c;'>▦</span> {_html_escape(basemap_t)}"
            f"</td></tr></table>"
        )
        cursor.insertBlock()

    def _page_break(self, cursor):
        """Force the next block onto a new page (left-aligned for section titles)."""
        cursor.movePosition(QTextCursor.MoveOperation.End)
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(Qt.AlignmentFlag.AlignLeft)
        block_fmt.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        block_fmt.setTopMargin(0)
        block_fmt.setBottomMargin(0)
        cursor.insertBlock(block_fmt)

    def _center_block(self, cursor, page_break=QTextFormat.PageBreakFlag.PageBreak_Auto):
        cursor.movePosition(QTextCursor.MoveOperation.End)
        center_format = QTextBlockFormat()
        center_format.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        center_format.setPageBreakPolicy(page_break)
        cursor.insertBlock(center_format)
