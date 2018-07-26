# -*- coding: utf-8 -*-

from PyQt5 import QtGui, QtNetwork
from PyQt5.Qt import QImage, QByteArray, QBuffer, Qt, QImageReader, QColor, QImageWriter, QTransform, QPixmap
from PyQt5.QtCore import QByteArray
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtNetwork import QUdpSocket, QHostAddress
from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QPushButton, QVBoxLayout)
from PyQt5.QtWidgets import QDialog
from qgis.core import QgsMessageLog
try:
    from pydevd import *
except ImportError:
    None

# TODO :Make this functionality


# class UDPClient(QDialog):
#     def __init__(self, host=None, port=None, type=None, parent=None):
#         super(UDPClient, self).__init__(parent)
#         mcast_addr = host
#         mcast_port = port
#         type = type
#         self.statusLabel = QLabel("Listening for broadcasted messages")
#         quitButton = QPushButton("&Quit")
# 
#         self.udpSocket = QUdpSocket(self)
#         dstAddress = QHostAddress()
#         dstAddress.setAddress(mcast_addr)
#         self.udpSocket.bind(dstAddress, mcast_port)
# 
#         self.udpSocket.readyRead.connect(self.processPendingDatagrams)
#         quitButton.clicked.connect(self.close)
# 
#         buttonLayout = QHBoxLayout()
#         buttonLayout.addStretch(1)
#         buttonLayout.addWidget(quitButton)
#         buttonLayout.addStretch(1)
# 
#         mainLayout = QVBoxLayout()
#         mainLayout.addWidget(self.statusLabel)
#         mainLayout.addLayout(buttonLayout)
#         self.setLayout(mainLayout)
# 
#         self.setWindowTitle("Broadcast Receiver")
# 
#     def processPendingDatagrams(self):
#         while self.udpSocket.hasPendingDatagrams():
#             datagram, host, port = self.udpSocket.readDatagram(
#                 self.udpSocket.pendingDatagramSize())
#             buf = QBuffer()
#             b = buf.write(self.udpSocket.readAll())
#             buf.seek(buf.pos() - b)
#             image = QImage()
#             image.loadFromData(buf.buffer())
#             image.save(r"D:\test.png")
