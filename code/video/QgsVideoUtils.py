# -*- coding: utf-8 -*-
from QGIS_FMV.utils.QgsFmvUtils import (GetImageWidth,
                                        GetImageHeight,
                                        GetSensor,
                                        GetLine3DIntersectionWithDEM,
                                        GetFrameCenter,
                                        hasElevationModel,
                                        GetGCPGeoTransform)

from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from osgeo import gdal
import numpy as np
try:
    from pydevd import *
except ImportError:
    None


class VideoUtils(object):

    @staticmethod
    def GetNormalizedWidth(surface):
        '''Calculate normalized Width
        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return: double
        '''
        try:
            return surface.widget.height(
            ) * (GetImageWidth() / GetImageHeight())
        except ZeroDivisionError:
            return 0.0

    @staticmethod
    def GetInverseMatrix(x, y, gt, surface):
        ''' inverse matrix transformation (lon-lat to video units x,y) '''
        gt = GetGCPGeoTransform()
        imagepoint = np.array(np.dot(np.linalg.inv(gt), [x, y, 1]))
        scalar = imagepoint[2]
        ximage = imagepoint[0]/scalar
        yimage = imagepoint[1]/scalar
        scr_x = (ximage / VideoUtils.GetXRatio(surface)) + \
            VideoUtils.GetXBlackZone(surface)
        scr_y = (yimage / VideoUtils.GetYRatio(surface)) + \
            VideoUtils.GetYBlackZone(surface)
        return scr_x, scr_y

    @staticmethod
    def GetXRatio(surface):
        '''ratio between event.x() and real image width on screen.
        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return: double
        '''
        return GetImageWidth() / (surface.widget.width() - (2 * VideoUtils.GetXBlackZone(surface)))

    @staticmethod
    def GetYRatio(surface):
        '''ratio between event.y() and real image height on screen.
        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return: double
        '''
        return GetImageHeight() / (surface.widget.height() - (2 * VideoUtils.GetYBlackZone(surface)))

    @staticmethod
    def GetXBlackZone(surface):
        '''Return is X in black screen on video
        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return: double
        '''
        x = 0.0
        try:
            if (surface.widget.width() / surface.widget.height()) > (GetImageWidth() / GetImageHeight()):
                x = (surface.widget.width() - 
                     (VideoUtils.GetNormalizedWidth(surface))) / 2.0
        except ZeroDivisionError:
            None
        return x

    @staticmethod
    def GetNormalizedHeight(surface):
        '''Calculate normalized Height
        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return: double
        '''
        return surface.widget.width(
        ) / (GetImageWidth() / GetImageHeight())

    @staticmethod
    def GetYBlackZone(surface):
        '''Return is Y in black screen on video
        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return: double
        '''
        y = 0.0
        try:
            if (surface.widget.width() / surface.widget.height()) < (GetImageWidth() / GetImageHeight()):
                y = (surface.widget.height() - 
                     (VideoUtils.GetNormalizedHeight(surface))) / 2.0
        except ZeroDivisionError:
            None
        return y

    @staticmethod
    def IsPointOnScreen(x, y, surface):
        '''determines if a clicked point lands on the image (False if lands on the
            black borders or outside)
        @type x: int
        @param x:

        @type y: int
        @param y:

        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return: bool
         '''
        res = True
        try:
            if x > (VideoUtils.GetNormalizedWidth(surface) + VideoUtils.GetXBlackZone(surface)) or x < VideoUtils.GetXBlackZone(surface):
                res = False
            if y > (VideoUtils.GetNormalizedHeight(surface) + VideoUtils.GetYBlackZone(surface)) or y < VideoUtils.GetYBlackZone(surface):
                res = False
        except ZeroDivisionError:
            None
        return res

    @staticmethod
    def GetTransf(event, surface):
        '''Return video coordinates to map coordinates
        @type event: QMouseEvent
        @param event:
        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return:
        '''
        gt = GetGCPGeoTransform()
        #return gt([(event.x() - VideoUtils.GetXBlackZone(surface)) * VideoUtils.GetXRatio(surface), (event.y() - VideoUtils.GetYBlackZone(surface)) * VideoUtils.GetYRatio(surface)])
        imagepoint = [(event.x() - VideoUtils.GetXBlackZone(surface)) * VideoUtils.GetXRatio(surface), (event.y() - VideoUtils.GetYBlackZone(surface)) * VideoUtils.GetYRatio(surface), 1]
        worldpoint = np.array(np.dot(gt, imagepoint))
        scalar = worldpoint[2]
        xworld = worldpoint[0]/scalar
        yworld = worldpoint[1]/scalar
                
        return xworld, yworld
    
    @staticmethod
    def GetPointCommonCoords(event, surface):
        ''' Common functon for get coordinates on mousepressed
        @type event: QMouseEvent
        @param event:

        @type surface: QAbstractVideoSurface
        @param surface: Abstract video surface
        @return:
        '''
        transf = VideoUtils.GetTransf(event, surface)
        targetAlt = GetFrameCenter()[2]

        Longitude = float(round(transf[1], 5))
        Latitude = float(round(transf[0], 5))
        Altitude = float(round(targetAlt, 0))

        if hasElevationModel():
            sensor = GetSensor()
            target = [transf[0], transf[1], targetAlt]
            projPt = GetLine3DIntersectionWithDEM(sensor, target)
            if projPt:
                Longitude = float(round(projPt[1], 5))
                Latitude = float(round(projPt[0], 5))
                Altitude = float(round(projPt[2], 0))
        return Longitude, Latitude, Altitude
