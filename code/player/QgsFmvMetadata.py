# -*- coding: utf-8 -*-
import csv

from PyQt5.QtCore import Qt, QSizeF, QCoreApplication
from PyQt5.QtGui import (QCursor,
                         QFont,
                         QTextCursor,
                         QTextDocument,
                         QTextBlockFormat,
                         QTextCharFormat,
                         QTextTableFormat,
                         QBrush,
                         QColor)
from PyQt5.QtPrintSupport import QPrinter
from PyQt5.QtWidgets import QDockWidget, QApplication, QTableWidget, QTableWidgetItem
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
        timestamp = str(self.player.player.position()) + " seconds"
        frame = self.player.videoWidget.GetCurrentFrame()
        data = self.player.GetPacketData()

        rows = self.VManager.rowCount()
        columns = self.VManager.columnCount()

        out, _ = askForFiles(self, QCoreApplication.translate(
                                      "QgsFmvMetadata", "Save PDF"),
                                      isSave=True,
                                      exts='pdf')
        if out == "":
            return

        try:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

            font_normal = QFont("Helvetica", 10, QFont.Normal)
            font_bold = QFont("Helvetica", 12, QFont.Bold)

            printer = QPrinter(QPrinter.HighResolution)
            printer.setOrientation(QPrinter.Portrait)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setFullPage(True)
            printer.setPaperSize(QPrinter.A4)
            printer.setOutputFileName(out)
            printer.setPageMargins(15, 15, 15, 15, QPrinter.Point)
            printer.setColorMode(QPrinter.Color)

            document = QTextDocument()
            document.setDefaultFont(font_normal)

            cursor = QTextCursor(document)
            cursor.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
            cursor.insertHtml(
                """
                <p style='text-align: center;'>
                <img style='display: block; margin-left: auto; margin-right: auto;' 
                src=\':/imgFMV/images/header_logo.png\' width='116' height='56' />
                </p>
                <p style='text-align: center;'>
                <strong>Video :&nbsp;</strong>%s<strong>
                </p>
                <p style='text-align: center;'>
                <strong>TimeStamp :&nbsp;</strong>%s</p><br><br>
                """
                % (self.player.fileName, timestamp))

            tableFormat = QTextTableFormat()
            tableFormat.setHeaderRowCount(1)
            tableFormat.setBorderBrush(QBrush(Qt.black))
            tableFormat.setAlignment(Qt.AlignHCenter)
            tableFormat.setCellPadding(2)
            tableFormat.setCellSpacing(2)

            centerFormat = QTextBlockFormat()
            centerFormat.setAlignment(Qt.AlignCenter)
            cursor.insertBlock(centerFormat)

            textTable = cursor.insertTable(rows + 1, columns, tableFormat)

            tableHeaderFormat = QTextCharFormat()
            tableHeaderFormat.setFont(font_bold)
            tableHeaderFormat.setBackground(QColor("#67b03a"))
            tableHeaderFormat.setForeground(Qt.white)

            alternate_background = QTextCharFormat()
            alternate_background.setBackground(QColor("#DDE9ED"))

            for column in range(columns):
                cell = textTable.cellAt(0, column)
                cell.setFormat(tableHeaderFormat)
                cellCursor = cell.firstCursorPosition()
                cellCursor.insertText(self.VManager.horizontalHeaderItem(
                    column).text())

            row = 0
            for key in sorted(data.keys()):
                cell0 = textTable.cellAt(row + 1, 0)
                cell1 = textTable.cellAt(row + 1, 1)
                cell2 = textTable.cellAt(row + 1, 2)
                if (row+1)%2 == 0:
                    cell0.setFormat(alternate_background)
                    cell1.setFormat(alternate_background)
                    cell2.setFormat(alternate_background)
                cellCursor0 = cell0.firstCursorPosition()
                cellCursor0.insertText(str(key))
                cellCursor1 = cell1.firstCursorPosition()
                cellCursor1.insertText(str(data[key][0]))
                cellCursor2 = cell2.firstCursorPosition()
                cellCursor2.insertText(str(data[key][1]))
                row += 1

            cursor.movePosition(QTextCursor.End, QTextCursor.MoveAnchor)

            cursor.insertHtml("""
            <br><p style='text-align: center;'><strong>Current Frame</strong></p><br>
            """)

            centerFormat = QTextBlockFormat()
            centerFormat.setAlignment(Qt.AlignHCenter)
            cursor.insertBlock(centerFormat)
            cursor.insertImage(frame.scaledToWidth(500))

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
        data = self.player.GetPacketData()
        out, _ = askForFiles(self, QCoreApplication.translate(
                                      "QgsFmvMetadata", "Save CSV"),
                                      isSave=True,
                                      exts='csv')
        if out == "":
            return
        try:
            with open(unicode(out), 'w') as stream:
                headers = list()
                # 3 Columns always
                for column in range(self.VManager.columnCount()):
                    headers.append(self.VManager.model(
                    ).headerData(column, Qt.Horizontal))

                writer = csv.DictWriter(stream, fieldnames=headers)
                writer.writeheader()

                for key in sorted(data.keys()):
                    rowdata = {}
                    rowdata[headers[0]] = unicode(str(key))
                    rowdata[headers[1]] = unicode(str(data[key][0]))
                    rowdata[headers[2]] = unicode(str(data[key][1]))
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
        self.hide()
