# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/ui_FmvManager.ui'
#
# Created by: PyQt5 UI code generator 5.10.1
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_ManagerWindow(object):
    def setupUi(self, ManagerWindow):
        ManagerWindow.setObjectName("ManagerWindow")
        ManagerWindow.resize(600, 353)
        self.gridLayout = QtWidgets.QGridLayout(ManagerWindow)
        self.gridLayout.setMargin(0);
        self.gridLayout.setObjectName("gridLayout")
        self.mOpenMPEGButton = QtWidgets.QToolButton(ManagerWindow)
        self.mOpenMPEGButton.setText("")
        self.mOpenMPEGButton.setObjectName("mOpenMPEGButton")
        self.gridLayout.addWidget(self.mOpenMPEGButton, 0, 0, 1, 1)

        self.versionLabel = QtWidgets.QLabel(ManagerWindow)
        self.versionLabel.setText("v 1.12")
        self.versionLabel.setStyleSheet("QLabel { color : grey; }");
        self.gridLayout.addWidget(self.versionLabel, 0, 1, 1, 1)
        
        #deactivate for 1.0 Version
        #self.mActionCreateMISBButton = QtWidgets.QToolButton(ManagerWindow)
        #self.mActionCreateMISBButton.setText("")
        #self.mActionCreateMISBButton.setObjectName("mActionCreateMISBButton")
        #self.gridLayout.addWidget(self.mActionCreateMISBButton, 0, 1, 1, 1)
        #self.mOpenStreamButton = QtWidgets.QToolButton(ManagerWindow)
        #self.mOpenStreamButton.setText("")
        #self.mOpenStreamButton.setObjectName("mOpenStreamButton")
        #self.gridLayout.addWidget(self.mOpenStreamButton, 0, 2, 1, 1)
        
        spacerItem = QtWidgets.QSpacerItem(600, 10, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.gridLayout.addItem(spacerItem, 0, 1, 1, 1)
        self.mCloseButton = QtWidgets.QToolButton(ManagerWindow)
        self.mCloseButton.setText("")
        icon4 = QtGui.QIcon()
        icon4.addPixmap(QtGui.QPixmap(":/imgFMV/images/close.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.mCloseButton.setIcon(icon4)
        self.mCloseButton.setObjectName("mCloseButton")
        self.gridLayout.addWidget(self.mCloseButton, 0, 2, 1, 1)
        self.VManager = QtWidgets.QTableWidget(ManagerWindow)
        self.VManager.setMinimumSize(QtCore.QSize(0, 150))
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
        self.VManager.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.VManager.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.VManager.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)                                                                               
        self.VManager.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.VManager.setDragDropMode(QtWidgets.QAbstractItemView.NoDragDrop)
        self.VManager.setAlternatingRowColors(True)
        self.VManager.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.VManager.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.VManager.setGridStyle(QtCore.Qt.SolidLine)
        self.VManager.setObjectName("VManager")
        self.VManager.setColumnCount(6)
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
        self.VManager.horizontalHeader().setStretchLastSection(True)
        self.VManager.verticalHeader().setVisible(False)
        self.gridLayout.addWidget(self.VManager, 1, 0, 1, 4)
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
        self.actionCreate_MISB_File = QtWidgets.QAction(ManagerWindow)
        icon3 = QtGui.QIcon()
        icon3.addPixmap(QtGui.QPixmap(":/imgFMV/images/multiplexer.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.actionCreate_MISB_File.setIcon(icon3)
        self.actionCreate_MISB_File.setObjectName("actionCreate_MISB_File")
        self.retranslateUi(ManagerWindow)
        self.actionOpen_Stream.triggered.connect(ManagerWindow.openStreamDialog)
        self.VManager.doubleClicked['QModelIndex'].connect(ManagerWindow.PlayVideoFromManager)
        self.actionOpen_MPEG2_File.triggered.connect(ManagerWindow.openVideoFileDialog)
        self.actionCreate_MISB_File.triggered.connect(ManagerWindow.openMuiltiplexorDialog)
        #self.CloseButton.triggered.connect(ManagerWindow.CloseFMV)
        self.mOpenMPEGButton.setDefaultAction( self.actionOpen_MPEG2_File )
        
        #Deactivate for 1.0 Version
        #self.mActionCreateMISBButton.setDefaultAction( self.actionCreate_MISB_File )
        #self.mOpenStreamButton.setDefaultAction( self.actionOpen_Stream )
        QtCore.QMetaObject.connectSlotsByName(ManagerWindow)

    def retranslateUi(self, ManagerWindow):
        _translate = QtCore.QCoreApplication.translate
        ManagerWindow.setWindowTitle(_translate("ManagerWindow", "Vi&deo Manager"))
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
        self.actionOpen_Stream.setText(_translate("ManagerWindow", "&Open Stream (experimental)"))
        self.actionOpen_MPEG2_File.setText(_translate("ManagerWindow", "Open &Video File"))
        self.actionCreate_MISB_File.setText(_translate("ManagerWindow", "&Create MISB File"))

from QGIS_FMV.gui import resources_rc
