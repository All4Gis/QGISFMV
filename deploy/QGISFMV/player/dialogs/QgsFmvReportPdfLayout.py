# -*- coding: utf-8 -*-
"""PDF page/layout helpers for the FMV analysis report.

Owns the report color palette and the pure sizing helpers used to lay out
the PDF document (page metrics, image scaling), extracted from
QgsFmvReportGenerator.py.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPageLayout

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

# Soft cap so High DPI printers do not create 10k-px images that break layout.
_MAX_PDF_IMAGE_PX = 1600


def _pdf_page_metrics(printer):
    """Page and content dimensions in points for QTextDocument layout."""
    page_rect = printer.pageLayout().paintRect(QPageLayout.Unit.Point)
    page_width = float(page_rect.width())
    page_height = float(page_rect.height())
    margin = _PDF_MARGIN_PT
    content_width = max(280.0, page_width - (2.0 * margin))
    content_height = max(320.0, page_height - (2.0 * margin))
    dpi = float(printer.resolution()) or 96.0
    return {
        "page_size": page_rect.size(),
        "page_width": page_width,
        "page_height": page_height,
        "content_width": content_width,
        "content_height": content_height,
        "margin": margin,
        "dpi": dpi,
        "pt_to_px": dpi / 72.0,
    }


def _scale_image_for_pdf(image, max_width_pt, max_height_pt, pt_to_px):
    """Scale a QImage to fit PDF content box (points → device pixels)."""
    if image is None or image.isNull():
        return None
    max_w_px = max(1, min(_MAX_PDF_IMAGE_PX, int(max_width_pt * pt_to_px)))
    max_h_px = max(1, min(_MAX_PDF_IMAGE_PX, int(max_height_pt * pt_to_px)))
    return image.scaled(
        max_w_px,
        max_h_px,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
