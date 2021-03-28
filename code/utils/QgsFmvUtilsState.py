from qgis.utils import iface as defIface


class globalVariablesState:

    def __init__(self):
        self.iface = defIface
        self.centerMode = 2
        self.gcornerPointUL = None
        self.gcornerPointUR = None
        self.gcornerPointLR = None
        self.gcornerPointLL = None
        self.gframeCenterLat = None
        self.gframeCenterLon = None
        self.geotransform_affine = None
        self.geotransform = None
        self.affineT = None
        self.transform = None
        self.groupName = None

        self.frameCenterElevation = None
        self.sensorLatitude = None
        self.sensorLongitude = None
        self.sensorTrueAltitude = [None] * 13
        self.xSize = 0
        self.ySize = 0

    def setGroupName(self, name):
        self.groupName = name

    def getGroupName(self):
        return self.groupName

    def setFrameCenterElevation(self, fe):
        self.frameCenterElevation = fe

    def getFrameCenterElevation(self):
        return self.frameCenterElevation

    def setSensorLatitude(self, sl):
        self.sensorLatitude = sl

    def getSensorLatitude(self):
        return self.sensorLatitude

    def setSensorLongitude(self, sl):
        self.sensorLongitude = sl

    def getSensorLongitude(self):
        return self.sensorLongitude

    def setSensorTrueAltitude(self, ta):
        self.sensorTrueAltitude = ta

    def getSensorTrueAltitude(self):
        return self.sensorTrueAltitude

    def setIface(self, iface):
        self.iface = iface

    def getIface(self):
        return self.iface

    def setCenterMode(self, mode):
        self.centerMode = mode

    def getCenterMode(self):
        return self.centerMode

    def setCornerUL(self, cornerPointUL):
        self.gcornerPointUL = cornerPointUL

    def getCornerUL(self):
        return self.gcornerPointUL

    def setCornerUR(self, cornerPointUR):
        self.gcornerPointUR = cornerPointUR

    def getCornerUR(self):
        return self.gcornerPointUR

    def setCornerLR(self, cornerPointLR):
        self.gcornerPointLR = cornerPointLR

    def getCornerLR(self):
        return self.gcornerPointLR

    def setCornerLL(self, cornerPointLL):
        self.gcornerPointLL = cornerPointLL

    def getCornerLL(self):
        return self.gcornerPointLL

    def setFrameCenter(self, frameCenterLat, frameCenterLon):
        self.gframeCenterLat = frameCenterLat
        self.gframeCenterLon = frameCenterLon

    def getFrameCenterLat(self):
        return self.gframeCenterLat

    def getFrameCenterLon(self):
        return self.gframeCenterLon

    def setAffineTransform(self, at):
        self.affineT = at

    def getAffineTransform(self):
        return self.affineT

    def setTransform(self, t):
        self.transform = t

    def getTransform(self):
        return self.transform

    def setXSize(self, xs):
        self.xSize = xs

    def getXSize(self):
        return self.xSize

    def setYSize(self, ys):
        self.ySize = ys

    def getYSize(self):
        return self.ySize
