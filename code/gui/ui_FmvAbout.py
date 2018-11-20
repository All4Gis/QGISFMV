# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\ui_FmvAbout.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_FmvAbout(object):
    def setupUi(self, FmvAbout):
        FmvAbout.setObjectName("FmvAbout")
        FmvAbout.resize(643, 559)
        FmvAbout.setMinimumSize(QtCore.QSize(200, 250))
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/Information.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        FmvAbout.setWindowIcon(icon)
        FmvAbout.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.verticalLayout = QtWidgets.QVBoxLayout(FmvAbout)
        self.verticalLayout.setObjectName("verticalLayout")
        self.webView = QtWebKitWidgets.QWebView(FmvAbout)
        self.webView.setProperty("url", QtCore.QUrl("about:blank"))
        self.webView.setObjectName("webView")
        self.verticalLayout.addWidget(self.webView)

        self.retranslateUi(FmvAbout)
        QtCore.QMetaObject.connectSlotsByName(FmvAbout)

    def retranslateUi(self, FmvAbout):
        _translate = QtCore.QCoreApplication.translate
        FmvAbout.setWindowTitle(_translate("FmvAbout", "About"))

from PyQt5 import QtWebKitWidgets
from QGIS_FMV.gui import resources_rc
