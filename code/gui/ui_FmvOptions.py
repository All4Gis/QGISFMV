# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\ui_FmvOptions.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_OptionsDialog(object):
    def setupUi(self, OptionsDialog):
        OptionsDialog.setObjectName("OptionsDialog")
        OptionsDialog.resize(461, 145)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/custom-options.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        OptionsDialog.setWindowIcon(icon)
        self.verticalLayout = QtWidgets.QVBoxLayout(OptionsDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tabWidget = QtWidgets.QTabWidget(OptionsDialog)
        self.tabWidget.setObjectName("tabWidget")
        self.Magnifier_tab = QtWidgets.QWidget()
        self.Magnifier_tab.setObjectName("Magnifier_tab")
        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.Magnifier_tab)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.gridLayout_3 = QtWidgets.QGridLayout()
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.label = QtWidgets.QLabel(self.Magnifier_tab)
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label.setFont(font)
        self.label.setObjectName("label")
        self.gridLayout_3.addWidget(self.label, 0, 0, 1, 1)
        self.rB_Square_m = QtWidgets.QRadioButton(self.Magnifier_tab)
        self.rB_Square_m.setObjectName("rB_Square_m")
        self.gridLayout_3.addWidget(self.rB_Square_m, 0, 1, 1, 1)
        self.rB_Circle_m = QtWidgets.QRadioButton(self.Magnifier_tab)
        self.rB_Circle_m.setChecked(True)
        self.rB_Circle_m.setObjectName("rB_Circle_m")
        self.gridLayout_3.addWidget(self.rB_Circle_m, 0, 2, 1, 1)
        self.verticalLayout_2.addLayout(self.gridLayout_3)
        self.tabWidget.addTab(self.Magnifier_tab, "")
        self.verticalLayout.addWidget(self.tabWidget)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.pushButton = QtWidgets.QPushButton(OptionsDialog)
        self.pushButton.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.pushButton.setObjectName("pushButton")
        self.horizontalLayout.addWidget(self.pushButton)
        self.verticalLayout.addLayout(self.horizontalLayout)

        self.retranslateUi(OptionsDialog)
        self.tabWidget.setCurrentIndex(0)
        self.pushButton.pressed.connect(OptionsDialog.SaveOptions)
        QtCore.QMetaObject.connectSlotsByName(OptionsDialog)

    def retranslateUi(self, OptionsDialog):
        _translate = QtCore.QCoreApplication.translate
        OptionsDialog.setWindowTitle(_translate("OptionsDialog", "Options"))
        self.label.setText(_translate("OptionsDialog", "Shape "))
        self.rB_Square_m.setText(_translate("OptionsDialog", "Square"))
        self.rB_Circle_m.setText(_translate("OptionsDialog", "Circle"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.Magnifier_tab), _translate("OptionsDialog", "Magnifier"))
        self.pushButton.setText(_translate("OptionsDialog", "Accept"))

from QGIS_FMV.gui import resources_rc
