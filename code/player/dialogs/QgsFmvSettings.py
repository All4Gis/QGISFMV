# -*- coding: utf-8 -*-
"""Unified FMV settings dialog (paths, layers, AI, magnifier, drawings, platform)."""

import os
import platform

from qgis.PyQt.QtCore import QCoreApplication, QSettings, QPoint, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QDialog,
    QFileDialog,
    QListWidgetItem,
    QMessageBox,
    QStyle,
    QStyleOptionSlider,
    QToolTip,
)
from qgis.core import Qgis as QGis

from QGISFMV.gui.ui_FmvSettings import Ui_FmvSettings
from QGISFMV.player.drawing.QgsFmvDrawToolBar import DrawToolBar as draw
from QGISFMV.utils.core.QgsFmvUtils import getNameSpace
from QGISFMV.utils.install.QgsFmvInstaller import (
    check_ffmpeg,
    check_python_deps,
    run_dependency_setup,
)
from QGISFMV.utils.layers.QgsFmvLayers import (
    RestoreDefaultLayerStyles,
    get_user_platform_icon,
    list_platform_icon_choices,
    refresh_platform_icon_layers,
    set_user_platform_icon,
)
from QGISFMV.utils.settings.QgsFmvSettings import (
    get,
    reloadRuntime,
    repair_ffmpeg_setting,
    save,
    set_value,
    settings_file,
)
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu


class FmvSettingsDialog(QDialog, Ui_FmvSettings):
    """Single settings window for the active FMV session and plugin paths."""

    _DTM_FILTER = "Raster (*.tif *.tiff *.hgt *.vrt);;All (*.*)"

    def __init__(self, parent=None, player=None):
        super().__init__(parent)
        self.setupUi(self)
        self._player = player
        self.settings = QSettings()
        self.NameSpace = getNameSpace()
        self._loading_platform_icons = False

        self.layerEdits = {
            "platform_lyr": self.ln_platformLyr,
            "footprint_lyr": self.ln_footprintLyr,
            "trajectory_lyr": self.ln_trajectoryLyr,
            "beams_lyr": self.ln_beamsLyr,
            "framecenter_lyr": self.ln_framecenterLyr,
            "frames_g": self.ln_framesG,
        }
        self._initUiExtras()
        repair_ffmpeg_setting()
        self._loadIniSettings()
        self.refreshStatus()
        draw.setValues(self)
        self._setupPlatformIcons()
        self.sl_Size.enterEvent = self.showSizeTip

    def _initUiExtras(self):
        self.cb_dnnProfile.setItemData(0, "aerial")
        self.cb_dnnProfile.setItemData(1, "coco")
        self.cb_dnnProfile.setItemData(2, "custom")
        self._dnnClassEdits = {
            "building": self.ln_dnnClass_building,
            "road": self.ln_dnnClass_road,
            "vehicle": self.ln_dnnClass_vehicle,
            "person": self.ln_dnnClass_person,
            "fire": self.ln_dnnClass_fire,
            "smoke": self.ln_dnnClass_smoke,
            "flood": self.ln_dnnClass_flood,
        }

    def _loadIniSettings(self):
        self.ln_ffmpeg.setText(get("GENERAL", "ffmpeg"))
        self.ln_dtm.setText(get("GENERAL", "dtm_file") or get("GENERAL", "DTM_file"))
        self.sb_dtmBuffer.setValue(
            int(get("GENERAL", "dtm_buffer_size", "2000") or 2000)
        )
        self.sb_minBuffer.setValue(int(get("GENERAL", "min_buffer_size", "5") or 5))
        self.ln_geocode.setText(get("GENERAL", "reverse_geocoding_url"))
        for key, edit in self.layerEdits.items():
            edit.setText(get("LAYERS", key))
        self.dsb_mosaicInterval.setValue(
            float(get("MOSAIC", "min_interval_sec", "2.0") or 2.0)
        )
        self.dsb_mosaicMove.setValue(
            float(get("MOSAIC", "min_move_meters", "30") or 30)
        )
        self.sb_mosaicFeather.setValue(int(get("MOSAIC", "feather_px", "56") or 56))
        self.sb_mosaicMaxDim.setValue(
            int(get("MOSAIC", "max_frame_dimension", "960") or 960)
        )
        self.sb_mosaicOutput.setValue(
            int(get("MOSAIC", "max_output_size", "2048") or 2048)
        )
        self.sb_mosaicRefresh.setValue(int(get("MOSAIC", "refresh_every", "3") or 3))
        self.sb_mosaicDisplay.setValue(int(get("MOSAIC", "display_every", "2") or 2))
        self.sb_mosaicKept.setValue(int(get("MOSAIC", "max_kept_frames", "80") or 80))
        enabled = str(get("DNN", "use_dnn_detection", "false")).strip().lower()
        self.chk_dnnEnabled.setChecked(enabled in ("1", "true", "yes", "on"))
        profile = (
            (get("DNN", "dnn_model_profile", "aerial") or "aerial").strip().lower()
        )
        idx_profile = self.cb_dnnProfile.findData(profile)
        if idx_profile < 0 and profile == "visdrone":
            idx_profile = self.cb_dnnProfile.findData("aerial")
        if idx_profile >= 0:
            self.cb_dnnProfile.setCurrentIndex(idx_profile)
        self.ln_onnxModel.setText(get("DNN", "onnx_model", "") or "")
        idx = self.cb_onnxType.findText(
            get("DNN", "onnx_model_type", "yolov8") or "yolov8"
        )
        if idx >= 0:
            self.cb_onnxType.setCurrentIndex(idx)
        self.sb_onnxInput.setValue(int(get("DNN", "onnx_input_size", "640") or 640))
        self.dsb_onnxConf.setValue(float(get("DNN", "onnx_confidence", "0.35") or 0.35))
        self.dsb_onnxNms.setValue(float(get("DNN", "onnx_nms", "0.45") or 0.45))
        for key, edit in self._dnnClassEdits.items():
            edit.setText(get("DNN", "dnn_{}_class_ids".format(key), "") or "")
        self._refreshDnnStatus()
        self.lbl_settingsFile.setText(
            QCoreApplication.translate(
                "FmvSettings", "Settings file: <code>{}</code>"
            ).format(settings_file())
        )

    def _setupPlatformIcons(self):
        self._loading_platform_icons = True
        current_icon = get_user_platform_icon(self.settings)

        if self.lw_platform_icons.count() == 0:
            for choice in list_platform_icon_choices():
                item = QListWidgetItem(QIcon(choice["path"]), choice["label"])
                item.setToolTip(choice["path"])
                item.setData(Qt.ItemDataRole.UserRole, choice["path"])
                self.lw_platform_icons.addItem(item)
        else:
            for index in range(self.lw_platform_icons.count()):
                item = self.lw_platform_icons.item(index)
                path = (item.toolTip() or "").strip()
                if not path.startswith(":/"):
                    data = item.data(Qt.ItemDataRole.UserRole)
                    if data:
                        path = str(data)
                item.setData(Qt.ItemDataRole.UserRole, path)
                if path:
                    item.setToolTip(os.path.basename(path))

        selected_row = 0
        if current_icon:
            current_norm = os.path.normpath(str(current_icon))
            current_base = os.path.basename(str(current_icon))
            for row in range(self.lw_platform_icons.count()):
                item = self.lw_platform_icons.item(row)
                path = item.data(Qt.ItemDataRole.UserRole) or ""
                if not path:
                    continue
                if (
                    os.path.normpath(str(path)) == current_norm
                    or os.path.basename(str(path)) == current_base
                ):
                    selected_row = row
                    break

        if self.lw_platform_icons.count() > 0:
            self.lw_platform_icons.setCurrentRow(selected_row)
            self._updatePlatformIconLabel(self.lw_platform_icons.currentItem())

        self._loading_platform_icons = False
        self.lw_platform_icons.itemSelectionChanged.connect(
            self._onPlatformIconSelectionChanged
        )

    def _updatePlatformIconLabel(self, item):
        if item is None:
            self.lbl_platform_icon_selected.setText("")
            return
        self.lbl_platform_icon_selected.setText(
            self.tr("Selected: {}").format(item.text())
        )

    def _onPlatformIconSelectionChanged(self):
        if self._loading_platform_icons:
            return
        item = self.lw_platform_icons.currentItem()
        if item is None:
            return
        icon_path = item.data(Qt.ItemDataRole.UserRole) or item.toolTip()
        if not icon_path:
            return

        set_user_platform_icon(icon_path, self.settings)
        self._updatePlatformIconLabel(item)

        group_name = None
        if self._player is not None:
            group_name = self._player._videoGroupName()
        refresh_platform_icon_layers(group_name)

        if (
            self._player is not None
            and getattr(self._player, "iface", None) is not None
        ):
            self._player.iface.mapCanvas().refresh()

    def showSizeTip(self, _):
        """Show a tooltip with the current size-slider value."""
        style = self.sl_Size.style()
        opt = QStyleOptionSlider()
        self.sl_Size.initStyleOption(opt)
        rect_handle = style.subControlRect(
            QStyle.ComplexControl.CC_Slider,
            opt,
            QStyle.SubControl.SC_SliderHandle,
            self.sl_Size,
        )
        pos_global = self.sl_Size.mapToGlobal(rect_handle.topLeft() + QPoint(5, 15))
        QToolTip.showText(pos_global, f"{self.sl_Size.value()} px", self)

    def pickFfmpegFolder(self):
        """Open a directory picker for the FFmpeg installation folder."""
        start = self.ln_ffmpeg.text().strip() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "", start)
        if path:
            self.ln_ffmpeg.setText(path)

    def pickDtmFile(self):
        """Open a file picker for the DTM (elevation model) file."""
        start = self.ln_dtm.text().strip() or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "", start, self._DTM_FILTER)
        if path:
            self.ln_dtm.setText(path)

    def pickOnnxModel(self):
        """Open a file picker for the ONNX detection model."""
        from QGISFMV.video.dnn.QgsFmvModelSetup import models_dir

        start = self.ln_onnxModel.text().strip() or models_dir()
        path, _ = QFileDialog.getOpenFileName(
            self,
            "",
            start,
            "ONNX models (*.onnx);;All (*.*)",
        )
        if path:
            self.ln_onnxModel.setText(path)

    def downloadVisdroneModel(self):
        """Download VisDrone weights and export to ONNX for aerial detection."""
        from QGISFMV.video.dnn.QgsFmvModelSetup import configure_aerial_dnn

        def _on_success(msg):
            self.chk_dnnEnabled.setChecked(True)
            self.ln_onnxModel.setText(msg)
            self.cb_onnxType.setCurrentText("yolov8")
            idx = self.cb_dnnProfile.findData("aerial")
            if idx >= 0:
                self.cb_dnnProfile.setCurrentIndex(idx)
            for key, val in (("vehicle", "3,4,5,8,9"), ("person", "0,1")):
                self._dnnClassEdits[key].setText(val)
            self.dsb_onnxConf.setValue(0.15)

        self._download_model(
            btn=self.btn_downloadVisdrone,
            status_text=QCoreApplication.translate(
                "FmvSettings",
                "Downloading VisDrone weights and exporting ONNX (may take a minute)…",
            ),
            download_fn=configure_aerial_dnn,
            success_title=QCoreApplication.translate(
                "FmvSettings", "VisDrone model ready"
            ),
            success_msg=QCoreApplication.translate(
                "FmvSettings",
                "Aerial model saved to {} — Vehicle and Person filters use VisDrone classes.",
            ),
            fail_title=QCoreApplication.translate(
                "FmvSettings", "Aerial model setup failed"
            ),
            on_success=_on_success,
            duration=8,
        )

    def downloadYoloModel(self):
        """Download YOLOv8n COCO model for general object detection."""
        from QGISFMV.video.dnn.QgsFmvModelSetup import (
            configure_default_dnn,
            default_yolov8n_path,
        )

        def _on_success(_msg):
            self.chk_dnnEnabled.setChecked(True)
            self.ln_onnxModel.setText(_msg)
            self.cb_onnxType.setCurrentText("yolov8")
            idx = self.cb_dnnProfile.findData("coco")
            if idx >= 0:
                self.cb_dnnProfile.setCurrentIndex(idx)
            for key in self._dnnClassEdits:
                self._dnnClassEdits[key].clear()

        self._download_model(
            btn=self.btn_downloadYolo,
            status_text=QCoreApplication.translate(
                "FmvSettings", "Downloading YOLOv8n…"
            ),
            download_fn=lambda: configure_default_dnn(default_yolov8n_path()),
            success_title=QCoreApplication.translate("FmvSettings", "YOLO model ready"),
            success_msg=QCoreApplication.translate(
                "FmvSettings",
                "Saved to {} — Vehicle and Person filters will use YOLO.",
            ),
            fail_title=QCoreApplication.translate("FmvSettings", "Download failed"),
            on_success=_on_success,
            duration=6,
        )

    def _download_model(
        self,
        btn,
        status_text,
        download_fn,
        success_title,
        success_msg,
        fail_title,
        on_success,
        duration=6,
    ):
        """Shared download-install-expose flow for DNN model setup buttons."""
        self.lbl_dnnStatus.setText(status_text)
        btn.setEnabled(False)
        try:
            ok, msg = download_fn()
            if ok:
                on_success(msg)
                qgsu.showUserAndLogMessage(
                    success_title,
                    success_msg.format(msg),
                    level=QGis.MessageLevel.Success,
                    duration=duration,
                )
            else:
                QMessageBox.warning(self, fail_title, msg)
        finally:
            btn.setEnabled(True)
            self._refreshDnnStatus()

    def _refreshDnnStatus(self):
        try:
            from QGISFMV.video.dnn.QgsFmvOnnxDetector import dnn_status_text

            self.lbl_dnnStatus.setText(f"<b>{dnn_status_text()}</b>")
        except Exception as exc:
            self.lbl_dnnStatus.setText(str(exc))

    def refreshStatus(self):
        """Refresh the dependency status labels (Python, FFmpeg, pymisb, DNN)."""
        py_ok, py_msg = check_python_deps()
        ff_ok, ff_msg = check_ffmpeg()

        pymisb_ok = False
        pymisb_msg = "not installed"
        try:
            import pymisb

            pymisb_ok = True
            pymisb_msg = f"v{pymisb.__version__} @ {pymisb.__file__}"
        except (ImportError, AttributeError) as exc:
            pymisb_msg = str(exc)

        lines = [
            f"<b>Python</b>: {'OK' if py_ok else 'Missing'} — {py_msg}",
            f"<b>FFmpeg</b>: {'OK' if ff_ok else 'Missing'} — {ff_msg}",
            f"<b>pymisb</b>: {'OK' if pymisb_ok else 'Missing'} — {pymisb_msg}",
            f"<b>Platform</b>: {platform.system()}",
        ]
        self.lbl_status.setText("<br>".join(lines))

    def runInstaller(self):
        """Run the interactive dependency installer and refresh status."""
        run_dependency_setup(interactive=True)
        reloadRuntime()
        self.refreshStatus()

    def restoreDefaultLayerStyles(self):
        """Reset all saved layer symbology to plugin defaults."""
        reply = QMessageBox.question(
            self,
            QCoreApplication.translate("FmvSettings", "Restore default map styles"),
            QCoreApplication.translate(
                "FmvSettings",
                "Remove saved symbology for all FMV map layers and apply plugin defaults?",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        restored = RestoreDefaultLayerStyles()
        qgsu.showUserAndLogMessage(
            QCoreApplication.translate("FmvSettings", "Map styles restored"),
            QCoreApplication.translate(
                "FmvSettings", "Default symbology applied to {} layer(s)."
            ).format(restored),
            level=QGis.MessageLevel.Success,
            duration=4,
        )

    def _saveVideoPreferences(self):
        if self.rB_Square_m.isChecked():
            self.settings.setValue(self.NameSpace + "/Options/magnifier/shape", 0)
        else:
            self.settings.setValue(self.NameSpace + "/Options/magnifier/shape", 1)

        self.settings.setValue(
            self.NameSpace + "/Options/magnifier/size", self.sl_Size.value()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/magnifier/factor", self.sb_factor.value()
        )

        self.settings.setValue(
            self.NameSpace + "/Options/drawings/polygons/width", self.poly_width.value()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/polygons/pen", self.poly_pen.color()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/polygons/brush", self.poly_brush.color()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/points/width", self.point_width.value()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/points/pen", self.point_pen.color()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/lines/width", self.lines_width.value()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/lines/pen", self.lines_pen.color()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/measures/width",
            self.measures_width.value(),
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/measures/pen", self.measures_pen.color()
        )
        self.settings.setValue(
            self.NameSpace + "/Options/drawings/measures/brush",
            self.measures_brush.color(),
        )

        item = self.lw_platform_icons.currentItem()
        if item is not None:
            icon_path = item.data(Qt.ItemDataRole.UserRole) or item.toolTip()
            if icon_path:
                set_user_platform_icon(icon_path, self.settings)

        draw.setValues(self)

    def saveSettings(self):
        """Persist all settings to settings.ini and apply runtime changes."""
        set_value("GENERAL", "ffmpeg", self.ln_ffmpeg.text().strip())
        set_value("GENERAL", "dtm_file", self.ln_dtm.text().strip())
        set_value("GENERAL", "dtm_buffer_size", str(self.sb_dtmBuffer.value()))
        set_value("GENERAL", "min_buffer_size", str(self.sb_minBuffer.value()))
        set_value("GENERAL", "reverse_geocoding_url", self.ln_geocode.text().strip())
        for key, edit in self.layerEdits.items():
            set_value("LAYERS", key, edit.text().strip())
        set_value("MOSAIC", "min_interval_sec", str(self.dsb_mosaicInterval.value()))
        set_value("MOSAIC", "min_move_meters", str(self.dsb_mosaicMove.value()))
        set_value("MOSAIC", "feather_px", str(self.sb_mosaicFeather.value()))
        set_value("MOSAIC", "max_frame_dimension", str(self.sb_mosaicMaxDim.value()))
        set_value("MOSAIC", "max_output_size", str(self.sb_mosaicOutput.value()))
        set_value("MOSAIC", "refresh_every", str(self.sb_mosaicRefresh.value()))
        set_value("MOSAIC", "display_every", str(self.sb_mosaicDisplay.value()))
        set_value("MOSAIC", "max_kept_frames", str(self.sb_mosaicKept.value()))

        from QGISFMV.video.dnn.QgsFmvModelSetup import apply_dnn_settings

        class_ids = {
            key: edit.text().strip() for key, edit in self._dnnClassEdits.items()
        }
        apply_dnn_settings(
            enabled=self.chk_dnnEnabled.isChecked(),
            model_path=self.ln_onnxModel.text().strip(),
            model_type=self.cb_onnxType.currentText(),
            input_size=self.sb_onnxInput.value(),
            confidence=self.dsb_onnxConf.value(),
            nms=self.dsb_onnxNms.value(),
            class_ids=class_ids,
            model_profile=self.cb_dnnProfile.currentData() or "aerial",
        )

        save()
        self._saveVideoPreferences()
        reloadRuntime()
        self._refreshDnnStatus()

        ff_ok, ff_msg = check_ffmpeg()
        if not ff_ok:
            QMessageBox.warning(
                self, QCoreApplication.translate("FmvSettings", "FFmpeg"), ff_msg
            )
        else:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("FmvSettings", "Settings saved"),
                QCoreApplication.translate(
                    "FmvSettings",
                    "Configuration updated and applied without restarting QGIS.",
                ),
                level=QGis.MessageLevel.Success,
                duration=4,
            )
        self.accept()


def open_fmv_settings(parent=None, player=None):
    """Show the unified FMV settings dialog."""
    dlg = FmvSettingsDialog(parent, player=player)
    dlg.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
    return dlg.exec()
