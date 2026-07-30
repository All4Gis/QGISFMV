# -*- coding: utf-8 -*-
"""PDF report generation, extracted from QgsFmvMetadata.py.

Owns the ReportGenerator class used to render the multi-section FMV
analysis PDF report. Metadata-formatting, geo/map, and PDF layout helpers
live in QgsFmvReportMetadata.py, QgsFmvReportGeo.py, and
QgsFmvReportPdfLayout.py respectively (imported below, and some re-exported
for backward compatibility with other call sites).
"""

import os
from datetime import datetime

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsMapRendererSequentialJob,
    QgsMapSettings,
    QgsProject,
    QgsRectangle,
)
from qgis.PyQt.QtCore import QCoreApplication, QPointF, QSize, Qt, QUrl
from qgis.PyQt.QtGui import (
    QColor,
    QFont,
    QImage,
    QPageSize,
    QPainter,
    QPen,
    QPolygonF,
    QTextBlockFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextImageFormat,
    QTextLength,
    QTextTableFormat,
)
from qgis.PyQt.QtPrintSupport import QPrinter

from QGISFMV.player.dialogs.QgsFmvReportGeo import (
    _create_osm_basemap_layer,
    _extent_from_corners,
    _footprint_corners_for_report,
    _geo_to_pixel,
    _padded_map_extent,
    _sensor_position_for_report_with_group,
)
from QGISFMV.player.dialogs.QgsFmvReportMetadata import (
    _SUMMARY_SPECS,
    _build_grouped_metadata_html,
    _classification_level,
    _html_escape,
    _is_classified,
    _metadata_dict_from_table,
    _summary_field_value,
)
from QGISFMV.player.dialogs.QgsFmvReportPdfLayout import (
    _PDF_COLORS,
    _pdf_page_metrics,
    _scale_image_for_pdf,
)
from QGISFMV.utils.logging import log
from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get
from QGISFMV.utils.ui.QgsFmvResources import ICON_HEADER_LOGO
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu

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

        # ScreenResolution + fixed 96 DPI keeps QTextDocument page size and
        # image point sizes in the same unit space (HighResolution caused
        # orphaned section titles / images on the next page).
        printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
        printer.setResolution(96)
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
        # Title + note + caption budget; image must fit the rest of the page.
        _section_chrome_pt = 120.0
        frame_max_height_pt = max(
            180.0,
            min(
                metrics["content_height"] * 0.62,
                metrics["content_height"] - _section_chrome_pt,
            ),
        )
        map_max_height_pt = max(
            160.0,
            min(280.0, metrics["content_height"] - _section_chrome_pt - 60.0),
        )

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
            self._insert_image_section(
                cursor,
                title=QCoreApplication.translate(
                    "QgsFmvMetadata", "Frame Footprint Map"
                ),
                note=None,
                image=map_img,
                metrics=metrics,
                max_width_pt=content_width,
                max_height_pt=map_max_height_pt,
                document=document,
                font_section=font_section,
                html_before=self._footprint_map_intro_html(data),
            )
            self._insert_footprint_map_legend(cursor)

        self._page_break(cursor)
        self._insert_metadata_section(cursor, data, VManager, font_section)

        # Annotated frame — own page; title + image kept together by sizing
        if frame is not None and not frame.isNull():
            frame_note = QCoreApplication.translate(
                "QgsFmvMetadata",
                "Current video frame with user drawings burned in. Timestamp: {0}",
            ).format(timestamp)
            self._insert_image_section(
                cursor,
                title=QCoreApplication.translate(
                    "QgsFmvMetadata", "Video Frame with Drawings"
                ),
                note=frame_note,
                image=frame,
                metrics=metrics,
                max_width_pt=content_width,
                max_height_pt=frame_max_height_pt,
                document=document,
                font_section=font_section,
                caption=timestamp,
            )

        # Clean frame — separate page
        if frame_clean is not None and not frame_clean.isNull():
            clean_note = QCoreApplication.translate(
                "QgsFmvMetadata",
                "Same video frame without drawings or overlays. Timestamp: {0}",
            ).format(timestamp)
            self._insert_image_section(
                cursor,
                title=QCoreApplication.translate(
                    "QgsFmvMetadata", "Video Frame without Annotations"
                ),
                note=clean_note,
                image=frame_clean,
                metrics=metrics,
                max_width_pt=content_width,
                max_height_pt=frame_max_height_pt,
                document=document,
                font_section=font_section,
                caption=timestamp,
            )

        # Footer on its own page so it never pushes the last frame image away
        # from its section title.
        self._page_break(cursor)
        self._insert_footer(cursor, generated_at)

        document.print(printer)

        if task is not None and task.isCanceled():
            return None
        return {
            "task": task.description() if task is not None else "Save PDF Report Task"
        }

    def _footprint_map_intro_html(self, data):
        """Caption + sensor coords HTML for the footprint mini-map section."""
        caption_t = QCoreApplication.translate(
            "QgsFmvMetadata",
            "Mini map with OpenStreetMap basemap and the current frame footprint",
        )
        group_name = None
        if self.player is not None and hasattr(self.player, "_videoGroupName"):
            group_name = self.player._videoGroupName()
        lat, lon = _sensor_position_for_report_with_group(data, group_name, self.player)
        lat_text = f"{lat:.6f}" if lat is not None else "—"
        lon_text = f"{lon:.6f}" if lon is not None else "—"
        coord_t = QCoreApplication.translate("QgsFmvMetadata", "Sensor position")
        return (
            f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt; margin:0 0 8px 0;'>"
            f"{_html_escape(caption_t)}<br>"
            f"<strong>{_html_escape(coord_t)}:</strong> "
            f"{_html_escape(lat_text)}, {_html_escape(lon_text)}</p>"
        )

    def _insert_image_section(
        self,
        cursor,
        title,
        note,
        image,
        metrics,
        max_width_pt,
        max_height_pt,
        document,
        font_section,
        caption=None,
        html_before=None,
    ):
        """Insert title + note + image as one table so they stay on the same page."""
        if image is None or image.isNull() or metrics is None:
            return

        safe_h = max(
            160.0,
            min(max_height_pt, metrics["content_height"] - 120.0),
        )
        scaled = _scale_image_for_pdf(image, max_width_pt, safe_h, metrics["pt_to_px"])
        if scaled is None or scaled.isNull():
            return

        display_w = float(scaled.width()) / metrics["pt_to_px"]
        display_h = float(scaled.height()) / metrics["pt_to_px"]
        resource_name = "fmv_img_%d.png" % abs(id(scaled))
        document.addResource(
            QTextDocument.ResourceType.ImageResource,
            QUrl(resource_name),
            scaled,
        )

        cursor.movePosition(QTextCursor.MoveOperation.End)

        table_fmt = QTextTableFormat()
        table_fmt.setBorder(0)
        table_fmt.setCellPadding(2)
        table_fmt.setCellSpacing(0)
        table_fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        table_fmt.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        table_fmt.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)

        has_intro = bool(html_before or note)
        row_count = 2 + (1 if has_intro else 0) + (1 if caption else 0)
        table = cursor.insertTable(row_count, 1, table_fmt)

        size_pt = font_section.pointSize() if font_section.pointSize() > 0 else 11
        title_html = (
            f"<h2 style='color:{_PDF_COLORS['accent_dark']}; font-size:{size_pt}pt; "
            f"font-weight:bold; margin:0 0 6px 0; padding-bottom:4px; "
            f"border-bottom:2px solid {_PDF_COLORS['accent']};'>"
            f"{_html_escape(title)}</h2>"
        )
        table.cellAt(0, 0).firstCursorPosition().insertHtml(title_html)

        row = 1
        if has_intro:
            intro_parts = []
            if html_before:
                intro_parts.append(html_before)
            if note:
                intro_parts.append(
                    f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt; "
                    f"margin:4px 0 8px 0;'>{_html_escape(note)}</p>"
                )
            table.cellAt(row, 0).firstCursorPosition().insertHtml("".join(intro_parts))
            row += 1

        img_cursor = table.cellAt(row, 0).firstCursorPosition()
        block = QTextBlockFormat()
        block.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        img_cursor.setBlockFormat(block)
        image_fmt = QTextImageFormat()
        image_fmt.setName(resource_name)
        image_fmt.setWidth(display_w)
        image_fmt.setHeight(display_h)
        img_cursor.insertImage(image_fmt)
        row += 1

        if caption:
            cap_html = (
                f"<p style='color:{_PDF_COLORS['muted']}; font-size:7.5pt; "
                f"text-align:center; margin:6px 0 0 0;'>"
                f"{_html_escape(caption)}</p>"
            )
            table.cellAt(row, 0).firstCursorPosition().insertHtml(cap_html)

        cursor.movePosition(QTextCursor.MoveOperation.End)

    def _insert_metadata_section(self, cursor, data, VManager, font_section):
        """Insert metadata title + table in one HTML block (same page start)."""
        cursor.movePosition(QTextCursor.MoveOperation.End)
        size_pt = font_section.pointSize() if font_section.pointSize() > 0 else 11
        title = QCoreApplication.translate("QgsFmvMetadata", "Metadata Details")
        subtitle = QCoreApplication.translate(
            "QgsFmvMetadata",
            "MISB metadata fields grouped by category for the current frame.",
        )
        html = (
            f"<h2 style='color:{_PDF_COLORS['accent_dark']}; font-size:{size_pt}pt; "
            f"font-weight:bold; margin:0 0 6px 0; padding-bottom:4px; "
            f"border-bottom:2px solid {_PDF_COLORS['accent']};'>"
            f"{_html_escape(title)}</h2>"
            f"<p style='color:{_PDF_COLORS['muted']}; font-size:8pt; margin:0 0 10px 0;'>"
            f"{_html_escape(subtitle)}</p>"
            f"{_build_grouped_metadata_html(data, VManager)}"
        )
        cursor.insertHtml(html)
        cursor.insertBlock()

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
                video_name,
                file_path,
                timestamp,
                precision_ts,
                generated_at,
                classification,
            )
        )

    # ── executive summary ───────────────────────────────────────────────

    def _insert_summary(self, cursor, data):
        """Key telemetry snapshot in a compact grid."""
        summary_t = QCoreApplication.translate("QgsFmvMetadata", "Executive Summary")
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

        lat, lon = _sensor_position_for_report_with_group(data, group_name, self.player)
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
        """Render a mini map with OSM and the current frame footprint.

        Always returns an image when an extent can be resolved — even if the
        OSM basemap or FMV layers are unavailable — so the PDF section is not
        silently omitted.
        """
        group_name = None
        if self.player is not None and hasattr(self.player, "_videoGroupName"):
            group_name = self.player._videoGroupName()

        extent = self._footprint_extent_for_report(data, group_name)
        if extent is None or extent.isNull() or extent.isEmpty():
            log.warning("PDF footprint map skipped: no extent (corners/sensor)")
            return None

        osm_layer = None
        try:
            osm_layer = _create_osm_basemap_layer()
        except Exception as exc:
            log.debug("OSM basemap for PDF report unavailable: %s", exc)

        fmv_layers = self._footprint_report_layers(group_name)

        render_layers = []
        if osm_layer is not None and osm_layer.isValid():
            render_layers.append(osm_layer)
        render_layers.extend(fmv_layers)

        image = QImage(width_px, height_px, QImage.Format.Format_ARGB32)
        image.fill(QColor(30, 34, 42))

        if render_layers:
            try:
                project = QgsProject.instance()
                map_settings = QgsMapSettings()
                map_settings.setLayers(render_layers)
                map_settings.setExtent(extent)
                map_settings.setDestinationCrs(
                    QgsCoordinateReferenceSystem("EPSG:4326")
                )
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

                rendered = None
                if hasattr(renderer, "renderedImage"):
                    rendered = renderer.renderedImage()
                if rendered is not None and not rendered.isNull():
                    if rendered.size() != QSize(width_px, height_px):
                        rendered = rendered.scaled(
                            width_px,
                            height_px,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    image = rendered
            except Exception as exc:
                log.warning("PDF map layer render failed, using overlay only: %s", exc)

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

        lat, lon = _sensor_position_for_report_with_group(data, group_name, self.player)
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
        platform_t = QCoreApplication.translate("QgsFmvMetadata", "Platform position")
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

    def _center_block(
        self, cursor, page_break=QTextFormat.PageBreakFlag.PageBreak_Auto
    ):
        cursor.movePosition(QTextCursor.MoveOperation.End)
        center_format = QTextBlockFormat()
        center_format.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        center_format.setPageBreakPolicy(page_break)
        cursor.insertBlock(center_format)
