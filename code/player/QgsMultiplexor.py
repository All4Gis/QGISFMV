# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QDialog, QApplication

from QGIS_FMV.gui.ui_FmvMultiplexer import Ui_VideoMultiplexer
from QGIS_FMV.utils.QgsFmvUtils import askForFiles
from QGIS_FMV.klvdata.common import datetime_to_bytes, int_to_bytes, float_to_bytes, bytes_to_str
import csv
import time
import itertools
from datetime import datetime
from math import tan, atan
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.utils.QgsFmvUtils import _spawn, getVideoFolder
import math
from QGIS_FMV.geo import sphere

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
_key25 =  b'\x19'

# Sensor Ellipsoid Height
_domain75 = (0, 2 ** 16 - 1)
_range75 = (-900, 19000)
_key75 = b'\x4B'


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
    
    def CreateMISB(self):
        ''' Create MISB Video '''
        ''' Only tested using DJI Data '''
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()
        # Get Image Size
        
        p = _spawn(['-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height',
                    '-of', 'csv=s=x:p=0',
                    self.video_file], t="probe")

        (output, _) = p.communicate()
        width, height = bytes_to_str(output).split("x")
        
        HFOV = self.sp_hfov.value()
        VFOV = self.sp_vfov.value()
        
        # TODO: Calculate focal length
        #focallength = (int(height)/2) / atan(float(VFOV) / 2)
        
        index = self.cmb_telemetry.currentIndex()
        out_record = self.cmb_telemetry.itemData(index)
        
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
                            _bytes = float_to_bytes(OSD_yaw, _domain5, _range5)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key5 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                        
                        # Platform Pitch Angle
                        if k == "OSD.pitch":
                            OSD_pitch = float(v)
                            _bytes = float_to_bytes(OSD_pitch, _domain6, _range6)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key6 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Platform Roll Angle
                        if k == "OSD.roll":
                            OSD_roll = float(v)
                            _bytes = float_to_bytes(OSD_roll, _domain7, _range7)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key7 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Sensor Latitude
                        if k == "OSD.latitude":
                            OSD_latitude = float(v)
                            _bytes = float_to_bytes(OSD_latitude, _domain13, _range13)
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
                            _bytes = float_to_bytes(OSD_altitude, _domain15, _range15)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key15 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Sensor Ellipsoid Height
                        if k == "OSD.height [m]":
                            OSD_height = float(v)
                            _bytes = float_to_bytes(OSD_height, _domain75, _range75)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key75 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes
                        
                        # Sensor Relative Azimuth Angle
                        if k == "GIMBAL.yaw":
                            GIMBAL_yaw = float(v)
                            _bytes = float_to_bytes(GIMBAL_yaw, _domain18, _range18)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key18 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                        
                        # Sensor Relative Elevation Angle
                        if k == "GIMBAL.pitch":
                            _bytes = float_to_bytes(float(v), _domain19, _range19)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key19 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                        
                        # Sensor Relative Roll Angle
                        if k == "GIMBAL.roll":
                            _bytes = float_to_bytes(float(v), _domain20, _range20)
                            _len = int_to_bytes(len(_bytes))
                            _bytes = _key20 + _len + _bytes
                            sizeTotal += len(_bytes)
                            bufferData += _bytes   
                            
                    except Exception:
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
                    
                    # TODO : Make mathematical formulas for calculate Slant range and frame center
                    # Slant Range
                    #h_e = HFOV*math.pi/360.
                    v_e = VFOV*math.pi/360.
                    #hPrint = 2*h*math.tan(h_e) #sensor footprint width in m
                    vPrint = 2*OSD_height*math.tan(v_e) #sensor footprint length in m
                    #fPrint = float(vPrint*hPrint) # sensor footprint area in m^2
                                        
                    distance = OSD_altitude/tan(OSD_pitch)
                    
                    angle =atan((distance + (vPrint/2)) / OSD_altitude)

                    slant = (distance + (vPrint/2)) / math.cos(angle)
                    
                    _bytes = float_to_bytes(slant, _domain21, _range21)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key21 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Target Width ,0 by default
                    _bytes = float_to_bytes(float(0), _domain22, _range22)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key22 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Frame Center Latitude
                    initialPoint = (OSD_longitude, OSD_latitude)

                    destPoint = sphere.destination(initialPoint, slant, GIMBAL_yaw)
                    
                    _bytes = float_to_bytes(destPoint[1], _domain23, _range23)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key23 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                       
                    # Frame Center Longitude
                    _bytes = float_to_bytes(destPoint[0], _domain24, _range24)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key24 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                    
                    # Frame Center Elevation 
                    _bytes = float_to_bytes(0, _domain25, _range25)
                    _len = int_to_bytes(len(_bytes))
                    _bytes = _key25 + _len + _bytes
                    sizeTotal += len(_bytes)
                    bufferData += _bytes
                        
                    # set packet header
                    writeData = cle
                    writeData += int_to_bytes(sizeTotal)
                    writeData += bufferData
                        
                    f_write = open(end_path, "wb+")
                    f_write.write(writeData)
                    f_write.close()
                except Exception:
                        continue   
 
        QApplication.restoreOverrideCursor() 
        QApplication.processEvents()    
        
        # We add it to the manager
        _, name = os.path.split(self.video_file)
        self.parent.AddFileRowToManager(name, self.video_file, islocal=True, klv_folder=self.klv_folder)
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
