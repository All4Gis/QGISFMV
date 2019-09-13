# -*- coding: utf-8 -*-
from qgis.PyQt.QtGui import QImage
from QGIS_FMV.utils.QgsFmvUtils import convertMatToQImage, convertQImageToMat
import numpy as np

try:
    from cv2 import (cvtColor,
                     Canny,
                     COLOR_BGR2LAB,
                     COLOR_LAB2BGR,
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
        '''Gray Image Filter
        @type image: QImage
        @param image:
        @return: QImage
        '''
        return image.convertToFormat(QImage.Format_Grayscale8)

    @staticmethod
    def MirrredFilter(image):
        '''Mirror Horizontal Image Filter
        @type image: QImage
        @param image:
        @return: QImage
        '''
        return image.mirrored(True, False)

    @staticmethod
    def MonoFilter(image):
        '''Mono Image Filter
        @type image: QImage
        @param image:
        @return: QImage
        '''
        return image.convertToFormat(QImage.Format_Mono)

    @staticmethod
    def EdgeFilter(image, sigma=0.33):
        '''Edge Image Filter
        @type image: QImage
        @param image:
        @return: QImage
        '''
        gray = convertQImageToMat(image)
        v = np.median(gray)
        lower = int(max(0, (1.0 - sigma) * v))
        upper = int(min(255, (1.0 + sigma) * v))
        canny = Canny(gray, lower, upper)
        return convertMatToQImage(canny)

    @staticmethod
    def NDVIFilter(image):
        '''NDVI Filter
        @type image: QImage
        @param image:
        @return: QImage
        '''
        original = convertQImageToMat(image)
        lowerLimit = 5

        # First, make containers
        oldHeight, oldWidth = original[:, :, 0].shape
        ndviImage = np.zeros((oldHeight, oldWidth, 3), np.uint8)  # make a blank RGB image

        red = (original[:, :, 2]).astype('float')
        blue = (original[:, :, 0]).astype('float')

        # Perform NDVI calculation
        summ = red + blue
        summ[summ < lowerLimit] = lowerLimit  # do some saturation to prevent low intensity noise

        ndvi = (((red - blue) / (summ) + 1) * 127).astype('uint8')  # the index

        redSat = (ndvi - 128) * 2  # red channel
        bluSat = ((255 - ndvi) - 128) * 2  # blue channel
        redSat[ndvi < 128] = 0  # if the NDVI is negative, no red info
        bluSat[ndvi >= 128] = 0  # if the NDVI is positive, no blue info

        # Red Channel
        ndviImage[:, :, 2] = redSat
        # Blue Channel
        ndviImage[:, :, 0] = bluSat
        # Green Channel
        ndviImage[:, :, 1] = 255 - (bluSat + redSat)

        return convertMatToQImage(ndviImage)

    @staticmethod
    def AutoContrastFilter(image):
        '''Auto Contrast Image Filter
        @type image: QImage
        @param image:
        @return: QImage
        '''
        img = convertQImageToMat(image, cn=4)
        clahe = createCLAHE(clipLimit=4., tileGridSize=(8, 8))
        # convert from BGR to LAB color space
        lab = cvtColor(img, COLOR_BGR2LAB)
        l, a, b = split(lab)  # split on 3 different channels

        l2 = clahe.apply(l)  # apply CLAHE to the L-channel

        lab = merge((l2, a, b))  # merge channels
        invert = cvtColor(lab, COLOR_LAB2BGR)  # convert from LAB to BGR
        return convertMatToQImage(invert)
