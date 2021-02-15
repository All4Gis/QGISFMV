  # -*- coding: utf-8 -*-
from configparser import ConfigParser
import os
import sys
from os.path import dirname, abspath
import pathlib
import platform
from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import QMessageBox, QProgressBar, QInputDialog, QLineEdit
from qgis.core import Qgis as QGis, QgsApplication
from qgis.utils import iface
from subprocess import Popen, PIPE
from urllib.request import urlretrieve, build_opener, install_opener
import zipfile

import requests
import subprocess
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu

plugin_dir = pathlib.Path(__file__).parent.parent
sys.path.append(plugin_dir)

parser = ConfigParser(delimiters=(':'), comment_prefixes='/', allow_no_value=True)
fileConfig = os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini')
parser.read(fileConfig)

ffmpegConf = parser['GENERAL']['ffmpeg']
DemConf = parser['GENERAL']['DTM_file']

try:
    import winreg
except ImportError:
    None
try:
    import apt
except ImportError:
    None
try:
    from pydevd import *
except ImportError:
    None

windows = platform.system() == 'Windows'

# Download link
LavFilters = "https://github.com/Nevcairiel/LAVFilters/releases/download/0.74.1/LAVFilters-0.74.1-Installer.exe"

# 64 Bits
if platform.machine().endswith('64'):
    FFMPEG = "https://ffmpeg.zeranoe.com/builds/win64/static/ffmpeg-20190502-7eba264-win64-static.zip"
# 32 Bits
else:
    FFMPEG = "https://ffmpeg.zeranoe.com/builds/win32/static/ffmpeg-20190502-7eba264-win32-static.zip"

DemGlobal = "http://www.gisandbeers.com/RRSS/Cartografia/ETOPO1.zip"

progress = QProgressBar()
progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

opener = build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36')]
install_opener(opener)

def reporthook(blocknum, blocksize, totalsize):
    ''' Url retrieve progress '''
    readsofar = blocknum * blocksize
    if totalsize > 0:
        percent = readsofar * 1e2 / totalsize
        progress.setValue(int(percent))


def WindowsInstaller():
    ''' complete windows installation '''
    if not IsLavFilters():
        ''' lAV Filters '''
        buttonReply = qgsu.CustomMessage("QGIS FMV",
                                         QCoreApplication.translate("QgsFmvInstaller", """<b>Missing python dependency</b>"""),
                                         QCoreApplication.translate("QgsFmvInstaller", "Do you want install Lav Filters?"),
                                         icon="Information")
        if buttonReply == QMessageBox.Yes:

            progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Downloading LAV Filters...")
            progressMessageBar.layout().addWidget(progress)
            iface.messageBar().pushWidget(progressMessageBar, QGis.Info)

            # Install Lav Filter
            filename = 'LavFilters.exe'
            urlretrieve(LavFilters, filename, reporthook)
            process = Popen(filename, stdout=PIPE, creationflags=0x08000000)
            process.wait()
            os.remove(filename)
            iface.messageBar().clearWidgets()

    if not IsFFMPEG():
        ''' FFMPEG Lib '''
        buttonReply = qgsu.CustomMessage("QGIS FMV",
                                         QCoreApplication.translate("QgsFmvInstaller", """<b>Missing FFMPEG dependency</b>"""),
                                         QCoreApplication.translate("QgsFmvInstaller", "Do you want install FFMPEG?"),
                                         icon="Information")
        if buttonReply == QMessageBox.Yes:
            # Download FFMPEG # Prevent HTTP Error 403: Forbidden
            progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Downloading FFMPEG...")
            progressMessageBar.layout().addWidget(progress)
            iface.messageBar().pushWidget(progressMessageBar, QGis.Info)

            filename = 'FFMPEG.zip'
            urlretrieve(FFMPEG, filename, reporthook)
            zip_ref = zipfile.ZipFile(filename, 'r')

            dest = os.path.join(os.getenv("SystemDrive"), os.sep, "FFMPEG")
            extensions = ('.exe')

            for zip_info in zip_ref.infolist():
                if zip_info.filename[-1] == '/':
                    continue
                zip_info.filename = os.path.basename(zip_info.filename)
                if zip_info.filename.endswith(extensions):
                    zip_ref.extract(zip_info, dest)

            zip_ref.close()

            parser.set('GENERAL', 'ffmpeg', os.getenv("SystemDrive") + os.sep + "FFMPEG")

            with open(fileConfig, 'w') as configfile:
                parser.write(configfile)
            
            os.remove(filename)
            iface.messageBar().clearWidgets()

    if not isDem():
        ''' DEM File '''        
        buttonReply = qgsu.CustomMessage("QGIS FMV",
                                 QCoreApplication.translate("QgsFmvInstaller","""<b>Dem file not exist!</b>"""),
                                 QCoreApplication.translate("QgsFmvInstaller", "Do you want download global DEM?"),
                                 icon="Information")
        if buttonReply == QMessageBox.Yes:
            progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Downloading Global DEM...")
            progressMessageBar.layout().addWidget(progress)
            iface.messageBar().pushWidget(progressMessageBar, QGis.Info)
               
            filename = 'DemGlobalFMV.zip'     
            urlretrieve(DemGlobal,filename, reporthook)
            zip_ref = zipfile.ZipFile(filename, 'r')

            dest = os.path.join(os.getenv("SystemDrive"), os.sep, "DemGlobalFMV")
            extensions = ('.tif')

            for zip_info in zip_ref.infolist():
                if zip_info.filename[-1] == '/':
                    continue
                zip_info.filename = os.path.basename(zip_info.filename)
                if zip_info.filename.endswith(extensions):
                    zip_ref.extract(zip_info, dest)

            zip_ref.close()

            parser.set('GENERAL', 'DTM_file', os.getenv("SystemDrive") + os.sep + "DemGlobalFMV"+ os.sep +"ETOPO1.tif")

            with open(fileConfig, 'w') as configfile:
                parser.write(configfile)

            os.remove(filename)
            iface.messageBar().clearWidgets()
        

    try:
        import cv2, matplotlib  # noqa
    except ImportError:
        try:
            buttonReply = qgsu.CustomMessage("QGIS FMV : " + QCoreApplication.translate("QgsFmvInstaller", "<b>Missing dependencies</b>"),
                                             QCoreApplication.translate("QgsFmvInstaller", "Do you want install missing dependencies?"),
                                             icon="Information")
            if buttonReply == QMessageBox.Yes:
                install_pip_requirements()
                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", "Python libraries installed correctly"))
        except ImportError:
            None
    finally:
        try:
            import cv2, matplotlib  # noqa
            # We update dependencies
            if matplotlib.__version__ < '3.1.0' or cv2.__version__ < '4.1.0':
                buttonReply = qgsu.CustomMessage("QGIS FMV : " + QCoreApplication.translate("QgsFmvInstaller", "<b>Updates available</b>"),
                                                 QCoreApplication.translate("QgsFmvInstaller", "Do you want upgrade dependencies?"),
                                                 icon="Information")
                if buttonReply == QMessageBox.Yes:
                    install_pip_requirements()
                    qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", "Python libraries updated correctly"))
        except ImportError:
            qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", "Error installing the python libraries, use the requirements file!"),
                                       level=QGis.Critical)
            raise
    return


def get_password():
        """Return Linux user Password."""
        password, ok = QInputDialog.getText(
            None, "Enter Linux user password for install missing dependencies", "Password:",
            QLineEdit.Password
        )
        return password if ok else ''


# Tested using 3.12.1-București and Ubuntu 18.04
def LinuxInstaller():
    '''Complete Linux installation '''
    pwd = None
    
    try:
        import cv2, matplotlib, apt  # noqa
    except ImportError:
        try:

            buttonReply = qgsu.CustomMessage("QGIS FMV : " + QCoreApplication.translate("QgsFmvInstaller", "Missing python dependencies"),
                                             QCoreApplication.translate("QgsFmvInstaller", "Do you want install missing dependencies?"),
                                             icon="Information")
            if buttonReply == QMessageBox.Yes:
                
                ''' Aditional dependencies'''
                if pwd is None:
                    ret = get_password()
                    if ret == "":
                        return
        
                    pwd = ret
            
                # Install matplotlib
                cmd = 'sudo apt -y install matplotlib'
                subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)
                
                # Install apt
                cmd = 'sudo pip3 install python-apt'
                subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)

                # Install OpenCV
#                 package_dir = QgsApplication.qgisSettingsDirPath() + 'python/plugins/QGIS_FMV/'
#                 opencv_file = os.path.join(package_dir, 'install-opencv.sh')
#                 cmd = 'sh ' + opencv_file
#                 subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)

                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", "Python libraries installed correctly"))
        except ImportError:
            None
    finally:
        try:
            import cv2, matplotlib,apt  # noqa
        except ImportError:
            qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", "Error installing the python libraries, use the requirements file!"),
                                       level=QGis.Critical)
            

    if not IsLavFilters():
        ''' lAV Filters (GStreamer on Linux)'''

        buttonReply = qgsu.CustomMessage("QGIS FMV",
                                         QCoreApplication.translate("QgsFmvInstaller", "Missing GStreamer dependency"),
                                         QCoreApplication.translate("QgsFmvInstaller", "Do you want install GStreamer?"),
                                         icon="Information")
        if buttonReply == QMessageBox.Yes:
            
            if pwd is None:
                ret = get_password()
                if ret == "":
                    return
    
                pwd = ret
            
            # Install GStreamer
            progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Downloading GStreamer...")
            progressMessageBar.layout().addWidget(progress)
            iface.messageBar().pushWidget(progressMessageBar, QGis.Info)

            cmd = 'sudo apt-get -y install python3-pyqt5.qtmultimedia gst123 libgstreamer1.0-0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav gstreamer1.0-doc gstreamer1.0-tools gstreamer1.0-x gstreamer1.0-alsa gstreamer1.0-gl gstreamer1.0-gtk3 gstreamer1.0-qt5 gstreamer1.0-pulseaudio libqt5gstreamer-1.0-0 qtmultimedia5-examples libqt5multimedia5-plugins'
            gst_rc = subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)
            if gst_rc != 0:
                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'INSTALLATION FAILED: Failed to install GStreamer library.'), level=QGis.Critical)
            else:
                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'INSTALLATION SUCCESSFUL: Sucessfully installed GStreamer package.'))

            iface.messageBar().clearWidgets()

    if not IsFFMPEG():
        ''' FFMPEG Lib '''

        buttonReply = qgsu.CustomMessage("QGIS FMV",
                                         QCoreApplication.translate("QgsFmvInstaller", "Missing FFMPEG dependency"),
                                         QCoreApplication.translate("QgsFmvInstaller", "Do you want install FFMPEG?"),
                                         icon="Information")
        if buttonReply == QMessageBox.Yes:
            
            if pwd is None:
                ret = get_password()
                if ret == "":
                    return
    
                pwd = ret
                
            # Download FFMPEG
            progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Downloading FFMPEG...")
            progressMessageBar.layout().addWidget(progress)
            iface.messageBar().pushWidget(progressMessageBar, QGis.Info)

            cmd = 'sudo apt-get -y install ffmpeg'
            ff_rc = subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)
            if ff_rc != 0:
                qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'Failed to install ffmpeg library, trying add-apt-repository.'), level=QGis.Critical)

                cmd = 'sudo add-apt-repository ppa:jonathonf/ffmpeg-4'
                ppa_rc = subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)
                if ppa_rc != 0:
                    qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'INSTALLATION FAILED: Could not install ffmpeg package.'), level=QGis.Critical)

                else:
                    qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'GET REPO SUCCESSFUL: Successfully added trusty-media repo where ffmpeg is located'))

                    cmd = 'sudo apt-get update'
                    up_rc = subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)
                    if up_rc != 0:
                        qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'UPDATE FAILED: Failed to retrieve packages.'), level=QGis.Critical)
                    else:
                        qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'UPDATE SUCCESSFUL: Sucessfully retrived updated packages.'))
                        cmd = 'sudo apt-get -y install ffmpeg'
                        ffm_rc = subprocess.call('echo {} | sudo -S {}'.format(pwd, cmd), shell=True)
                        if ffm_rc != 0:
                            qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'INSTALLATION FAILED: Could not install ffmpeg package.'), level=QGis.Critical)
                        else:
                            qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", 'INSTALLATION SUCCESSFUL: Sucessfully installed ffmpeg package.'))

                            parser.set('GENERAL', 'ffmpeg', '/usr/bin/')
                            with open(fileConfig, 'w') as configfile:
                                parser.write(configfile)

                            iface.messageBar().clearWidgets()
            else:
                parser.set('GENERAL', 'ffmpeg', '/usr/bin/')
                with open(fileConfig, 'w') as configfile:
                    parser.write(configfile)

                iface.messageBar().clearWidgets()

    if not isDem():
        ''' DEM File '''
        progressMessageBar = iface.messageBar().createMessage("QGIS FMV",
                                                              QCoreApplication.translate("QgsFmvInstaller", "Dem file not exist!"))
        iface.messageBar().pushWidget(progressMessageBar, QGis.Info)
        parser.set('GENERAL', 'DTM_file', "")

        with open(fileConfig, 'w') as configfile:
            parser.write(configfile)
        iface.messageBar().clearWidgets()

    return


# TODO
def MacInstaller():
    '''complete Mac installation '''
    return


def isDem():
    ''' Check if Dem is present '''
    if windows:
        if not os.path.isfile(DemConf):
            return False
    return True


def IsLavFilters():
    ''' Check if LavFilters is present '''
    if windows:
        software_list = WinSoftwareInstalled(winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_32KEY) + WinSoftwareInstalled(winreg.HKEY_LOCAL_MACHINE, winreg.KEY_WOW64_64KEY) + WinSoftwareInstalled(winreg.HKEY_CURRENT_USER, 0)
        if not any('LAV Filters' in software['name'] for software in software_list):
            # does not exist
            return False
    else:
        cache = apt.Cache()
        cache.open()
        try:
            #print("lav filters")
            return cache["gst123"].is_installed
        except Exception:
            # does not exist
            return False
    return True


def IsFFMPEG():
    ''' Chech if FFMPEG is present '''
    if windows:
        if not os.path.isdir(ffmpegConf):
            return False
        if not os.path.isfile(os.path.join(ffmpegConf, 'ffmpeg.exe')):
            return False
    else:
        cache = apt.Cache()
        cache.open()
        try:
            return cache["ffmpeg"].is_installed
        except Exception:
            # does not exist
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


def install_pip_requirements():
    ''' Install Requeriments from pip >= 10.0.1'''
    package_dir = QgsApplication.qgisSettingsDirPath() + 'python/plugins/QGIS_FMV/'
    requirements_file = os.path.join(package_dir, 'requirements.txt')
    if not os.path.isfile(requirements_file):
        qgsu.showUserAndLogMessage(QCoreApplication.translate("QgsFmvInstaller", "No requirements file found in {}").format(
            requirements_file), onlyLog=True)
        raise
    try:
        process = Popen(["python3", "-m", 'pip', "install", '--upgrade', 'pip'],
                        shell=windows,
                        stdout=PIPE,
                        stderr=PIPE)
        process.wait()
        process = Popen(["python3", "-m", 'pip', "install", '-U', 'pip', 'setuptools'],
                        shell=windows,
                        stdout=PIPE,
                        stderr=PIPE)
        process.wait()
        process = Popen(["pip3", "install", '--user', '-r', requirements_file],
                        shell=windows,
                        stdout=PIPE,
                        stderr=PIPE)
        process.wait()
    except Exception:
        raise

    return
