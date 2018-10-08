import os

from PyQt5.QtGui import QColor, QFont, QPolygonF
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication, QPointF
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
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsSvgMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsDistanceArea,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsWkbTypes
)
from QGIS_FMV.geo import sphere as sphere
from qgis.core import Qgis as QGis
from qgis.utils import iface
from QGIS_FMV.utils.QgsFmvStyles import FmvLayerStyles as S

try:
    from pydevd import *
except ImportError:
    None

_layerreg = QgsProject.instance()
crtSensorSrc = 'DEFAULT'
crtPltTailNum = 'DEFAULT'


def AddDrawPointOnMap(pointIndex, Longitude, Latitude, Altitude):
    # add pin point on the map
    pointLyr = qgsu.selectLayerByName(Point_lyr)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    feature = QgsFeature()
    feature.setAttributes(
        [pointIndex, Longitude, Latitude, Altitude])
    p = QgsPointXY()
    p.set(Longitude, Latitude)
    geom = QgsGeometry.fromPointXY(p)
    feature.setGeometry(geom)
    pointLyr.addFeatures([feature])
    CommonLayer(pointLyr)
    return


def AddDrawLineOnMap(Longitude, Latitude, Altitude, drawLines):
    # add Line on the map
    linelyr = qgsu.selectLayerByName(Line_lyr)
    if linelyr is None:
        return
    linelyr.startEditing()
    f = QgsFeature()
    if linelyr.featureCount() == 0 or drawLines[-1][0] is None:
        f.setAttributes(
            [Longitude, Latitude, Altitude])
        geom = QgsGeometry.fromPolylineXY(
            [QgsPointXY(Longitude, Latitude), QgsPointXY(Longitude, Latitude)])
        f.setGeometry(geom)
        linelyr.addFeatures([f])

    else:
        f_last = linelyr.getFeature(linelyr.featureCount())
        f.setAttributes(
            [Longitude, Latitude, Altitude])
        geom = QgsGeometry.fromPolylineXY(
            [QgsPointXY(Longitude, Latitude),
             QgsPointXY(f_last.attribute(0), f_last.attribute(1))])
        f.setGeometry(geom)
        linelyr.addFeatures([f])

    CommonLayer(linelyr)
    return

# TODO: MAKE FUNCTION
def RemoveLastDrawPolygonOnMap():
    polyLyr = qgsu.selectLayerByName(Polygon_lyr)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    CommonLayer(polyLyr)
    return

def RemoveAllDrawPolygonOnMap():
    polyLyr = qgsu.selectLayerByName(Polygon_lyr)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    polyLyr.dataProvider().truncate()
    CommonLayer(polyLyr)
    return

def AddDrawPolygonOnMap(poly_coordinates):
    # Add Polygon
    polyLyr = qgsu.selectLayerByName(Polygon_lyr)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    feature = QgsFeature()
    point = QPointF()
    # create  float polygon --> construcet out of 'point'

    list_polygon = QPolygonF()
    for x in xrange(0, len(poly_coordinates)):
        if x % 2 == 0:
            point.setX(poly_coordinates[x])
            point.setY(poly_coordinates[x + 1])
            list_polygon.append(point)
    point.setX(poly_coordinates[0])
    point.setY(poly_coordinates[1])
    list_polygon.append(point)

    geomP = QgsGeometry.fromQPolygonF(list_polygon)
    feature.setGeometry(geomP)

    # Calculate Area WSG84 (Meters)
    area_wsg84 = QgsDistanceArea()
    area_wsg84.setSourceCrs(QgsCoordinateReferenceSystem.fromOgcWmsCrs(
        'EPSG:4326'), QgsProject.instance().transformContext())
    if (area_wsg84.sourceCrs().isGeographic()):
        area_wsg84.setEllipsoid(
            area_wsg84.sourceCrs().ellipsoidAcronym())

    # Calculate Centroid
    centroid = feature.geometry().centroid().asPoint()

    feature.setAttributes([centroid.x(), centroid.y(
    ), 0.0, area_wsg84.measurePolygon(geomP.asPolygon()[0])])

    polyLyr.addFeatures([feature])

    CommonLayer(polyLyr)
    return


def UpdateFootPrintData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL):
    ''' Update Footprint Values '''
    global crtSensorSrc
    imgSS = packet.GetImageSourceSensor()
    footprintLyr = qgsu.selectLayerByName(Footprint_lyr)

    try:
        if all(v is not None for v in [footprintLyr, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]) and all(v >= 2 for v in [len(cornerPointUL), len(cornerPointUR), len(cornerPointLR), len(cornerPointLL)]):
            if(imgSS != crtSensorSrc):
                SetDefaultFootprintStyle(footprintLyr, imgSS)
                crtSensorSrc = imgSS

            footprintLyr.startEditing()
            if footprintLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([cornerPointUL[1], cornerPointUL[0],
                                       cornerPointUR[1], cornerPointUR[0],
                                       cornerPointLR[1], cornerPointLR[0],
                                       cornerPointLL[1], cornerPointLL[0]])
                surface = QgsGeometry.fromPolygonXY([[
                    QgsPointXY(cornerPointUL[1],
                               cornerPointUL[0]),
                    QgsPointXY(
                        cornerPointUR[1], cornerPointUR[0]),
                    QgsPointXY(
                        cornerPointLR[1], cornerPointLR[0]),
                    QgsPointXY(
                        cornerPointLL[1], cornerPointLL[0]),
                    QgsPointXY(cornerPointUL[1], cornerPointUL[0])]])
                feature.setGeometry(surface)
                footprintLyr.addFeatures([feature])
            else:
                footprintLyr.beginEditCommand(
                    "ChangeGeometry + ChangeAttribute")
                fetId = 1
                attrib = {0: cornerPointUL[1],
                          1: cornerPointUL[0],
                          2: cornerPointUR[1],
                          3: cornerPointUR[0],
                          4: cornerPointLR[1],
                          5: cornerPointLR[0],
                          6: cornerPointLL[1],
                          7: cornerPointLL[0]}

                footprintLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})

                footprintLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolygonXY([[QgsPointXY(cornerPointUL[1],
                                                                   cornerPointUL[0]),
                                                        QgsPointXY(
                        cornerPointUR[1], cornerPointUR[0]),
                        QgsPointXY(
                        cornerPointLR[1], cornerPointLR[0]),
                        QgsPointXY(
                        cornerPointLL[1], cornerPointLL[0]),
                        QgsPointXY(cornerPointUL[1], cornerPointUL[0])]])})
            footprintLyr.endEditCommand()

            CommonLayer(footprintLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvLayers", "Failed Update FootPrint Layer! : "), str(e))
    return


def UpdateBeamsData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL):
    ''' Update Beams Values '''
    lat = packet.GetSensorLatitude()
    lon = packet.GetSensorLongitude()
    alt = packet.GetSensorTrueAltitude()

    beamsLyr = qgsu.selectLayerByName(Beams_lyr)

    try:
        if all(v is not None for v in [beamsLyr, lat, lon, alt, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]) and all(v >= 2 for v in [len(cornerPointUL), len(cornerPointUR), len(cornerPointLR), len(cornerPointLL)]):
            beamsLyr.startEditing()
            if beamsLyr.featureCount() == 0:

                # UL
                featureUL = QgsFeature()
                featureUL.setAttributes(
                    [lon, lat, alt, cornerPointUL[1], cornerPointUL[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointUL[1], cornerPointUL[0])])
                featureUL.setGeometry(surface)
                beamsLyr.addFeatures([featureUL])
                # UR
                featureUR = QgsFeature()
                featureUR.setAttributes(
                    [lon, lat, alt, cornerPointUR[1], cornerPointUR[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointUR[1], cornerPointUR[0])])
                featureUR.setGeometry(surface)
                beamsLyr.addFeatures([featureUR])
                # LR
                featureLR = QgsFeature()
                featureLR.setAttributes(
                    [lon, lat, alt, cornerPointLR[1], cornerPointLR[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointLR[1], cornerPointLR[0])])
                featureLR.setGeometry(surface)
                beamsLyr.addFeatures([featureLR])
                # LL
                featureLL = QgsFeature()
                featureLL.setAttributes(
                    [lon, lat, alt, cornerPointLL[1], cornerPointLL[0]])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(cornerPointLL[1], cornerPointLL[0])])
                featureLL.setGeometry(surface)
                beamsLyr.addFeatures([featureLL])

            else:
                beamsLyr.beginEditCommand(
                    "ChangeGeometry + ChangeAttribute")
                # UL
                fetId = 1
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointUL[1], 4: cornerPointUL[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([QgsPointXY(lon, lat), QgsPointXY(cornerPointUL[1], cornerPointUL[0])])})
                # UR
                fetId = 2
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointUR[1], 4: cornerPointUR[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([
                        QgsPointXY(lon, lat),
                        QgsPointXY(cornerPointUR[1], cornerPointUR[0])])})
                # LR
                fetId = 3
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointLR[1], 4: cornerPointLR[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([
                        QgsPointXY(lon, lat),
                        QgsPointXY(cornerPointLR[1], cornerPointLR[0])])})
                # LL
                fetId = 4
                attrib = {0: lon, 1: lat, 2: alt,
                          3: cornerPointLL[1], 4: cornerPointLL[0]}
                beamsLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})
                beamsLyr.dataProvider().changeGeometryValues(
                    {fetId: QgsGeometry.fromPolylineXY([
                        QgsPointXY(lon, lat),
                        QgsPointXY(cornerPointLL[1],
                                   cornerPointLL[0])])})

                beamsLyr.endEditCommand()

            CommonLayer(beamsLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Beams Layer! : "), str(e))
    return


def UpdateTrajectoryData(packet):
    ''' Update Trajectory Values '''
    global tLastLon
    global tLastLat

    lat = packet.GetSensorLatitude()
    lon = packet.GetSensorLongitude()
    alt = packet.GetSensorTrueAltitude()

    try:
        if tLastLon == 0.0 and tLastLat == 0.0:
            tLastLon = lon
            tLastLat = lat
        else:
            # little check to see if telemetry data are plausible before
            # drawing.

            distance = sphere.distance((tLastLon, tLastLat), (lon, lat))
            if distance > 1000:  # 1 km is the best value for prevent draw trajectory when start video again
                return
    except Exception:
        None

    tLastLon = lon
    tLastLat = lat
    trajectoryLyr = qgsu.selectLayerByName(Trajectory_lyr)

    try:
        if all(v is not None for v in [trajectoryLyr, lat, lon, alt]):
            trajectoryLyr.startEditing()
            f = QgsFeature()
            if trajectoryLyr.featureCount() == 0:
                f.setAttributes(
                    [lon, lat, alt])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat), QgsPointXY(lon, lat)])
                f.setGeometry(surface)
                trajectoryLyr.addFeatures([f])

            else:
                f_last = trajectoryLyr.getFeature(trajectoryLyr.featureCount())
                f.setAttributes(
                    [lon, lat, alt])
                surface = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(lon, lat),
                     QgsPointXY(f_last.attribute(0), f_last.attribute(1))])
                f.setGeometry(surface)
                trajectoryLyr.addFeatures([f])

            CommonLayer(trajectoryLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Trajectory Layer! : "), str(e))
    return


def UpdateFrameCenterData(packet):
    ''' Update FrameCenter Values '''
    lat = packet.GetFrameCenterLatitude()
    lon = packet.GetFrameCenterLongitude()
    alt = packet.GetFrameCenterElevation()
    PlatformHeading = packet.GetPlatformHeadingAngle()
    frameCenterLyr = qgsu.selectLayerByName(FrameCenter_lyr)

    try:
        if all(v is not None for v in [frameCenterLyr, lat, lon, alt, PlatformHeading]):
            frameCenterLyr.startEditing()
            frameCenterLyr.renderer().symbol().setAngle(float(PlatformHeading))

            if frameCenterLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([lon, lat, alt])
                p = QgsPointXY()
                p.set(lon, lat)
                geom = QgsGeometry.fromPointXY(p)
                feature.setGeometry(geom)
                frameCenterLyr.addFeatures([feature])

            else:
                frameCenterLyr.beginEditCommand(
                    "ChangeGeometry + ChangeAttribute")
                fetId = 1
                attrib = {0: lon, 1: lat, 2: alt}
                frameCenterLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})

                frameCenterLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry.fromPointXY(QgsPointXY(lon, lat))})
                frameCenterLyr.endEditCommand()

            CommonLayer(frameCenterLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Frame Center Layer! : "), str(e))

    return


def UpdatePlatformData(packet):
    ''' Update PlatForm Values '''
    global crtPltTailNum
    lat = packet.GetSensorLatitude()
    lon = packet.GetSensorLongitude()
    alt = packet.GetSensorTrueAltitude()
    PlatformHeading = packet.GetPlatformHeadingAngle()
    platformTailNumber = packet.GetPlatformTailNumber()
    platformLyr = qgsu.selectLayerByName(Platform_lyr)

    try:
        if all(v is not None for v in [platformLyr, lat, lon, alt, PlatformHeading]):
            if platformTailNumber != crtPltTailNum:
                SetDefaultPlatformStyle(platformLyr, platformTailNumber)
                crtPltTailNum = platformTailNumber

            platformLyr.startEditing()
            platformLyr.renderer().symbol().setAngle(float(PlatformHeading))

            if platformLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([lon, lat, alt])
                p = QgsPointXY()
                p.set(lon, lat)
                geom = QgsGeometry.fromPointXY(p)
                feature.setGeometry(geom)
                platformLyr.addFeatures([feature])

            else:
                platformLyr.beginEditCommand(
                    "ChangeGeometry + ChangeAttribute")
                fetId = 1
                attrib = {0: lon, 1: lat, 2: alt}
                platformLyr.dataProvider().changeAttributeValues(
                    {fetId: attrib})

                platformLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry.fromPointXY(QgsPointXY(lon, lat))})
                platformLyr.endEditCommand()

            CommonLayer(platformLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Platform Layer! : "), str(e))

    return


def CommonLayer(value):
    ''' Common commands Layers '''
    value.commitChanges()
    value.updateExtents()
    value.triggerRepaint()


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
    if group is not None:
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
