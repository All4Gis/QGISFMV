# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/ui_FmvAbout.ui'
#
# Created by: PyQt5 UI code generator 5.10.1
#
# WARNING! All changes made in this file will be lost!

from qgis.PyQt import QtCore, QtGui, QtWidgets

class Ui_FmvAbout(object):
    def setupUi(self, FmvAbout):
        FmvAbout.setObjectName("FmvAbout")
        FmvAbout.resize(643, 559)
        FmvAbout.setMinimumSize(QtCore.QSize(200, 250))
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/Information.png"), QtGui.QIcon.Mode.Normal, QtGui.QIcon.State.Off)
        FmvAbout.setWindowIcon(icon)
        FmvAbout.setLocale(QtCore.QLocale(QtCore.QLocale.Language.English, QtCore.QLocale.Country.UnitedStates))
        self.verticalLayout = QtWidgets.QVBoxLayout(FmvAbout)
        self.verticalLayout.setObjectName("verticalLayout")
        if _WebView is not None:
            self.webView = _WebView(FmvAbout)
            self.webView.setProperty("url", QtCore.QUrl("about:blank"))
        else:
            self.webView = QtWidgets.QTextBrowser(FmvAbout)
            self.webView.setOpenExternalLinks(True)
        self.webView.setObjectName("webView")
        self.verticalLayout.addWidget(self.webView)

        self.retranslateUi(FmvAbout)
        QtCore.QMetaObject.connectSlotsByName(FmvAbout)

    def retranslateUi(self, FmvAbout):
        _translate = QtCore.QCoreApplication.translate
        FmvAbout.setWindowTitle(_translate("FmvAbout", "About"))

_WebView = None
try:
    from qgis.PyQt.QtWebKitWidgets import QWebView as _WebView
except ImportError:
    try:
        from qgis.PyQt.QtWebEngineWidgets import QWebEngineView as _WebView
    except ImportError:
        _WebView = None
from QGIS_FMV.gui import resources_rc
