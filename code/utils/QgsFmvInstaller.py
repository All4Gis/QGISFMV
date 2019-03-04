import subprocess
import os, sys
from os.path import dirname, abspath
from urllib.request import urlretrieve
import platform
import zipfile
from PyQt5.QtWidgets import QMessageBox
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.utils.QgsFmvUtils import install_pip_requirements
import urllib.request
from configparser import SafeConfigParser
from qgis.PyQt.QtWidgets import QProgressBar
from qgis.PyQt.QtCore import *
from qgis.utils import iface
from qgis.core import Qgis as QGis
from PyQt5.QtCore import Qt
import pathlib
import requests

plugin_dir = pathlib.Path(__file__).parent.parent
sys.path.append(plugin_dir)

parser = SafeConfigParser(delimiters=(':'), comment_prefixes='/', allow_no_value=True)
fileConfig = os.path.join(dirname(dirname(abspath(__file__))), 'settings.ini')
parser.read(fileConfig)

ffmpegConf = parser['GENERAL']['ffmpeg']
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

LavFilters = "https://github.com/Nevcairiel/LAVFilters/releases/download/0.73.1/LAVFilters-0.73.1-Installer.exe"

# 64 Bits
if platform.machine().endswith('64'):
    FFMPEG = "https://ffmpeg.zeranoe.com/builds/win64/static/ffmpeg-20190225-2e67f75-win64-static.zip"
# 32 Bits
else:
    FFMPEG = "https://ffmpeg.zeranoe.com/builds/win32/static/ffmpeg-20190225-2e67f75-win32-static.zip"

DemGlobal = "http://www.gisandbeers.com/RRSS/Cartografia/DEM-Mundial.rar"

progress = QProgressBar()
progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36')]
urllib.request.install_opener(opener)


def reporthook(blocknum, blocksize, totalsize):
    readsofar = blocknum * blocksize
    if totalsize > 0:
        percent = readsofar * 1e2 / totalsize
        progress.setValue(int(percent))


def WindowsInstaller():
    ''' complete windows installation '''
    if not IsLavFilters():
        ''' lAV Filters '''
        buttonReply = qgsu.CustomMessage("QGIS FMV", "Missing dependency", "Do you want install Lav Filters?", icon="Information")
        if buttonReply == QMessageBox.Yes:

            progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Downloading LAV Filters...")
            progressMessageBar.layout().addWidget(progress)
            iface.messageBar().pushWidget(progressMessageBar, QGis.Info)

            # Install Lav Filter
            filename = 'LavFilters.exe'
            urlretrieve(LavFilters, filename, reporthook)
            process = subprocess.Popen(filename, stdout=subprocess.PIPE, creationflags=0x08000000)
            process.wait()
            os.remove(filename)
            iface.messageBar().clearWidgets()

    if not IsFFMPEG():
        ''' FFMPEG Lib '''
        buttonReply = qgsu.CustomMessage("QGIS FMV", "Missing dependency", "Do you want install FFMPEG?", icon="Information")
        if buttonReply == QMessageBox.Yes:
            # Download FFMPEG # Prevent HTTP Error 403: Forbidden
            progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Downloading FFMPEG...")
            progressMessageBar.layout().addWidget(progress)
            iface.messageBar().pushWidget(progressMessageBar, QGis.Info)

            filename = 'FFMPEG.zip'
            urlretrieve(FFMPEG, filename, reporthook)
            zip_ref = zipfile.ZipFile(filename, 'r')

            dest = os.path.join(os.getenv("SystemDrive"), "FFMPEG")
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
        progressMessageBar = iface.messageBar().createMessage("QGIS FMV", " Dem file not exist!")
        iface.messageBar().pushWidget(progressMessageBar, QGis.Info)
        parser.set('GENERAL', 'DTM_file', "")

        with open(fileConfig, 'w') as configfile:
            parser.write(configfile)
        iface.messageBar().clearWidgets()

    try:
        import homography, cv2, matplotlib
    except ImportError:
        try:
            buttonReply = qgsu.CustomMessage("QGIS FMV", "Missing dependency", "Do you want install missing dependencies?", icon="Information")
            if buttonReply == QMessageBox.Yes:
                install_pip_requirements()
                iface.messageBar().pushMessage("QGIS FMV", "Python libraries installed correctly", QGis.Info, 3)
        except ImportError:
            None
    finally:
        try:
            import homography, cv2, matplotlib
        except ImportError:
            iface.messageBar().pushMessage("QGIS FMV", "Error installing the python libraries, use the requirements file!", QGis.Critical, 3)
            raise
    return


# TODO
def LinuxInstaller():
    '''complete Linux installation '''
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
    return True


def IsFFMPEG():
    ''' Chech if FFMPEG is present '''
    if windows:
        if not os.path.isdir(ffmpegConf):
            return False
        if not os.path.isfile(os.path.join(ffmpegConf, 'ffmpeg.exe')):
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


def download_file_from_google_drive(id, destination):
    URL = "https://docs.google.com/uc?export=download"

    session = requests.Session()

    response = session.get(URL, params={'id':id }, stream=True)
    token = get_confirm_token(response)

    if token:
        params = {'id': id, 'confirm': token}
        response = session.get(URL, params=params, stream=True)

    save_response_content(response, destination)


def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value

    return None


def save_response_content(response, destination):
    CHUNK_SIZE = 32768
    total_length = int(response.headers.get('content-length'))
    dl = 0
    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk:  # filter out keep-alive new chunks
                dl += len(chunk)
                done = int(50 * dl / total_length)
                f.write(chunk)
                progress.setValue(done)
