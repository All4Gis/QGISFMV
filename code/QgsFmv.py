# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QGIS Full Motion Video (FMV)
                                 A QGIS plugin

 Analyze and manage georeferenced video data in your maps

                             -------------------
        begin                : 2018-03-13
        copyright            : (C) 2018 All4Gis.
        email                : franka1986@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 #   any later version.                                                    *
 *                                                                         *
 ***************************************************************************/
"""

import os.path

from qgis.PyQt.QtCore import (
    QSettings,
    QCoreApplication,
    QTranslator,
    QTimer,
    Qt,
)
from qgis.PyQt.QtGui import QIcon, QAction
from qgis.PyQt.QtWidgets import QDialog
from QGISFMV.about.QgsFmvAbout import FmvAbout
from QGISFMV.player.dialogs.QgsFmvSettings import open_fmv_settings
from QGISFMV.utils.install.QgsFmvInstaller import run_dependency_setup
from qgis.core import Qgis as QGis
from QGISFMV.utils.logging import log
from QGISFMV.utils.settings.QgsFmvSettings import reloadRuntime, repair_ffmpeg_setting
from QGISFMV.utils.ui.QgsUtils import QgsUtils as qgsu
from QGISFMV.utils.ui.QgsFmvResources import ICON_ABOUT, ICON_OPTIONS, ICON_PLUGIN
from qgis.core import QgsApplication


class Fmv:
    """Main Class"""

    def __init__(self, iface):
        """Constructor"""
        self.iface = iface
        repair_ffmpeg_setting()
        reloadRuntime()
        # Do not mutate global QGIS settings (parallel_rendering / OpenCL).
        # Those belong to the user/QGIS Preferences, not this plugin.

        self.plugin_dir = os.path.dirname(__file__)

        localeSetting = QSettings().value("locale/userLocale")
        if localeSetting:
            locale = localeSetting[0:2]
            localePath = os.path.join(
                self.plugin_dir, "i18n", "qgisfmv_{}.qm".format(locale)
            )
            if os.path.exists(localePath):
                self.translator = QTranslator()
                self.translator.load(localePath)

                QCoreApplication.installTranslator(self.translator)

        self._FMVManager = None
        self._depsWarned = False
        self.toolbar = None
        self._aboutToQuitHooked = False

    def initGui(self):
        """FMV Action"""
        app = QgsApplication.instance()
        if app is not None and not self._aboutToQuitHooked:
            # Must stop QThreads before QGIS destroys docks (otherwise Qt qFatal).
            app.aboutToQuit.connect(self._onAboutToQuit)
            self._aboutToQuitHooked = True

        self.actionFMV = QAction(
            QIcon(ICON_PLUGIN),
            "FMV",
            self.iface.mainWindow(),
        )
        self.actionFMV.triggered.connect(self.run)

        self.iface.registerMainWindowAction(
            self.actionFMV, qgsu.SetShortcutForPluginFMV("FMV")
        )
        self.iface.addPluginToMenu(
            QCoreApplication.translate("QgsFmv", "Full Motion Video (FMV)"),
            self.actionFMV,
        )

        self.actionConfig = QAction(
            QIcon(ICON_OPTIONS),
            QCoreApplication.translate("QgsFmv", "FMV Settings"),
            self.iface.mainWindow(),
        )
        self.actionConfig.triggered.connect(self.openSettings)
        self.iface.registerMainWindowAction(
            self.actionConfig,
            qgsu.SetShortcutForPluginFMV("FMV Settings", "Ctrl+Shift+F"),
        )
        self.iface.addPluginToMenu(
            QCoreApplication.translate("QgsFmv", "Full Motion Video (FMV)"),
            self.actionConfig,
        )

        toolbar_title = QCoreApplication.translate("QgsFmv", "Full Motion Video (FMV)")
        self.toolbar = self.iface.addToolBar(toolbar_title)
        self.toolbar.setObjectName("QGISFMVToolbar")
        self.toolbar.setWindowTitle(toolbar_title)
        self.toolbar.addAction(self.actionFMV)
        self.toolbar.addAction(self.actionConfig)

        self.actionAbout = QAction(
            QIcon(ICON_ABOUT),
            "FMV About",
            self.iface.mainWindow(),
        )
        self.actionAbout.triggered.connect(self.About)
        self.iface.registerMainWindowAction(
            self.actionAbout, qgsu.SetShortcutForPluginFMV("FMV About", "Alt+A")
        )
        self.iface.addPluginToMenu(
            QCoreApplication.translate("QgsFmv", "Full Motion Video (FMV)"),
            self.actionAbout,
        )

        try:
            from QGISFMV.video.dnn.QgsFmvModelSetup import ensure_default_dnn_assets

            ok, model_path = ensure_default_dnn_assets(quiet=True)
            if ok:
                log.info("YOLO/ONNX model ready at %s", model_path)
        except Exception as exc:
            log.debug("DNN auto-setup skipped: %s", exc)

    def _onAboutToQuit(self):
        """QGIS is exiting — tear down threads before dock widgets are destroyed."""
        self._teardownRuntime()

    def _teardownRuntime(self):
        """Stop player/manager workers and dispose readers (idempotent)."""
        manager = self._FMVManager
        self._FMVManager = None
        if manager is None:
            return
        try:
            manager.shutdown()
        except Exception as exc:
            log.debug("Fmv._teardownRuntime: manager.shutdown failed: %s", exc)
        try:
            self.iface.removeDockWidget(manager)
        except Exception as exc:
            log.debug("Fmv._teardownRuntime: removeDockWidget failed: %s", exc)

    def unload(self):
        """Unload Plugin — tear down manager/player workers before UI removal."""
        if self._aboutToQuitHooked:
            app = QgsApplication.instance()
            if app is not None:
                try:
                    app.aboutToQuit.disconnect(self._onAboutToQuit)
                except Exception as exc:
                    log.debug("aboutToQuit disconnect failed: %s", exc)
            self._aboutToQuitHooked = False

        self._teardownRuntime()

        self.iface.removePluginMenu(
            QCoreApplication.translate("QgsFmv", "Full Motion Video (FMV)"),
            self.actionFMV,
        )
        self.iface.removePluginMenu(
            QCoreApplication.translate("QgsFmv", "Full Motion Video (FMV)"),
            self.actionConfig,
        )
        self.iface.removePluginMenu(
            QCoreApplication.translate("QgsFmv", "Full Motion Video (FMV)"),
            self.actionAbout,
        )
        if self.toolbar is not None:
            self.iface.mainWindow().removeToolBar(self.toolbar)
            self.toolbar.deleteLater()
            self.toolbar = None

    def openSettings(self):
        """Open unified FMV settings dialog."""
        player = None
        if self._FMVManager is not None:
            player = getattr(self._FMVManager, "_PlayerDlg", None)
        if (
            open_fmv_settings(self.iface.mainWindow(), player=player)
            == QDialog.DialogCode.Accepted
        ):
            self.applyRuntimeSettings()

    def applyRuntimeSettings(self):
        """Re-read settings.ini into cached module globals and open FMV windows."""
        reloadRuntime()
        if self._FMVManager is not None:
            self._FMVManager.applyRuntimeSettings()

    def About(self):
        """Show About Dialog"""
        self._aboutDlg = FmvAbout()
        self._aboutDlg.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint
        )
        self._aboutDlg.exec()

    def run(self):
        """Run method — show manager immediately; check deps asynchronously."""
        if self._FMVManager is None:
            self.CreateDockWidget()
        else:
            self._FMVManager.show()
            self._FMVManager.raise_()

        if not self._depsWarned:
            QTimer.singleShot(0, self._warnMissingDependencies)

    def _warnMissingDependencies(self):
        if self._depsWarned:
            return
        self._depsWarned = True
        depsOk = run_dependency_setup(interactive=False)
        if not depsOk:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate(
                    "QgsFmv",
                    "Some FMV dependencies are missing (FFmpeg and/or pymisb).",
                ),
                QCoreApplication.translate(
                    "QgsFmv",
                    "Open FMV Settings from the toolbar to set the FFmpeg folder "
                    "and install Python packages, or run ./install_dev.sh "
                    "(macOS/Linux) / install_dev.bat (Windows).",
                ),
                level=QGis.MessageLevel.Warning,
                duration=12,
            )

    def CreateDockWidget(self):
        """Create Manager Video QDockWidget"""
        try:
            from QGISFMV.manager.QgsManager import FmvManager

            self._FMVManager = FmvManager(self.iface)
            self.iface.addDockWidget(
                Qt.DockWidgetArea.BottomDockWidgetArea, self._FMVManager
            )
            self._FMVManager.show()
            self._FMVManager.raise_()
        except Exception as exc:
            qgsu.showUserAndLogMessage(
                QCoreApplication.translate("QgsFmv", "Could not open Video Manager"),
                str(exc),
                level=QGis.MessageLevel.Critical,
                duration=12,
            )
            self._FMVManager = None
