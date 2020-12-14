#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.elementparser import BytesElementParser
from QGIS_FMV.klvdata.elementparser import DateTimeElementParser
from QGIS_FMV.klvdata.elementparser import StringElementParser
from QGIS_FMV.klvdata.elementparser import IntegerElementParser
from QGIS_FMV.klvdata.elementparser import LocationElementParser
from QGIS_FMV.klvdata.misb0601 import UASLocalMetadataSet
from QGIS_FMV.klvdata.setparser import SetParser
from QGIS_FMV.klvdata.seriesparser import SeriesParser

@UASLocalMetadataSet.add_parser
class VMTILocalSet(SetParser):
    """MISB ST0903 VMTI Metadata nested local set parser.

    Must be a subclass of Element or duck type Element.
    """
    key = b'\x4A'
    name = "VMTI Local Set"
    parsers = {}

    _unknown_element = UnknownElement


@VMTILocalSet.add_parser
class Checksum(BytesElementParser):
    """Checksum used to detect errors within a UAV Local Set packet.

    Checksum formed as lower 16-bits of summation performed on entire
    LS packet, including 16-byte US key and 1-byte checksum length.

    Initialized from bytes value as BytesValue.
    """
    key = b'\x01'
    TAG = 1
    UDSKey = "-"
    LDSName = "Checksum"
    ESDName = ""
    UDSName = ""

@VMTILocalSet.add_parser
class PrecisionTimeStamp(DateTimeElementParser):
    """Precision Timestamp represented in microseconds.

    Precision Timestamp represented in the number of microseconds elapsed
    since midnight (00:00:00), January 1, 1970 not including leap seconds.

    See MISB ST 0601.11 for additional details.
    """
    key = b'\x02'
    TAG = 2
    UDSKey = "06 0E 2B 34 01 01 01 03 07 02 01 01 01 05 00 00"
    LDSName = "Precision Time Stamp"
    ESDName = ""
    UDSName = "User Defined Time Stamp"

@VMTILocalSet.add_parser
class NumberDetectedTargets(IntegerElementParser):
    key = b'\x05'
    TAG = 5
    UDSKey = "-"
    LDSName = "Number of Detected Targets"
    ESDName = "Number of Detected Targets"
    UDSName = ""
    
    _signed = False
    _size = 3

@VMTILocalSet.add_parser
class NumberReportedTargets(IntegerElementParser):
    key = b'\x06'
    TAG = 6
    UDSKey = "-"
    LDSName = "Number of Reported Targets"
    ESDName = "Number of Reported Targets"
    UDSName = ""
    
    _signed = False
    _size = 3

@VMTILocalSet.add_parser
class FrameWidth(IntegerElementParser):
    key = b'\x08'
    TAG = 8
    UDSKey = "-"
    LDSName = "Frame Width"
    ESDName = "Frame Width"
    UDSName = ""
    
    _signed = False
    _size = 3

@VMTILocalSet.add_parser
class FrameHeight(IntegerElementParser):
    key = b'\x09'
    TAG = 9
    UDSKey = "-"
    LDSName = "Frame Height"
    ESDName = "Frame Height"
    UDSName = ""
    
    _signed = False
    _size = 3

@VMTILocalSet.add_parser
class SourceSensor(StringElementParser):
    key = b'\x0A'
    TAG = 10
    UDSKey = "-"
    LDSName = "Source Sensor"
    ESDName = "Source Sensor"
    UDSName = ""

    _encoding = 'UTF-8'
    min_length, max_length = 0, 127

@VMTILocalSet.add_parser
class VTargetSeries(SeriesParser):
    key = b'\x65'
    TAG = 101

    name = "VTarget Series"
    parser = None

@VTargetSeries.set_parser
class VTargetPack(SetParser):
    name = "VMTI Target Pack"
    parsers = {}

    def __init__(self, value):
        """All parser needs is the value, no other information"""
        self.key = value[0].to_bytes(1, byteorder='big')
        super().__init__(value[1:])

@VTargetPack.add_parser
class CentroidPixel(IntegerElementParser):
    key = b'\x01'
    TAG = 1
    UDSKey = "-"
    LDSName = "Centroid Pixel"
    ESDName = "Centroid Pixel"
    UDSName = ""
    
    _signed = False
    _size = 3

@VTargetPack.add_parser
class BoundingBoxTopLeftPixel(IntegerElementParser):
    key = b'\x02'
    TAG = 2
    UDSKey = "-"
    LDSName = "Bounding Box Top Left Pixel"
    ESDName = "Bounding Box Top Left Pixel"
    UDSName = ""
    
    _signed = False
    _size = 3

@VTargetPack.add_parser
class BoundingBoxBottomRightPixel(IntegerElementParser):
    key = b'\x03'
    TAG = 3
    UDSKey = "-"
    LDSName = "Bounding Box Bottom Right Pixel"
    ESDName = "Bounding Box Bottom Right Pixel"
    UDSName = ""
    
    _signed = False
    _size = 3

@VTargetPack.add_parser
class DetectionCount(IntegerElementParser):
    key = b'\x06'
    TAG = 6
    UDSKey = "-"
    LDSName = "Detection Count"
    ESDName = "Detection Count"
    UDSName = ""
    
    _signed = False
    _size = 2

@VTargetPack.add_parser
class TargetIntensity(IntegerElementParser):
    key = b'\x09'
    TAG = 9
    UDSKey = "-"
    LDSName = "Target Intensity"
    ESDName = "Target Intensity"
    UDSName = ""
    
    _signed = False
    _size = 3

@VTargetPack.add_parser
class TargetLocation(LocationElementParser):
    key = b'\x11'
    TAG = 17
    UDSKey = "-"
    LDSName = "Target Location"
    ESDName = "Target Location"
    UDSName = ""