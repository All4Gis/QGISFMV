# -*- coding: utf-8 -*-
"""Timeline bookmarks: add / clear / export / auto-mark from alerts."""

from __future__ import annotations

import csv
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from qgis.core import Qgis as QGis
from qgis.PyQt.QtCore import QCoreApplication, QObject

from QGISFMV.geo.QgsFmvSpatial import metadata_lat_lon
from QGISFMV.utils.core.QgsFmvUtils import askForFiles
from QGISFMV.utils.logging import log
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


def _event_geo(ev):
    """Return ``(lat, lon, alt)`` from a timeline event (may be None)."""
    lat = getattr(ev, "lat", None)
    lon = getattr(ev, "lon", None)
    alt = getattr(ev, "alt", None)
    try:
        lat = float(lat) if lat is not None else None
        lon = float(lon) if lon is not None else None
        alt = float(alt) if alt is not None else 0.0
    except (TypeError, ValueError):
        return None, None, 0.0
    return lat, lon, alt


def bookmarks_to_rows(events):
    """Convert timeline events to ``(index, time_sec, label, lat, lon, alt)`` rows."""
    rows = []
    for i, ev in enumerate(events, start=1):
        lat, lon, alt = _event_geo(ev)
        rows.append(
            (
                i,
                float(getattr(ev, "time_sec", 0.0)),
                str(getattr(ev, "label", "") or ""),
                lat,
                lon,
                alt,
            )
        )
    return rows


def write_bookmarks_csv(path, events):
    """Write bookmark rows to a CSV file. Returns number of rows written."""
    rows = bookmarks_to_rows(events)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["index", "time_sec", "label", "lat", "lon", "alt"])
        for row in rows:
            writer.writerow(row)
    return len(rows)


def write_bookmarks_kml(path, events, video_name="FMV"):
    """Write bookmarks as KML placemarks with frame-center coordinates when known."""
    ns = "http://www.opengis.net/kml/2.2"
    kml = ET.Element("kml", xmlns=ns)
    doc = ET.SubElement(kml, "Document")
    ET.SubElement(doc, "name").text = f"{video_name} bookmarks"
    ET.SubElement(doc, "description").text = (
        f"Exported {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    )
    folder = ET.SubElement(doc, "Folder")
    ET.SubElement(folder, "name").text = "Bookmarks"
    for idx, time_sec, label, lat, lon, alt in bookmarks_to_rows(events):
        pm = ET.SubElement(folder, "Placemark")
        ET.SubElement(pm, "name").text = f"{label or 'Bookmark'} @ {time_sec:.2f}s"
        ET.SubElement(pm, "description").text = (
            f"index={idx}; time_sec={time_sec:.3f}; label={label}; "
            f"lat={lat}; lon={lon}; alt={alt}"
        )
        pt = ET.SubElement(pm, "Point")
        if lat is not None and lon is not None:
            ET.SubElement(pt, "coordinates").text = f"{lon},{lat},{alt or 0.0}"
        else:
            ET.SubElement(pt, "coordinates").text = "0,0,0"
    tree = ET.ElementTree(kml)
    try:
        ET.indent(tree, space="  ")
    except AttributeError:
        pass
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return len(events)


class BookmarkController(QObject):
    """Owns timeline bookmark UX for a player instance."""

    def __init__(self, player):
        super().__init__(player)
        self._player = player

    def _timeline(self):
        return getattr(self._player, "timeline", None)

    def _current_geo(self):
        """Best-effort frame-center ``(lat, lon, alt)`` for the playhead."""
        player = self._player
        try:
            from QGISFMV.utils.core.QgsFmvUtils import GetFrameCenter

            lat, lon, elev = GetFrameCenter()
            if lat is not None and lon is not None:
                return float(lat), float(lon), float(elev or 0.0)
        except Exception as exc:
            log.debug("bookmark GetFrameCenter: %s", exc)
        pos = metadata_lat_lon(getattr(player, "data", None), prefer_frame_center=True)
        if pos is not None:
            lat, lon = pos
            return float(lat), float(lon), 0.0
        return None, None, None

    def addBookmark(self, time_sec=None, label=None, lat=None, lon=None, alt=None):
        """Add a bookmark at *time_sec* (default: current playhead)."""
        timeline = self._timeline()
        if timeline is None:
            return None
        if time_sec is None:
            time_sec = float(getattr(self._player, "currentInfo", 0.0) or 0.0)
        if not label:
            label = QCoreApplication.translate("QgsFmvPlayer", "Bookmark")
            label = f"{label} {timeline.eventCount() + 1}"
        if lat is None or lon is None:
            lat, lon, alt = self._current_geo()
        ev = timeline.addEvent(time_sec, label=label, lat=lat, lon=lon, alt=alt)
        story = getattr(self._player, "storyboardController", None)
        if story is not None and hasattr(story, "onBookmark"):
            try:
                story.onBookmark()
            except Exception as exc:
                log.debug("storyboard onBookmark: %s", exc)
        return ev

    def clearBookmarks(self):
        """Remove every bookmark from the timeline."""
        timeline = self._timeline()
        if timeline is not None:
            timeline.clearEvents()

    def onAlertTriggered(self, message):
        """Auto-drop a red marker when an alert fires."""
        from qgis.PyQt.QtGui import QColor

        timeline = self._timeline()
        if timeline is None:
            return
        t = float(getattr(self._player, "currentInfo", 0.0) or 0.0)
        label = message if message else "Alert"
        if len(label) > 48:
            label = label[:45] + "..."
        lat, lon, alt = self._current_geo()
        timeline.addEvent(
            t, label=label, color=QColor(255, 64, 64), lat=lat, lon=lon, alt=alt
        )

    def exportBookmarks(self, path=None):
        """Export bookmarks to CSV or KML (extension chooses format).

        If *path* is None, opens a save dialog. Returns the written path or None.
        """
        timeline = self._timeline()
        if timeline is None:
            return None
        events = (
            timeline.events()
            if hasattr(timeline, "events")
            else list(getattr(timeline, "_events", []))
        )
        if not events:
            qgsu.showUserAndLogMessage(
                "",
                QCoreApplication.translate(
                    "QgsFmvPlayer", "No timeline bookmarks to export."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return None

        if path is None:
            out, _ = askForFiles(
                self._player,
                QCoreApplication.translate("QgsFmvPlayer", "Export Bookmarks"),
                isSave=True,
                exts=["csv", "kml"],
            )
            if not out:
                return None
            path = out[0] if isinstance(out, (list, tuple)) else out

        if not path:
            return None

        video = os.path.basename(getattr(self._player, "fileName", "") or "FMV")
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".kml":
                write_bookmarks_kml(path, events, video_name=video)
            else:
                if not ext:
                    path = path + ".csv"
                write_bookmarks_csv(path, events)
        except OSError as exc:
            log.error("Bookmark export failed: %s", exc)
            qgsu.showUserAndLogMessage(
                "",
                QCoreApplication.translate(
                    "QgsFmvPlayer", "Could not export bookmarks."
                ),
                level=QGis.MessageLevel.Warning,
            )
            return None

        qgsu.showUserAndLogMessage(
            "",
            QCoreApplication.translate("QgsFmvPlayer", "Bookmarks exported."),
            level=QGis.MessageLevel.Info,
        )
        return path
