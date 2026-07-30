# -*- coding: utf-8 -*-
"""Live georeferenced mosaic orchestration for QgsFmvPlayer."""

import glob
import os
import shutil

from qgis.core import Qgis as QGis
from qgis.core import QgsProject, QgsRasterLayer, QgsTask
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtWidgets import QFileDialog

from QGISFMV.utils.core.QgsFmvUtils import (
    ExtendMosaic,
    getVideoFolder,
    resetMosaicFrameCounter,
)
from QGISFMV.utils.layers.QgsFmvLayers import (
    CreateGroupByName,
    addLayerNoCrsDialog,
    frames_g,
)
from QGISFMV.utils.settings.QgsFmvSettings import get as settings_get
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class MosaicController:
    """Manage incremental mosaic capture, merge tasks, and canvas layer refresh."""

    def __init__(self, player):
        self._player = player
        self._task = None
        self._generation = 0
        self._session_folder = None
        self._session_generation = 0
        self.reset()

    def reset(self):
        """Clear mosaic state and cancel any in-flight build task."""
        self._generation += 1
        task = self._task
        self._task = None
        if task is not None:
            try:
                task.cancel()
            except Exception as exc:
                from QGISFMV.utils.logging import log

                log.debug("mosaic task cancel failed: %s", exc)

        # Drop layer reference; RemoveGroupByName / project cleanup owns removal.
        self.layer = None
        self.folder = None
        self.slots = None
        self.slot = 0
        self.frame_count = 0
        self.frame_paths = []
        self.built_count = 0
        self.active_path = None
        self.busy = False
        self.pending_rebuild = False
        self._session_folder = None
        self._session_generation = self._generation
        self.refresh_every = int(settings_get("MOSAIC", "refresh_every", "3"))
        self.display_every = int(settings_get("MOSAIC", "display_every", "2"))
        self.max_kept_frames = int(settings_get("MOSAIC", "max_kept_frames", "80"))
        self.rebuild_count = 0

    def _session_is_current(self):
        """True if this controller still owns the session that started the task."""
        return (
            self.folder is not None
            and self.folder == self._session_folder
            and self._generation == self._session_generation
        )

    def apply_runtime_settings(self):
        """Reload mosaic tuning parameters from settings.ini."""
        self.refresh_every = int(settings_get("MOSAIC", "refresh_every", "3"))
        self.display_every = int(settings_get("MOSAIC", "display_every", "2"))
        self.max_kept_frames = int(settings_get("MOSAIC", "max_kept_frames", "80"))

    @property
    def enabled(self):
        """True when mosaic creation is active."""
        return self._player.creatingMosaic

    def set_enabled(self, value):
        """Enable or disable mosaic creation and manage the mosaic folder."""
        player = self._player
        player.creatingMosaic = value

        if value:
            if getattr(player, "session", None) is not None:
                player.session.activate()
            else:
                from QGISFMV.utils.core.QgsFmvUtils import ensureGlobalState

                ensureGlobalState(player.iface)
            resetMosaicFrameCounter()
            import QGISFMV.utils.layers.QgsFmvLayers as _layers

            _layers.groupName = player._videoGroupName()
            self.reset()

            folder = getVideoFolder(player.fileName)
            qgsu.createFolderByName(folder, "mosaic")
            self.folder = os.path.join(folder, "mosaic")
            self.slots = [
                os.path.join(self.folder, "mosaic_0.tif"),
                os.path.join(self.folder, "mosaic_1.tif"),
            ]

            for pattern in ("g_*.tiff", "g_*.tif", "mosaic_*.tif"):
                for old in glob.glob(os.path.join(self.folder, pattern)):
                    try:
                        os.remove(old)
                    except OSError:
                        pass

            CreateGroupByName(visible=True)
        elif self.folder is not None:
            self.display_every = 1
            self.rebuild()

    def on_frame_added(self, frame_path):
        """Queue a new frame and trigger a rebuild when the refresh interval is reached."""
        if not frame_path:
            return
        self.frame_paths.append(frame_path)
        self.frame_count = len(self.frame_paths)
        self._prune_old_frames()
        if self.busy:
            self.pending_rebuild = True
            return
        if self.frame_count == 1 or self.frame_count % max(1, self.refresh_every) == 0:
            self.rebuild()

    def _prune_old_frames(self):
        """Drop old per-frame GeoTIFFs once they are already baked into the mosaic."""
        max_kept = max(10, int(self.max_kept_frames))
        while self.built_count > 0 and len(self.frame_paths) > max_kept:
            old = self.frame_paths.pop(0)
            self.built_count -= 1
            self.frame_count = len(self.frame_paths)
            try:
                if old and os.path.isfile(old):
                    os.remove(old)
            except OSError:
                pass

    def rebuild(self):
        """Extend the mosaic with all pending frames (non-blocking)."""
        player = self._player
        if self.busy or self.folder is None or self.slots is None:
            return

        new_frames = self.frame_paths[self.built_count :]
        if not new_frames:
            return

        # Always incremental: warp previous mosaic onto an expanded grid when
        # extent grows. Avoid O(n) full remosaic of every g_*.tiff.
        base_path = self.active_path if self.built_count > 0 else None

        self.busy = True
        self._session_folder = self.folder
        self._session_generation = self._generation
        target = self.slots[self.slot]
        task = QgsTask.fromFunction(
            "Building Mosaic Task",
            ExtendMosaic,
            out_path=target,
            new_frames=new_frames,
            base_path=base_path,
            on_finished=self._on_built,
            flags=QgsTask.Flag.CanCancel,
        )
        self._task = task
        player._add_background_task(task)

    def _on_built(self, error, result=None):
        player = self._player
        self._task = None
        # Ignore stale completions after reset/switch (closing may already be False).
        if player.closing or not self._session_is_current():
            self.busy = False
            self.pending_rebuild = False
            return

        self.busy = False
        if error is not None or not result or result.get("error"):
            self.pending_rebuild = False
            if error is not None:
                detail = str(error)
            elif result and result.get("error"):
                detail = result["error"]
            else:
                detail = "Mosaic build returned no output"
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "Mosaic build failed"),
                detail,
                level=QGis.MessageLevel.Warning,
            )
            return

        self.built_count = len(self.frame_paths)
        self.active_path = result["out"]
        self.rebuild_count += 1
        force_refresh = (
            result.get("full_rebuild")
            or self.rebuild_count == 1
            or self.rebuild_count % max(1, self.display_every) == 0
        )
        if force_refresh:
            self._refresh_layer(result["out"])
        self.slot = 1 - self.slot
        self._prune_old_frames()

        if self.enabled and self.pending_rebuild and self._session_is_current():
            self.pending_rebuild = False
            self.rebuild()
        else:
            self.pending_rebuild = False

    def _refresh_layer(self, path):
        player = self._player
        import QGISFMV.utils.layers.QgsFmvLayers as _layers

        _layers.groupName = player._videoGroupName()

        if self.layer is not None and self.layer.isValid():
            try:
                # Update in place to avoid layer-tree flicker.
                from qgis.core import QgsDataProvider

                opts = QgsDataProvider.ProviderOptions()
                self.layer.setDataSource(path, "Mosaic", "gdal", opts)
                if self.layer.isValid():
                    self.layer.setOpacity(0.88)
                    self.layer.dataProvider().reloadData()
                    self.layer.triggerRepaint()
                    try:
                        player.iface.mapCanvas().refresh()
                    except Exception as exc:
                        from QGISFMV.utils.logging import log

                        log.debug("Mosaic canvas refresh failed: %s", exc)
                    return
            except Exception as exc:
                from QGISFMV.utils.logging import log

                log.debug("Mosaic in-place layer update failed: %s", exc)
            try:
                QgsProject.instance().removeMapLayer(self.layer.id())
            except Exception as exc:
                from QGISFMV.utils.logging import log

                log.debug("Mosaic layer removal failed: %s", exc)
            self.layer = None

        layer = QgsRasterLayer(path, "Mosaic", "gdal")
        if not layer.isValid():
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "Mosaic layer invalid"),
                path,
                level=QGis.MessageLevel.Warning,
            )
            return

        layer.setOpacity(0.88)
        addLayerNoCrsDialog(layer, True, frames_g, isSubGroup=True)
        self.layer = layer

        root = QgsProject.instance().layerTreeRoot()
        video_group = player._videoGroupName()
        if video_group:
            vg = root.findGroup(video_group)
            if vg is not None:
                vg.setExpanded(True)
                sg = vg.findGroup(frames_g)
                if sg is not None:
                    sg.setItemVisibilityChecked(True)
                    sg.setExpanded(True)
        tree_layer = root.findLayer(layer.id())
        if tree_layer is not None:
            tree_layer.setItemVisibilityChecked(True)

        try:
            player.iface.layerTreeView().refreshLayerSymbology(layer.id())
        except Exception as exc:
            from QGISFMV.utils.logging import log

            log.debug("Mosaic tree symbology refresh failed: %s", exc)

        try:
            player.iface.mapCanvas().refresh()
        except Exception as exc:
            from QGISFMV.utils.logging import log

            log.debug("Mosaic canvas refresh failed: %s", exc)

    def export_mosaic(self, parent=None):
        """Save the current mosaic GeoTIFF to a user-chosen path."""
        if not self.active_path or not os.path.isfile(self.active_path):
            # Try a last rebuild if we have frames but no active mosaic yet.
            if self.frame_paths and not self.busy:
                self.display_every = 1
                self.rebuild()
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "Export Mosaic"),
                QCoreApplication.translate(
                    "QgsFmvPlayer",
                    "No mosaic available yet. Enable mosaic and play the video first.",
                ),
                level=QGis.MessageLevel.Warning,
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            parent,
            QCoreApplication.translate("QgsFmvPlayer", "Export Mosaic"),
            "",
            "GeoTIFF (*.tif *.tiff)",
        )
        if not path:
            return
        if not path.lower().endswith((".tif", ".tiff")):
            path += ".tif"
        try:
            shutil.copy2(self.active_path, path)
        except OSError as exc:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmvPlayer", "Export Mosaic"),
                str(exc),
                level=QGis.MessageLevel.Warning,
            )
            return
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate("QgsFmvPlayer", "Export Mosaic"),
            QCoreApplication.translate(
                "QgsFmvPlayer", "Mosaic exported to {path}"
            ).format(path=path),
            level=QGis.MessageLevel.Success,
            duration=3,
        )
