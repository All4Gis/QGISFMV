# -*- coding: utf-8 -*-
import sys
from QGIS_FMV.utils.QgsFmvUtils import install_pip_requirements

try:
    sys.path.append(
        "D:\eclipse\plugins\org.python.pydev.core_6.4.4.201807281807\pysrc")
    from pydevd import *
except ImportError:
    None

try:
    import cv2
    import xml.etree.cElementTree as etree
    from homography import from_points
except ImportError:
    try:
        install_pip_requirements()
    except ImportError:
        None
finally:
    try:
        import cv2
        import xml.etree.cElementTree as etree
        from homography import from_points
    except ImportError:
        None


def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
