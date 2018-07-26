# -*- coding: utf-8 -*-
import sys


try:
    sys.path.append(
        "D:\eclipse\plugins\org.python.pydev_6.2.0.201711281614\pysrc")
except ImportError:
    None


def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
