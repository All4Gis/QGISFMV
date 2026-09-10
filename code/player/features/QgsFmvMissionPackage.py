# -*- coding: utf-8 -*-

"""Bundle bookmarks, geo index, exports, and mosaic into one mission ZIP."""

from __future__ import annotations

import csv
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from html import escape

import defusedxml.ElementTree as ET
from qgis.core import Qgis as QGis
from qgis.PyQt.QtCore import QCoreApplication
from QGIS_FMV.utils.core.QgsFmvUtils import askForFiles
from QGIS_FMV.utils.logging import log
from QGIS_FMV.utils.ui.QgsUtils import QgsUtils as qgsu


def write_geotime_csv(path, samples):
    """Write geo/time index samples to CSV. Returns row count."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["lon", "lat", "time_sec"])

        for sample in samples:
            w.writerow([sample[0], sample[1], sample[2]])

    return len(samples)


def write_detections_csv(path, detections_by_class):
    """Write last AI detections snapshot to CSV."""
    rows = 0

    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["class", "track_id", "lon", "lat", "score"])

        for cls, points in (detections_by_class or {}).items():
            for p in points:
                w.writerow(
                    [
                        cls,
                        p.get("track_id"),
                        p.get("lon"),
                        p.get("lat"),
                        p.get("score"),
                    ]
                )
                rows += 1

    return rows


def write_manifest(path, entries, video_name, notes=None):
    """Write a human-readable MANIFEST.txt."""
    lines = [
        "QGIS FMV Mission Package",
        f"Video: {video_name}",
        ("Exported: " f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"),
        "",
        "Contents:",
    ]

    for name, detail in entries:
        lines.append(f"  - {name}: {detail}")

    if notes:
        lines.append("")
        lines.append(notes)

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def build_mission_package(player, zip_path):
    """Collect available mission artifacts into zip_path.

    Returns zip path or None.
    """
    video = os.path.basename(getattr(player, "fileName", "") or "FMV")

    entries = []

    with tempfile.TemporaryDirectory(prefix="fmv_mission_") as tmp:

        # Bookmarks
        bm = getattr(player, "bookmarkController", None)
        timeline = getattr(player, "timeline", None)
        events = []

        if timeline is not None and hasattr(timeline, "events"):
            events = timeline.events()

        if bm is not None and events:
            try:
                from QGIS_FMV.player.features.QgsFmvBookmarkController import (
                    write_bookmarks_csv, write_bookmarks_kml)

                csv_p = os.path.join(tmp, "bookmarks.csv")
                kml_p = os.path.join(tmp, "bookmarks.kml")

                n = write_bookmarks_csv(csv_p, events)
                write_bookmarks_kml(
                    kml_p,
                    events,
                    video_name=video,
                )

                entries.append(("bookmarks.csv / .kml", f"{n} markers"))

            except Exception as exc:
                log.debug("mission bookmarks: %s", exc)

        # Geo/time index
        seek = getattr(player, "mapSeekController", None)

        if seek is not None and seek.index.samples:
            try:
                geo_p = os.path.join(
                    tmp,
                    "geotime_index.csv",
                )

                n = write_geotime_csv(
                    geo_p,
                    seek.index.samples,
                )

                entries.append(("geotime_index.csv", f"{n} samples"))

            except Exception as exc:
                log.debug("mission geotime: %s", exc)

        # AI detections snapshot
        try:
            from QGIS_FMV.video.filters.QgsFmvDetectionMap import \
                last_detections

            dets = last_detections()

            if dets:
                det_p = os.path.join(
                    tmp,
                    "ai_detections.csv",
                )

                n = write_detections_csv(
                    det_p,
                    dets,
                )

                entries.append(("ai_detections.csv", f"{n} points"))

        except Exception as exc:
            log.debug("mission detections: %s", exc)

        # Layer group KML (best-effort)
        try:
            from QGIS_FMV.utils.layers.QgsFmvExport import exportGroupToKML

            # Keep import available for compatibility with the existing
            # export module/API.
            _ = exportGroupToKML

            kml_out = os.path.join(
                tmp,
                "layers.kml",
            )

            group = (
                player._videoGroupName() if hasattr(player, "_videoGroupName") else None
            )

            _write_group_kml_silent(
                group,
                kml_out,
            )

            if os.path.isfile(kml_out) and os.path.getsize(kml_out) > 0:
                entries.append(("layers.kml", "telemetry / drawings"))

        except Exception as exc:
            log.debug("mission layers kml: %s", exc)

        # Mosaic GeoTIFF copy
        mosaic = getattr(player, "mosaic", None)

        if mosaic is not None:
            active = getattr(
                mosaic,
                "active_path",
                None,
            )

            if active and os.path.isfile(active):
                dest = os.path.join(
                    tmp,
                    "mosaic.tif",
                )

                try:
                    shutil.copy2(active, dest)

                    entries.append(
                        (
                            "mosaic.tif",
                            os.path.basename(active),
                        )
                    )

                except OSError as exc:
                    log.debug(
                        "mission mosaic copy: %s",
                        exc,
                    )

        # Geofence ring
        geo = getattr(
            player,
            "geofenceController",
            None,
        )

        if geo is not None and geo.rules():
            try:
                gf_p = os.path.join(
                    tmp,
                    "geofence.csv",
                )

                with open(
                    gf_p,
                    "w",
                    encoding="utf-8",
                    newline="",
                ) as fh:
                    w = csv.writer(fh)
                    w.writerow(["lon", "lat"])

                    for rule in geo.rules():
                        for lon, lat in rule.ring:
                            w.writerow([lon, lat])

                entries.append(
                    (
                        "geofence.csv",
                        f"{len(geo.rules())} AOI(s)",
                    )
                )

            except Exception as exc:
                log.debug(
                    "mission geofence: %s",
                    exc,
                )

        # Storyboard GeoTIFFs
        story_copied = 0

        try:
            story = getattr(
                player,
                "storyboardController",
                None,
            )

            paths = list(story.paths()) if story is not None else []

            if not paths and getattr(player, "fileName", None):
                from QGIS_FMV.utils.core.QgsFmvUtils import getVideoFolder

                folder = os.path.join(
                    getVideoFolder(player.fileName),
                    "storyboard",
                )

                if os.path.isdir(folder):
                    paths = [
                        os.path.join(folder, name)
                        for name in sorted(os.listdir(folder))
                        if name.lower().endswith((".tif", ".tiff"))
                    ]

            if paths:
                dest_dir = os.path.join(
                    tmp,
                    "storyboard",
                )

                os.makedirs(
                    dest_dir,
                    exist_ok=True,
                )

                for src in paths:
                    if not src or not os.path.isfile(src):
                        continue

                    shutil.copy2(
                        src,
                        os.path.join(
                            dest_dir,
                            os.path.basename(src),
                        ),
                    )

                    story_copied += 1

                if story_copied:
                    entries.append(
                        (
                            "storyboard/",
                            f"{story_copied} GeoTIFF(s)",
                        )
                    )

        except Exception as exc:
            log.debug(
                "mission storyboard: %s",
                exc,
            )

        if not entries:
            return None

        write_manifest(
            os.path.join(
                tmp,
                "MANIFEST.txt",
            ),
            entries,
            video,
            notes=("Open layers.kml / bookmarks.kml " "in QGIS or Google Earth."),
        )

        with zipfile.ZipFile(
            zip_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as zf:
            for root, _dirs, files in os.walk(tmp):
                for name in files:
                    full = os.path.join(
                        root,
                        name,
                    )

                    arc = os.path.relpath(
                        full,
                        tmp,
                    )

                    zf.write(
                        full,
                        arcname=arc,
                    )

    return zip_path


def _write_group_kml_silent(group_name, out_path):
    """Best-effort silent KML export of the video group.

    Uses defusedxml only for XML parsing/validation. The KML itself
    is constructed as text because defusedxml.ElementTree does not
    provide XML construction helpers such as Element() and SubElement().
    """
    try:
        from QGIS_FMV.utils.layers.QgsFmvExport import (_findVideoGroup,
                                                        _groupLayers)

        group = _findVideoGroup(group_name)

        if group is None:
            return

        from QGIS_FMV.utils.layers import QgsFmvExport as exp

        ns = "http://www.opengis.net/kml/2.2"

        group_title = group_name or "FMV"

        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            f'<kml xmlns="{ns}">',
            "  <Document>",
            f"    <name>{escape(str(group_title))}</name>",
        ]

        count = 0

        for lyr_name, layer in _groupLayers(group):
            lines.extend(
                [
                    "    <Folder>",
                    f"      <name>{escape(str(lyr_name))}</name>",
                ]
            )

            for feat in layer.getFeatures():
                geom = feat.geometry()

                if geom is None or geom.isEmpty():
                    continue

                try:
                    pts = exp._extract_points_from_geom(geom)
                except Exception:
                    pts = []

                if not pts:
                    continue

                placemark_name = f"{lyr_name}-{feat.id()}"

                lines.extend(
                    [
                        "      <Placemark>",
                        ("        <name>" f"{escape(placemark_name)}" "</name>"),
                    ]
                )

                if len(pts) == 1:
                    x, y = pts[0]

                    lines.extend(
                        [
                            "        <Point>",
                            ("          <coordinates>" f"{x},{y},0" "</coordinates>"),
                            "        </Point>",
                        ]
                    )

                else:
                    coordinates = " ".join(f"{x},{y},0" for x, y in pts)

                    lines.extend(
                        [
                            "        <LineString>",
                            (
                                "          <coordinates>"
                                f"{escape(coordinates)}"
                                "</coordinates>"
                            ),
                            "        </LineString>",
                        ]
                    )

                lines.extend(
                    [
                        "      </Placemark>",
                    ]
                )

                count += 1

            lines.extend(
                [
                    "    </Folder>",
                ]
            )

        if count == 0:
            return

        lines.extend(
            [
                "  </Document>",
                "</kml>",
                "",
            ]
        )

        kml_text = "\n".join(lines)

        # Validate the generated KML using defusedxml.
        ET.fromstring(kml_text)

        with open(
            out_path,
            "w",
            encoding="utf-8",
            newline="",
        ) as fh:
            fh.write(kml_text)

    except Exception as exc:
        log.debug(
            "silent group kml: %s",
            exc,
        )


class MissionPackageController:
    """UI façade for mission ZIP export."""

    def __init__(self, player):
        self.player = player

    def export(self, path=None):
        if path is None:
            out, _ = askForFiles(
                self.player,
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Export Mission Package",
                ),
                isSave=True,
                exts=["zip"],
            )

            if not out:
                return None

            path = out[0] if isinstance(out, (list, tuple)) else out

        if not path:
            return None

        if not str(path).lower().endswith(".zip"):
            path = str(path) + ".zip"

        try:
            result = build_mission_package(
                self.player,
                path,
            )

        except Exception as exc:
            log.error(
                "Mission package failed: %s",
                exc,
            )

            qgsu.showUserAndLogMessage(
                "",
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Could not build mission package.",
                ),
                level=QGis.MessageLevel.Warning,
            )

            return None

        if result is None:
            qgsu.showUserAndLogMessage(
                "",
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "Nothing to package yet " "(play with telemetry / add bookmarks).",
                ),
                level=QGis.MessageLevel.Warning,
            )

            return None

        qgsu.showUserAndLogMessage(
            "",
            QCoreApplication.translate(
                "QgsFmvPlayer",
                "Mission package exported.",
            ),
            level=QGis.MessageLevel.Info,
        )

        return result
