# -*- coding: utf-8 -*-
from PyQt5.QtGui import QImage
from QGIS_FMV.utils.QgsFmvUtils import convertMatToQImage, convertQImageToMat
import numpy as np

try:
    from cv2 import (cvtColor,
                     Canny,
                     COLOR_BGR2LAB,
                     COLOR_LAB2BGR,
                     COLOR_GRAY2RGB,
                     cvtColor,
                     createCLAHE,
                     merge,
                     split,
                     cvtColor)
except ImportError:
    None

try:
    from pydevd import *
except ImportError:
    None


class VideoFilters():
    """ VideoFilters Class """

    @staticmethod
    def GrayFilter(image):
        ''' Gray Image Filter '''
        return image.convertToFormat(QImage.Format_Grayscale8)

    @staticmethod
    def MirrredFilter(image):
        ''' Mirror Horizontal Image Filter '''
        return image.mirrored(True, False)

    @staticmethod
    def MonoFilter(image):
        ''' Mono Image Filter '''
        return image.convertToFormat(QImage.Format_Mono)

    @staticmethod
    def EdgeFilter(image):
        ''' Edge Image Filter '''
        gray = convertQImageToMat(image)
        canny = Canny(gray, 100, 150)
        return convertMatToQImage(canny)

    @staticmethod
    def NDVIFilter(image):
        ''' NDVI Filter '''
        original = convertQImageToMat(image)
        lowerLimit = 5

        #First, make containers
        oldHeight, oldWidth = original[:,:,0].shape; 
        ndviImage = np.zeros((oldHeight, oldWidth, 3), np.uint8) #make a blank RGB image

        red = (original[:,:,2]).astype('float')
        blue = (original[:,:,0]).astype('float')

        #Perform NDVI calculation
        summ = red+blue
        summ[summ<lowerLimit] = lowerLimit #do some saturation to prevent low intensity noise

        ndvi = (((red-blue)/(summ)+1)*127).astype('uint8')  #the index

        redSat = (ndvi-128)*2  #red channel
        bluSat = ((255-ndvi)-128)*2 #blue channel
        redSat[ndvi<128] = 0; #if the NDVI is negative, no red info
        bluSat[ndvi>=128] = 0; #if the NDVI is positive, no blue info

        #Red Channel
        ndviImage[:,:,2] = redSat
        #Blue Channel
        ndviImage[:,:,0] = bluSat
        #Green Channel
        ndviImage[:,:,1] = 255-(bluSat+redSat)

        return convertMatToQImage(ndviImage)

    @staticmethod
    def AutoContrastFilter(image):
        ''' Auto Contrast Image Filter '''
        img = convertQImageToMat(image)
        clahe = createCLAHE(clipLimit=4., tileGridSize=(40, 40))
        # convert from BGR to LAB color space
        lab = cvtColor(img, COLOR_BGR2LAB)
        l, a, b = split(lab)  # split on 3 different channels

        l2 = clahe.apply(l)  # apply CLAHE to the L-channel

        lab = merge((l2, a, b))  # merge channels
        invert = cvtColor(lab, COLOR_LAB2BGR)  # convert from LAB to BGR
        return convertMatToQImage(invert)

#     @staticmethod
#     def ThresholdingFilter(image):
#         from cv2  import threshold,THRESH_BINARY
#         gray= convertQImageToMat(VideoFilters.GrayFilter(image))
#         ret,th = threshold(gray,127,255,THRESH_BINARY)
#         return convertMatToQImage(th)

#     @staticmethod
#     def EqualizeContrastFilter(image):
#         from cv2  import adaptiveThreshold,ADAPTIVE_THRESH_MEAN_C,THRESH_BINARY,getStructuringElement,MORPH_ELLIPSE,MORPH_CLOSE,morphologyEx,NORM_MINMAX,normalize
#         import numpy as np
#
#         gray= convertQImageToMat(VideoFilters.GrayFilter(image))
#         kernel1 = getStructuringElement(MORPH_ELLIPSE,(20,20))
#         close = morphologyEx(gray,MORPH_CLOSE,kernel1)
#         div = np.float32(gray)/(close)
#         res = np.uint8(normalize(div,div,0,255,NORM_MINMAX))
#         return convertMatToQImage(res)
