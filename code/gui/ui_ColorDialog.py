# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui\ui_ColorDialog.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_ColorDialog(object):
    def setupUi(self, ColorDialog):
        ColorDialog.setObjectName("ColorDialog")
        ColorDialog.resize(347, 161)
        ColorDialog.setMaximumSize(QtCore.QSize(16777215, 220))
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/imgFMV/images/color_picker.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        ColorDialog.setWindowIcon(icon)
        ColorDialog.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        self.verticalLayout = QtWidgets.QVBoxLayout(ColorDialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.formLayout_2 = QtWidgets.QFormLayout()
        self.formLayout_2.setObjectName("formLayout_2")
        self.label = QtWidgets.QLabel(ColorDialog)
        self.label.setObjectName("label")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label)
        self.brightnessSlider = QtWidgets.QSlider(ColorDialog)
        self.brightnessSlider.setMinimum(-100)
        self.brightnessSlider.setMaximum(100)
        self.brightnessSlider.setOrientation(QtCore.Qt.Horizontal)
        self.brightnessSlider.setObjectName("brightnessSlider")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.brightnessSlider)
        self.label_2 = QtWidgets.QLabel(ColorDialog)
        self.label_2.setObjectName("label_2")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_2)
        self.label_3 = QtWidgets.QLabel(ColorDialog)
        self.label_3.setObjectName("label_3")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_3)
        self.label_4 = QtWidgets.QLabel(ColorDialog)
        self.label_4.setObjectName("label_4")
        self.formLayout_2.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_4)
        self.contrastSlider = QtWidgets.QSlider(ColorDialog)
        self.contrastSlider.setMinimum(-100)
        self.contrastSlider.setMaximum(100)
        self.contrastSlider.setOrientation(QtCore.Qt.Horizontal)
        self.contrastSlider.setObjectName("contrastSlider")
        self.formLayout_2.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.contrastSlider)
        self.hueSlider = QtWidgets.QSlider(ColorDialog)
        self.hueSlider.setMinimum(-100)
        self.hueSlider.setMaximum(100)
        self.hueSlider.setOrientation(QtCore.Qt.Horizontal)
        self.hueSlider.setObjectName("hueSlider")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.hueSlider)
        self.saturationSlider = QtWidgets.QSlider(ColorDialog)
        self.saturationSlider.setMinimum(-100)
        self.saturationSlider.setMaximum(100)
        self.saturationSlider.setOrientation(QtCore.Qt.Horizontal)
        self.saturationSlider.setObjectName("saturationSlider")
        self.formLayout_2.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.saturationSlider)
        self.verticalLayout.addLayout(self.formLayout_2)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.pushButton = QtWidgets.QPushButton(ColorDialog)
        self.pushButton.setObjectName("pushButton")
        self.verticalLayout.addWidget(self.pushButton)

        self.retranslateUi(ColorDialog)
        self.pushButton.clicked.connect(ColorDialog.ResetColorValues)
        self.brightnessSlider.valueChanged['int'].connect(ColorDialog.ColorChange)
        self.contrastSlider.valueChanged['int'].connect(ColorDialog.ColorChange)
        self.hueSlider.valueChanged['int'].connect(ColorDialog.ColorChange)
        self.saturationSlider.valueChanged['int'].connect(ColorDialog.ColorChange)
        QtCore.QMetaObject.connectSlotsByName(ColorDialog)

    def retranslateUi(self, ColorDialog):
        _translate = QtCore.QCoreApplication.translate
        ColorDialog.setWindowTitle(_translate("ColorDialog", "Color Options"))
        self.label.setText(_translate("ColorDialog", "Brightness"))
        self.label_2.setText(_translate("ColorDialog", "Contrast"))
        self.label_3.setText(_translate("ColorDialog", "Hue"))
        self.label_4.setText(_translate("ColorDialog", "Saturation"))
        self.pushButton.setText(_translate("ColorDialog", "Reset"))

from QGIS_FMV.gui import resources_rc
