# -*- coding: utf-8 -*-
import os
from os.path import dirname, abspath
from qgis.PyQt.QtGui import QColor, QFont, QPolygonF, QPen, QPainter, QBrush, qRgba
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtCore import QCoreApplication, QPointF, Qt
#from qgis.PyQt.QtCore.Qt import *

from configparser import ConfigParser
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from qgis.PyQt.QtCore import QVariant, QSettings
from qgis.core import (QgsPalLayerSettings,
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
                       QgsLineString,
                       QgsRenderContext
                       )

from qgis.utils import iface
from QGIS_FMV.utils.QgsFmvStyles import FmvLayerStyles as S
from kadas._kadasgui import *
from itertools import groupby
#from qgis._3d import (QgsPhongMaterialSettings,
#                      QgsVectorLayer3DRenderer,
#                      QgsLine3DSymbol,
#                      QgsPoint3DSymbol,
#                      QgsPolygon3DSymbol)

try:
    from pydevd import *
except ImportError:
    None

parser = ConfigParser()
parser.read(os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini'))

#Platform_lyr = parser['LAYERS']['Platform_lyr']
#Beams_lyr = parser['LAYERS']['Beams_lyr']
#Footprint_lyr = parser['LAYERS']['Footprint_lyr']
#FrameCenter_lyr = parser['LAYERS']['FrameCenter_lyr']
#FrameAxis_lyr = parser['LAYERS']['FrameAxis_lyr']
#Point_lyr = parser['LAYERS']['Point_lyr']
#Line_lyr = parser['LAYERS']['Line_lyr']
#Polygon_lyr = parser['LAYERS']['Polygon_lyr']
#Trajectory_lyr = parser['LAYERS']['Trajectory_lyr']

frames_g = parser['LAYERS']['frames_g']
epsg = parser['LAYERS']['epsg']
groupName = None

encoding = "utf-8"

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

platformMarker=''
frameCenterMarker=''
frameAxisMarker=''
footprintMarker=''
trajectoryMarker=''
lastTrajectoryEle=''
linesEle=[]
pointsEle=[]
pointsLblEle=[]
polygonsEle=[]
beamMarkerUR=''
beamMarkerUL=''
beamMarkerLL=''
beamMarkerLR=''



def AddDrawPointOnMap(pointIndex, Longitude, Latitude, Altitude):
    '''  add pin point on the map '''
    global pointsEle
    global pointsLblEle
    
    #RemoveAllDrawPointOnMap()
    
    p = KadasPointItem( QgsCoordinateReferenceSystem("EPSG:4326"), KadasPointItem.ICON_CROSS )
    p.setZIndex( 100 )
    p.setPosition(KadasItemPos.fromPoint(QgsPointXY(Longitude, Latitude)))
    KadasMapCanvasItemManager.addItem( p )
    pointsEle.append(p)

    textItem = KadasTextItem( QgsCoordinateReferenceSystem("EPSG:4326") )
    textItem.setText( str(pointIndex) );
    textItem.setPosition( KadasItemPos.fromPoint(QgsPointXY(Longitude, Latitude)) )
    textItem.setAnchorX( 0 )
    textItem.setAnchorY( 1.0 )
    KadasMapCanvasItemManager.addItem( textItem )
    pointsLblEle.append(textItem)
    
    SetDefaultPointStyle(p, textItem)
    
    


def AddDrawLineOnMap(drawLines):
    '''  add Line on the map '''
    global linesEle
    
    RemoveAllDrawLineOnMap()
    
    for k, v in groupby(drawLines, key=lambda x: x == [None, None, None]):
        points = []
        if k is False:
            list1 = list(v)
            for i in range(0, len(list1)):
                pt = QgsPointXY(list1[i][0], list1[i][1])
                points.append(pt)
            l = KadasLineItem(QgsCoordinateReferenceSystem("EPSG:4326"))
            SetDefaultLineStyle(l)
            KadasMapCanvasItemManager.addItem( l )
            l.setZIndex( 90 )
            geom = QgsGeometry.fromPolylineXY(points)
            l.addPartFromGeometry(geom.get())
            linesEle.append(l)
    return

def GetMapItems():
    global platformMarker, frameCenterMarker, footprintMarker
    
    return {
        "platform": platformMarker,
        "framecenter": frameCenterMarker,
        "footprint": footprintMarker
    }
    

def RemoveAllDrawings():

    global crtSensorSrc, crtPltTailNum, platformMarker, frameCenterMarker, trajectoryMarker, frameAxisMarker, footprintMarker, beamMarkerUR, beamMarkerUL, beamMarkerLL, beamMarkerLR, linesEle, pointsEle, pointsLblEle, polygonsEle, lastTrajectoryEle
    #qgsu.showUserAndLogMessage("", "Clearing all mapItems drawings.")
    for ele in [platformMarker, frameCenterMarker, trajectoryMarker, frameAxisMarker, footprintMarker, beamMarkerUR, beamMarkerUL, beamMarkerLL, beamMarkerLR]:
        if ele != '':
            KadasMapCanvasItemManager.removeItem(ele)
    
    for ele in linesEle:
        KadasMapCanvasItemManager.removeItem(ele)
    
    for ele in pointsEle:
        KadasMapCanvasItemManager.removeItem(ele)
    
    for ele in pointsLblEle:
        KadasMapCanvasItemManager.removeItem(ele)
    
    for ele in polygonsEle:
        KadasMapCanvasItemManager.removeItem(ele)
    
    crtSensorSrc, crtPltTailNum, lastTrajectoryEle, platformMarker, frameCenterMarker, trajectoryMarker, frameAxisMarker, footprintMarker, beamMarkerUR, beamMarkerUL, beamMarkerLL, beamMarkerLR = 'DEFAULT', 'DEFAULT', '', '', '', '', '', '', '', '', '', ''
    linesEle, pointsEle, pointsLblEle, polygonsEle = [], [], [], []

def RemoveAllDrawLineOnMap():
    ''' Remove all features on Line Layer '''
    global linesEle
        
    for ele in linesEle:
        KadasMapCanvasItemManager.removeItem(ele)
    
    linesEle = []
    

def RemoveLastDrawPolygonOnMap():
    '''  Remove Last Feature on Polygon Layer '''
    global polygonsEle
    
    if polygonsEle:
        KadasMapCanvasItemManager.removeItem(polygonsEle.pop())


def RemoveLastDrawPointOnMap():
    ''' Remove Last features on Point Layer '''
    global pointsEle, pointsLblEle
    
    if pointsEle:
        KadasMapCanvasItemManager.removeItem(pointsEle.pop())
        
    if pointsLblEle:
        KadasMapCanvasItemManager.removeItem(pointsLblEle.pop())


def RemoveAllDrawPointOnMap():
    ''' Remove all features on Point Layer '''
    global pointsEle, pointsLblEle
    
    for ele in pointsEle:
        KadasMapCanvasItemManager.removeItem(ele)
        
    for ele in pointsLblEle:
        KadasMapCanvasItemManager.removeItem(ele)
    
    pointsEle = []
    pointsLblEle = []
    


def RemoveAllDrawPolygonOnMap():
    ''' Remove all features on Polygon Layer '''
    global polygonsEle
    for ele in polygonsEle:
        KadasMapCanvasItemManager.removeItem(ele)
    
    polygonsEle = []
    

def AddDrawPolygonOnMap(poly_coordinates):
    ''' Add Polygon Layer '''
    global polygonsEle
    
    #RemoveAllDrawPolygonOnMap()
    
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
        'EPSG:4326'), _layerreg.transformContext())
    if (area_wsg84.sourceCrs().isGeographic()):
        area_wsg84.setEllipsoid(
            area_wsg84.sourceCrs().ellipsoidAcronym())

    # Calculate Centroid
    try:
        centroid = feature.geometry().centroid().asPoint()
    except Exception:
        return False

    feature.setAttributes([centroid.x(), centroid.y(
    ), 0.0, area_wsg84.measurePolygon(geomP.asPolygon()[0])])
    
    p = KadasPolygonItem(QgsCoordinateReferenceSystem("EPSG:4326"))
    SetDefaultPolygonStyle(p)
    p.setZIndex(90)
    p.addPartFromGeometry(geomP.get())
    KadasMapCanvasItemManager.addItem(p)
    polygonsEle.append(p)
    return True


def SetcrtSensorSrc():
    ''' Set Style based on Sensor type '''
    global crtSensorSrc, crtSensorSrc2
    crtSensorSrc = crtSensorSrc2 = 'DEFAULT'


def SetcrtPltTailNum():
    ''' Set Style based on Platform Type Number '''
    global crtPltTailNum
    crtPltTailNum = 'DEFAULT'


def UpdateFootPrintData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele):
    ''' Update Footprint Values '''
    global crtSensorSrc, groupName, footprintMarker
    imgSS = packet.ImageSourceSensor
    
    if all(v is not None for v in [cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]) and all(v >= 2 for v in [len(cornerPointUL), len(cornerPointUR), len(cornerPointLR), len(cornerPointLL)]):
        
        if footprintMarker == '':
            footprintMarker = KadasPolygonItem(QgsCoordinateReferenceSystem("EPSG:4326"))
            KadasMapCanvasItemManager.addItem( footprintMarker )
            footprintMarker.setZIndex( 90 )
        
        if(imgSS != crtSensorSrc):
            SetDefaultFootprintStyle(footprintMarker, imgSS)
            crtSensorSrc = imgSS
            
        footprintMarker.clear()
        geom = QgsGeometry.fromPolygonXY([[
                    QgsPointXY(cornerPointUL[1],
                               cornerPointUL[0]),
                    QgsPointXY(
                        cornerPointUR[1], cornerPointUR[0]),
                    QgsPointXY(
                        cornerPointLR[1], cornerPointLR[0]),
                    QgsPointXY(
                        cornerPointLL[1], cornerPointLL[0]),
                    QgsPointXY(cornerPointUL[1], cornerPointUL[0])]])
        
        footprintMarker.addPartFromGeometry(geom.get())
    
    return


def UpdateBeamsData(packet, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL, ele):
    global beamMarkerUR, beamMarkerUL, beamMarkerLL, beamMarkerLR
    
    ''' Update Beams Values '''
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    if all(v is not None for v in [lat, lon, alt, cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL]) and all(v >= 2 for v in [len(cornerPointUL), len(cornerPointUR), len(cornerPointLR), len(cornerPointLL)]):
        
        #ul
        if beamMarkerUL == '':
            beamMarkerUL = KadasLineItem(QgsCoordinateReferenceSystem("EPSG:4326"))
            SetDefaultBeamsStyle(beamMarkerUL)
            KadasMapCanvasItemManager.addItem( beamMarkerUL )
            beamMarkerUL.setZIndex( 80 )
        
        beamMarkerUL.clear()
        geom = QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointUL[1], cornerPointUL[0]))
        beamMarkerUL.addPartFromGeometry(geom)
        
        #ur
        if beamMarkerUR == '':
            beamMarkerUR = KadasLineItem(QgsCoordinateReferenceSystem("EPSG:4326"))
            SetDefaultBeamsStyle(beamMarkerUR)
            KadasMapCanvasItemManager.addItem( beamMarkerUR )
            beamMarkerUR.setZIndex( 80 )
        
        beamMarkerUR.clear()
        geom = QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointUR[1], cornerPointUR[0]))
        beamMarkerUR.addPartFromGeometry(geom)
        
        #lr
        if beamMarkerLR == '':
            beamMarkerLR = KadasLineItem(QgsCoordinateReferenceSystem("EPSG:4326"))
            SetDefaultBeamsStyle(beamMarkerLR)
            KadasMapCanvasItemManager.addItem( beamMarkerLR )
            beamMarkerLR.setZIndex( 80 )
        
        beamMarkerLR.clear()
        geom = QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointLR[1], cornerPointLR[0]))
        beamMarkerLR.addPartFromGeometry(geom)
        
        #ll
        if beamMarkerLL == '':
            beamMarkerLL = KadasLineItem(QgsCoordinateReferenceSystem("EPSG:4326"))
            SetDefaultBeamsStyle(beamMarkerLL)
            KadasMapCanvasItemManager.addItem( beamMarkerLL )
            beamMarkerLL.setZIndex( 80 )
        
        beamMarkerLL.clear()
        geom = QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(cornerPointLL[1], cornerPointLL[0]))
        beamMarkerLL.addPartFromGeometry(geom)
        
    return


def UpdateTrajectoryData(packet, ele):
    global trajectoryMarker, lastTrajectoryEle
    ''' Update Trajectory Values '''
    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    if all(v is not None for v in [lat, lon, alt]):
    
        if lastTrajectoryEle != '':
            if trajectoryMarker == '':
                trajectoryMarker = KadasLineItem(QgsCoordinateReferenceSystem("EPSG:4326"))
                KadasMapCanvasItemManager.addItem( trajectoryMarker )
                SetDefaultTrajectoryStyle(trajectoryMarker)
                trajectoryMarker.setZIndex( 80 )
            
            geom = QgsLineString(QgsPoint(lastTrajectoryEle.SensorLongitude, lastTrajectoryEle.SensorLatitude, alt), QgsPoint(lon, lat, alt))
            trajectoryMarker.addPartFromGeometry(geom)
        
        lastTrajectoryEle = packet
        
    return


#def UpdateFrameAxisData(packet, ele):
def UpdateFrameAxisData(imgSS, sensor, framecenter, ele):
    ''' Update Frame Axis Values '''
    global crtSensorSrc2, groupName, frameAxisMarker

    lat = sensor[0]
    lon = sensor[1]
    alt = sensor[2]
    fc_lat = framecenter[0]
    fc_lon = framecenter[1]
    fc_alt = framecenter[2]
    
    if all(v is not None for v in [lat, lon, alt, fc_lat, fc_lon]):
    
        if frameAxisMarker == '':
            frameAxisMarker = KadasLineItem(QgsCoordinateReferenceSystem("EPSG:4326"))
            KadasMapCanvasItemManager.addItem( frameAxisMarker )
            SetDefaultFrameAxisStyle(frameAxisMarker)
            frameAxisMarker.setZIndex( 80 )
        
        frameAxisMarker.clear()
        geom = QgsLineString(QgsPoint(lon, lat, alt), QgsPoint(fc_lon, fc_lat, fc_alt))
        frameAxisMarker.addPartFromGeometry(geom)
    
    return


def UpdateFrameCenterData(pt, ele):
    global frameCenterMarker
    ''' Update FrameCenter Values '''
    lat = pt[0]
    lon = pt[1]
    alt = pt[2]
    
    if alt is None:
        alt = 0.0
    
    if all(v is not None for v in [lat, lon, alt]):
    
        if frameCenterMarker == '':
            frameCenterMarker = KadasPointItem( QgsCoordinateReferenceSystem("EPSG:4326") )
            SetDefaultFrameCenterStyle(frameCenterMarker)
            #mPosMarker->setIconFill( Qt::blue )
            #mPosMarker->setIconOutline( QPen( Qt::blue ) )
            frameCenterMarker.setZIndex( 100 )
            KadasMapCanvasItemManager.addItem( frameCenterMarker )
        
    frameCenterMarker.setPosition(KadasItemPos.fromPoint(QgsPointXY(lon,lat)))

    return


def UpdatePlatformData(packet, ele):
    ''' Update PlatForm Values '''
    global crtPltTailNum, groupName, platformMarker

    lat = packet.SensorLatitude
    lon = packet.SensorLongitude
    alt = packet.SensorTrueAltitude
    PlatformHeading = packet.PlatformHeadingAngle
    platformTailNumber = packet.PlatformTailNumber
    
    if all(v is not None for v in [lat, lon, alt, PlatformHeading]):
    
        if platformMarker == '':
            platformMarker = KadasSymbolItem( QgsCoordinateReferenceSystem("EPSG:4326" ))
            platformMarker.setZIndex( 100 )
            platformMarker.setup( ":/imgFMV/images/platforms/platform_default.svg", 0.5, 0.5, 50, 50 )
            KadasMapCanvasItemManager.addItem( platformMarker )
        
        if platformTailNumber != crtPltTailNum:
            SetDefaultPlatformStyle(platformMarker, platformTailNumber)
            crtPltTailNum = platformTailNumber
                
        platformMarker.setPosition(KadasItemPos.fromPoint(QgsPointXY(lon,lat)))
        platformMarker.setAngle(-float(PlatformHeading))

    return


def CommonLayer(value):
    return
    ''' Common commands Layers '''
    value.commitChanges()
    value.updateExtents()
    iface.layerTreeView().refreshLayerSymbology(value.id())


def CreateGroupByName(name=frames_g):
    ''' Create Group if not exist '''
    global groupName
    root = _layerreg.layerTreeRoot()
    videogroup = root.findGroup(groupName)
    group = videogroup.findGroup(name)
    if group is None:
        # group = root.insertGroup(-1, name)  # Insert on bottom
        group = videogroup.insertGroup(-1, name)  # Insert on bottom
        # Unchecked visibility
        group.setItemVisibilityCheckedRecursive(False)
        group.setExpanded(False)
    return


def RemoveGroupByName(name=frames_g):
    ''' Remove Group if not exist '''
    root = _layerreg.layerTreeRoot()
    group = root.findGroup(name)
    if group is not None:
        for child in group.children():
            dump = child.name()
            _layerreg.removeMapLayer(dump.split("=")[-1].strip())
        root.removeChildNode(group)
    return


def CreateVideoLayers(ele, name):
    ''' Create Video Layers '''
    global groupName
    groupName = name
    
    #return
    #
    #if qgsu.selectLayerByName(Footprint_lyr, groupName) is None:
    #    lyr_footprint = newPolygonsLayer(
    #        None,
    #        ["Corner Longitude Point 1",
    #         "Corner Latitude Point 1",
    #         "Corner Longitude Point 2",
    #         "Corner Latitude Point 2",
    #         "Corner Longitude Point 3",
    #         "Corner Latitude Point 3",
    #         "Corner Longitude Point 4",
    #         "Corner Latitude Point 4"],
    #        epsg,
    #        Footprint_lyr)
    #    SetDefaultFootprintStyle(lyr_footprint)
    #    addLayerNoCrsDialog(lyr_footprint, group=groupName)
    #
    #    # 3D Style
    #    if ele:
    #        SetDefaultFootprintStyle(lyr_footprint)
    #
    #if qgsu.selectLayerByName(Beams_lyr, groupName) is None:
    #    lyr_beams = newLinesLayer(
    #        None,
    #        ["longitude",
    #         "latitude",
    #         "altitude",
    #         "Corner Longitude",
    #         "Corner Latitude"],
    #        epsg,
    #        Beams_lyr, LineZ)
    #    SetDefaultBeamsStyle(lyr_beams)
    #    addLayerNoCrsDialog(lyr_beams, group=groupName)
    #    # 3D Style
    #    if ele:
    #        SetDefaultBeamsStyle(lyr_beams)
    #
    #if qgsu.selectLayerByName(Trajectory_lyr, groupName) is None:
    #    lyr_Trajectory = newLinesLayer(
    #        None,
    #        ["longitude", "latitude", "altitude"], epsg, Trajectory_lyr, LineZ)
    #    SetDefaultTrajectoryStyle(lyr_Trajectory)
    #    addLayerNoCrsDialog(lyr_Trajectory, group=groupName)
    #    # 3D Style
    #    if ele:
    #        SetDefaultTrajectoryStyle(lyr_Trajectory)
    #
    #if qgsu.selectLayerByName(FrameAxis_lyr, groupName) is None:
    #    lyr_frameaxis = newLinesLayer(
    #        None, ["longitude", "latitude", "altitude", "Corner Longitude", "Corner Latitude", "Corner altitude"], epsg, FrameAxis_lyr, LineZ)
    #    SetDefaultFrameAxisStyle(lyr_frameaxis)
    #    addLayerNoCrsDialog(lyr_frameaxis, group=groupName)
    #    # 3D Style
    #    if ele:
    #        SetDefaultFrameAxisStyle(lyr_frameaxis)
    #
    #if qgsu.selectLayerByName(Platform_lyr, groupName) is None:
    #    lyr_platform = newPointsLayer(
    #        None,
    #        ["longitude", "latitude", "altitude"], epsg, Platform_lyr, PointZ)
    #    SetDefaultPlatformStyle(lyr_platform)
    #    addLayerNoCrsDialog(lyr_platform, group=groupName)
    #    # 3D Style
    #    if ele:
    #        SetDefaultPlatformStyle(lyr_platform)
    #
    #if qgsu.selectLayerByName(Point_lyr, groupName) is None:
    #    lyr_point = newPointsLayer(
    #        None, ["number", "longitude", "latitude", "altitude"], epsg, Point_lyr)
    #    SetDefaultPointStyle(lyr_point)
    #    addLayerNoCrsDialog(lyr_point, group=groupName)
    #
    #if qgsu.selectLayerByName(FrameCenter_lyr, groupName) is None:
    #    lyr_framecenter = newPointsLayer(
    #        None, ["longitude", "latitude", "altitude"], epsg, FrameCenter_lyr)
    #    SetDefaultFrameCenterStyle(lyr_framecenter)
    #    addLayerNoCrsDialog(lyr_framecenter, group=groupName)
    #    # 3D Style
    #    if ele:
    #        SetDefaultFrameCenterStyle(lyr_framecenter)
    #
    #if qgsu.selectLayerByName(Line_lyr, groupName) is None:
    #    #         lyr_line = newLinesLayer(
    #    # None, ["longitude", "latitude", "altitude"], epsg, Line_lyr)
    #    lyr_line = newLinesLayer(None, [], epsg, Line_lyr)
    #    SetDefaultLineStyle(lyr_line)
    #    addLayerNoCrsDialog(lyr_line, group=groupName)
    #
    #if qgsu.selectLayerByName(Polygon_lyr, groupName) is None:
    #    lyr_polygon = newPolygonsLayer(
    #        None, ["Centroid_longitude", "Centroid_latitude", "Centroid_altitude", "Area"], epsg, Polygon_lyr)
    #    SetDefaultPolygonStyle(lyr_polygon)
    #    addLayerNoCrsDialog(lyr_polygon, group=groupName)
    #
    #QApplication.processEvents()
    #return


def ExpandLayer(layer, value=True):
    '''Collapse/Expand layer'''
    ltl = _layerreg.layerTreeRoot().findLayer(layer.id())
    ltl.setExpanded(value)
    QApplication.processEvents()
    return


def SetDefaultFootprintStyle(mapItem, sensor='DEFAULT'):
    ''' Footprint Symbol '''
    style = S.getSensor(sensor)
    
    mPen = QPen()
    mPen.setColor(QColor(style['OUTLINE_COLOR']))
    mPen.setWidth(int(style['OUTLINE_WIDTH']))
    mapItem.setOutline( mPen )
    
    b = QBrush()
    tmp = style['COLOR'].split(',')

    c = qRgba(int(tmp[0]), int(tmp[1]), int(tmp[2]), int(tmp[3]))
    b.setColor(QColor.fromRgba(c))
    b.setStyle(Qt.SolidPattern)
    mapItem.setFill(b)
    


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


def SetDefaultTrajectoryStyle(mapItem):
    ''' Trajectory Symbol '''
    style = S.getTrajectory('DEFAULT')
    
    mPen = QPen()
    mPen.setColor(QColor(style['COLOR']))
    mPen.setWidth(int(style['WIDTH']))
    mPen.setStyle(Qt.DashDotLine)

    mapItem.setOutline( mPen )
    

def SetDefaultPlatformStyle(mapItem, platform='DEFAULT'):
    ''' Platform Symbol '''
    style = S.getPlatform(platform)    
    mapItem.setup(style["NAME"], 0.5, 0.5, 110, 110 )
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


def SetDefaultFrameCenterStyle(mapItem):
    ''' Frame Center Symbol '''
    style = S.getFrameCenterPoint()
    
    if style['NAME'] == 'cross':
        mapItem.setIconType(KadasPointItem.ICON_CROSS)
    
    mPen = QPen()
    mPen.setColor(QColor(style['LINE_COLOR']))
    mPen.setWidth(int(style['LINE_WIDTH']))
    
    mapItem.setIconOutline(mPen)
    mapItem.setIconSize(int(style['SIZE']))

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


def SetDefaultFrameAxisStyle(mapItem, sensor='DEFAULT'):
    ''' Line Symbol '''
    sensor_style = S.getSensor(sensor)
    style = S.getFrameAxis()

    mPen = QPen()
    mPen.setColor(QColor(sensor_style['OUTLINE_COLOR']))
    mPen.setWidth(int(style['OUTLINE_WIDTH']))
    mPen.setStyle(Qt.DashLine)

    mapItem.setOutline( mPen );


def SetDefaultPointStyle(mapItem, textItem):
    ''' Point Symbol '''
    style = S.getDrawingPoint()
    
    mPen = QPen()
    mPen.setColor(QColor(style['LINE_COLOR']))
    mPen.setWidth(int(style['LINE_WIDTH']))
    
    mapItem.setIconOutline(mPen)
    mapItem.setIconSize(int(style['SIZE']))
    
    textItem.setOutlineColor(QColor(style['LABEL_FONT_COLOR']))
    textItem.setFillColor( QColor(style['LABEL_FONT_COLOR']) )
    
    font = QFont()
    font.setFamily( style['LABEL_FONT'] )
    font.setPointSize( style['LABEL_FONT_SIZE'] )
    textItem.setFont( font )
    
    return


def SetDefaultLineStyle(mapItem):
    ''' Line Symbol '''
    style = S.getDrawingLine()
    mPen = QPen()
    mPen.setColor(style['COLOR'])
    mPen.setWidth(style['WIDTH'])
    mapItem.setOutline( mPen )
    

def SetDefaultPolygonStyle(mapItem):
    ''' Polygon Symbol '''
    style = S.getDrawingPolygon()
        
    mPen = QPen()
    mPen.setColor(QColor(style['OUTLINE_COLOR']))
    mPen.setWidth(int(style['OUTLINE_WIDTH']))
    mapItem.setOutline( mPen )
    
    b = QBrush()
    tmp = style['COLOR'].split(',')

    c = qRgba(int(tmp[0]), int(tmp[1]), int(tmp[2]), int(tmp[3]))
    b.setColor(QColor.fromRgba(c))
    b.setStyle(Qt.SolidPattern)
    mapItem.setFill(b)

def SetDefaultBeamsStyle(mapItem, beam='DEFAULT'):
    ''' Beams Symbol'''
    style = S.getBeam(beam)
    
    mPen = QPen( QColor.fromRgba(style['COLOR']), 1)
    #mapItem.setFill( QBrush( color ) )
    mapItem.setOutline( mPen );
    return

# TODO : Update layer symbology if draw color change?
# def UpdateStylesDrawLayers(NameSpace):
#     ''' Update Symbology Drawing Layers '''
#     s = QSettings()
#     pointLyr = qgsu.selectLayerByName(Point_lyr, groupName)
#     if pointLyr is None:
#         return
#
#     style = S.getDrawingPoint()
#     LINE_COLOR = s.value(NameSpace + "/Options/drawings/points/pen")
#
#     symbol = QgsMarkerSymbol.createSimple(
#         {'name': style["NAME"],
#          'line_color': LINE_COLOR.name(),
#          'line_width': s.value(NameSpace + "/Options/drawings/points/width"),
#          'size': style["SIZE"]})
#
#     renderer = QgsSingleSymbolRenderer(symbol)
#     pointLyr.setRenderer(renderer)
#     CommonLayer(pointLyr)
#
#     linelyr = qgsu.selectLayerByName(Line_lyr, groupName)
#     if linelyr is None:
#         return
#
#     style = S.getDrawingLine()
#     symbol = linelyr.renderer().symbol()
#
#     COLOR = s.value(NameSpace + "/Options/drawings/lines/pen")
#
#     symbol.setColor(COLOR.name())
#     symbol.setWidth(s.value(NameSpace + "/Options/drawings/lines/width"))
#     CommonLayer(linelyr)
#
#     polyLyr = qgsu.selectLayerByName(Polygon_lyr, groupName)
#     if polyLyr is None:
#         return
#
#     style = S.getDrawingPolygon()
#
#     OUTLINE_COLOR = s.value(NameSpace + "/Options/drawings/polygons/pen")
#     COLOR = s.value(NameSpace + "/Options/drawings/polygons/brush")
#
#     fill_sym = QgsFillSymbol.createSimple({'color': COLOR.name(),
#                                        'outline_color': OUTLINE_COLOR.name(),
#                                        'outline_style': style['OUTLINE_STYLE'],
#                                        'outline_width': s.value(NameSpace + "/Options/drawings/polygons/width")})
#
#     renderer = QgsSingleSymbolRenderer(fill_sym)
#     polyLyr.setRenderer(renderer)
#     CommonLayer(polyLyr)
#     QApplication.processEvents()
#     return


def addLayer(layer, loadInLegend=True, group=None, isSubGroup=False):
    """
    Add one or several layers to the QGIS session and layer registry.
    @param layer: The layer object or list with layers  to add the QGIS layer registry and session.
    @param loadInLegend: True if this layer should be added to the legend.
    :return: The added layer
    """
    global groupName
    if not hasattr(layer, "__iter__"):
        layer = [layer]
    if group is not None:
        _layerreg.addMapLayers(layer, False)
        root = _layerreg.layerTreeRoot()
        if isSubGroup:
            vg = root.findGroup(groupName)
            g = vg.findGroup(group)
            g.insertChildNode(0, QgsLayerTreeLayer(layer[0]))
        else:
            g = root.findGroup(group)
            g.insertChildNode(0, QgsLayerTreeLayer(layer[0]))
    else:
        _layerreg.addMapLayers(layer, loadInLegend)
    return layer


def addLayerNoCrsDialog(layer, loadInLegend=True, group=None, isSubGroup=False):
    '''
    Tries to add a layer from layer object
    Same as the addLayer method, but it does not ask for CRS, regardless of current
    configuration in QGIS settings
    '''
    settings = QSettings()
    prjSetting3 = settings.value('/Projections/defaultBehavior')
    settings.setValue('/Projections/defaultBehavior', '')
    layer = addLayer(layer, loadInLegend, group, isSubGroup)
    settings.setValue('/Projections/defaultBehavior', prjSetting3)
    QApplication.processEvents()
    return layer


def _toQgsField(f):
    ''' Create QgsFiel '''
    if isinstance(f, QgsField):
        return f
    return QgsField(f[0], TYPE_MAP.get(f[1], QVariant.String))


def newPointsLayer(filename, fields, crs, name=None, geometryType=Point, encoding=encoding):
    ''' Create new Point Layer '''
    return newVectorLayer(filename, fields, geometryType, crs, name, encoding)


def newLinesLayer(filename, fields, crs, name=None, geometryType=Line, encoding=encoding):
    ''' Create new Line Layer '''
    return newVectorLayer(filename, fields, geometryType, crs, name, encoding)


def newPolygonsLayer(filename, fields, crs, name=None, encoding=encoding):
    ''' Create new Polygon Layer '''
    return newVectorLayer(filename, fields, Polygon, crs, name, encoding)


def newVectorLayer(filename, fields, geometryType, crs, name=None, encoding=encoding):
    '''
    Creates a new vector layer
    @param filename: The filename to store the file. The extensions determines the type of file.
    If extension is not among the supported ones, a shapefile will be created and the file will
    get an added '.shp' to its path.
    If the filename is None, a memory layer will be created
    @param fields: the fields to add to the layer. Accepts a QgsFields object or a list of tuples (field_name, field_type)
    Accepted field types are basic Python types str, float, int and bool
    @param geometryType: The type of geometry of the layer to create.
    @param crs: The crs of the layer to create. Accepts a QgsCoordinateSystem object or a string with the CRS authId.
    @param encoding: The layer encoding
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
            extension = str(key)
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
