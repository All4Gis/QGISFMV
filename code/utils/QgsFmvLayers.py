import os

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication
from QGIS_FMV.fmvConfig import Platform_lyr, Beams_lyr, Footprint_lyr, frames_g
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.PyQt.QtCore import QVariant, QSettings
from qgis.core import (
    QgsLayerTreeLayer,
    QgsField,
    QgsFields,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsFillSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer
)
from qgis.core import Qgis as QGis, QgsWkbTypes
from qgis.core import QgsProject
from qgis.utils import iface


try:
    from pydevd import *
except ImportError:
    None

_layerreg = QgsProject.instance()


def CreateGroupByName(name=frames_g):
    ''' Create Group if not exist '''
    root = QgsProject.instance().layerTreeRoot()
    group = root.findGroup(name)
    if group is None:
        root.insertGroup(0, name)
    return


def RemoveGroupByName(name=frames_g):
    ''' Remove Group if not exist '''
    root = QgsProject.instance().layerTreeRoot()
    group = root.findGroup(name)
    if not group is None:
        for child in group.children():
            dump = child.name()
            id = dump.split("=")[-1].strip()
            QgsProject.instance().removeMapLayer(id)
        root.removeChildNode(group)
    return


def CreateVideoLayers():
    ''' Create Video Layers '''
    if qgsu.selectLayerByName(Footprint_lyr) is None:
        lyr_footprint = newPolygonsLayer(
            None, ["Corner Longitude Point 1", "Corner Latitude Point 1", "Corner Longitude Point 2", "Corner Latitude Point 2", "Corner Longitude Point 3", "Corner Latitude Point 3", "Corner Longitude Point 4", "Corner Latitude Point 4"], 'EPSG:4326', Footprint_lyr)
        SetDefaultFootprintStyle(lyr_footprint)
        addLayerNoCrsDialog(lyr_footprint)

    if qgsu.selectLayerByName(Beams_lyr) is None:
        lyr_beams = newLinesLayer(
            None, ["longitude", "latitude", "altitude", "Corner Longitude", "Corner Latitude"], 'EPSG:4326', Beams_lyr)
        SetDefaultBeamsStyle(lyr_beams)
        addLayerNoCrsDialog(lyr_beams)

    if qgsu.selectLayerByName(Platform_lyr) is None:
        lyr_platform = newPointsLayer(
            None, ["longitude", "latitude", "altitude"], 'EPSG:4326', Platform_lyr)
        SetDefaultPlatformStyle(lyr_platform)
        addLayerNoCrsDialog(lyr_platform)

    # QApplication.processEvents(QEventLoop.AllEvents, 50)
    QApplication.processEvents()
    return


def RemoveVideoLayers():
    ''' Create Video Layers '''
    try:
        QgsProject.instance().removeMapLayer(qgsu.selectLayerByName(Platform_lyr).id())
    except:
        None
    try:
        QgsProject.instance().removeMapLayer(qgsu.selectLayerByName(Beams_lyr).id())
    except:
        None
    try:
        QgsProject.instance().removeMapLayer(qgsu.selectLayerByName(Footprint_lyr).id())
    except:
        None
    iface.mapCanvas().refresh()
    QApplication.processEvents()
    return


def SetDefaultFootprintStyle(layer):
    ''' Footprint Symbol '''
    fill_sym = QgsFillSymbol.createSimple({'color': '0, 0, 255,40',
                                           'outline_color': '#ff5733',
                                           'outline_style': 'solid',
                                           'outline_width': '1'})
    renderer = QgsSingleSymbolRenderer(fill_sym)
    layer.setRenderer(renderer)
    return


def SetDefaultPlatformStyle(layer):
    ''' Platform Symbol '''
    svgStyle = {}
    svgStyle['name'] = ":/imgFMV/images/platform.svg"
    svgStyle['outline'] = '#FFFFFF'
    svgStyle['outline-width'] = '1'
    svgStyle['size'] = '18'
    symbol_layer = QgsSvgMarkerSymbolLayer.create(svgStyle)
    layer.renderer().symbol().changeSymbolLayer(0, symbol_layer)
    return


def SetDefaultBeamsStyle(layer):
    ''' Beams Symbol'''
    symbol = layer.renderer().symbol()
    symbol.setColor(QColor.fromRgb(255, 87, 51))
    symbol.setWidth(1)
    return


def addLayer(layer, loadInLegend=True, group=None):
    """
    Add one or several layers to the QGIS session and layer registry.
    :param layer: The layer object or list with layers  to add the QGIS layer registry and session.
    :param loadInLegend: True if this layer should be added to the legend.
    :return: The added layer
    """
    if not hasattr(layer, "__iter__"):
        layer = [layer]
    _layerreg.addMapLayers(layer, loadInLegend)
    if group is not None:
        root = QgsProject.instance().layerTreeRoot()
        g = root.findGroup(group)
        g.insertChildNode(0, QgsLayerTreeLayer(layer[0]))
    return layer


def addLayerNoCrsDialog(layer, loadInLegend=True, group=None):
    '''
    Tries to add a layer from layer object
    Same as the addLayer method, but it does not ask for CRS, regardless of current
    configuration in QGIS settings
    '''
    settings = QSettings()
    prjSetting3 = settings.value('/Projections/defaultBehavior')
    settings.setValue('/Projections/defaultBehavior', '')
    layer = addLayer(layer, loadInLegend, group)
    settings.setValue('/Projections/defaultBehavior', prjSetting3)
    QApplication.processEvents()
    return layer


TYPE_MAP = {
    str: QVariant.String,
    float: QVariant.Double,
    int: QVariant.Int,
    bool: QVariant.Bool
}

try:
    GEOM_TYPE_MAP = {
        QGis.WKBPoint: 'Point',
        QGis.WKBLineString: 'LineString',
        QGis.WKBPolygon: 'Polygon',
        QGis.WKBMultiPoint: 'MultiPoint',
        QGis.WKBMultiLineString: 'MultiLineString',
        QGis.WKBMultiPolygon: 'MultiPolygon',
    }
except:
    GEOM_TYPE_MAP = {
        QgsWkbTypes.Point: 'Point',
        QgsWkbTypes.LineString: 'LineString',
        QgsWkbTypes.Polygon: 'Polygon',
        QgsWkbTypes.MultiPoint: 'MultiPoint',
        QgsWkbTypes.MultiLineString: 'MultiLineString',
        QgsWkbTypes.MultiPolygon: 'MultiPolygon',
    }
    QGis.WKBPoint = QgsWkbTypes.Point
    QGis.WKBMultiPoint = QgsWkbTypes.MultiPoint
    QGis.WKBLine = QgsWkbTypes.LineString
    QGis.WKBMultiLine = QgsWkbTypes.MultiLineString
    QGis.WKBPolygon = QgsWkbTypes.Polygon
    QGis.WKBMultiPolygon = QgsWkbTypes.MultiPolygon


def _toQgsField(f):
    if isinstance(f, QgsField):
        return f
    return QgsField(f[0], TYPE_MAP.get(f[1], QVariant.String))


def newPointsLayer(filename, fields, crs, name=None, encoding="utf-8"):
    return newVectorLayer(filename, fields, QGis.WKBPoint, crs, name, encoding)


def newLinesLayer(filename, fields, crs, name=None, encoding="utf-8"):
    return newVectorLayer(filename, fields, QGis.WKBLine, crs, name, encoding)


def newPolygonsLayer(filename, fields, crs, name=None, encoding="utf-8"):
    return newVectorLayer(filename, fields, QGis.WKBPolygon, crs, name, encoding)


def newVectorLayer(filename, fields, geometryType, crs, name=None, encoding="utf-8"):
    '''
    Creates a new vector layer
    :param filename: The filename to store the file. The extensions determines the type of file.
    If extension is not among the supported ones, a shapefile will be created and the file will
    get an added '.shp' to its path.
    If the filename is None, a memory layer will be created
    :param fields: the fields to add to the layer. Accepts a QgsFields object or a list of tuples (field_name, field_type)
    Accepted field types are basic Python types str, float, int and bool
    :param geometryType: The type of geometry of the layer to create.
    :param crs: The crs of the layer to create. Accepts a QgsCoordinateSystem object or a string with the CRS authId.
    :param encoding: The layer encoding
    '''
    if isinstance(crs, basestring):
        crs = QgsCoordinateReferenceSystem(crs)
    if filename is None:
        uri = GEOM_TYPE_MAP[geometryType]
        if crs.isValid():
            uri += '?crs=' + crs.authid() + '&'
        fieldsdesc = ['field=' + f for f in fields]

        fieldsstring = '&'.join(fieldsdesc)
        uri += fieldsstring

        if name is None:
            name = "mem_layer"
        layer = QgsVectorLayer(uri, name, 'memory')

    else:
        formats = QgsVectorFileWriter.supportedFiltersAndFormats()
        OGRCodes = {}
        for (key, value) in formats.items():
            extension = unicode(key)
            extension = extension[extension.find('*.') + 2:]
            extension = extension[:extension.find(' ')]
            OGRCodes[extension] = value

        extension = os.path.splitext(filename)[1][1:]
        if extension not in OGRCodes:
            extension = 'shp'
            filename = filename + '.shp'

        if isinstance(fields, QgsFields):
            qgsfields = fields
        else:
            qgsfields = QgsFields()
            for field in fields:
                qgsfields.append(_toQgsField(field))

        QgsVectorFileWriter(filename, encoding, qgsfields,
                            geometryType, crs, OGRCodes[extension])

        layer = QgsVectorLayer(filename, os.path.basename(filename), 'ogr')

    return layer
