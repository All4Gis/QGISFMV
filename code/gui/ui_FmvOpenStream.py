# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\ui_FmvOpenStream.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_FmvOpenStream(object):
    def setupUi(self, FmvOpenStream):
        FmvOpenStream.setObjectName("FmvOpenStream")
        FmvOpenStream.resize(355, 71)
        FmvOpenStream.setMinimumSize(QtCore.QSize(0, 0))
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/stream.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        FmvOpenStream.setWindowIcon(icon)
        FmvOpenStream.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.verticalLayout = QtWidgets.QVBoxLayout(FmvOpenStream)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout_2 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.cmb_protocol = QtWidgets.QComboBox(FmvOpenStream)
        self.cmb_protocol.setCursor(QtGui.QCursor(QtCore.Qt.IBeamCursor))
        self.cmb_protocol.setObjectName("cmb_protocol")
        self.cmb_protocol.addItem("")
        self.cmb_protocol.addItem("")
        self.cmb_protocol.addItem("")
        self.horizontalLayout_2.addWidget(self.cmb_protocol)
        self.ln_host = QtWidgets.QLineEdit(FmvOpenStream)
        self.ln_host.setText("")
        self.ln_host.setObjectName("ln_host")
        self.horizontalLayout_2.addWidget(self.ln_host)
        self.ln_port = QtWidgets.QLineEdit(FmvOpenStream)
        self.ln_port.setInputMethodHints(QtCore.Qt.ImhNone)
        self.ln_port.setText("")
        self.ln_port.setObjectName("ln_port")
        self.horizontalLayout_2.addWidget(self.ln_port)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.btn_Open = QtWidgets.QPushButton(FmvOpenStream)
        self.btn_Open.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.btn_Open.setObjectName("btn_Open")
        self.horizontalLayout_3.addWidget(self.btn_Open)
        self.verticalLayout.addLayout(self.horizontalLayout_3)

        self.retranslateUi(FmvOpenStream)
        self.btn_Open.clicked['bool'].connect(FmvOpenStream.OpenStream)
        QtCore.QMetaObject.connectSlotsByName(FmvOpenStream)

    def retranslateUi(self, FmvOpenStream):
        _translate = QtCore.QCoreApplication.translate
        FmvOpenStream.setWindowTitle(_translate("FmvOpenStream", "Open Stream"))
        self.cmb_protocol.setItemText(0, _translate("FmvOpenStream", "RTP"))
        self.cmb_protocol.setItemText(1, _translate("FmvOpenStream", "UDP"))
        self.cmb_protocol.setItemText(2, _translate("FmvOpenStream", "TCP"))
        self.ln_host.setPlaceholderText(_translate("FmvOpenStream", "127.0.0.1"))
        self.ln_port.setPlaceholderText(_translate("FmvOpenStream", "5005"))
        self.btn_Open.setText(_translate("FmvOpenStream", "Ok"))

from QGIS_FMV.gui import resources_rc
