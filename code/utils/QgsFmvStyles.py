  # -*- coding: utf-8 -*-
from qgis.PyQt.QtGui import QColor, qRgba


class FmvLayerStyles(object):

    # sensor holder
    S = {}

    # platform holder
    P = {}

    # trajectory holder
    T = {}

    # beam holder
    B = {}

    # frame center holder
    F = {}

    # frame axis holder
    FA = {}

    # drawings Point holder
    DP = {}

    # drawings Line holder
    DL = {}

    # drawing Polygons holder
    DPL = {}

    #
    # SENSOR STYLES (based on meta attribute "Image Source Sensor")
    #

    # Default
    S['DEFAULT'] = {}
    S['DEFAULT']['COLOR'] = '126,217,255,60'
    S['DEFAULT']['OUTLINE_COLOR'] = '#5392fa'
    S['DEFAULT']['OUTLINE_STYLE'] = 'solid'
    S['DEFAULT']['OUTLINE_WIDTH'] = '2'

    # IR sensor
    S['IR'] = {}
    S['IR']['COLOR'] = '234, 135, 8, 60'
    S['IR']['OUTLINE_COLOR'] = '#ba340f'
    S['IR']['OUTLINE_STYLE'] = 'solid'
    S['IR']['OUTLINE_WIDTH'] = '2'

    # EOW sensor
    S['EOW'] = {}
    S['EOW']['COLOR'] = '126, 217, 255, 60'
    S['EOW']['OUTLINE_COLOR'] = '#5392fa'
    S['EOW']['OUTLINE_STYLE'] = 'solid'
    S['EOW']['OUTLINE_WIDTH'] = '2'

    # BLEND sensor
    S['BLEND'] = {}
    S['BLEND']['COLOR'] = '255, 255, 255, 60'
    S['BLEND']['OUTLINE_COLOR'] = '#a7a7a7'
    S['BLEND']['OUTLINE_STYLE'] = 'solid'
    S['BLEND']['OUTLINE_WIDTH'] = '2'

    # Short Wave Infra Red sensor
    S['EON_SWIR'] = {}
    S['EON_SWIR']['COLOR'] = '234, 135, 8, 60'
    S['EON_SWIR']['OUTLINE_COLOR'] = '#ba340f'
    S['EON_SWIR']['OUTLINE_STYLE'] = 'solid'
    S['EON_SWIR']['OUTLINE_WIDTH'] = '2'

    # EON sensor
    S['EON'] = {}
    S['EON']['COLOR'] = '249, 167, 62, 60'
    S['EON']['OUTLINE_COLOR'] = '#ba340f'
    S['EON']['OUTLINE_STYLE'] = 'solid'
    S['EON']['OUTLINE_WIDTH'] = '2'

    # FLIR SS380-HD HDIR sensor
    S['FLIR SS380-HD HDIR'] = {}
    S['FLIR SS380-HD HDIR']['COLOR'] = '234, 135, 8, 60'
    S['FLIR SS380-HD HDIR']['OUTLINE_COLOR'] = '#ba340f'
    S['FLIR SS380-HD HDIR']['OUTLINE_STYLE'] = 'solid'
    S['FLIR SS380-HD HDIR']['OUTLINE_WIDTH'] = '2'

    # SP sensor
    S['SP'] = {}
    S['SP']['COLOR'] = '219, 204, 0, 60'
    S['SP']['OUTLINE_COLOR'] = '#9E9300'
    S['SP']['OUTLINE_STYLE'] = 'solid'
    S['SP']['OUTLINE_WIDTH'] = '2'
    #
    # PLATFORM STYLES (based on meta attribute platform)
    #

    # Default
    P['DEFAULT'] = {}
    P['DEFAULT']['NAME'] = ':/imgFMV/images/platforms/platform_default.svg'
    P['DEFAULT']['OUTLINE'] = '255, 255, 255, 60'
    P['DEFAULT']['OUTLINE_WIDTH'] = '1'
    P['DEFAULT']['SIZE'] = '18'

    # Super Puma Platform
    P['Super Puma TH06'] = {}
    P['Super Puma TH06']['NAME'] = ':/imgFMV/images/platforms/plat_super_puma.svg'
    P['Super Puma TH06']['OUTLINE'] = '255, 255, 255, 60'
    P['Super Puma TH06']['OUTLINE_WIDTH'] = '1'
    P['Super Puma TH06']['SIZE'] = '18'

    # N97826 Platform
    P['N97826'] = {}
    P['N97826']['NAME'] = ':/imgFMV/images/platforms/plat_N97826.svg'
    P['N97826']['OUTLINE'] = '255, 255, 255, 60'
    P['N97826']['OUTLINE_WIDTH'] = '1'
    P['N97826']['SIZE'] = '18'

    # VH-ZXX Platform
    P['VH-ZXX'] = {}
    P['VH-ZXX']['NAME'] = ':/imgFMV/images/platforms/plat_VH-ZXX.svg'
    P['VH-ZXX']['OUTLINE'] = '255, 255, 255, 60'
    P['VH-ZXX']['OUTLINE_WIDTH'] = '1'
    P['VH-ZXX']['SIZE'] = '18'

    # ADS15 Platform
    P['ADS15'] = {}
    P['ADS15']['NAME'] = ':/imgFMV/images/platforms/plat_ADS15.svg'
    P['ADS15']['OUTLINE'] = '255, 255, 255, 60'
    P['ADS15']['OUTLINE_WIDTH'] = '1'
    P['ADS15']['SIZE'] = '18'

    #
    # FRAMECENTER POINT STYLES
    #
    F['DEFAULT'] = {}
    F['DEFAULT']['NAME'] = 'cross'
    F['DEFAULT']['LINE_COLOR'] = '#000000'
    F['DEFAULT']['LINE_WIDTH'] = '0'
    F['DEFAULT']['SIZE'] = '10'

    #
    # FRAME AXIS STYLES
    #
    FA['DEFAULT'] = {}
    FA['DEFAULT']['OUTLINE_WIDTH'] = '2'
    FA['DEFAULT']['OUTLINE_STYLE'] = 'dash'

    #
    # TRAJECTORY STYLES
    #
    T['DEFAULT'] = {}
    T['DEFAULT']['NAME'] = 'dash blue'
    T['DEFAULT']['COLOR'] = '#0000ff'
    T['DEFAULT']['WIDTH'] = '2'
    T['DEFAULT']['customdash'] = '3;2'
    T['DEFAULT']['use_custom_dash'] = '1'

    #
    # BEAM STYLES
    #
    B['DEFAULT'] = {}
    B['DEFAULT']['COLOR'] = qRgba(138, 138, 138, 180)

    #
    # DRAWINGS POINT STYLES
    #
    DP['DEFAULT'] = {}
    DP['DEFAULT']['NAME'] = 'cross'
    DP['DEFAULT']['LINE_COLOR'] = '#DC143C'
    DP['DEFAULT']['LINE_WIDTH'] = '1'
    DP['DEFAULT']['SIZE'] = '10'
    DP['DEFAULT']['LABEL_FONT'] = 'Arial'
    DP['DEFAULT']['LABEL_FONT_SIZE'] = 12
    DP['DEFAULT']['LABEL_FONT_COLOR'] = '#DC143C'
    DP['DEFAULT']['LABEL_SIZE'] = 12
    DP['DEFAULT']['LABEL_BUFFER_COLOR'] = 'white'

    #
    # DRAWINGS LINE STYLES
    #
    DL['DEFAULT'] = {}
    DL['DEFAULT']['COLOR'] = QColor.fromRgb(252, 215, 108)
    DL['DEFAULT']['WIDTH'] = 1

    #
    # DRAWINGS POLYGONS STYLES
    #
    DPL['DEFAULT'] = {}
    DPL['DEFAULT']['COLOR'] = '252, 215, 108, 100'
    DPL['DEFAULT']['OUTLINE_COLOR'] = '#FCD76C'
    DPL['DEFAULT']['OUTLINE_STYLE'] = 'solid'
    DPL['DEFAULT']['OUTLINE_WIDTH'] = '1'

    @staticmethod
    def getPlatform(name):
        style = None
        try:
            style = FmvLayerStyles.P[name]
        except Exception:
            style = FmvLayerStyles.P['DEFAULT']
        return style

    @staticmethod
    def getSensor(name):
        style = None
        try:
            style = FmvLayerStyles.S[name]
        except Exception:
            style = FmvLayerStyles.S['DEFAULT']
        return style

    @staticmethod
    def getTrajectory(name):
        style = None
        try:
            style = FmvLayerStyles.T[name]
        except Exception:
            style = FmvLayerStyles.T['DEFAULT']
        return style

    @staticmethod
    def getBeam(name):
        style = None
        try:
            style = FmvLayerStyles.B[name]
        except Exception:
            style = FmvLayerStyles.B['DEFAULT']
        return style

    @staticmethod
    def getDrawingPoint():
        style = FmvLayerStyles.DP['DEFAULT']
        return style

    @staticmethod
    def getFrameCenterPoint():
        style = FmvLayerStyles.F['DEFAULT']
        return style

    @staticmethod
    def getFrameAxis():
        style = FmvLayerStyles.FA['DEFAULT']
        return style

    @staticmethod
    def getDrawingLine():
        style = FmvLayerStyles.DL['DEFAULT']
        return style

    @staticmethod
    def getDrawingPolygon():
        style = FmvLayerStyles.DPL['DEFAULT']
        return style
