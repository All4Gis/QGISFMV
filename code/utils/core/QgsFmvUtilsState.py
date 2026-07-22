# -*- coding: utf-8 -*-
"""Telemetry / georeferencing field holder (base for VideoSession)."""


def _default_iface():
    try:
        from qgis.utils import iface as defIface

        return defIface
    except ImportError:
        return None


class globalVariablesState:
    """Global video state."""

    def __init__(self):
        self.iface = _default_iface()
        self.centerMode = 2
        self.gcornerPointUL = None
        self.gcornerPointUR = None
        self.gcornerPointLR = None
        self.gcornerPointLL = None
        self.gframeCenterLat = None
        self.gframeCenterLon = None
        self.affineT = None
        self.transform = None
        self.groupName = None
        self.frameCenterElevation = None
        self.sensorLatitude = None
        self.sensorLongitude = None
        self.sensorTrueAltitude = [None] * 13
        self.xSize = 0
        self.ySize = 0

    def setGroupName(self, v):
        """Set the active layer-tree group name."""
        self.groupName = v

    def setFrameCenterElevation(self, v):
        """Set the frame center elevation in metres."""
        self.frameCenterElevation = v

    def getFrameCenterElevation(self):
        """Return the frame center elevation in metres."""
        return self.frameCenterElevation

    def setSensorLatitude(self, v):
        """Set the sensor latitude (degrees)."""
        self.sensorLatitude = v

    def getSensorLatitude(self):
        """Return the sensor latitude (degrees)."""
        return self.sensorLatitude

    def setSensorLongitude(self, v):
        """Set the sensor longitude (degrees)."""
        self.sensorLongitude = v

    def getSensorLongitude(self):
        """Return the sensor longitude (degrees)."""
        return self.sensorLongitude

    def setSensorTrueAltitude(self, v):
        """Set the sensor true altitude array."""
        self.sensorTrueAltitude = v

    def getSensorTrueAltitude(self):
        """Return the sensor true altitude array."""
        return self.sensorTrueAltitude

    def setIface(self, v):
        """Set the QGIS iface reference."""
        self.iface = v

    def getIface(self):
        """Return the QGIS iface reference."""
        return self.iface

    def setCenterMode(self, v):
        """Set the frame-center display mode."""
        self.centerMode = v

    def getCenterMode(self):
        """Return the frame-center display mode."""
        return self.centerMode

    def setCornerUL(self, v):
        """Set the upper-left footprint corner."""
        self.gcornerPointUL = v

    def getCornerUL(self):
        """Return the upper-left footprint corner."""
        return self.gcornerPointUL

    def setCornerUR(self, v):
        """Set the upper-right footprint corner."""
        self.gcornerPointUR = v

    def getCornerUR(self):
        """Return the upper-right footprint corner."""
        return self.gcornerPointUR

    def setCornerLR(self, v):
        """Set the lower-right footprint corner."""
        self.gcornerPointLR = v

    def getCornerLR(self):
        """Return the lower-right footprint corner."""
        return self.gcornerPointLR

    def setCornerLL(self, v):
        """Set the lower-left footprint corner."""
        self.gcornerPointLL = v

    def getCornerLL(self):
        """Return the lower-left footprint corner."""
        return self.gcornerPointLL

    def setFrameCenter(self, lat, lon):
        """Set the frame center latitude and longitude."""
        self.gframeCenterLat = lat
        self.gframeCenterLon = lon

    def getFrameCenterLat(self):
        """Return the frame center latitude."""
        return self.gframeCenterLat

    def getFrameCenterLon(self):
        """Return the frame center longitude."""
        return self.gframeCenterLon

    def setAffineTransform(self, v):
        """Set the affine geotransform coefficients."""
        self.affineT = v

    def getAffineTransform(self):
        """Return the affine geotransform coefficients."""
        return self.affineT

    def setTransform(self, v):
        """Set the GDAL GeoTransform tuple."""
        self.transform = v

    def getTransform(self):
        """Return the GDAL GeoTransform tuple."""
        return self.transform

    def setXSize(self, v):
        """Set the video frame width in pixels."""
        self.xSize = v

    def getXSize(self):
        """Return the video frame width in pixels."""
        return self.xSize

    def setYSize(self, v):
        """Set the video frame height in pixels."""
        self.ySize = v

    def getYSize(self):
        """Return the video frame height in pixels."""
        return self.ySize
