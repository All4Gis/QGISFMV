from PyQt5.QtGui import QColor, qRgba


class FmvLayerStyles(object):

    #sensor holder
    S = {}

    #platform holder
    P = {}

    #trajectory holder
    T = {}

    #beam holder
    B = {}

    #drawings holder
    D = {}

    #
    # SENSOR STYLES (based on meta attribute "Image Source Sensor")
    #

    #Default
    S['DEFAULT'] = {} 
    S['DEFAULT']['COLOR'] = '126, 217, 255, 60'
    S['DEFAULT']['OUTLINE_COLOR'] = '#5392fa'
    S['DEFAULT']['OUTLINE_STYLE'] = 'solid'
    S['DEFAULT']['OUTLINE_WIDTH'] = '1'

    #IR sensor
    S['IR'] = {} 
    S['IR']['COLOR'] = '234, 135, 8, 60'
    S['IR']['OUTLINE_COLOR'] = '#ba340f'
    S['IR']['OUTLINE_STYLE'] = 'solid'
    S['IR']['OUTLINE_WIDTH'] = '1'

    #EOW sensor
    S['EOW'] = {} 
    S['EOW']['COLOR'] = '126, 217, 255, 60'
    S['EOW']['OUTLINE_COLOR'] = '#5392fa'
    S['EOW']['OUTLINE_STYLE'] = 'solid'
    S['EOW']['OUTLINE_WIDTH'] = '1'

    #BLEND sensor
    S['BLEND'] = {} 
    S['BLEND']['COLOR'] = '255, 255, 255, 60'
    S['BLEND']['OUTLINE_COLOR'] = '#a7a7a7'
    S['BLEND']['OUTLINE_STYLE'] = 'solid'
    S['BLEND']['OUTLINE_WIDTH'] = '1'

    #Short Wave Infra Red sensor
    S['EON_SWIR'] = {} 
    S['EON_SWIR']['COLOR'] = '234, 135, 8, 60'
    S['EON_SWIR']['OUTLINE_COLOR'] = '#ba340f'
    S['EON_SWIR']['OUTLINE_STYLE'] = 'solid'
    S['EON_SWIR']['OUTLINE_WIDTH'] = '1'

    #
    # PLATFORM STYLES (based on meta attribute platform)
    #

    #Default
    P['DEFAULT'] = {} 
    P['DEFAULT']['NAME'] = ':/imgFMV/images/platform.svg'
    P['DEFAULT']['OUTLINE'] = '255, 255, 255, 60'
    P['DEFAULT']['OUTLINE_WIDTH'] = '1'
    P['DEFAULT']['SIZE'] = '18'

    #Super Puma Platform
    P['Super Puma TH06'] = {}
    P['Super Puma TH06']['NAME'] = '../apps/qgis/python/plugins/QGIS_FMV/images/plat_super_puma.svg'
    P['Super Puma TH06']['OUTLINE'] = '255, 255, 255, 60'
    P['Super Puma TH06']['OUTLINE_WIDTH'] = '1'
    P['Super Puma TH06']['SIZE'] = '18'

    #
    # TRAJECTORY STYLES
    #
    T['DEFAULT'] = {}
    T['DEFAULT']['COLOR'] = QColor.fromRgb(0, 0, 255)
    T['DEFAULT']['WIDTH'] = 1

    #
    # BEAM STYLES
    #
    B['DEFAULT'] = {}
    B['DEFAULT']['COLOR'] = qRgba(138, 138, 138, 180)

    #
    # DRAWINGS STYLES
    #
    D['DEFAULT'] = {}
    D['DEFAULT']['NAME'] = 'cross'
    D['DEFAULT']['LINE_COLOR'] = '#FF0000'
    D['DEFAULT']['LINE_WIDTH'] = '1'
    D['DEFAULT']['SIZE'] = '4'


    @staticmethod
    def getPlatform(name):
        style = None
        try:
            style = FmvLayerStyles.P[name]
        except:
            style = FmvLayerStyles.P['DEFAULT']
        return style

    @staticmethod
    def getSensor(name):
        style = None
        try:
            style = FmvLayerStyles.S[name]
        except:
            style = FmvLayerStyles.S['DEFAULT']
        return style

    @staticmethod
    def getTrajectory(name):
        style = None
        try:
            style = FmvLayerStyles.T[name]
        except:
            style = FmvLayerStyles.T['DEFAULT']
        return style

    @staticmethod
    def getBeam(name):
        style = None
        try:
            style = FmvLayerStyles.B[name]
        except:
            style = FmvLayerStyles.B['DEFAULT']
        return style

    @staticmethod
    def getDrawingPoint():
        style = FmvLayerStyles.D['DEFAULT']
        return style
