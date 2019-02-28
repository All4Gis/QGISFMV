import os
from os.path import dirname, abspath
from PyQt5.QtGui import QColor, QFont, QPolygonF
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QCoreApplication, QPointF

from configparser import SafeConfigParser
parser = SafeConfigParser()
parser.read(os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini'))

Platform_lyr = parser['LAYERS']['Platform_lyr']
Beams_lyr = parser['LAYERS']['Beams_lyr']
Footprint_lyr = parser['LAYERS']['Footprint_lyr']
FrameCenter_lyr = parser['LAYERS']['FrameCenter_lyr']
FrameAxis_lyr = parser['LAYERS']['FrameAxis_lyr']
Point_lyr = parser['LAYERS']['Point_lyr']
Line_lyr = parser['LAYERS']['Line_lyr']
Polygon_lyr = parser['LAYERS']['Polygon_lyr']
frames_g = parser['LAYERS']['frames_g']
Trajectory_lyr = parser['LAYERS']['Trajectory_lyr']
epsg = parser['LAYERS']['epsg']

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
    QgsPoint,
    QgsLineString
)

from qgis.utils import iface
from QGIS_FMV.utils.QgsFmvStyles import FmvLayerStyles as S
from itertools import groupby
from qgis._3d import (QgsPhongMaterialSettings,
                      QgsVectorLayer3DRenderer,
                      QgsLine3DSymbol,
                      QgsPoint3DSymbol,
                      QgsPolygon3DSymbol)

try:
    from pydevd import *
except ImportError:
    None

_layerreg = QgsProject.instance()
crtSensorSrc = crtSensorSrc2 = crtPltTailNum = 'DEFAULT'

TYPE_MAP = {
    str: QVariant.String,
    float: QVariant.Double,
    int: QVariant.Int,
    bool: QVariant.Bool
}

Point = 'Point'
PointZ = 'PointZ'
LineZ = 'LineStringZ'
Line = 'LineString'
Polygon = 'Polygon'


def AddDrawPointOnMap(pointIndex, Longitude, Latitude, Altitude):
    '''  add pin point on the map '''
    pointLyr = qgsu.selectLayerByName(Point_lyr)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    feature = QgsFeature()
    feature.setAttributes(
        [pointIndex, Longitude, Latitude, Altitude])
    p = QgsPointXY()
    p.set(Longitude, Latitude)
    feature.setGeometry(QgsGeometry.fromPointXY(p))
    pointLyr.addFeatures([feature])
    CommonLayer(pointLyr)
    return

# TODO : Add only ID Attributes?


def AddDrawLineOnMap(drawLines):
    '''  add Line on the map '''

    RemoveAllDrawLineOnMap()
    linelyr = qgsu.selectLayerByName(Line_lyr)
    if linelyr is None:
        return

    linelyr.startEditing()
    for k, v in groupby(drawLines, key=lambda x: x == [None, None, None]):
        points = []
        if k is False:
            list1 = list(v)
            for i in range(0, len(list1)):
                pt = QgsPointXY(list1[i][0], list1[i][1])
                points.append(pt)
            polyline = QgsGeometry.fromPolylineXY(points)
            f = QgsFeature()
            f.setGeometry(polyline)
            linelyr.addFeatures([f])

    CommonLayer(linelyr)
    return


def RemoveAllDrawLineOnMap():
    ''' Remove all features on Line Layer '''
    lineLyr = qgsu.selectLayerByName(Line_lyr)
    if lineLyr is None:
        return
    lineLyr.startEditing()
    lineLyr.dataProvider().truncate()
    CommonLayer(lineLyr)
    return


def RemoveLastDrawPolygonOnMap():
    '''  Remove Last Feature on Polygon Layer '''
    polyLyr = qgsu.selectLayerByName(Polygon_lyr)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    listOfIds = [feat.id() for feat in polyLyr.getFeatures()]
    polyLyr.deleteFeature(listOfIds[-1])
    CommonLayer(polyLyr)
    return


def RemoveLastDrawPointOnMap():
    ''' Remove Last features on Point Layer '''
    pointLyr = qgsu.selectLayerByName(Point_lyr)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    listOfIds = [feat.id() for feat in pointLyr.getFeatures()]
    pointLyr.deleteFeature(listOfIds[-1])
    CommonLayer(pointLyr)
    return


def RemoveAllDrawPointOnMap():
    ''' Remove all features on Point Layer '''
    pointLyr = qgsu.selectLayerByName(Point_lyr)
    if pointLyr is None:
        return
    pointLyr.startEditing()
    pointLyr.dataProvider().truncate()
    CommonLayer(pointLyr)
    return


def RemoveAllDrawPolygonOnMap():
    ''' Remove all features on Polygon Layer '''
    polyLyr = qgsu.selectLayerByName(Polygon_lyr)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    polyLyr.dataProvider().truncate()
    CommonLayer(polyLyr)
    return


def AddDrawPolygonOnMap(poly_coordinates):
    ''' Add Polygon Layer '''
    polyLyr = qgsu.selectLayerByName(Polygon_lyr)
    if polyLyr is None:
        return
    polyLyr.startEditing()
    feature = QgsFeature()
    point = QPointF()
    # create  float polygon --> construcet out of 'point'

    list_polygon = QPolygonF()
    for x in range(0, len(poly_coordinates)):
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


def SetcrtSensorSrc():
    global crtSensorSrc, crtSensorSrc2
    crtSensorSrc = crtSensorSrc2 = 'DEFAULT'


def SetcrtPltTailNum():
    global crtPltTailNum
    crtPltTailNum = 'DEFAULT'


def UpdateFootPrintData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele):
    ''' Update Footprint Values '''
    global crtSensorSrc
    imgSS = packet.ImageSourceSensor
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

            CommonLayer(footprintLyr)
            # 3D Style
            if ele:
                SetDefaultFootprint3DStyle(footprintLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvLayers", "Failed Update FootPrint Layer! : "), str(e))
    return


def UpdateBeamsData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele):
    ''' Update Beams Values '''
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude

    beamsLyr = qgsu.selectLayerByName(Beams_lyr)

    try:
        if all(v is not None for v in [beamsLyr, lat, lon, alt, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]) and all(v >= 2 for v in [len(cornerPointUL), len(cornerPointUR), len(cornerPointLR), len(cornerPointLL)]):
            beamsLyr.startEditing()
            if beamsLyr.featureCount() == 0:

                # UL
                featureUL = QgsFeature()
                featureUL.setAttributes(
                    [lon, lat, alt, cornerPointUL[1], cornerPointUL[0]])
                featureUL.setGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointUL[1], cornerPointUL[0])))
                beamsLyr.addFeatures([featureUL])
                # UR
                featureUR = QgsFeature()
                featureUR.setAttributes(
                    [lon, lat, alt, cornerPointUR[1], cornerPointUR[0]])
                featureUR.setGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointUR[1], cornerPointUR[0])))
                beamsLyr.addFeatures([featureUR])
                # LR
                featureLR = QgsFeature()
                featureLR.setAttributes(
                    [lon, lat, alt, cornerPointLR[1], cornerPointLR[0]])
                featureLR.setGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointLR[1], cornerPointLR[0])))
                beamsLyr.addFeatures([featureLR])
                # LL
                featureLL = QgsFeature()
                featureLL.setAttributes(
                    [lon, lat, alt, cornerPointLL[1], cornerPointLL[0]])
                featureLL.setGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointLL[1], cornerPointLL[0])))
                beamsLyr.addFeatures([featureLL])

            else:
                # UL
                beamsLyr.dataProvider().changeAttributeValues(
                    {1: {0: lon, 1: lat, 2: alt, 3: cornerPointUL[1], 4: cornerPointUL[0]}})
                beamsLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointUL[1], cornerPointUL[0])))})
                # UR
                beamsLyr.dataProvider().changeAttributeValues(
                    {2: {0: lon, 1: lat, 2: alt, 3: cornerPointUR[1], 4: cornerPointUR[0]}})
                beamsLyr.dataProvider().changeGeometryValues(
                    {2: QgsGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointUR[1], cornerPointUR[0])))})
                # LR
                beamsLyr.dataProvider().changeAttributeValues(
                    {3: {0: lon, 1: lat, 2: alt, 3: cornerPointLR[1], 4: cornerPointLR[0]}})
                beamsLyr.dataProvider().changeGeometryValues(
                    {3: QgsGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointLR[1], cornerPointLR[0])))})
                # LL
                beamsLyr.dataProvider().changeAttributeValues(
                    {4: {0: lon, 1: lat, 2: alt, 3: cornerPointLL[1], 4: cornerPointLL[0]}})
                beamsLyr.dataProvider().changeGeometryValues(
                    {4: QgsGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointLL[1], cornerPointLL[0])))})

            CommonLayer(beamsLyr)
            # 3D Style
            if ele:
                SetDefaultBeams3DStyle(beamsLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Beams Layer! : "), str(e))
    return


def UpdateTrajectoryData(packet, ele):
    ''' Update Trajectory Values '''
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude

    trajectoryLyr = qgsu.selectLayerByName(Trajectory_lyr)

    try:
        if all(v is not None for v in [trajectoryLyr, lat, lon, alt]):
            trajectoryLyr.startEditing()
            f = QgsFeature()
            if trajectoryLyr.featureCount() == 0:
                f.setAttributes(
                    [lon, lat, alt])
                f.setGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(lon, lat, alt)))
                trajectoryLyr.addFeatures([f])

            else:
                f_last = trajectoryLyr.getFeature(trajectoryLyr.featureCount())
                f.setAttributes([lon, lat, alt])
                f.setGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(f_last.attribute(0), f_last.attribute(1), f_last.attribute(2))))
                trajectoryLyr.addFeatures([f])

            CommonLayer(trajectoryLyr)
            # 3D Style
            if ele:
                SetDefaultTrajectory3DStyle(trajectoryLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Trajectory Layer! : "), str(e))
    return


def UpdateFrameAxisData(packet, ele):
    ''' Update Frame Axis Values '''
    global crtSensorSrc2

    imgSS = packet.ImageSourceSensor
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    fc_lat = packet.FrameCenterLatitude
    fc_lon = packet.FrameCenterLongitude
    fc_alt = packet.FrameCenterElevation

    frameaxisLyr = qgsu.selectLayerByName(FrameAxis_lyr)

    try:
        if all(v is not None for v in [frameaxisLyr, lat, lon, alt, fc_lat, fc_lon]):
            if(imgSS != crtSensorSrc2):
                SetDefaultFrameAxisStyle(frameaxisLyr, imgSS)
                crtSensorSrc2 = imgSS
            frameaxisLyr.startEditing()
            if frameaxisLyr.featureCount() == 0:
                f = QgsFeature()
                f.setAttributes(
                    [lon, lat, alt, fc_lon, fc_lat, fc_alt])
                f.setGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(fc_lon, fc_lat, fc_alt)))
                frameaxisLyr.addFeatures([f])
            else:
                frameaxisLyr.dataProvider().changeAttributeValues(
                    {1: {0: lon, 1: lat, 2: alt, 3: fc_lon, 4: fc_lat, 5: fc_alt}})
                frameaxisLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry(QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(fc_lon, fc_lat, fc_alt)))})

            CommonLayer(frameaxisLyr)
            # 3D Style
            if ele:
                SetDefaultFrameAxis3DStyle(frameaxisLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Frame axis Layer! : "), str(e))
    return


def UpdateFrameCenterData(packet, ele):
    ''' Update FrameCenter Values '''
    lat = packet.FrameCenterLatitude
    lon = packet.FrameCenterLongitude
    alt = packet.FrameCenterElevation
    if packet.FrameCenterElevation == None:
        alt = 0.0
    
    frameCenterLyr = qgsu.selectLayerByName(FrameCenter_lyr)

    try:
        if all(v is not None for v in [frameCenterLyr, lat, lon, alt]):
            frameCenterLyr.startEditing()

            if frameCenterLyr.featureCount() == 0:
                feature = QgsFeature()
                feature.setAttributes([lon, lat, alt])
                p = QgsPointXY()
                p.set(lon, lat)
                feature.setGeometry(QgsGeometry.fromPointXY(p))
                frameCenterLyr.addFeatures([feature])

            else:
                frameCenterLyr.dataProvider().changeAttributeValues(
                    {1: {0: lon, 1: lat, 2: alt}})

                frameCenterLyr.dataProvider().changeGeometryValues(
                    {1: QgsGeometry.fromPointXY(QgsPointXY(lon, lat))})

            CommonLayer(frameCenterLyr)
            # 3D Style
            if ele:
                SetDefaultFrameCenter3DStyle(frameCenterLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Frame Center Layer! : "), str(e))

    return


def UpdatePlatformData(packet, ele):
    ''' Update PlatForm Values '''
    global crtPltTailNum

    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    PlatformHeading = packet.PlatformHeadingAngle
    platformTailNumber = packet.PlatformTailNumber
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
                feature.setGeometry(QgsPoint(lon, lat, alt))
                platformLyr.addFeatures([feature])

            else:
                platformLyr.dataProvider().changeAttributeValues(
                    {1: {0: lon, 1: lat, 2: alt}})

                platformLyr.dataProvider().changeGeometryValues({1: QgsGeometry(QgsPoint(lon, lat, alt))})

            CommonLayer(platformLyr)
            # 3D Style
            if ele:
                SetDefaultPlatform3DStyle(platformLyr)

    except Exception as e:
        qgsu.showUserAndLogMessage(QCoreApplication.translate(
            "QgsFmvUtils", "Failed Update Platform Layer! : "), str(e))

    return


def CommonLayer(value):
    ''' Common commands Layers '''
    value.commitChanges()
    value.updateExtents()
    iface.layerTreeView().refreshLayerSymbology(value.id())


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


def CreateVideoLayers(ele):
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

        # 3D Style
        if ele:
            SetDefaultFootprint3DStyle(lyr_footprint)

    if qgsu.selectLayerByName(Beams_lyr) is None:
        lyr_beams = newLinesLayer(
            None,
            ["longitude",
             "latitude",
             "altitude",
             "Corner Longitude",
             "Corner Latitude"],
            epsg,
            Beams_lyr, LineZ)
        SetDefaultBeamsStyle(lyr_beams)
        addLayerNoCrsDialog(lyr_beams)
        # 3D Style
        if ele:
            SetDefaultBeams3DStyle(lyr_beams)

    if qgsu.selectLayerByName(Trajectory_lyr) is None:
        lyr_Trajectory = newLinesLayer(
            None,
            ["longitude", "latitude", "altitude"], epsg, Trajectory_lyr, LineZ)
        SetDefaultTrajectoryStyle(lyr_Trajectory)
        addLayerNoCrsDialog(lyr_Trajectory)
        # 3D Style
        if ele:
            SetDefaultTrajectory3DStyle(lyr_Trajectory)

    if qgsu.selectLayerByName(FrameAxis_lyr) is None:
        lyr_frameaxis = newLinesLayer(
            None, ["longitude", "latitude", "altitude", "Corner Longitude", "Corner Latitude", "Corner altitude"], epsg, FrameAxis_lyr, LineZ)
        SetDefaultFrameAxisStyle(lyr_frameaxis)
        addLayerNoCrsDialog(lyr_frameaxis)
        # 3D Style
        if ele:
            SetDefaultFrameAxis3DStyle(lyr_frameaxis)

    if qgsu.selectLayerByName(Platform_lyr) is None:
        lyr_platform = newPointsLayer(
            None,
            ["longitude", "latitude", "altitude"], epsg, Platform_lyr, PointZ)
        SetDefaultPlatformStyle(lyr_platform)
        addLayerNoCrsDialog(lyr_platform)
        # 3D Style
        if ele:
            SetDefaultPlatform3DStyle(lyr_platform)

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
        # 3D Style
        if ele:
            SetDefaultFrameCenter3DStyle(lyr_framecenter)

    if qgsu.selectLayerByName(Line_lyr) is None:
        #         lyr_line = newLinesLayer(
        # None, ["longitude", "latitude", "altitude"], epsg, Line_lyr)
        lyr_line = newLinesLayer(None, [], epsg, Line_lyr)
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
            qgsu.selectLayerByName(FrameAxis_lyr).id())
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


def SetDefaultFootprint3DStyle(layer):
    ''' Platform 3D Symbol '''
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 0, 0))
    material.setAmbient(QColor(255, 0, 0))
    symbol = QgsPolygon3DSymbol()
    symbol.setAltitudeClamping(2)
    symbol.setMaterial(material)

    renderer = QgsVectorLayer3DRenderer()
    renderer.setLayer(layer)
    renderer.setSymbol(symbol)
    layer.setRenderer3D(renderer)
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


def SetDefaultPlatform3DStyle(layer):
    ''' Platform 3D Symbol '''
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 0, 0))
    material.setAmbient(QColor(255, 0, 0))
    symbol = QgsPoint3DSymbol()
    symbol.setShape(1)
    S = {}
    S['radius'] = 20
    symbol.setShapeProperties(S)
    symbol.setAltitudeClamping(2)
    symbol.setMaterial(material)

    renderer = QgsVectorLayer3DRenderer()
    renderer.setLayer(layer)
    renderer.setSymbol(symbol)
    layer.setRenderer3D(renderer)
    return


def SetDefaultTrajectory3DStyle(layer):
    ''' Trajectory 3D Symbol '''
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(0, 0, 255))
    material.setAmbient(QColor(0, 0, 255))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(5)
    symbol.setAltitudeClamping(2)
    symbol.setMaterial(material)

    renderer = QgsVectorLayer3DRenderer()
    renderer.setLayer(layer)
    renderer.setSymbol(symbol)
    layer.setRenderer3D(renderer)
    return


def SetDefaultFrameAxis3DStyle(layer):
    ''' Frame Axis 3D Symbol '''
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(0, 0, 255))
    material.setAmbient(QColor(0, 0, 255))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(5)
    symbol.setAltitudeClamping(2)
    symbol.setMaterial(material)

    renderer = QgsVectorLayer3DRenderer()
    renderer.setLayer(layer)
    renderer.setSymbol(symbol)
    layer.setRenderer3D(renderer)
    return


def SetDefaultBeams3DStyle(layer):
    ''' Beams 3D Symbol '''
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 255, 255))
    material.setAmbient(QColor(255, 255, 255))
    symbol = QgsLine3DSymbol()

    symbol.setWidth(5)
    symbol.setAltitudeClamping(2)
    symbol.setMaterial(material)

    renderer = QgsVectorLayer3DRenderer()
    renderer.setLayer(layer)
    renderer.setSymbol(symbol)
    layer.setRenderer3D(renderer)
    return


def SetDefaultFrameCenterStyle(layer):
    ''' Frame Center Symbol '''
    style = S.getFrameCenterPoint()
    symbol = QgsMarkerSymbol.createSimple(
        {'name': style["NAME"], 'line_color': style["LINE_COLOR"], 'line_width': style["LINE_WIDTH"], 'size': style["SIZE"]})
    renderer = QgsSingleSymbolRenderer(symbol)
    layer.setRenderer(renderer)
    return


def SetDefaultFrameCenter3DStyle(layer):
    ''' Frame Center 3D Symbol '''
    material = QgsPhongMaterialSettings()
    material.setDiffuse(QColor(255, 255, 255))
    material.setAmbient(QColor(255, 255, 255))
    symbol = QgsPoint3DSymbol()
    symbol.setShape(1)
    S = {}
    S['radius'] = 20
    symbol.setShapeProperties(S)
    symbol.setAltitudeClamping(2)
    symbol.setMaterial(material)

    renderer = QgsVectorLayer3DRenderer()
    renderer.setLayer(layer)
    renderer.setSymbol(symbol)
    layer.setRenderer3D(renderer)
    return


def SetDefaultFrameAxisStyle(layer, sensor='DEFAULT'):
    ''' Line Symbol '''
    sensor_style = S.getSensor(sensor)
    style = S.getFrameAxis()
    fill_sym = QgsLineSymbol.createSimple({'color': sensor_style['OUTLINE_COLOR'],
                                           'width': sensor_style['OUTLINE_WIDTH'],
                                           'outline_style': style['OUTLINE_STYLE']})
    renderer = QgsSingleSymbolRenderer(fill_sym)
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


def _toQgsField(f):
    if isinstance(f, QgsField):
        return f
    return QgsField(f[0], TYPE_MAP.get(f[1], QVariant.String))


def newPointsLayer(filename, fields, crs, name=None, geometryType=Point, encoding="utf-8"):
    return newVectorLayer(filename, fields, geometryType, crs, name, encoding)


def newLinesLayer(filename, fields, crs, name=None, geometryType=Line, encoding="utf-8"):
    return newVectorLayer(filename, fields, geometryType, crs, name, encoding)


def newPolygonsLayer(filename, fields, crs, name=None, encoding="utf-8"):
    return newVectorLayer(filename, fields, Polygon, crs, name, encoding)


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
    if isinstance(crs, str):
        crs = QgsCoordinateReferenceSystem(crs)
    if filename is None:
        uri = geometryType
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
