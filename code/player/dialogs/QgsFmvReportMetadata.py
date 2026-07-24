# -*- coding: utf-8 -*-
"""Metadata-formatting helpers for the FMV analysis report.

Owns lookup/normalization of MISB metadata entries and the HTML table
builders used by the PDF report, extracted from QgsFmvReportGenerator.py.
"""
import html

from qgis.PyQt.QtCore import QCoreApplication

from QGISFMV.utils.logging import log
from QGISFMV.player.dialogs.QgsFmvReportPdfLayout import _PDF_COLORS


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
