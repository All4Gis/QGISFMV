# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\ui_FmvMetadata.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_FmvMetadata(object):
    def setupUi(self, FmvMetadata):
        FmvMetadata.setObjectName("FmvMetadata")
        FmvMetadata.resize(345, 491)
        FmvMetadata.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.dockWidgetContents = QtWidgets.QWidget()
        self.dockWidgetContents.setMinimumSize(QtCore.QSize(300, 0))
        self.dockWidgetContents.setObjectName("dockWidgetContents")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.dockWidgetContents)
        self.verticalLayout.setObjectName("verticalLayout")
        self.menubarwidget = QtWidgets.QMenuBar(self.dockWidgetContents)
        self.menubarwidget.setStyleSheet("QMenuBar {\n"
"    background-color: transparent;\n"
"}")
        self.menubarwidget.setObjectName("menubarwidget")
        self.menuSave = QtWidgets.QMenu(self.menubarwidget)
        self.menuSave.setEnabled(False)
        self.menuSave.setObjectName("menuSave")
        self.verticalLayout.addWidget(self.menubarwidget)
        self.line = QtWidgets.QFrame(self.dockWidgetContents)
        self.line.setFrameShape(QtWidgets.QFrame.HLine)
        self.line.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.line.setObjectName("line")
        self.verticalLayout.addWidget(self.line)
        self.VManager = QtWidgets.QTableWidget(self.dockWidgetContents)
        self.VManager.setFocusPolicy(QtCore.Qt.NoFocus)
        self.VManager.setStyleSheet("QHeaderView::section\n"
"{\n"
"spacing: 10px;\n"
"background-color: rgb(88,150,50);\n"
"color: white;\n"
"border: 1px solid  rgb(147,176,35);\n"
"margin: 1px;\n"
"text-align: center;\n"
"font-family: arial;\n"
"font-weight: bold;\n"
"font-size:12px;\n"
"}\n"
"\n"
"QTableView\n"
" {\n"
" alternate-background-color: rgb(221, 233, 237); \n"
" background-color: none;\n"
"font-weight: bold;\n"
"color: rgb(56, 95, 107);\n"
" }")
        self.VManager.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.VManager.setAlternatingRowColors(True)
        self.VManager.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.VManager.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectColumns)
        self.VManager.setTextElideMode(QtCore.Qt.ElideMiddle)
        self.VManager.setCornerButtonEnabled(False)
        self.VManager.setObjectName("VManager")
        self.VManager.setColumnCount(3)
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
        self.VManager.horizontalHeader().setVisible(True)
        self.VManager.horizontalHeader().setStretchLastSection(True)
        self.VManager.verticalHeader().setVisible(False)
        self.VManager.verticalHeader().setStretchLastSection(False)
        self.verticalLayout.addWidget(self.VManager)
        FmvMetadata.setWidget(self.dockWidgetContents)
        self.actionSave_as_PDF = QtWidgets.QAction(FmvMetadata)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/pdf.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionSave_as_PDF.setIcon(icon)
        self.actionSave_as_PDF.setObjectName("actionSave_as_PDF")
        self.actionSave_as_CSV = QtWidgets.QAction(FmvMetadata)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap(":/imgFMV/images/csv.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionSave_as_CSV.setIcon(icon1)
        self.actionSave_as_CSV.setObjectName("actionSave_as_CSV")
        self.menuSave.addAction(self.actionSave_as_PDF)
        self.menuSave.addAction(self.actionSave_as_CSV)
        self.menubarwidget.addAction(self.menuSave.menuAction())

        self.retranslateUi(FmvMetadata)
        self.actionSave_as_CSV.triggered.connect(FmvMetadata.SaveACSV)
        self.actionSave_as_PDF.triggered.connect(FmvMetadata.SaveAsPDF)
        QtCore.QMetaObject.connectSlotsByName(FmvMetadata)

    def retranslateUi(self, FmvMetadata):
        _translate = QtCore.QCoreApplication.translate
        FmvMetadata.setWindowTitle(_translate("FmvMetadata", "Metadata"))
        self.menuSave.setTitle(_translate("FmvMetadata", "Save"))
        item = self.VManager.horizontalHeaderItem(0)
        item.setText(_translate("FmvMetadata", "Tag"))
        item = self.VManager.horizontalHeaderItem(1)
        item.setText(_translate("FmvMetadata", "Key"))
        item = self.VManager.horizontalHeaderItem(2)
        item.setText(_translate("FmvMetadata", "Value"))
        self.actionSave_as_PDF.setText(_translate("FmvMetadata", "Save as PDF"))
        self.actionSave_as_PDF.setShortcut(_translate("FmvMetadata", "Ctrl+Shift+P"))
        self.actionSave_as_CSV.setText(_translate("FmvMetadata", "Save as CSV"))
        self.actionSave_as_CSV.setShortcut(_translate("FmvMetadata", "Ctrl+Shift+C"))

from QGIS_FMV.gui import resources_rc
