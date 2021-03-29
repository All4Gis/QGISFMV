class InteractionState(object):
    """ Interaction Video Player Class """

    def __init__(self):
        self.pointDrawer = False
        self.measureDistance = False
        self.measureArea = False
        self.lineDrawer = False
        self.polygonDrawer = False
        self.magnifier = False
        self.stamp = False
        self.objectTracking = False
        self.censure = False
        self.HandDraw = False

    def clear(self):
        """ Reset Interaction variables """
        self.__init__()


class FilterState(object):
    """ Filters State Video Player Class """

    def __init__(self):
        self.contrastFilter = False
        self.monoFilter = False
        self.MirroredHFilter = False
        self.edgeDetectionFilter = False
        self.grayColorFilter = False
        self.invertColorFilter = False
        self.NDVI = False

    def clear(self):
        """ Reset Filter variables """
        self.__init__()

    def hasFiltersSlow(self):
        """ Check if video has Slow filters aplicated """
        if True in (self.contrastFilter, self.edgeDetectionFilter, self.NDVI):
            return True
        return False
