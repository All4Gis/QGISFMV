# -*- coding: utf-8 -*-
"""Export telemetry layers to KML / GPX."""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from qgis.PyQt.QtWidgets import QFileDialog
from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    Qgis as QGis,
)

from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


def _layerByName(name, group=None):
    """Find a map layer by name, optionally scoped to a layer-tree group."""
    if group is not None:
        for lyr_name, lyr in _groupLayers(group):
            if lyr_name == name:
                return lyr
    root = QgsProject.instance().layerTreeRoot()
    for lyr in root.findLayers():
        if lyr.name() == name:
            return lyr.layer()
    return None


def _findVideoGroup(group_name=None):
    """Find the FMV video layer group, falling back to the first non-root group."""
    root = QgsProject.instance().layerTreeRoot()
    if group_name:
        group = root.findGroup(group_name)
        if group is not None:
            return group
    for child in root.children():
        if hasattr(child, "findLayers") and child.name() != "FMV Georeferenced Frames":
            return child
    return None


def _groupLayers(group):
    """Yield (layer_name, QgsVectorLayer) for all vector layers in a group (recursive)."""
    if group is None:
        return
    for child in group.children():
        if hasattr(child, "layer"):
            layer = child.layer()
            if layer is not None and layer.type() == 0:  # VectorLayer
                yield child.name(), layer
        elif hasattr(child, "findLayers"):
            yield from _groupLayers(child)


def _to_4326_transform(layer):
    """Return a QgsCoordinateTransform from *layer* CRS to EPSG:4326, or None."""
    src_crs = layer.crs()
    if src_crs.authid() == "EPSG:4326":
        return None
    crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")
    return QgsCoordinateTransform(src_crs, crs_4326, QgsProject.instance())


def _extract_points_from_geom(geom):
    """Extract ordered (lon, lat) vertices from any geometry type."""
    from qgis.core import QgsWkbTypes

    wkb = geom.wkbType()
    if wkb in (QgsWkbTypes.LineString, QgsWkbTypes.LineStringZ):
        return [(pt.x(), pt.y()) for pt in geom.asPolyline()]
    if wkb in (QgsWkbTypes.MultiLineString, QgsWkbTypes.MultiLineStringZ):
        return [(pt.x(), pt.y()) for part in geom.asMultiPolyline() for pt in part]
    if wkb in (QgsWkbTypes.Point, QgsWkbTypes.PointZ):
        pt = geom.asPoint()
        return [(pt.x(), pt.y())]
    if wkb in (QgsWkbTypes.MultiPoint, QgsWkbTypes.MultiPointZ):
        return [(pt.x(), pt.y()) for pt in geom.asMultiPoint()]
    return []


def _collect_layer_points(layer):
    """Collect all (lon, lat) vertices from a layer, applying CRS transform."""
    ct = _to_4326_transform(layer)
    points = []
    for feat in layer.getFeatures():
        geom = feat.geometry()
        if geom is None or geom.isNull():
            continue
        if ct is not None:
            geom = geom.clone()
            geom.transform(ct)
        points.extend(_extract_points_from_geom(geom))
    return points


def _build_gpx_document(name, points):
    """Build a GPX XML tree with a single track segment."""
    gpx_ns = "http://www.topografix.com/GPX/1/1"
    xsi_ns = "http://www.w3.org/2001/XMLSchema-instance"
    gpx = ET.Element(
        "gpx",
        version="1.1",
        creator="QGIS FMV",
        xmlns=gpx_ns,
        **{"xmlns:xsi": xsi_ns},
    )
    metadata = ET.SubElement(gpx, "metadata")
    ET.SubElement(metadata, "name").text = name
    ET.SubElement(metadata, "time").text = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    trk = ET.SubElement(gpx, "trk")
    ET.SubElement(trk, "name").text = name
    trkseg = ET.SubElement(trk, "trkseg")
    for lon, lat in points:
        ET.SubElement(trkseg, "trkpt", lat=f"{lat:.6f}", lon=f"{lon:.6f}")
    return gpx


def _write_gpx_file(gpx, path):
    """Write a GPX ElementTree to *path*."""
    tree = ET.ElementTree(gpx)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _build_kml_geometry(geom, geom_type_str):
    """Build KML geometry XML element from a QGIS geometry.

    geom_type_str: "point", "linestring", "polygon"
    Coordinates are in EPSG:4326 (lon, lat).
    """
    if geom_type_str == "point":
        pt = geom.asPoint()
        return f"{pt.x()},{pt.y()}"
    elif geom_type_str == "linestring":
        if geom.isMultipart():
            parts = geom.asMultiPolyline()
        else:
            parts = [geom.asPolyline()]
        coords = []
        for part in parts:
            for pt in part:
                coords.append(f"{pt.x()},{pt.y()}")
        return " ".join(coords)
    elif geom_type_str == "polygon":
        if geom.isMultipart():
            rings = geom.asMultiPolygon()[0]
        else:
            rings = geom.asPolygon()
        coords = []
        for ring in rings:
            for pt in ring:
                coords.append(f"{pt.x()},{pt.y()}")
        return " ".join(coords)
    return ""


def exportGroupToKML(group_name=None):
    """Export all layers in the current video group to a single KML file.

    Writes a hand-crafted KML that Google Earth Pro / Earth Web can open
    without complaints about invalid geometry or missing schemas.
    """
    group = _findVideoGroup(group_name)
    if group is None:
        qgsu.showUserAndLogMessage(
            "",
            "No FMV layer group found. Open a video first.",
            level=QGis.MessageLevel.Warning,
        )
        return

    path, _ = QFileDialog.getSaveFileName(
        None,
        QCoreApplication.translate("QgsFmvExport", "Export to KML"),
        "",
        "KML (*.kml)",
    )
    if not path:
        return
    if not path.lower().endswith(".kml"):
        path += ".kml"

    layers = list(_groupLayers(group))
    if not layers:
        qgsu.showUserAndLogMessage(
            "",
            "No vector layers found in the FMV group.",
            level=QGis.MessageLevel.Warning,
        )
        return

    crs_4326 = QgsCoordinateReferenceSystem("EPSG:4326")

    # --- build KML XML ---
    ns = "http://www.opengis.net/kml/2.2"
    kml = ET.Element("kml", xmlns=ns)
    doc = ET.SubElement(kml, "Document")

    name_el = ET.SubElement(doc, "name")
    name_el.text = "FMV Export"

    exported = 0
    for name, layer in layers:
        src_crs = layer.crs()
        ct = None
        if src_crs.authid() != "EPSG:4326":
            ct = QgsCoordinateTransform(src_crs, crs_4326, QgsProject.instance())

        # Determine geometry type
        geom_type = layer.geometryType()  # 0=Point, 1=Line, 2=Polygon
        if geom_type == 0:
            kml_tag = "Point"
            ogr_type_str = "point"
        elif geom_type == 1:
            kml_tag = "LineString"
            ogr_type_str = "linestring"
        else:
            kml_tag = "Polygon"
            ogr_type_str = "polygon"

        folder = ET.SubElement(doc, "Folder")
        folder_name = ET.SubElement(folder, "name")
        folder_name.text = name

        feature_count = 0
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isNull() or geom.isEmpty():
                continue

            if ct is not None:
                geom = geom.clone()
                geom.transform(ct)

            placemark = ET.SubElement(folder, "Placemark")

            # Use first attribute as name if available
            pm_name = ET.SubElement(placemark, "name")
            attrs = [feat.attribute(i) for i in range(layer.fields().count())]
            pm_name.text = str(attrs[0]) if attrs and attrs[0] is not None else name

            geom_el = ET.SubElement(placemark, kml_tag)
            coords_text = _build_kml_geometry(geom, ogr_type_str)
            if not coords_text:
                continue
            coords_el = ET.SubElement(geom_el, "coordinates")
            coords_el.text = coords_text

            # Extended data with all attributes
            ext = ET.SubElement(placemark, "ExtendedData")
            for i, field in enumerate(layer.fields()):
                val = feat.attribute(i)
                if val is not None:
                    data_el = ET.SubElement(ext, "Data", name=field.name())
                    val_el = ET.SubElement(data_el, "value")
                    val_el.text = str(val)

            feature_count += 1

        exported += feature_count

    if exported == 0:
        qgsu.showUserAndLogMessage(
            "",
            "No features exported.",
            level=QGis.MessageLevel.Warning,
        )
        return

    # Write KML
    tree = ET.ElementTree(kml)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)

    qgsu.showUserAndLogMessage(
        "",
        f"Exported {exported} feature(s) to {path}",
        level=QGis.MessageLevel.Success,
        duration=3,
    )


def exportGroupToGPX(group_name=None):
    """Export platform trajectory as a GPX track."""
    from QGISFMV.utils.layers.QgsFmvLayers import Platform_lyr, Trajectory_lyr

    group = _findVideoGroup(group_name)
    layer = _layerByName(Trajectory_lyr, group)
    if layer is None or layer.featureCount() == 0:
        platform = _layerByName(Platform_lyr, group)
        if platform is not None:
            layer = platform
    if layer is None:
        qgsu.showUserAndLogMessage(
            "",
            "Platform track layer not found.",
            level=QGis.MessageLevel.Warning,
        )
        return

    path, _ = QFileDialog.getSaveFileName(
        None,
        QCoreApplication.translate("QgsFmvExport", "Export track to GPX"),
        "",
        "GPX (*.gpx)",
    )
    if not path:
        return
    if not path.lower().endswith(".gpx"):
        path += ".gpx"

    all_points = _collect_layer_points(layer)
    if not all_points:
        qgsu.showUserAndLogMessage(
            "",
            "No track points found.",
            level=QGis.MessageLevel.Warning,
        )
        return

    gpx = _build_gpx_document(layer.name(), all_points)
    _write_gpx_file(gpx, path)

    qgsu.showUserAndLogMessage(
        "",
        f"Track exported to {path} ({len(all_points)} points)",
        level=QGis.MessageLevel.Success,
        duration=3,
    )


def _collect_line_points(layer):
    """Extract ordered (lon, lat) vertices from a line/point layer."""
    return _collect_layer_points(layer)


def exportObjectTrack(parent=None, group_name=None):
    """Export the Object Track layer to GPX or GeoJSON."""
    from QGISFMV.utils.layers.QgsFmvLayers import ObjectTrack_lyr
    from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get
    from qgis.core import QgsVectorFileWriter, QgsCoordinateTransformContext

    layer_name = settings_get("LAYERS", "objecttrack_lyr", ObjectTrack_lyr)
    group = _findVideoGroup(group_name)
    layer = _layerByName(layer_name, group)
    if layer is None:
        qgsu.showUserAndLogMessage(
            "",
            QCoreApplication.translate("QgsFmvExport", "Object Track layer not found."),
            level=QGis.MessageLevel.Warning,
        )
        return

    path, selected = QFileDialog.getSaveFileName(
        parent,
        QCoreApplication.translate("QgsFmvExport", "Export Object Track"),
        "",
        "GPX (*.gpx);;GeoJSON (*.geojson *.json)",
    )
    if not path:
        return

    lower = path.lower()
    wants_geojson = "geojson" in (selected or "").lower() or lower.endswith(
        (".geojson", ".json")
    )
    if wants_geojson and not lower.endswith((".geojson", ".json")):
        path += ".geojson"
        wants_geojson = True
    elif not wants_geojson and not lower.endswith(".gpx"):
        path += ".gpx"

    if wants_geojson:
        options = QgsVectorFileWriter.SaveVectorOptions()
        options.driverName = "GeoJSON"
        options.fileEncoding = "UTF-8"
        result = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer,
            path,
            QgsCoordinateTransformContext(),
            options,
        )
        err = result[0] if isinstance(result, tuple) else result
        if err != QgsVectorFileWriter.WriterError.NoError:
            qgsu.showUserAndLogMessage(
                "",
                QCoreApplication.translate(
                    "QgsFmvExport", "Failed to export Object Track."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return
        qgsu.showUserAndLogMessage(
            "",
            QCoreApplication.translate(
                "QgsFmvExport", "Object Track exported to {path}"
            ).format(path=path),
            level=QGis.MessageLevel.Success,
            duration=3,
        )
        return

    all_points = _collect_line_points(layer)
    if not all_points:
        qgsu.showUserAndLogMessage(
            "",
            QCoreApplication.translate("QgsFmvExport", "No object track points found."),
            level=QGis.MessageLevel.Warning,
        )
        return

    gpx = _build_gpx_document(layer.name(), all_points)
    _write_gpx_file(gpx, path)

    qgsu.showUserAndLogMessage(
        "",
        QCoreApplication.translate(
            "QgsFmvExport",
            "Object Track exported to {path} ({count} points)",
        ).format(path=path, count=len(all_points)),
        level=QGis.MessageLevel.Success,
        duration=3,
    )
