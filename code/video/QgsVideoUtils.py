from QGIS_FMV.utils.QgsFmvUtils import (GetImageWidth,
                                        GetImageHeight)


class VideoUtils(object):

    @staticmethod
    def GetNormalizedWidth(surface):
        return surface.widget.height(
        ) * (GetImageWidth() / GetImageHeight())

    @staticmethod
    def GetInverseMatrix(x, y, gt, surface):
        ''' inverse matrix transformation (lon-lat to video units x,y) '''
        transf = (~gt)([x, y])
        scr_x = (transf[0] / VideoUtils.GetXRatio(surface)) + \
            VideoUtils.GetXBlackZone(surface)
        scr_y = (transf[1] / VideoUtils.GetYRatio(surface)) + \
            VideoUtils.GetYBlackZone(surface)
        return scr_x, scr_y

    @staticmethod
    def GetXRatio(surface):
        ''' ratio between event.x() and real image width on screen. '''
        return GetImageWidth() / (surface.widget.width() - (2 * VideoUtils.GetXBlackZone(surface)))

    @staticmethod
    def GetYRatio(surface):
        ''' ratio between event.y() and real image height on screen. '''
        return GetImageHeight() / (surface.widget.height() - (2 * VideoUtils.GetYBlackZone(surface)))

    @staticmethod
    def GetXBlackZone(surface):
        ''' Return is X in black screen on video '''
        x = 0.0
        if (surface.widget.width() / surface.widget.height()) > (GetImageWidth() / GetImageHeight()):
            x = (surface.widget.width() -
                 (VideoUtils.GetNormalizedWidth(surface))) / 2.0
        return x

    @staticmethod
    def GetNormalizedHeight(surface):
        return surface.widget.width(
        ) / (GetImageWidth() / GetImageHeight())

    @staticmethod
    def GetYBlackZone(surface):
        ''' Return is Y in black screen on video '''
        y = 0.0
        if (surface.widget.width() / surface.widget.height()) < (GetImageWidth() / GetImageHeight()):
            y = (surface.widget.height() -
                 (VideoUtils.GetNormalizedHeight(surface))) / 2.0
        return y
