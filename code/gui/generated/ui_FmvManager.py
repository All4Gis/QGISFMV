# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\ui_FmvManager.ui'
#
# Created by: PyQt5 UI code generator 5.9
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets
from QGIS_FMV.gui.generated import resources_rc


class Ui_ManagerWindow(object):
    def setupUi(self, ManagerWindow):
        ManagerWindow.setObjectName("ManagerWindow")
        ManagerWindow.resize(678, 180)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/manager.png"),
                       QtGui.QIcon.Normal, QtGui.QIcon.Off)
        ManagerWindow.setWindowIcon(icon)
        ManagerWindow.setLocale(QtCore.QLocale(
            QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        ManagerWindow.setFeatures(QtWidgets.QDockWidget.AllDockWidgetFeatures)
        self.dockWidgetContents = QtWidgets.QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.dockWidgetContents)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.menubarwidget = QtWidgets.QMenuBar(self.dockWidgetContents)
        self.menubarwidget.setStyleSheet("QMenuBar {\n"
                                         "    background-color: transparent;\n"
                                         "}")
        self.menubarwidget.setObjectName("menubarwidget")
        self.menuFile = QtWidgets.QMenu(self.menubarwidget)
        self.menuFile.setObjectName("menuFile")
        self.verticalLayout.addWidget(self.menubarwidget)
        self.VManager = QtWidgets.QTableWidget(self.dockWidgetContents)
        font = QtGui.QFont()
        font.setFamily("Arial")
        font.setPointSize(9)
        font.setBold(True)
        font.setWeight(75)
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        self.VManager.setFont(font)
        self.VManager.viewport().setProperty(
            "cursor", QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.VManager.setFocusPolicy(QtCore.Qt.NoFocus)
        self.VManager.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.VManager.setStyleSheet("QHeaderView::section\n"
                                    "{\n"
                                    "spacing: 10px;\n"
                                    "background-color: rgb(88,150,50);\n"
                                    "color: white;\n"
                                    "border: 1px solid  rgb(147,176,35);\n"
                                    "margin: 0px;\n"
                                    "text-align: center;\n"
                                    "font-family: arial;\n"
                                    "font-size:12px;\n"
                                    "}\n"
                                    "\n"
                                    "QTableView\n"
                                    " {\n"
                                    " alternate-background-color: rgb(221, 233, 237); \n"
                                    " background-color: none;\n"
                                    "font-weight: bold;\n"
                                    "color: rgb(56, 95, 107);\n"
                                    " }\n"
                                    "")
        self.VManager.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers)
        self.VManager.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)
        self.VManager.setAlternatingRowColors(True)
        self.VManager.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection)
        self.VManager.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self.VManager.setGridStyle(QtCore.Qt.SolidLine)
        self.VManager.setObjectName("VManager")
        self.VManager.setColumnCount(4)
        self.VManager.setRowCount(0)
        item = QtWidgets.QTableWidgetItem()
        self.VManager.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.VManager.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.VManager.setHorizontalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.VManager.setHorizontalHeaderItem(3, item)
        self.VManager.horizontalHeader().setStretchLastSection(True)
        self.VManager.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.VManager)
        ManagerWindow.setWidget(self.dockWidgetContents)
        self.actionOpen_Video = QtWidgets.QAction(ManagerWindow)
        self.actionOpen_Video.setObjectName("actionOpen_Video")
        self.actionMetadata = QtWidgets.QAction(ManagerWindow)
        self.actionMetadata.setObjectName("actionMetadata")
        self.actionConverter_Video = QtWidgets.QAction(ManagerWindow)
        self.actionConverter_Video.setObjectName("actionConverter_Video")
        self.actionExtract = QtWidgets.QAction(ManagerWindow)
        self.actionExtract.setObjectName("actionExtract")
        self.actionSave_Video_Info_To_Json = QtWidgets.QAction(ManagerWindow)
        self.actionSave_Video_Info_To_Json.setObjectName(
            "actionSave_Video_Info_To_Json")
        self.actionShow_Video_Info = QtWidgets.QAction(ManagerWindow)
        self.actionShow_Video_Info.setObjectName("actionShow_Video_Info")
        self.menuFile.addAction(self.actionOpen_Video)
        self.menubarwidget.addAction(self.menuFile.menuAction())

        self.retranslateUi(ManagerWindow)
        self.actionOpen_Video.triggered.connect(
            ManagerWindow.openVideoFileDialog)
        self.VManager.doubleClicked['QModelIndex'].connect(
            ManagerWindow.PlayVideoFromManager)
        QtCore.QMetaObject.connectSlotsByName(ManagerWindow)

    def retranslateUi(self, ManagerWindow):
        _translate = QtCore.QCoreApplication.translate
        ManagerWindow.setWindowTitle(
            _translate("ManagerWindow", "Video Manager"))
        self.menuFile.setTitle(_translate("ManagerWindow", "File"))
        item = self.VManager.horizontalHeaderItem(0)
        item.setText(_translate("ManagerWindow", "Id"))
        item = self.VManager.horizontalHeaderItem(1)
        item.setText(_translate("ManagerWindow", "Name"))
        item = self.VManager.horizontalHeaderItem(2)
        item.setText(_translate("ManagerWindow", "Status"))
        item = self.VManager.horizontalHeaderItem(3)
        item.setText(_translate("ManagerWindow", "Source"))
        self.actionOpen_Video.setText(
            _translate("ManagerWindow", "Open Video"))
        self.actionMetadata.setText(_translate("ManagerWindow", "Metadata"))
        self.actionConverter_Video.setText(
            _translate("ManagerWindow", "Converter Video"))
        self.actionExtract.setText(_translate(
            "ManagerWindow", "Extract All Frames"))
        self.actionSave_Video_Info_To_Json.setText(
            _translate("ManagerWindow", "Save Video Info To Json"))
        self.actionShow_Video_Info.setText(
            _translate("ManagerWindow", "Show Video Info"))
