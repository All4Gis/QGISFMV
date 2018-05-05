# -*- coding: utf-8 -*-
import sys


# from PyQt5.QtCore import QCoreApplication
# from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
try:
    sys.path.append(
        "D:\eclipse\plugins\org.python.pydev_6.2.0.201711281614\pysrc")
except ImportError:
    None

try:
    sys.path.append(
        "D:\eclipse\plugins\org.python.pydev_5.9.2.201708151115\pysrc")
except ImportError:
    None

# try:
#
#     try:
#         import pip
#     except ImportError:
#         raise
#     try:
#         import cv2
#     except Exception as e:
#         pip.main(["install", "opencv-python==3.4.0.12"])
#
#     try:
#         import matplotlib.pyplot as matplot
#     except Exception as e:
#         pip.main(["install", "matplotlib==2.0.0"])
#
# except Exception as e:
#     qgsu.showUserAndQgsFmvLogMessage(QCoreApplication.translate(
#         "Fmv", "Error: Missing Requeriments packages."))


def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
