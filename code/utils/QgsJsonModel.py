# 2017 by Gregor Engberding , MIT License
# Modificated for work in QGIS FMV Plugin

from PyQt5.QtCore import (QFile,
                          QJsonDocument,
                          QAbstractItemModel,
                          QModelIndex,
                          Qt,
                          QByteArray,
                          QVariant,
                          QJsonParseError)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
try:
    from pydevd import *
except ImportError:
    None


class QJsonTreeItem(object):
    """ Json TreeView Class """

    def __init__(self, parent=None):
        """ Constructor """
        self.mParent = parent
        self.mChilds = []
        self.mType = None
        self.mValue = ""

    def appendChild(self, item):
        self.mChilds.append(item)

    def child(self, row):
        return self.mChilds[row]

    def parent(self):
        return self.mParent

    def childCount(self):
        return len(self.mChilds)

    def row(self):
        if self.mParent is not None:
            return self.mParent.mChilds.index(self)
        return 0

    def setKey(self, key):
        self.mKey = key

    def setValue(self, value):
        self.mValue = value

    def setType(self, t):
        self.mType = t

    def key(self):
        return self.mKey

    def value(self):
        return self.mValue

    def type(self):
        return self.mType

    def load(self, value, parent=None):
        rootItem = QJsonTreeItem(parent)
        rootItem.setKey("root")
        jsonType = None

        try:
            value = value.toVariant()
            jsonType = value.type()
        except AttributeError:
            pass

        try:
            value = value.toObject()
            jsonType = value.type()

        except AttributeError:
            pass

        if isinstance(value, dict):
            """ process the key/value pairs """
            for key in value:
                v = value[key]
                child = self.load(v, rootItem)
                child.setKey(key)
                try:
                    child.setType(v.type())
                except AttributeError:
                    child.setType(v.__class__)
                rootItem.appendChild(child)

        elif isinstance(value, list):
            """ process the values in the list """
            for i, v in enumerate(value):
                child = self.load(v, rootItem)
                child.setKey(str(i))
                child.setType(v.__class__)
                rootItem.appendChild(child)

        else:
            """ value is processed """
            rootItem.setValue(value)
            try:
                rootItem.setType(value.type())
            except AttributeError:
                if jsonType is not None:
                    rootItem.setType(jsonType)
                else:
                    rootItem.setType(value.__class__)

        return rootItem


class QJsonModel(QAbstractItemModel):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mRootItem = QJsonTreeItem()
        self.mHeaders = ["key", "value"]

    def load(self, fileName):
        if fileName is None or fileName is False:
            return False
        js = None
        stream = QFile(fileName)
        if stream.open(QFile.ReadOnly):
            js = QByteArray((stream.readAll()))
            stream.close()
            self.loadJson(js)
        else:
            qgsu.showUserAndLogMessage(
                "", stream.errorString(), onlyLog=True)

    def loadJson(self, value):
        error = QJsonParseError()
        self.mDocument = QJsonDocument.fromJson(value, error)

        if self.mDocument is not None:
            self.beginResetModel()
            if self.mDocument.isArray():
                self.mRootItem.load(list(self.mDocument.array()))
            else:
                self.mRootItem = self.mRootItem.load(self.mDocument.object())
            self.endResetModel()

            return True

        qgsu.showUserAndLogMessage(
                "", "QJsonModel: error loading Json", onlyLog=True)
        return False

    def loadJsonFromConsole(self, value):
        error = QJsonParseError()
        self.mDocument = QJsonDocument.fromJson(value, error)

        if self.mDocument is not None:
            self.beginResetModel()
            if self.mDocument.isArray():
                self.mRootItem.load(list(self.mDocument.array()))
            else:
                self.mRootItem = self.mRootItem.load(self.mDocument.object())
            self.endResetModel()

            return True

        qgsu.showUserAndLogMessage(
                "", "QJsonModel: error loading Json", onlyLog=True)
        return False

    def data(self, index, role):
        if not index.isValid():
            return QVariant()

        item = index.internalPointer()
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return str(item.key())
            elif col == 1:
                return str(item.value())
            elif col == 2:
                return str(item.type())

        return QVariant()

    def headerData(self, section, orientation, role):
        if role != Qt.DisplayRole:
            return QVariant()

        if orientation == Qt.Horizontal:
            return self.mHeaders[section]

        return QVariant()

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        if not parent.isValid():
            parentItem = self.mRootItem
        else:
            parentItem = parent.internalPointer()
        try:
            childItem = parentItem.child(row)
            return self.createIndex(row, column, childItem)
        except IndexError:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QModelIndex()

        childItem = index.internalPointer()
        parentItem = childItem.parent()

        if parentItem == self.mRootItem:
            return QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            parentItem = self.mRootItem
        else:
            parentItem = parent.internalPointer()

        return parentItem.childCount()

    def columnCount(self, _):
        return 2
