# -*- coding: utf-8 -*-
import csv

from PyQt5.QtCore import Qt, QSizeF, QCoreApplication
from PyQt5.QtGui import (QCursor, QTextCursor, QTextDocument, QTextCharFormat,
                         QTextTableFormat, QBrush, QColor)
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtWidgets import QDockWidget, QApplication, QFileDialog
from QGIS_FMV.gui.ui_FmvMetadata import Ui_FmvMetadata
from QGIS_FMV.utils.QgsFmvUtils import askForFiles
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.core import Qgis as QGis


try:
    from pydevd import *
except ImportError:
    None


class QgsFmvMetadata(QDockWidget, Ui_FmvMetadata):
    """ Metadata Class Reports """

    def __init__(self, parent=None, player=None):
        """ Contructor"""
        super(QgsFmvMetadata, self).__init__(parent)
        self.setupUi(self)
        self.player = player
        self.parent = parent

    def SaveAsPDF(self):
        """ Save Table as pdf """
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save File", "", "PDF Files (*.pdf)")
        if fileName == "":
            return

        try:
            videoName = self.player.fileName
            timestamp = self.player.player.position()
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
            rows = self.VManager.rowCount()
            columns = self.VManager.columnCount()

            printer = QPrinter(QPrinter.HighResolution)
            innerRect = printer.pageRect()
            sizeF = QSizeF(innerRect.size().width(), innerRect.size().height())
            header = QTextDocument()
            header.setPageSize(sizeF)
            cursor_header = QTextCursor(header)
            format1 = QTextCharFormat()
            format1.setFontPointSize(16)
            cursor_header.insertHtml(
                "<p style='text-align: left;'><strong>Video</strong>: %s <strong>&nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp;TimeStamp</strong>: %s </p>" % (videoName, timestamp))
            cursor_header.insertHtml("<br><br><br> ")

            cursor_header.select(QTextCursor.Document)
            fragment_header = cursor_header.selection()

            document = QTextDocument()
            cursor = QTextCursor(document)
            tableFormat = QTextTableFormat()
            tableFormat.setHeaderRowCount(1)
            tableFormat.setBorderBrush(QBrush(Qt.black))
            tableFormat.setAlignment(Qt.AlignHCenter)
            tableFormat.setCellPadding(5)
            tableFormat.setCellSpacing(5)

            cursor.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
            cursor.insertFragment(fragment_header)

            textTable = cursor.insertTable(rows + 1, columns, tableFormat)

            tableHeaderFormat = QTextCharFormat()
            tableHeaderFormat.setBackground(QColor("#DADADA"))

            for column in range(columns):
                cell = textTable.cellAt(0, column)
                cell.setFormat(tableHeaderFormat)
                cellCursor = cell.firstCursorPosition()
                cellCursor.insertText(self.VManager.horizontalHeaderItem(
                    column).data(Qt.DisplayRole))

            for row in range(rows):
                for column in range(columns):
                    item = self.VManager.item(row, column)
                    if item is not None:
                        cell = textTable.cellAt(row + 1, column)
                        cellCursor = cell.firstCursorPosition()
                        cellCursor.insertText(
                            self.VManager.item(row, column).text())

            cursor.movePosition(QTextCursor.End)
            printer.setOrientation(QPrinter.Portrait)

            printer.setPageMargins(
                30, 100, 10, 40, QPrinter.DevicePixel)
            printer.setFullPage(True)
            printer.setPageSize(QPrinter.A4)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(fileName)

            document.print_(printer)
            QApplication.restoreOverrideCursor()
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvMetadata", "Succesfully creating PDF"))
        except Exception as e:
            QApplication.restoreOverrideCursor()
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvMetadata", "Failed creating PDF : " + str(e)), level=QGis.Warning)
            return
        return

    def SaveACSV(self):
        """ Save Table as CSV  """
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save File", "", "CSV Files (*.csv)")
        if fileName == "":
            return
        try:
            with open(unicode(fileName), 'w') as stream:
                headers = list()
                for column in range(self.VManager.columnCount()):
                    headers.append(self.VManager.model(
                    ).headerData(column, Qt.Horizontal))

                writer = csv.DictWriter(stream, fieldnames=headers)
                writer.writeheader()
                for row in range(self.VManager.rowCount()):
                    rowdata = {}
                    for column in range(self.VManager.columnCount()):
                        item = self.VManager.item(row, column)
                        name = self.VManager.model().headerData(column, Qt.Horizontal)
                        if item is not None:
                            rowdata[name] = unicode(item.text())
                        else:
                            rowdata[name] = ''
                    writer.writerow(rowdata)
            QApplication.restoreOverrideCursor()
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvMetadata", "Succesfully creating CSV"))
        except Exception as e:
            QApplication.restoreOverrideCursor()
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvMetadata", "Failed creating CSV : " + str(e)), level=QGis.Warning)

        return

    def closeEvent(self, _):
        """ Close Dock Event """
        self.parent.metadataDlg = None
