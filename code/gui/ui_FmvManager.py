# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\ui_FmvManager.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_ManagerWindow(object):
    def setupUi(self, ManagerWindow):
        ManagerWindow.setObjectName("ManagerWindow")
        ManagerWindow.resize(761, 281)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/manager.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        ManagerWindow.setWindowIcon(icon)
        ManagerWindow.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        ManagerWindow.setFeatures(QtWidgets.QDockWidget.AllDockWidgetFeatures)
        self.dockWidgetContents = QtWidgets.QWidget()
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.dockWidgetContents)
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
        self.VManager.viewport().setProperty("cursor", QtGui.QCursor(QtCore.Qt.PointingHandCursor))
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
        self.VManager.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.VManager.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)
        self.VManager.setAlternatingRowColors(True)
        self.VManager.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.VManager.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.VManager.setGridStyle(QtCore.Qt.SolidLine)
        self.VManager.setObjectName("VManager")
        self.VManager.setColumnCount(7)
        self.VManager.setRowCount(0)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        item.setFont(font)
        self.VManager.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        item.setFont(font)
        self.VManager.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        item.setFont(font)
        self.VManager.setHorizontalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        item.setFont(font)
        self.VManager.setHorizontalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        item.setFont(font)
        self.VManager.setHorizontalHeaderItem(4, item)
        item = QtWidgets.QTableWidgetItem()
        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.PreferAntialias)
        item.setFont(font)
        self.VManager.setHorizontalHeaderItem(5, item)
        item = QtWidgets.QTableWidgetItem()
        self.VManager.setHorizontalHeaderItem(6, item)
        self.VManager.horizontalHeader().setStretchLastSection(True)
        self.VManager.verticalHeader().setVisible(False)
        self.verticalLayout.addWidget(self.VManager)
        ManagerWindow.setWidget(self.dockWidgetContents)
        self.actionOpen_Stream = QtWidgets.QAction(ManagerWindow)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/imgFMV/images/stream.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionOpen_Stream.setIcon(icon1)
        self.actionOpen_Stream.setObjectName("actionOpen_Stream")
        self.actionOpen_MPEG2_File = QtWidgets.QAction(ManagerWindow)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap(":/imgFMV/images/misb-file.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionOpen_MPEG2_File.setIcon(icon2)
        self.actionOpen_MPEG2_File.setObjectName("actionOpen_MPEG2_File")
        self.menuFile.addAction(self.actionOpen_Stream)
        self.menuFile.addAction(self.actionOpen_MPEG2_File)
        self.menubarwidget.addAction(self.menuFile.menuAction())

        self.retranslateUi(ManagerWindow)
        self.actionOpen_Stream.triggered.connect(ManagerWindow.openStreamDialog)
        self.VManager.doubleClicked['QModelIndex'].connect(ManagerWindow.PlayVideoFromManager)
        self.actionOpen_MPEG2_File.triggered.connect(ManagerWindow.openVideoFileDialog)
        QtCore.QMetaObject.connectSlotsByName(ManagerWindow)

    def retranslateUi(self, ManagerWindow):
        _translate = QtCore.QCoreApplication.translate
        ManagerWindow.setWindowTitle(_translate("ManagerWindow", "Video Manager"))
        self.menuFile.setTitle(_translate("ManagerWindow", "File"))
        item = self.VManager.horizontalHeaderItem(0)
        item.setText(_translate("ManagerWindow", "Id"))
        item = self.VManager.horizontalHeaderItem(1)
        item.setText(_translate("ManagerWindow", "Name"))
        item = self.VManager.horizontalHeaderItem(2)
        item.setText(_translate("ManagerWindow", "Status"))
        item = self.VManager.horizontalHeaderItem(3)
        item.setText(_translate("ManagerWindow", "Source"))
        item = self.VManager.horizontalHeaderItem(4)
        item.setText(_translate("ManagerWindow", "Start Location"))
        item = self.VManager.horizontalHeaderItem(5)
        item.setText(_translate("ManagerWindow", "Progress"))
        self.actionOpen_Stream.setText(_translate("ManagerWindow", "Open Stream"))
        self.actionOpen_MPEG2_File.setText(_translate("ManagerWindow", "Open Video File"))

from QGIS_FMV.gui import resources_rc
