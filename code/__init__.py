# -*- coding: utf-8 -*-
from qgis.utils import iface
from QGIS_FMV.utils.QgsFmvInstaller import CheckDependencies

#CheckDependencies()

def classFactory(iface):
    from .QgsFmv import Fmv
    return Fmv(iface)
