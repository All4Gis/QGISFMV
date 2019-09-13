# -*- coding: utf-8 -*-
import csv
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtGui import (QFont,
                             QTextCursor,
                             QTextDocument,
                             QTextBlockFormat,
                             QTextCharFormat,
                             QTextTableFormat,
                             QBrush,
                             QColor)
from qgis.PyQt.QtPrintSupport import QPrinter
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.core import Qgis as QGis, QgsTask, QgsApplication

from PyQt5.QtGui import QTextFormat

from QGIS_FMV.gui.ui_FmvMetadata import Ui_FmvMetadata
from QGIS_FMV.utils.QgsFmvUtils import askForFiles, _seconds_to_time, BurnDrawingsImage
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu

try:
    from pydevd import *
except ImportError:
    None


class QgsFmvMetadata(QDockWidget, Ui_FmvMetadata):
    """ Metadata Class Reports """

    def __init__(self, player=None):
        """ Contructor"""
        super().__init__()
        self.setupUi(self)
        self.player = player

    def finishedTask(self, e, result=None):
        """ Common finish task function """
        if e is None:
            if result is None:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvMetadata", 'Completed with no exception and no result '
                    '(probably manually canceled by the user)'), level=QGis.Warning)
            else:
                qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "QgsFmvMetadata", "Succesfully " + result['task'] + "!"))
        else:
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                "QgsFmvMetadata", "Failed " + result['task'] + "!"), level=QGis.Warning)
            raise e

    def SaveAsPDF(self):
        """ Save Table as pdf
            The drawings are saved by default
        """
        timestamp = _seconds_to_time(self.player.currentInfo)

        # Frame save drawings
        frame = BurnDrawingsImage(self.player.videoWidget.currentFrame(), self.player.videoWidget.grab(self.player.videoWidget.surface.videoRect()).toImage())

        data = self.player.GetPacketData()
        rows = self.VManager.rowCount()
        columns = self.VManager.columnCount()
        fileName = self.player.fileName

        out, _ = askForFiles(self, QCoreApplication.translate(
            "QgsFmvMetadata", "Save PDF"),
            isSave=True,
            exts='pdf')
        if not out:
            return

        task = QgsTask.fromFunction('Save PDF Report Task',
                                    self.CreatePDF,
                                    out=out,
                                    timestamp=timestamp,
                                    data=data,
                                    frame=frame,
                                    rows=rows,
                                    columns=columns,
                                    fileName=fileName,
                                    VManager=self.VManager,
                                    on_finished=self.finishedTask,
                                    flags=QgsTask.CanCancel)

        QgsApplication.taskManager().addTask(task)
        return

    def CreatePDF(self, task, out, timestamp, data, frame, rows, columns, fileName, VManager):
        ''' Create PDF QgsTask '''

        font_normal = QFont("Helvetica", 8, QFont.Normal)
        font_bold = QFont("Helvetica", 9, QFont.Bold)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)

        printer.setPageSize(QPrinter.A4)
        printer.setOutputFileName(out)
        printer.setFullPage(True)

        document = QTextDocument()
        document.setDefaultFont(font_normal)
        document.setPageSize(printer.paperSize(QPrinter.Point))

        cursor = QTextCursor(document)
        video_t = QCoreApplication.translate("QgsFmvMetadata", "Video : ")
        time_t = QCoreApplication.translate("QgsFmvMetadata", "TimeStamp : ")

        cursor.insertHtml(
            """
            <p style='text-align: center;'>
            <img style='display: block; margin-left: auto; margin-right: auto;'
            src=\':/imgFMV/images/header_logo.png\' width='200' height='25' />
            <p style='text-align: center;'>
            <strong>%s</strong>%s<strong>
            <p style='text-align: center;'>
            <strong>%s</strong>%s
            <p></p>
            """
            % (video_t, fileName, time_t, timestamp))

        tableFormat = QTextTableFormat()
        tableFormat.setBorderBrush(QBrush(Qt.black))
        tableFormat.setAlignment(Qt.AlignHCenter)
        tableFormat.setHeaderRowCount(1)
        tableFormat.setCellPadding(2)
        tableFormat.setCellSpacing(2)

        cursor.insertTable(rows + 1, columns, tableFormat)

        tableHeaderFormat = QTextCharFormat()
        tableHeaderFormat.setFont(font_bold)
        tableHeaderFormat.setBackground(QColor("#67b03a"))
        tableHeaderFormat.setForeground(Qt.white)
        tableHeaderFormat.setVerticalAlignment(QTextCharFormat.AlignMiddle)

        alternate_background = QTextCharFormat()
        alternate_background.setBackground(QColor("#DDE9ED"))

        for column in range(columns):
            cursor.mergeBlockCharFormat(tableHeaderFormat)
            cursor.insertText(VManager.horizontalHeaderItem(
                column).text())
            cursor.movePosition(QTextCursor.NextCell)

        row = 1
        for key in sorted(data.keys()):
            values = [str(key), str(data[key][0]), str(data[key][1])]
            for column in range(columns):
                cursor.insertText(values[column])
                if (row) % 2 == 0:
                    cursor.mergeBlockCharFormat(alternate_background)

                cursor.movePosition(QTextCursor.NextCell)
            row += 1

        cursor.movePosition(QTextCursor.End)

        current_t = QCoreApplication.translate("QgsFmvMetadata", "Current Frame")

        self.TextBlockCenter(cursor, TextFormat=QTextFormat.PageBreak_AlwaysBefore)

        cursor.insertHtml("""
                          <br><p style='text-align: center;'><strong>""" + current_t + """</strong></p><br>
                          """)

        self.TextBlockCenter(cursor)
        cursor.insertImage(frame.scaledToWidth(500, Qt.SmoothTransformation))

        document.print_(printer)

        if task.isCanceled():
            return None
        return {'task': task.description()}

    def TextBlockCenter(self, cursor, TextFormat=QTextFormat.PageBreak_Auto):
        """ Return  QTextBlockFormat object align center """
        centerFormat = QTextBlockFormat()
        centerFormat.setAlignment(Qt.AlignHCenter)
        centerFormat.setPageBreakPolicy(TextFormat)
        cursor.insertBlock(centerFormat)
        return

    def SaveACSV(self):
        """ Save Table as CSV  """
        data = self.player.GetPacketData()
        out, _ = askForFiles(self, QCoreApplication.translate(
            "QgsFmvMetadata", "Save CSV"),
            isSave=True,
            exts='csv')
        if not out:
            return

        task = QgsTask.fromFunction('Save CSV Report Task',
                                    self.CreateCSV,
                                    out=out,
                                    data=data,
                                    VManager=self.VManager,
                                    on_finished=self.finishedTask,
                                    flags=QgsTask.CanCancel)

        QgsApplication.taskManager().addTask(task)
        return

    def CreateCSV(self, task, out, data, VManager):
        ''' Create CSV QgsTask '''
        with open(out, 'w') as stream:
            headers = list()
            # 3 Columns always
            for column in range(VManager.columnCount()):
                headers.append(VManager.model(
                ).headerData(column, Qt.Horizontal))

            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()

            for key in sorted(data.keys()):
                rowdata = {}
                rowdata[headers[0]] = str(key)
                rowdata[headers[1]] = str(data[key][0])
                rowdata[headers[2]] = str(data[key][1])
                writer.writerow(rowdata)

        if task.isCanceled():
            return None
        return {'task': task.description()}

    def closeEvent(self, _):
        """ Close Dock Event """
        self.hide()
