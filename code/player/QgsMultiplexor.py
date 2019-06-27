# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QDialog, QApplication, QProgressBar

from QGIS_FMV.gui.ui_FmvMultiplexer import Ui_VideoMultiplexer
from QGIS_FMV.utils.QgsFmvUtils import askForFiles
from QGIS_FMV.klvdata.common import datetime_to_bytes, int_to_bytes, float_to_bytes, bytes_to_str
import csv
import time
import itertools
from datetime import datetime
from math import tan, radians, cos, pi, sin
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.utils.QgsFmvUtils import _spawn, getVideoFolder, CornerEstimationWithoutOffsets

from QGIS_FMV.geo import sphere
from qgis.core import Qgis as QGis

try:
    from pydevd import *
except ImportError:
    None
    
'''
'TODO : After all the tests I haven't managed to generate a MISB video,
for now I make this adaptation to be able to see it in QGIS FMV
'''
# Klv header
cle = b'\x06\x0e+4\x02\x0b\x01\x01\x0e\x01\x03\x01\x01\x00\x00\x00'

# Checksum
_key1 = b'\x01'

# Precision Time Stamp
_key2 = b'\x02'

# Platform Heading Angle
_domain5 = (0, 2 ** 16 - 1)
_range5 = (0, 360)
_key5 = b'\x05'

# Platform Pitch Angle
_domain6 = (-(2 ** 15 - 1), 2 ** 15 - 1)
_range6 = (-20, 20)
_key6 = b'\x06'

# Platform Roll Angle
_domain7 = (-(2 ** 15 - 1), 2 ** 15 - 1)
_range7 = (-50, 50)
_key7 = b'\x07'

# Sensor Latitude
_domain13 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range13 = (-90, 90)
_key13 = b'\x0D'

# Sensor Longitude
_domain14 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range14 = (-180, 180)
_key14 = b'\x0E'

# Sensor True Altitude
_domain15 = (0, 2 ** 16 - 1)
_range15 = (-900, 19000)
_key15 = b'\x0F'

# Sensor Horizontal Field of View
_domain16 = (0, 2 ** 16 - 1)
_range16 = (0, 180)
_key16 = b'\x10'

# Sensor Vertical Field of View
_domain17 = (0, 2 ** 16 - 1)
_range17 = (0, 180)
_key17 = b'\x11'

# Sensor Relative Azimuth Angle
_domain18 = (0, 2 ** 32 - 1)
_range18 = (0, 360)
_key18 = b'\x12'

# Sensor Relative Elevation Angle
_domain19 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range19 = (-180, 180)
_key19 = b'\x13'

# Sensor Relative Roll Angle
_domain20 = (0, 2 ** 32 - 1)
_range20 = (0, 360)
_key20 = b'\x14'

# Slant Range
_domain21 = (0, 2 ** 32 - 1)
_range21 = (0, +5e6)
_key21 = b'\x15'

# Target Width
_domain22 = (0, 2 ** 16 - 1)
_range22 = (0, +10e3)
_key22 = b'\x16'

# Frame Center Latitude
_domain23 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range23 = (-90, 90)
_key23 = b'\x17'

# Frame Center Longitude
_domain24 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range24 = (-180, 180)
_key24 = b'\x18'

# Frame Center Elevation
_domain25 = (0, 2 ** 16 - 1)
_range25 = (-900, +19e3)
_key25 = b'\x19'

# Sensor Ellipsoid Height
_domain75 = (0, 2 ** 16 - 1)
_range75 = (-900, 19000)
_key75 = b'\x4B'

# Corner Latitude Point 1 (Full)
_domain82 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range82 = (-90, 90)
_key82 = b'\x52'

# Corner Longitude Point 1 (Full)
_domain83 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range83 = (-180, 180)
_key83 = b'\x53'

# Corner Latitude Point 2 (Full) 
_domain84 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range84 = (-90, 90)
_key84 = b'\x54'

# Corner Longitude Point 2 (Full) 
_domain85 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range85 = (-180, 180)
_key85 = b'\x55'

# Corner Latitude Point 3 (Full)
_domain86 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range86 = (-90, 90)
_key86 = b'\x56'

# Corner Longitude Point 3 (Full)
_domain87 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range87 = (-180, 180)
_key87 = b'\x57'

# Corner Latitude Point 4 (Full)
_domain88 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range88 = (-90, 90)
_key88 = b'\x58'

# Corner Longitude Point 4 (Full)
_domain89 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range89 = (-180, 180)
_key89 = b'\x59'

# Platform Pitch Angle (Full)
_domain90 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range90 = (-90, 90)
_key90 = b'\x5A'

# Platform Roll Angle (Full)
_domain91 = (-(2 ** 31 - 1), 2 ** 31 - 1)
_range91 = (-90, 90)
_key91 = b'\x5B'


class Multiplexor(QDialog, Ui_VideoMultiplexer):
    """ About Dialog """

    def __init__(self, iface, parent=None, Exts=None):
        """ Contructor """
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.parent = parent
        
        self.video_file = None
        self.csv_file = None
        self.Exts = Exts        

    def OpenCsvFile(self):
        ''' Open Csv File '''
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "Multiplexor", "Open file"),
            exts="csv")
        if filename:
            self.csv_file = filename
            self.ln_inputMeta.setText(self.csv_file)
        return

    def OpenVideoFile(self):
        ''' Open Video File '''
        filename, _ = askForFiles(self, QCoreApplication.translate(
            "Multiplexor", "Open file"),
            exts=self.Exts)
        if filename:
            self.video_file = filename
            self.ln_inputVideo.setText(self.video_file)
        return
    
    def CreateCSV(self):
        ''' Create csv for each recording '''
        self.cmb_telemetry.clear()
        input_video = self.ln_inputVideo.text()
        input_metadata = self.ln_inputMeta.text()
        
        if input_video == "" or input_metadata == "":
            qgsu.showUserAndLogMessage(QCoreApplication.translate(
                    "Multiplexor", "You must complete all the information"))
            return

        self.ReadCSVRecordings(input_metadata)           
        # Enable create video button
        self.bt_createMISB.setEnabled(True)
        return
    
    def GetRows(self, csv_file):
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter=",")
            data = list(reader)
            row_count = len(data)
        return row_count
    
    def CreateMISB(self):
        ''' Create MISB Video '''
        ''' Only tested using DJI Data '''
        # Create ProgressBar
        self.iface.messageBar().clearWidgets()
        progressMessageBar = self.iface.messageBar().createMessage("Creating video packets...")
        progress = QProgressBar()
        progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        self.iface.messageBar().pushWidget(progressMessageBar, QGis.Info)
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
                
        HFOV = self.sp_hfov.value()
        VFOV = self.sp_vfov.value()
        
        index = self.cmb_telemetry.currentIndex()
        out_record = self.cmb_telemetry.itemData(index)
        rowCount = self.GetRows(out_record)
        progress.setMaximum(rowCount)
        
        d = {}
        with open(out_record) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                date_start = datetime.strptime(row["CUSTOM.updateTime"], '%Y/%m/%d %H:%M:%S.%f')
                break
        
        with open(out_record) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                for k in row:
                    stripK = k.strip()
                    stripV = row[k].strip()
                    d[stripK] = stripV    
            
                # We create the klv file for every moment
                sizeTotal = 0
                bufferData = b''
                cnt = 0

                for k, v in d.items():
                    try:
                        if k == "CUSTOM.updateTime":
                            # We prevent it from failing in the exact times that don't have milliseconds
                            try:
                                date_end = datetime.strptime(v, '%Y/%m/%d %H:%M:%S.%f')
                            except:
                                date_end = datetime.strptime(v, '%Y/%m/%d %H:%M:%S')
    
                            _bytes = datetime_to_bytes(date_end)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key2 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Platform Heading Angle
                        if k == "OSD.yaw":
                            OSD_yaw = float(v)
                            _bytes = float_to_bytes(round(OSD_yaw, 4), _domain5, _range5)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key5 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                        
                        # Platform Pitch Angle
                        if k == "OSD.pitch":
                            OSD_pitch = float(v)
                            _bytes = float_to_bytes(round(OSD_pitch, 4), _domain6, _range6)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key6 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Platform Roll Angle
                        if k == "OSD.roll":
                            OSD_roll = float(v)
                            _bytes = float_to_bytes(round(OSD_roll, 4), _domain7, _range7)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key7 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Sensor Latitude
                        if k == "OSD.latitude":
                            OSD_latitude = float(v)
                            _bytes = float_to_bytes(round(OSD_latitude, 4), _domain13, _range13)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key13 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Sensor Longitude
                        if k == "OSD.longitude":
                            OSD_longitude = float(v)
                            _bytes = float_to_bytes(OSD_longitude, _domain14, _range14)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key14 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes

                        # Sensor True Altitude
                        if k == "OSD.altitude [m]":
                            OSD_altitude = float(v)
                            _bytes = float_to_bytes(round(OSD_altitude, 4), _domain15, _range15)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key15 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Sensor Ellipsoid Height
                        if k == "OSD.height [m]":
                            OSD_height = float(v)
                            _bytes = float_to_bytes(round(OSD_height, 4), _domain75, _range75)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key75 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Sensor Relative Azimuth Angle
                        if k == "GIMBAL.yaw":
                            #GIMBAL_yaw = float(v)
                            GIMBAL_yaw = 0.0
                            _bytes = float_to_bytes(round(GIMBAL_yaw, 4), _domain18, _range18)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key18 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                        
                        # Sensor Relative Elevation Angle
                        if k == "GIMBAL.pitch":
                            GIMBAL_pitch = float(v)
                            _bytes = float_to_bytes(round(GIMBAL_pitch, 4), _domain19, _range19)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key19 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                        
                        # Sensor Relative Roll Angle
                        if k == "GIMBAL.roll":
                            GIMBAL_roll = float(v)
                            _bytes = float_to_bytes(round(GIMBAL_roll, 4), _domain20, _range20)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key20 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                            
                    except Exception:
                        print("Multiplexer error")
                        continue    
                
                try:
                    # Diference time
                    td = date_end - date_start
                    end_path = self.klv_folder + "/%.1f.klv" % (round(td.total_seconds(), 1))
                    
                    # CheckSum
                    v = abs(hash(end_path)) % (10 ** 4)
                    _bytes = int_to_bytes(v, 4)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key1 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Sensor Horizontal Field of View
                    v = self.sp_hfov.value()
                    _bytes = float_to_bytes(float(v), _domain16, _range16)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key16 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Sensor Vertical Field of View
                    v = self.sp_vfov.value()
                    _bytes = float_to_bytes(float(v), _domain17, _range17)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key17 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes

                    # TODO : Check these calculations
                    # Slant Range                    
                    anlge = 180 + (OSD_pitch + GIMBAL_pitch)
                    slantRange = abs(OSD_altitude / (cos(radians(anlge))))
                    
                    _bytes = float_to_bytes(round(slantRange, 4), _domain21, _range21)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key21 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Target Width
                    # targetWidth = 0.0
                    targetWidth = 2.0 * slantRange * tan(radians(HFOV / 2.0)) 
                    
                    _bytes = float_to_bytes(round(targetWidth, 4), _domain22, _range22)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key22 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Frame Center Latitude
                    angle = 90 + (OSD_pitch + GIMBAL_pitch)
                    tgHzDist = OSD_altitude * tan(radians(angle))
                    r_earth = 6371008.8
                    
                    dy =  tgHzDist * cos(radians(OSD_yaw))
                    framecenterlatitude = OSD_latitude  + (dy / r_earth) * (180 / pi)
                    
                    _bytes = float_to_bytes(round(framecenterlatitude, 4), _domain23, _range23)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key23 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                       
                    # Frame Center Longitude
                    dx = tgHzDist * sin(radians(OSD_yaw))
                    framecenterlongitude = OSD_longitude + (dx / r_earth) * (180 / pi) / cos(OSD_latitude * pi/180)
                    
                    _bytes = float_to_bytes(round(framecenterlongitude, 4), _domain24, _range24)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key24 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Frame Center Elevation 
                    frameCenterElevation = 0.0
                    
                    _bytes = float_to_bytes(frameCenterElevation, _domain25, _range25)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key25 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes

                    # TODO : If we save the corners in the klv have a overflow
#                     # CALCULATE CORNERS COORDINATES
#                     sensor = (OSD_longitude, OSD_latitude, OSD_altitude)
#                     frameCenter = (destPoint[0], destPoint[1], frameCenterElevation)
#                     FOV = (VFOV, HFOV)
#                     others = (OSD_yaw, GIMBAL_yaw, targetWidth, slantRange)
#                     cornerPointUL, cornerPointUR, cornerPointLR, cornerPointLL = CornerEstimationWithoutOffsets(sensor=sensor, frameCenter=frameCenter, FOV=FOV, others=others)
#                      
#                     # Corner Latitude Point 1 (Full)
#                     _bytes = float_to_bytes(round(cornerPointUL[0],4), _domain82, _range82)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key82 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
#                       
#                     # Corner Longitude Point 1 (Full)
#                     _bytes = float_to_bytes(round(cornerPointUL[1],4), _domain83, _range83)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key83 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
#                       
#                     # Corner Latitude Point 2 (Full) 
#                     _bytes = float_to_bytes(round(cornerPointUR[0],4), _domain84, _range84)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key84 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
#                       
#                     # Corner Longitude Point 2 (Full) 
#                     _bytes = float_to_bytes(round(cornerPointUR[1],4), _domain85, _range85)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key85 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
#                       
#                     # Corner Latitude Point 3 (Full)
#                     _bytes = float_to_bytes(round(cornerPointLR[0],4), _domain86, _range86)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key86 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
#                        
#                     # Corner Longitude Point 3 (Full)
#                     _bytes = float_to_bytes(round(cornerPointLR[1],4), _domain87, _range87)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key87 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
#                       
#                     # Corner Latitude Point 4 (Full)
#                     _bytes = float_to_bytes(round(cornerPointLL[0],4), _domain88, _range88)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key88 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
#                        
#                     # Corner Longitude Point 4 (Full)
#                     _bytes = float_to_bytes(round(cornerPointLL[1],4), _domain89, _range89)
#                     _len = int_to_bytes(len(_bytes))
#                     _bytes = _key89 + _len + _bytes
#                     sizeTotal += len(_bytes)
#                     bufferData += _bytes
                     
                    # Platform Pitch Angle (Full)
                    _bytes = float_to_bytes(round(OSD_pitch, 4), _domain90, _range90)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key90 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                     
                    # Platform Roll Angle (Full)
                    _bytes = float_to_bytes(round(OSD_roll, 4), _domain91, _range91)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key91 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                            
                    # set packet header
                    writeData = cle
                    writeData += int_to_bytes(sizeTotal)
                    writeData += bufferData
                    
                    # Write packet
                    f_write = open(end_path, "wb+")
                    f_write.write(writeData)
                    f_write.close()
                    
                    cnt += 1
                    
                    progress.setValue(cnt)
                    # QApplication.processEvents()    
                    
                except Exception as e:
                    print("Multiplexer error")   
 
        QApplication.restoreOverrideCursor() 
        QApplication.processEvents()    
        progress.setValue(rowCount)
        self.iface.messageBar().clearWidgets()
        # We add it to the manager
        _, name = os.path.split(self.video_file)
        self.parent.AddFileRowToManager(name, self.video_file, islocal=True, klv_folder=self.klv_folder)
        # Close dialog
        self.close()
        return
                        
    def ReadCSVRecordings(self, csv_raw):
        ''' Read the csv for each recording '''
        rows_list = []
        with open(csv_raw) as csvfile:
            reader = csv.DictReader(csvfile)
            rows = []
            index = 0
            for row in reader:
                for k in row:
                    if k == "CUSTOM.isVideo":
                        if row[k].strip() == "":
                            if not rows:
                                continue
                            else:
                                rows_list.append(rows)
                                rows = []     
                        else:
                            rows.append(index)
                index += 1
        
        if not rows_list:
            rows_list.append(rows)
        # Create csv
        self.CreateDJICsv(rows_list, csv_raw)
        return

    def CreateDJICsv(self, rows_list, csv_raw):
        ''' DJI Drone: Create csv result files for each record '''
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        
        folder = getVideoFolder(self.video_file)
        
        qgsu.createFolderByName(folder, "klv")
        qgsu.createFolderByName(folder, "csv")
        
        self.klv_folder = os.path.join(folder, "klv")
        out_csv = os.path.join(folder, "csv")

        for values in rows_list:            
            timestamp = int(time.time() * 1000.0)
            filename = "_".join(["recording", str(timestamp)])
            out_record = os.path.join(out_csv, filename + ".csv")
            # The column that corresponds to the stop is also removed
            with open(csv_raw, 'r') as f_input, open(out_record, 'w', newline='') as f_output:
                csv_input = csv.reader(f_input)
                csv.writer(f_output).writerows(itertools.islice(csv_input, 0, 1))
                csv.writer(f_output).writerows(itertools.islice(csv_input, int(values[0]), int(values[-1])))
                
            self.cmb_telemetry.addItem(filename, out_record)
        
        self.bt_createMISB.setEnabled(True) 
        QApplication.restoreOverrideCursor() 
        QApplication.processEvents()      
        return
