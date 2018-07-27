# -*- coding: utf-8 -*-
import sys


try:
    sys.path.append(
        "D:\eclipse\plugins\org.python.pydev.core_6.4.3.201807050139\pysrc")
except ImportError:
    None


def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
