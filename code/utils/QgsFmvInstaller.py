  # -*- coding: utf-8 -*-
from configparser import ConfigParser
import os, sys
from os.path import dirname, abspath
import pathlib
import platform
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox, QProgressBar, QInputDialog, QLineEdit
from qgis.core import Qgis as QGis, QgsApplication
from qgis.utils import iface

plugin_dir = pathlib.Path(__file__).parent.parent
sys.path.append(plugin_dir)

parser = ConfigParser(delimiters=(':'), comment_prefixes='/', allow_no_value=True)
fileConfig = os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini')
parser.read(fileConfig)

DemConf = parser['GENERAL']['DTM_file']

try:
    import winreg
except ImportError:
    None
try:
    from pydevd import *
except ImportError:
    None

windows = platform.system() == 'Windows'

if windows:
    ffmpegConf = os.path.join(QgsApplication.applicationDirPath(), '..', 'opt', 'ffmpeg')
else:
    ffmpegConf = '/usr/bin'

DemGlobal = "http://www.gisandbeers.com/RRSS/Cartografia/DEM-Mundial.rar"

def CheckDependencies():
    ''' complete windows installation '''
    if not IsLavFilters():
        iface.messageBar().pushMessage(QCoreApplication.translate("QgsFmvInstaller", "FMV: Missing Lav Filters"), QGis.Critical, 10)

    if not IsFFMPEG():
        iface.messageBar().pushMessage(QCoreApplication.translate("QgsFmvInstaller", "FMV: Missing FFMPEG"), QGis.Critical, 10)

    if not isDem():
        iface.messageBar().pushMessage(QCoreApplication.translate("QgsFmvInstaller", "FMV: Missing DTM"), QGis.Critical, 10)

    try:
        import homography
    except ImportError:
        iface.messageBar().pushMessage(QCoreApplication.translate("QgsFmvInstaller", "FMV: Missing python-homography"), QGis.Critical, 10)
    try:
        import cv2
    except ImportError:
        iface.messageBar().pushMessage(QCoreApplication.translate("QgsFmvInstaller", "FMV: Missing python-opencv"), QGis.Critical, 10)

    # try:
    #     import matplotlib
    # except ImportError:
    #     iface.messageBar().pushMessage(QCoreApplication.translate("QgsFmvInstaller", "FMV: Missing python-matplotlib"), QGis.Critical, 10)
    return


def isDem():
    ''' Check if Dem is present '''
    return os.path.isfile(DemConf)

def IsLavFilters():
    ''' Check if LavFilters is present '''
    if windows:
        software_list = WinSoftwareInstalled(winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY) + WinSoftwareInstalled(winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY) + WinSoftwareInstalled(winreg.HKEY_CURRENT_USER, 0)
        if not any('LAV Filters' in software['name'] for software in software_list):
            # does not exist
            return False
    elif apt:
        cache = apt.Cache()
        cache.open()
        try:
            print("lav filters")
            return cache["gst123"].is_installed
        except Exception:
            # does not exist
            return False
    return True


def IsFFMPEG():
    ''' Chech if FFMPEG is present '''
    if not os.path.isdir(ffmpegConf):
        return False
    if windows:
        if not os.path.isfile(os.path.join(ffmpegConf, 'ffmpeg.exe')):
            return False
    else:
        if not os.path.isfile(os.path.join(ffmpegConf, 'ffmpeg')):
            return False
    return True


def WinSoftwareInstalled(hive, flag):
    aReg = winreg.ConnectRegistry(None, hive)
    aKey = winreg.OpenKey(aReg, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                          0, winreg.KEY_READ | flag)

    count_subkey = winreg.QueryInfoKey(aKey)[0]

    software_list = []

    for i in range(count_subkey):
        software = {}
        try:
            asubkey_name = winreg.EnumKey(aKey, i)
            asubkey = winreg.OpenKey(aKey, asubkey_name)
            software['name'] = winreg.QueryValueEx(asubkey, "DisplayName")[0]

            try:
                software['version'] = winreg.QueryValueEx(asubkey, "DisplayVersion")[0]
            except EnvironmentError:
                software['version'] = 'undefined'
            try:
                software['publisher'] = winreg.QueryValueEx(asubkey, "Publisher")[0]
            except EnvironmentError:
                software['publisher'] = 'undefined'
            software_list.append(software)
        except EnvironmentError:
            continue

    return software_list
