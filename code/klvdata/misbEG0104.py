#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# The MIT License (MIT)
#
# Copyright (c) 2017 Matthew Pare (paretech@gmail.com)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from QGIS_FMV.klvdata.common import hexstr_to_bytes
from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.elementparser import BytesElementParser
from QGIS_FMV.klvdata.elementparser import DateTimeElementParser
from QGIS_FMV.klvdata.elementparser import StringElementParser
from QGIS_FMV.klvdata.elementparser import IEEE754ElementParser
from QGIS_FMV.klvdata.setparser import SetParser
from QGIS_FMV.klvdata.streamparser import StreamParser


class UnknownElement(UnknownElement):
    pass


@StreamParser.add_parser
class UAVBasicUniversalMetadataSet(SetParser):
    """MISB EG0104.4 Predator UAV Basic Universal Metadata Set
    http://www.gwg.nga.mil/misb/docs/eg/EG0104.4.pdf
    """

    # key = hexstr_to_bytes('06 0E 2B 34 - 01 01 01 01 – 02 01 03 00 - 00 00 00 00')
    key = hexstr_to_bytes('06 0E 2B 34 - 02 01 01 01 – 0E 01 01 02 - 01 01 00 00')
    name = 'UAV Basic Universal Metadata Set'
    key_length = 16
    parsers = {}

    _unknown_element = UnknownElement


@UAVBasicUniversalMetadataSet.add_parser
class PrecisionTimeStamp(DateTimeElementParser):
    """Precision Timestamp represented in microseconds.

    Precision Timestamp represented in the number of microseconds elapsed
    since midnight (00:00:00), January 1, 1970 not including leap seconds.

    See MISB ST 0601.11 for additional details.
    """
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 02 01 01 01 05 00 00")
    TAG = 2
    UDSKey = "06 0E 2B 34 01 01 01 03 07 02 01 01 01 05 00 00"
    LDSName = "Precision Time Stamp"
    ESDName = ""
    UDSName = "User Defined Time Stamp"


@UAVBasicUniversalMetadataSet.add_parser
class MissionID(StringElementParser):
    """Mission ID is the descriptive mission identifier.

    Mission ID value field free text with maximum of 127 characters
    describing the event.
    """
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 01 05 05 00 00 00 00 00")
    TAG = 3
    UDSKey = "06 0E 2B 34 01 01 01 01 01 05 05 00 00 00 00 00"
    LDSName = "Mission ID"
    ESDName = "Mission Number"
    UDSName = "Episode Number"
    min_length, max_length = 0, 127


@UAVBasicUniversalMetadataSet.add_parser
class PlatformHeadingAngle(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 07 07 01 10 01 06 00 00 00")
    TAG = 5
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 06 00 00 00"
    LDSName = "Platform Heading Angle"
    ESDName = "UAV Heading (INS)"
    UDSName = "Platform Heading Angle"
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 360)


@UAVBasicUniversalMetadataSet.add_parser
class PlatformPitchAngle(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 07 07 01 10 01 05 00 00 00")
    TAG = 6
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 05 00 00 00"
    LDSName = "Platform Pitch Angle"
    ESDName = "UAV Pitch (INS)"
    UDSName = "Platform Pitch Angle"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-20, 20)


@UAVBasicUniversalMetadataSet.add_parser
class PlatformRollAngle(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 07 07 01 10 01 04 00 00 00")
    TAG = 7
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 04 00 00 00"
    LDSName = "Platform Roll Angle"
    ESDName = "UAV Roll (INS)"
    UDSName = "Platform Roll Angle"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-50, 50)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class PlatformDesignation(StringElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 01 01 20 01 00 00 00 00")
    TAG = 10
    UDSKey = "06 0E 2B 34 01 01 01 01 01 01 20 01 00 00 00 00"
    LDSName = "Platform Designation"
    ESDName = "Project ID Code"
    UDSName = "Device Designation"
    min_length, max_length = 0, 127


@UAVBasicUniversalMetadataSet.add_parser
class ImageSourceSensor(StringElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 04 20 01 02 01 01 00 00")
    TAG = 11
    UDSKey = "06 0E 2B 34 01 01 01 01 04 20 01 02 01 01 00 00"
    LDSName = "Image Source Sensor"
    ESDName = "Sensor Name"
    UDSName = "Image Source Device"
    min_length, max_length = 0, 127


@UAVBasicUniversalMetadataSet.add_parser
class ImageCoordinateSystem(StringElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 01 01 00 00 00 00")
    TAG = 12
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 01 01 00 00 00 00"
    LDSName = "Image Coordinate System"
    ESDName = "Image Coordinate System"
    UDSName = "Image Coordinate System"
    min_length, max_length = 0, 127


@UAVBasicUniversalMetadataSet.add_parser
class SensorLatitude(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 02 01 02 04 00 00")
    TAG = 13
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 02 04 00 00"
    LDSName = "Sensor Latitude"
    ESDName = "Sensor Latitude"
    UDSName = "Device Latitude"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class SensorLatitude1(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 02 01 02 04 02 00")
    TAG = 13
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 02 04 02 00"
    LDSName = "Sensor Latitude"
    ESDName = "Sensor Latitude"
    UDSName = "Device Latitude"
    _domain = (-(2 ** 63 - 1), 2 ** 63 - 1)
    _range = (-90, 90)
    units = 'degrees'


# the key is wrong, comes from 1.klv
@UAVBasicUniversalMetadataSet.add_parser
class SensorLatitude2(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 01 01 01 03 07 01 02 01 02 04 02 00")
    TAG = 13
    UDSKey = "06 0E 01 01 01 03 07 01 02 01 02 04 02 00"
    LDSName = "Sensor Latitude"
    ESDName = "Sensor Latitude"
    UDSName = "Device Latitude"
    _domain = (-(2 ** 63 - 1), 2 ** 63 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class SensorLongitude(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 02 01 02 06 00 00")
    TAG = 14
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 02 06 00 00"
    LDSName = "Sensor Longitude"
    ESDName = "Sensor Longitude"
    UDSName = "Device Longitude"
    _domain = (-(2 ** 63 - 1), 2 ** 63 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class SensorLongitude1(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 02 01 02 06 02 00")
    TAG = 14
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 02 06 02 00"
    LDSName = "Sensor Longitude"
    ESDName = "Sensor Longitude"
    UDSName = "Device Longitude"
    _domain = (-(2 ** 63 - 1), 2 ** 63 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class SensorTrueAltitude(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 02 01 02 02 00 00")
    TAG = 15
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 02 02 00 00"
    LDSName = "Sensor True Altitude"
    ESDName = "Sensor Altitude"
    UDSName = "Device Altitude"
    _domain = (0, 2 ** 16 - 1)
    _range = (-99999, 99999)
    units = 'meters'


@UAVBasicUniversalMetadataSet.add_parser
class SensorHorizontalFieldOfView(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 02 04 20 02 01 01 08 00 00")
    TAG = 16
    UDSKey = "06 0E 2B 34 01 01 01 02 04 20 02 01 01 08 00 00"
    LDSName = "Sensor Horizontal Field of View"
    ESDName = "Field of View"
    UDSName = "Field of View (FOVHorizontal)"
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class SensorVerticalFieldOfView(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0e 2b 34 01 01 01 07 04 20 02 01 01 0a 01 00")
    TAG = 17
    UDSKey = "06 0e 2b 34 01 01 01 07 04 20 02 01 01 0a 01 00"
    LDSName = "Sensor Vertical Field of View"
    ESDName = "Vertical Field of View"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class SensorRelativeAzimuthAngle(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0e 2b 34 01 01 01 01 07 01 10 01 02 00 00 00")
    TAG = 18
    UDSKey = "06 0e 2b 34 01 01 01 01 07 01 10 01 02 00 00 00"
    LDSName = "Sensor Relative Azimuth Angle"
    ESDName = "Sensor Relative Azimuth Angle"
    UDSName = ""
    _domain = (0, 2 ** 32 - 1)
    _range = (0, 360)
    units = 'degrees'

 
@UAVBasicUniversalMetadataSet.add_parser 
class SensorRelativeElevationAngle(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0e 2b 34 01 01 01 01 07 01 10 01 03 00 00 00")
    TAG = 19
    UDSKey = "06 0e 2b 34 01 01 01 01 07 01 10 01 03 00 00 00"
    LDSName = "Sensor Relative Elevation Angle"
    ESDName = "Sensor Relative Elevation Angle"
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'

    
@UAVBasicUniversalMetadataSet.add_parser
class SlantRange(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 08 01 01 00 00 00")
    TAG = 21
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 08 01 01 00 00 00"
    LDSName = "Slant Range"
    ESDName = "Slant Range"
    UDSName = "Slant Range"
    _domain = (0, 2 ** 32 - 1)
    _range = (0, +5e6)
    units = 'meters'


@UAVBasicUniversalMetadataSet.add_parser
class TargetWidth(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 09 02 01 00 00 00")
    TAG = 22
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 09 02 01 00 00 00"
    LDSName = "Target Width"
    ESDName = "Target Width"
    UDSName = "Target Width"
    _domain = (0, 2 ** 16 - 1)
    _range = (0, +10e3)
    units = 'meters'


@UAVBasicUniversalMetadataSet.add_parser
class FrameCenterLatitude(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 02 01 03 02 00 00")
    TAG = 23
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 03 02 00 00"
    LDSName = "Frame Center Latitude"
    ESDName = "Target Latitude"
    UDSName = "Frame Center Latitude"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class FrameCenterLongitude(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 02 01 03 04 00 00")
    TAG = 24
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 03 04 00 00"
    LDSName = "Frame Center Longitude"
    ESDName = "Target Longitude"
    UDSName = "Frame Center Longitude"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLatitudePoint1(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 07 01 00")
    TAG = 26
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 07 01 00"
    LDSName = "Offset Corner Latitude Point 1"
    ESDName = "SAR Latitude 4"
    UDSName = "Corner Latitude Point 1"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, +0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLongitudePoint1(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0B 01 00")
    TAG = 27
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0B 01 00"
    LDSName = "Offset Corner Longitude Point 1"
    ESDName = "SAR Longitude 4"
    UDSName = "Corner Longitude Point 1"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLatitudePoint2(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 08 01 00")
    TAG = 28
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 08 01 00"
    LDSName = "Offset Corner Latitude Point 2"
    ESDName = "SAR Latitude 1"
    UDSName = "Corner Latitude Point 2"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLongitudePoint2(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0C 01 00")
    TAG = 29
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0C 01 00"
    LDSName = "Offset Corner Longitude Point 2"
    ESDName = "SAR Longitude 1"
    UDSName = "Corner Longitude Point 2"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLatitudePoint3(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 09 01 00")
    TAG = 30
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 09 01 00"
    LDSName = "Offset Corner Latitude Point 3"
    ESDName = "SAR Latitude 2"
    UDSName = "Corner Latitude Point 3"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLongitudePoint3(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0D 01 00")
    TAG = 31
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0D 01 00"
    LDSName = "Offset Corner Longitude Point 3"
    ESDName = "SAR Longitude 2"
    UDSName = "Corner Longitude Point 3"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLatitudePoint4(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0A 01 00")
    TAG = 32
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0A 01 00"
    LDSName = "Offset Corner Latitude Point 4"
    ESDName = "SAR Latitude 3"
    UDSName = "Corner Latitude Point 4"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class OffsetCornerLongitudePoint4(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0E 01 00")
    TAG = 33
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0E 01 00"
    LDSName = "Offset Corner Longitude Point 4"
    ESDName = "SAR Longitude 3"
    UDSName = "Corner Longitude Point 4"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class StartDateTime(StringElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 02 01 02 01 01 00 00")
    TAG = 72
    UDSKey = "06 0E 2B 34 01 01 01 01 07 02 01 02 01 01 00 00"
    LDSName = "Start Date Time - UTC"
    UDSName = "Start Date Time - UTC"
    min_length, max_length = 0, 127


@UAVBasicUniversalMetadataSet.add_parser
class EventStartTime(DateTimeElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 02 01 02 07 01 00 00")
    TAG = 72
    UDSKey = "06 0E 2B 34 01 01 01 01 07 02 01 02 07 01 00 00"
    LDSName = "Event Start Time - UTC"
    ESDName = "Mission Start Time, Date, and Date of Collection"
    UDSName = "Event Start Date Time - UTC"


@UAVBasicUniversalMetadataSet.add_parser
class RVTLocalSet(StringElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 02 01 02 07 01 00 00")
    TAG = 73
    UDSKey = "06 0E 2B 34 01 01 01 01 07 02 01 02 07 01 00 00"
    LDSName = "RVT Local Data Set"
    ESDName = ""
    UDSName = "Remote Video Terminal Local Set"


@UAVBasicUniversalMetadataSet.add_parser
class VMTILocalSet(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 02 0B 01 01 0E 01 03 03 06 00 00 00")
    TAG = 74
    UDSKey = "06 0E 2B 34 02 0B 01 01 0E 01 03 03 06 00 00 00"
    LDSName = "VMTI Local Set"
    ESDName = ""
    UDSName = "Video Moving Target Indicator Local Set"


@UAVBasicUniversalMetadataSet.add_parser
class CornerLatitudePoint1Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 07 01 00")
    TAG = 82
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 07 01 00"
    LDSName = "Corner Latitude Point 1 (Full)"
    ESDName = "SAR Latitude 4"
    UDSName = "Corner Latitude Point 1 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class CornerLongitudePoint1Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0B 01 00")
    TAG = 83
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0B 01 00"
    LDSName = "Corner Longitude Point 1 (Full)"
    ESDName = "SAR Longitude 4"
    UDSName = "Corner Longitude Point 1 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class CornerLatitudePoint2Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 08 01 00")
    TAG = 84
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 08 01 00"
    LDSName = "Corner Latitude Point 2 (Full)"
    ESDName = "SAR Latitude 1"
    UDSName = "Corner Latitude Point 2 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class CornerLongitudePoint2Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0C 01 00")
    TAG = 85
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0C 01 00"
    LDSName = "Corner Longitude Point 2 (Full)"
    ESDName = "SAR Longitude 1"
    UDSName = "Corner Longitude Point 2 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class CornerLatitudePoint3Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 09 01 00")
    TAG = 86
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 09 01 00"
    LDSName = "Corner Latitude Point 3 (Full)"
    ESDName = "SAR Latitude 2"
    UDSName = "Corner Latitude Point 3 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class CornerLongitudePoint3Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0D 01 00")
    TAG = 87
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0D 01 00"
    LDSName = "Corner Longitude Point 3 (Full)"
    ESDName = "SAR Longitude 2"
    UDSName = "Corner Longitude Point 3 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class CornerLatitudePoint4Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0A 01 00")
    TAG = 88
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0A 01 00"
    LDSName = "Corner Latitude Point 4 (Full)"
    ESDName = "SAR Latitude 3"
    UDSName = "Corner Latitude Point 4 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class CornerLongitudePoint4Full(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 03 07 01 02 01 03 0E 01 00")
    TAG = 89
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0E 01 00"
    LDSName = "Corner Longitude Point 4 (Full)"
    ESDName = "SAR Longitude 3"
    UDSName = "Corner Longitude Point 4 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class PlatformPitchAngleFull(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 07 07 01 10 01 05 00 00 00")
    TAG = 90
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 05 00 00 00"
    LDSName = "Platform Pitch Angle (Full)"
    ESDName = "UAV Pitch (INS)"
    UDSName = "Platform Pitch Angle"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class PlatformRollAngleFull(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 07 07 01 10 01 04 00 00 00")
    TAG = 91
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 04 00 00 00"
    LDSName = "Platform Roll Angle (Full)"
    ESDName = "UAV Roll (INS)"
    UDSName = "Platform Roll Angle"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UAVBasicUniversalMetadataSet.add_parser
class MIISCoreIdentifier(StringElementParser):
     key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 0E 01 04 05 03 00 00 00")
     TAG = 94
     UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 04 05 03 00 00 00"
     LDSName = "MIIS Core Identifier"
     ESDName = ""
     UDSName = "Motion Imagery Identification System Core"


@UAVBasicUniversalMetadataSet.add_parser
class SARMotionImageryLocalSet(StringElementParser):
     key = hexstr_to_bytes("06 0E 2B 34 02 0B 01 01 0E 01 03 03 0D 00 00 00")
     TAG = 95
     UDSKey = "06 0E 2B 34 02 0B 01 01 0E 01 03 03 0D 00 00 00"
     LDSName = "SAR Motion Imagery Local Set"
     ESDName = ""
     UDSName = "SAR Motion Imagery Local Set"


@UAVBasicUniversalMetadataSet.add_parser
class TargetWidthExtended(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 07 01 09 02 01 00 00 00")
    TAG = 96
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 09 02 01 00 00 00"
    LDSName = "Target Width Extended"
    ESDName = "Target Width"
    UDSName = "Target Width"
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)
    units = 'meters'


@UAVBasicUniversalMetadataSet.add_parser
class DensityAltitudeExtended(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 0E 01 01 01 10 00 00 00")
    TAG = 103
    UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 01 01 10 00 00 00"
    LDSName = "Density Altitude Extended"
    ESDName = "Density Altitude"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 40000)
    units = 'meters'


@UAVBasicUniversalMetadataSet.add_parser
class SensorEllipsoidHeightExtended(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 0E 01 02 01 82 47 00 00")
    TAG = 104
    UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 02 01 82 47 00 00"
    LDSName = "Sensor Ellipsoid Height Extended"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 40000)
    units = 'meters'


@UAVBasicUniversalMetadataSet.add_parser
class AlternatePlatformEllipsoidHeightExtended(IEEE754ElementParser):
    key = hexstr_to_bytes("06 0E 2B 34 01 01 01 01 0E 01 02 01 82 48 00 00")
    TAG = 105
    UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 02 01 82 48 00 00"
    LDSName = " Alternate Platform Ellipsoid Height Extended"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 40000)
    units = 'meters'

