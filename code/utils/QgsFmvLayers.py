import os

from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import QApplication
from QGIS_FMV.fmvConfig import (Platform_lyr,
                                Beams_lyr,
                                Footprint_lyr,
                                FrameCenter_lyr,
                                Point_lyr,
                                Line_lyr,
                                Polygon_lyr,
                                frames_g,
                                Trajectory_lyr,
                                epsg)
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.PyQt.QtCore import QVariant, QSettings
from qgis.core import (
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsMarkerSymbol,
    QgsLayerTreeLayer,
    QgsField,
    QgsFields,
    QgsCoordinateReferenceSystem,
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer
)
from qgis.core import Qgis as QGis, QgsWkbTypes
from qgis.core import QgsProject
from qgis.utils import iface
from QGIS_FMV.utils.QgsFmvStyles import FmvLayerStyles as S

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
        group = root.insertGroup(-1, name)  # Insert on bottom
        # Unchecked visibility
        group.setItemVisibilityCheckedRecursive(False)
        group.setExpanded(False)
    return


def RemoveGroupByName(name=frames_g):
    ''' Remove Group if not exist '''
    root = QgsProject.instance().layerTreeRoot()
    group = root.findGroup(name)
    if not group is None:
        for child in group.children():
            dump = child.name()
            QgsProject.instance().removeMapLayer(dump.split("=")[-1].strip())
        root.removeChildNode(group)
    return


def CreateVideoLayers():
    ''' Create Video Layers '''
    if qgsu.selectLayerByName(Footprint_lyr) is None:
        lyr_footprint = newPolygonsLayer(
            None,
            ["Corner Longitude Point 1",
             "Corner Latitude Point 1",
             "Corner Longitude Point 2",
             "Corner Latitude Point 2",
             "Corner Longitude Point 3",
             "Corner Latitude Point 3",
             "Corner Longitude Point 4",
             "Corner Latitude Point 4"],
            epsg,
            Footprint_lyr)
        SetDefaultFootprintStyle(lyr_footprint)
        addLayerNoCrsDialog(lyr_footprint)

    if qgsu.selectLayerByName(Beams_lyr) is None:
        lyr_beams = newLinesLayer(
            None,
            ["longitude",
             "latitude",
             "altitude",
             "Corner Longitude",
             "Corner Latitude"],
            epsg,
            Beams_lyr)
        SetDefaultBeamsStyle(lyr_beams)
        addLayerNoCrsDialog(lyr_beams)

    if qgsu.selectLayerByName(Trajectory_lyr) is None:
        lyr_Trajectory = newLinesLayer(
            None,
            ["longitude", "latitude", "altitude"], epsg, Trajectory_lyr)
        SetDefaultTrajectoryStyle(lyr_Trajectory)
        addLayerNoCrsDialog(lyr_Trajectory)

    if qgsu.selectLayerByName(Platform_lyr) is None:
        lyr_platform = newPointsLayer(
            None,
            ["longitude", "latitude", "altitude"], epsg, Platform_lyr)
        SetDefaultPlatformStyle(lyr_platform)
        addLayerNoCrsDialog(lyr_platform)

    if qgsu.selectLayerByName(Point_lyr) is None:
        lyr_point = newPointsLayer(
            None, ["number", "longitude", "latitude", "altitude"], epsg, Point_lyr)
        SetDefaultPointStyle(lyr_point)
        addLayerNoCrsDialog(lyr_point)

    if qgsu.selectLayerByName(FrameCenter_lyr) is None:
        lyr_framecenter = newPointsLayer(
            None, ["longitude", "latitude", "altitude"], epsg, FrameCenter_lyr)
        SetDefaultFrameCenterStyle(lyr_framecenter)
        addLayerNoCrsDialog(lyr_framecenter)
    if qgsu.selectLayerByName(Line_lyr) is None:
        lyr_line = newLinesLayer(
            None, ["longitude", "latitude", "altitude"], epsg, Line_lyr)
        SetDefaultLineStyle(lyr_line)
        addLayerNoCrsDialog(lyr_line)

    if qgsu.selectLayerByName(Polygon_lyr) is None:
        lyr_polygon = newPolygonsLayer(
            None, ["Centroid_longitude", "Centroid_latitude", "Centroid_altitude", "Area"], epsg, Polygon_lyr)
        SetDefaultPolygonStyle(lyr_polygon)
        addLayerNoCrsDialog(lyr_polygon)

    QApplication.processEvents()
    return


def ExpandLayer(layer, value=True):
    '''Collapse/Expand layer'''
    ltl = QgsProject.instance().layerTreeRoot().findLayer(layer.id())
    ltl.setExpanded(value)
    QApplication.processEvents()
    return


def RemoveVideoLayers():
    ''' Remove Video Layers '''
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(Platform_lyr).id())
    except Exception:
        None
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(Beams_lyr).id())
    except Exception:
        None
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(Footprint_lyr).id())
    except Exception:
        None
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(Trajectory_lyr).id())
    except Exception:
        None
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(FrameCenter_lyr).id())
    except Exception:
        None
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(Point_lyr).id())
    except Exception:
        None
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(Line_lyr).id())
    except Exception:
        None
    try:
        QgsProject.instance().removeMapLayer(
            qgsu.selectLayerByName(Polygon_lyr).id())
    except Exception:
        None
    iface.mapCanvas().refresh()
    QApplication.processEvents()
    return


def SetDefaultFootprintStyle(layer, sensor='DEFAULT'):
    ''' Footprint Symbol '''
    style = S.getSensor(sensor)
    fill_sym = QgsFillSymbol.createSimple({'color': style['COLOR'],
                                           'outline_color': style['OUTLINE_COLOR'],
                                           'outline_style': style['OUTLINE_STYLE'],
                                           'outline_width': style['OUTLINE_WIDTH']})
    renderer = QgsSingleSymbolRenderer(fill_sym)
    layer.setRenderer(renderer)
    return


def SetDefaultTrajectoryStyle(layer):
    ''' Trajectory Symbol '''
    style = S.getTrajectory('DEFAULT')
    fill_sym = QgsLineSymbol.createSimple({'color': style['COLOR'],
                                           'width': style['WIDTH'],
                                           'customdash': style['customdash'],
                                           'use_custom_dash': style['use_custom_dash']})
    renderer = QgsSingleSymbolRenderer(fill_sym)
    layer.setRenderer(renderer)
    return


def SetDefaultPlatformStyle(layer, platform='DEFAULT'):
    ''' Platform Symbol '''
    style = S.getPlatform(platform)

    svgStyle = {}
    svgStyle['name'] = style["NAME"]
    svgStyle['outline'] = style["OUTLINE"]
    svgStyle['outline-width'] = style["OUTLINE_WIDTH"]
    svgStyle['size'] = style["SIZE"]

    symbol_layer = QgsSvgMarkerSymbolLayer.create(svgStyle)
    layer.renderer().symbol().changeSymbolLayer(0, symbol_layer)
    return


def SetDefaultFrameCenterStyle(layer):
    ''' Point Symbol '''
    style = S.getFrameCenterPoint()
    symbol = QgsMarkerSymbol.createSimple(
        {'name': style["NAME"], 'line_color': style["LINE_COLOR"], 'line_width': style["LINE_WIDTH"], 'size': style["SIZE"]})
    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)
    return


def SetDefaultPointStyle(layer):
    ''' Point Symbol '''
    style = S.getDrawingPoint()
    symbol = QgsMarkerSymbol.createSimple(
        {'name': style["NAME"], 'line_color': style["LINE_COLOR"], 'line_width': style["LINE_WIDTH"], 'size': style["SIZE"]})

    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)

    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()

    text_format.setFont(QFont(style["LABEL_FONT"], style["LABEL_FONT_SIZE"]))
    text_format.setColor(QColor(style["LABEL_FONT_COLOR"]))
    text_format.setSize(style["LABEL_SIZE"])

    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(1)
    buffer_settings.setColor(QColor(style["LABEL_BUFFER_COLOR"]))

    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)

    layer_settings.fieldName = "number"
    layer_settings.placement = 2
    layer_settings.enabled = True

    layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
    layer.setLabelsEnabled(True)
    layer.setLabeling(layer_settings)
    # my_layer.triggerRepaint()

    return


def SetDefaultLineStyle(layer):
    ''' Line Symbol '''
    style = S.getDrawingLine()
    symbol = layer.renderer().symbol()
    symbol.setColor(style['COLOR'])
    symbol.setWidth(style['WIDTH'])
    return


def SetDefaultPolygonStyle(layer):
    ''' Polygon Symbol '''
    style = S.getDrawingPolygon()
    fill_sym = QgsFillSymbol.createSimple({'color': style['COLOR'],
                                           'outline_color': style['OUTLINE_COLOR'],
                                           'outline_style': style['OUTLINE_STYLE'],
                                           'outline_width': style['OUTLINE_WIDTH']})
    renderer = QgsSingleSymbolRenderer(fill_sym)
    layer.setRenderer(renderer)
    return


def SetDefaultBeamsStyle(layer, beam='DEFAULT'):
    ''' Beams Symbol'''
    style = S.getBeam(beam)
    symbol = layer.renderer().symbol()
    symbol.setColor(QColor.fromRgba(style['COLOR']))
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
