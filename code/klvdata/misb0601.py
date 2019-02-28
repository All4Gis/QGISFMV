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
from QGIS_FMV.klvdata.elementparser import (BytesElementParser,
                                            DateTimeElementParser,
                                            MappedElementParser,
                                            StringElementParser)
from QGIS_FMV.klvdata.setparser import SetParser
from QGIS_FMV.klvdata.streamparser import StreamParser
try:
    from pydevd import *
except ImportError:
    None


class UnknownElement(UnknownElement):
    pass


@StreamParser.add_parser
class UASLocalMetadataSet(SetParser):
    """MISB ST0601 UAS Local Metadata Set
    """
    key = hexstr_to_bytes(
        '06 0E 2B 34 - 02 0B 01 01 – 0E 01 03 01 - 01 00 00 00')
    name = 'UAS Datalink Local Set'
    key_length = 1
    parsers = {}

    _unknown_element = UnknownElement


@UASLocalMetadataSet.add_parser
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


@UASLocalMetadataSet.add_parser
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


@UASLocalMetadataSet.add_parser
class MissionID(StringElementParser):
    """Mission ID is the descriptive mission identifier.
    Mission ID value field free text with maximum of 127 characters
    describing the event.
    """
    key = b'\x03'
    TAG = 3
    UDSKey = "06 0E 2B 34 01 01 01 01 01 05 05 00 00 00 00 00"
    LDSName = "Mission ID"
    ESDName = "Mission Number"
    UDSName = "Episode Number"
    min_length, max_length = 0, 127


@UASLocalMetadataSet.add_parser
class PlatformTailNumber(StringElementParser):
    key = b'\x04'
    TAG = 4
    UDSKey = "-"
    LDSName = "Platform Tail Number"
    ESDName = "Platform Tail Number"
    UDSName = ""
    min_length, max_length = 0, 127


@UASLocalMetadataSet.add_parser
class PlatformHeadingAngle(MappedElementParser):
    key = b'\x05'
    TAG = 5
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 06 00 00 00"
    LDSName = "Platform Heading Angle"
    ESDName = "UAV Heading (INS)"
    UDSName = "Platform Heading Angle"
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 360)


@UASLocalMetadataSet.add_parser
class PlatformPitchAngle(MappedElementParser):
    key = b'\x06'
    TAG = 6
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 05 00 00 00"
    LDSName = "Platform Pitch Angle"
    ESDName = "UAV Pitch (INS)"
    UDSName = "Platform Pitch Angle"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-20, 20)


@UASLocalMetadataSet.add_parser
class PlatformRollAngle(MappedElementParser):
    key = b'\x07'
    TAG = 7
    UDSKey = " 06 0E 2B 34 01 01 01 07 07 01 10 01 04 00 00 00"
    LDSName = "Platform Roll Angle"
    ESDName = "UAV Roll (INS)"
    UDSName = "Platform Roll Angle"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-50, 50)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class PlatformTrueAirspeed(MappedElementParser):
    key = b'\x08'
    TAG = 8
    UDSKey = "-"
    LDSName = "Platform True Airspeed"
    ESDName = "True Airspeed"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 255)
    units = 'meters/second'


@UASLocalMetadataSet.add_parser
class PlatformIndicatedAirspeed(MappedElementParser):
    key = b'\x09'
    TAG = 9
    UDSKey = "-"
    LDSName = "Platform Indicated Airspeed"
    ESDName = "Indicated Airspeed"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 255)
    units = 'meters/second'


@UASLocalMetadataSet.add_parser
class PlatformDesignation(StringElementParser):
    key = b'\x0A'
    TAG = 10
    UDSKey = "06 0E 2B 34 01 01 01 01 01 01 20 01 00 00 00 00"
    LDSName = "Platform Designation"
    ESDName = "Project ID Code"
    UDSName = "Device Designation"
    min_length, max_length = 0, 127


@UASLocalMetadataSet.add_parser
class ImageSourceSensor(StringElementParser):
    key = b'\x0B'
    TAG = 11
    UDSKey = "06 0E 2B 34 01 01 01 01 04 20 01 02 01 01 00 00"
    LDSName = "Image Source Sensor"
    ESDName = "Sensor Name"
    UDSName = "Image Source Device"
    min_length, max_length = 0, 127


@UASLocalMetadataSet.add_parser
class ImageCoordinateSystem(StringElementParser):
    key = b'\x0C'
    TAG = 12
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 01 01 00 00 00 00"
    LDSName = "Image Coordinate System"
    ESDName = "Image Coordinate System"
    UDSName = "Image Coordinate System"
    min_length, max_length = 0, 127


@UASLocalMetadataSet.add_parser
class SensorLatitude(MappedElementParser):
    key = b'\x0D'
    TAG = 13
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 02 04 02 00"
    LDSName = "Sensor Latitude"
    ESDName = "Sensor Latitude"
    UDSName = "Device Latitude"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class SensorLongitude(MappedElementParser):
    key = b'\x0E'
    TAG = 14
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 02 06 02 00"
    LDSName = "Sensor Longitude"
    ESDName = "Sensor Longitude"
    UDSName = "Device Longitude"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class SensorTrueAltitude(MappedElementParser):
    key = b'\x0F'
    TAG = 15
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 02 02 00 00"
    LDSName = "Sensor True Altitude"
    ESDName = "Sensor Altitude"
    UDSName = "Device Altitude"
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 19000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class SensorHorizontalFieldOfView(MappedElementParser):
    key = b'\x10'
    TAG = 16
    UDSKey = "06 0E 2B 34 01 01 01 02 04 20 02 01 01 08 00 00"
    LDSName = "Sensor Horizontal Field of View"
    ESDName = "Field of View"
    UDSName = "Field of View (FOVHorizontal)"
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class SensorVerticalFieldOfView(MappedElementParser):
    key = b'\x11'
    TAG = 17
    UDSKey = "-"
    LDSName = "Sensor Vertical Field of View"
    ESDName = "Vertical Field of View"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class SensorRelativeAzimuthAngle(MappedElementParser):
    key = b'\x12'
    TAG = 18
    UDSKey = "-"
    LDSName = "Sensor Relative Azimuth Angle"
    ESDName = "Sensor Relative Azimuth Angle"
    UDSName = ""
    _domain = (0, 2 ** 32 - 1)
    _range = (0, 360)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class SensorRelativeElevationAngle(MappedElementParser):
    key = b'\x13'
    TAG = 19
    UDSKey = "-"
    LDSName = "Sensor Relative Elevation Angle"
    ESDName = "Sensor Relative Elevation Angle"
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class SensorRelativeRollAngle(MappedElementParser):
    key = b'\x14'
    TAG = 20
    UDSKey = "-"
    LDSName = "Sensor Relative Roll Angle"
    ESDName = "Sensor Relative Roll Angle"
    UDSName = ""
    _domain = (0, 2 ** 32 - 1)
    _range = (0, 360)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class SlantRange(MappedElementParser):
    key = b'\x15'
    TAG = 21
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 08 01 01 00 00 00"
    LDSName = "Slant Range"
    ESDName = "Slant Range"
    UDSName = "Slant Range"
    _domain = (0, 2 ** 32 - 1)
    _range = (0, +5e6)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class TargetWidth(MappedElementParser):
    key = b'\x16'
    TAG = 22
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 09 02 01 00 00 00"
    LDSName = "Target Width"
    ESDName = "Target Width"
    UDSName = "Target Width"
    _domain = (0, 2 ** 16 - 1)
    _range = (0, +10e3)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class FrameCenterLatitude(MappedElementParser):
    key = b'\x17'
    TAG = 23
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 03 02 00 00"
    LDSName = "Frame Center Latitude"
    ESDName = "Target Latitude"
    UDSName = "Frame Center Latitude"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class FrameCenterLongitude(MappedElementParser):
    key = b'\x18'
    TAG = 24
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 02 01 03 04 00 00"
    LDSName = "Frame Center Longitude"
    ESDName = "Target Longitude"
    UDSName = "Frame Center Longitude"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class FrameCenterElevation(MappedElementParser):
    key = b'\x19'
    TAG = 25
    UDSKey = "-"
    LDSName = "Frame Center Elevation"
    ESDName = "Frame Center Elevation"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, +19e3)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class OffsetCornerLatitudePoint1(MappedElementParser):
    key = b'\x1A'
    TAG = 26
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 07 01 00"
    LDSName = "Offset Corner Latitude Point 1"
    ESDName = "SAR Latitude 4"
    UDSName = "Corner Latitude Point 1"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, +0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class OffsetCornerLongitudePoint1(MappedElementParser):
    key = b'\x1B'
    TAG = 27
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0B 01 00"
    LDSName = "Offset Corner Longitude Point 1"
    ESDName = "SAR Longitude 4"
    UDSName = "Corner Longitude Point 1"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class OffsetCornerLatitudePoint2(MappedElementParser):
    key = b'\x1C'
    TAG = 28
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 08 01 00"
    LDSName = "Offset Corner Latitude Point 2"
    ESDName = "SAR Latitude 1"
    UDSName = "Corner Latitude Point 2"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class OffsetCornerLongitudePoint2(MappedElementParser):
    key = b'\x1D'
    TAG = 29
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0C 01 00"
    LDSName = "Offset Corner Longitude Point 2"
    ESDName = "SAR Longitude 1"
    UDSName = "Corner Longitude Point 2"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class OffsetCornerLatitudePoint3(MappedElementParser):
    key = b'\x1E'
    TAG = 30
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 09 01 00"
    LDSName = "Offset Corner Latitude Point 3"
    ESDName = "SAR Latitude 2"
    UDSName = "Corner Latitude Point 3"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class OffsetCornerLongitudePoint3(MappedElementParser):
    key = b'\x1F'
    TAG = 31
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0D 01 00"
    LDSName = "Offset Corner Longitude Point 3"
    ESDName = "SAR Longitude 2"
    UDSName = "Corner Longitude Point 3"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class OffsetCornerLatitudePoint4(MappedElementParser):
    key = b'\x20'
    TAG = 32
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0A 01 00"
    LDSName = "Offset Corner Latitude Point 4"
    ESDName = "SAR Latitude 3"
    UDSName = "Corner Latitude Point 4"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class OffsetCornerLongitudePoint4(MappedElementParser):
    key = b'\x21'
    TAG = 33
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0E 01 00"
    LDSName = "Offset Corner Longitude Point 4"
    ESDName = "SAR Longitude 3"
    UDSName = "Corner Longitude Point 4"
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-0.075, 0.075)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class IcingDetected(MappedElementParser):
    key = b'\x22'
    TAG = 34
    UDSKey = ""
    LDSName = "Icing Detected"
    ESDName = "Icing Detected"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)
    units = 'flag'


@UASLocalMetadataSet.add_parser
class WindDirection(MappedElementParser):
    key = b'\x23'
    TAG = 35
    UDSKey = "-"
    LDSName = "Wind Direction"
    ESDName = "Wind Direction"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, +360)
    units = 'meters/second'


@UASLocalMetadataSet.add_parser
class WindSpeed(MappedElementParser):
    key = b'\x24'
    TAG = 36
    UDSKey = "-"
    LDSName = "Wind Speed"
    ESDName = "Wind Speed"
    UDSName = ""
    _domain = (0, 255)
    _range = (0, +100)
    units = 'meters/second'


@UASLocalMetadataSet.add_parser
class StaticPressure(MappedElementParser):
    key = b'\x25'
    TAG = 37
    UDSKey = "-"
    LDSName = "Static Pressure"
    ESDName = "Static Pressure"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, +5000)
    units = 'millibar'


@UASLocalMetadataSet.add_parser
class DensityAltitude(MappedElementParser):
    key = b'\x26'
    TAG = 38
    UDSKey = "-"
    LDSName = "Density Altitude"
    ESDName = "Density Altitude"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, +19e3)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class OutsideAirTemperature(MappedElementParser):
    key = b'\x27'
    TAG = 39
    UDSKey = "-"
    LDSName = "Outside Air Temperature"
    ESDName = "Air Temperature"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)
    units = 'celcius'


@UASLocalMetadataSet.add_parser
class TargetLocationLatitude(MappedElementParser):
    key = b'\x28'
    TAG = 40
    UDSKey = "-"
    LDSName = "Target Location Latitude"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class TargetLocationLongitude(MappedElementParser):
    key = b'\x29'
    TAG = 41
    UDSKey = "-"
    LDSName = "Target Location Longitude"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class TargetLocationElevation(MappedElementParser):
    key = b'\x2A'
    TAG = 42
    UDSKey = "-"
    LDSName = "Target Location Elevation"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 19000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class TargetTrackGateWidth(MappedElementParser):
    key = b'\x2B'
    TAG = 43
    UDSKey = "-"
    LDSName = "Target Track Gate Width"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 512)
    units = 'pixels'


@UASLocalMetadataSet.add_parser
class TargetTrackGateHeight(MappedElementParser):
    key = b'\x2C'
    TAG = 44
    UDSKey = "-"
    LDSName = "Target Track Gate Height"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 512)
    units = 'pixels'


@UASLocalMetadataSet.add_parser
class TargetErrorEstimateCE90(MappedElementParser):
    key = b'\x2D'
    TAG = 45
    UDSKey = "-"
    LDSName = "Target Error Estimate - CE90"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 4095)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class TargetErrorEstimateLE90(MappedElementParser):
    key = b'\x2E'
    TAG = 46
    UDSKey = "-"
    LDSName = "Target Error Estimate - LE90"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 4095)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class GenericFlagData01(MappedElementParser):
    key = b'\x2F'
    TAG = 47
    UDSKey = "-"
    LDSName = "Generic Flag Data 01"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)

# @UASLocalMetadataSet.add_parser
# class SecurityLocalMetadataSet(MappedElementParser):
#     key = b'\x30'
#     TAG = 48
#     UDSKey = "06 0E 2B 34 02 03 01 01 0E 01 03 03 02 00 00 00"
#     LDSName = "Security Local Set"
#     ESDName = ""
#     UDSName = "Security Local Set"


@UASLocalMetadataSet.add_parser
class DifferentialPressure(MappedElementParser):
    key = b'\x31'
    TAG = 49
    UDSKey = "-"
    LDSName = "Differential Pressure"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 5000)
    units = 'millibar'


@UASLocalMetadataSet.add_parser
class PlatformAngleOfAttack(MappedElementParser):
    key = b'\x32'
    TAG = 50
    UDSKey = "-"
    LDSName = "Platform Angle of Attack"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-20, 20)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class PlatformVerticalSpeed(MappedElementParser):
    key = b'\x33'
    TAG = 51
    UDSKey = "-"
    LDSName = "Platform Vertical Speed"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-180, 180)
    units = 'meters/second'


@UASLocalMetadataSet.add_parser
class PlatformSideslipAngle(MappedElementParser):
    key = b'\x34'
    TAG = 52
    UDSKey = "-"
    LDSName = "Platform Sideslip Angle"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-20, 20)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class AirfieldBarometricPressure(MappedElementParser):
    key = b'\x35'
    TAG = 53
    UDSKey = "-"
    LDSName = "Airfield Barometric Pressure"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 5000)
    units = 'millibar'


@UASLocalMetadataSet.add_parser
class AirfieldElevation(MappedElementParser):
    key = b'\x36'
    TAG = 54
    UDSKey = "-"
    LDSName = "Airfield Elevation"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 19000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class RelativeHumidity(MappedElementParser):
    key = b'\x37'
    TAG = 55
    UDSKey = "-"
    LDSName = "Relative Humidity"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 100)
    units = '%'


@UASLocalMetadataSet.add_parser
class PlatformGroundSpeed(MappedElementParser):
    key = b'\x38'
    TAG = 56
    UDSKey = "-"
    LDSName = "Platform Ground Speed"
    ESDName = "Platform Ground Speed"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 255)
    units = 'meters/second'


@UASLocalMetadataSet.add_parser
class GroundRange(MappedElementParser):
    key = b'\x39'
    TAG = 57
    UDSKey = "-"
    LDSName = "Ground Range"
    ESDName = "Ground Range"
    UDSName = ""
    _domain = (0, 2 ** 32 - 1)
    _range = (0, 5000000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class PlatformFuelRemaining(MappedElementParser):
    key = b'\x3A'
    TAG = 58
    UDSKey = "-"
    LDSName = "Platform Fuel Remaining"
    ESDName = "Platform Fuel Remaining"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 10000)
    units = 'kilograms'


@UASLocalMetadataSet.add_parser
class PlatformCallSign(StringElementParser):
    key = b'\x3B'
    TAG = 59
    UDSKey = "-"
    LDSName = "Platform Call Sign"
    ESDName = "Platform Call Sign"
    UDSName = ""


@UASLocalMetadataSet.add_parser
class WeaponLoad(MappedElementParser):
    key = b'\x3C'
    TAG = 60
    UDSKey = "-"
    LDSName = "Weapon Load"
    ESDName = "Weapon Load"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 2 ** 16 - 1)


@UASLocalMetadataSet.add_parser
class WeaponFired(MappedElementParser):
    key = b'\x3D'
    TAG = 61
    UDSKey = "-"
    LDSName = "Weapon Fired"
    ESDName = "Weapon Fired"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)


@UASLocalMetadataSet.add_parser
class LaserPRFCode(MappedElementParser):
    key = b'\x3E'
    TAG = 62
    UDSKey = "-"
    LDSName = "Laser PRF Code"
    ESDName = "Laser PRF Code"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 65535)


@UASLocalMetadataSet.add_parser
class SensorFieldOfViewName(MappedElementParser):
    key = b'\x3F'
    TAG = 63
    UDSKey = "-"
    LDSName = "Sensor Field of View Name"
    ESDName = "Sensor Field of View Name"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)


@UASLocalMetadataSet.add_parser
class PlatformMagneticHeading(MappedElementParser):
    key = b'\x40'
    TAG = 64
    UDSKey = "-"
    LDSName = "Platform Magnetic Heading"
    ESDName = "Platform Magnetic Heading"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 360)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class UASLSVersionNumber(MappedElementParser):
    key = b'\x41'
    TAG = 65
    UDSKey = "-"
    LDSName = "UAS Datalink LS Version Number"
    ESDName = "ESD ICD Version"
    UDSName = ""
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)
    units = 'number'


@UASLocalMetadataSet.add_parser
class AlternatePlatformLatitude(MappedElementParser):
    key = b'\x43'
    TAG = 67
    UDSKey = "-"
    LDSName = "Alternate Platform Latitude"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class AlternatePlatformLongitude(MappedElementParser):
    key = b'\x44'
    TAG = 68
    UDSKey = "-"
    LDSName = "Alternate Platform Longitude"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class AlternatePlatformAltitude(MappedElementParser):
    key = b'\x45'
    TAG = 69
    UDSKey = "-"
    LDSName = "Alternate Platform Altitude"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 19000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class AlternatePlatformName(StringElementParser):
    key = b'\x46'
    TAG = 70
    UDSKey = "-"
    LDSName = "Alternate Platform Name"
    ESDName = ""
    UDSName = ""
    min_length, max_length = 0, 127


@UASLocalMetadataSet.add_parser
class AlternatePlatformHeading(MappedElementParser):
    key = b'\x47'
    TAG = 71
    UDSKey = "-"
    LDSName = "Alternate Platform Heading"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (0, 360)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class EventStartTime(DateTimeElementParser):
    key = b'\x48'
    TAG = 72
    UDSKey = "06 0E 2B 34 01 01 01 01 07 02 01 02 07 01 00 00"
    LDSName = "Event Start Time - UTC"
    ESDName = "Mission Start Time, Date, and Date of Collection"
    UDSName = "Event Start Date Time - UTC"


@UASLocalMetadataSet.add_parser
class RVTLocalSet(MappedElementParser):
    key = b'\x49'
    TAG = 73
    UDSKey = "06 0E 2B 34 01 01 01 01 07 02 01 02 07 01 00 00"
    LDSName = "RVT Local Data Set"
    ESDName = ""
    UDSName = "Remote Video Terminal Local Set"


@UASLocalMetadataSet.add_parser
class VMTILocalSet(MappedElementParser):
    key = b'\x4A'
    TAG = 74
    UDSKey = "06 0E 2B 34 02 0B 01 01 0E 01 03 03 06 00 00 00"
    LDSName = "VMTI Local Set"
    ESDName = ""
    UDSName = "Video Moving Target Indicator Local Set"


@UASLocalMetadataSet.add_parser
class SensorEllipsoidHeightConversion(MappedElementParser):
    key = b'\x4B'
    TAG = 75
    UDSKey = "-"
    LDSName = "Sensor Ellipsoid Height"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 19000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class AlternatePlatformEllipsoidHeight(MappedElementParser):
    key = b'\x4C'
    TAG = 76
    UDSKey = "-"
    LDSName = "Alternate Platform Ellipsoid Height"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 19000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class OperationalMode(StringElementParser):
    key = b'\x4D'
    TAG = 77
    UDSKey = "-"
    LDSName = "Operational Mode"
    ESDName = ""
    UDSName = ""


@UASLocalMetadataSet.add_parser
class FrameCenterHeightAboveEllipsoid(MappedElementParser):
    key = b'\x4E'
    TAG = 78
    UDSKey = "-"
    LDSName = "Frame Center Height Above Ellipsoid"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 19000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class SensorNorthVelocity(MappedElementParser):
    key = b'\x4F'
    TAG = 79
    UDSKey = "-"
    LDSName = "Sensor North Velocity"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-327, 327)
    units = 'meters/second'


@UASLocalMetadataSet.add_parser
class SensorEastVelocity(MappedElementParser):
    key = b'\x50'
    TAG = 80
    UDSKey = "-"
    LDSName = "Sensor East Velocity"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 15 - 1), 2 ** 15 - 1)
    _range = (-327, 327)
    units = 'meters/second'

# @UASLocalMetadataSet.add_parser
# class ImageHorizonPixelPack(MappedElementParser):
#     key = b'\x51'
#     TAG = 81
#     UDSKey = "-"
#     LDSName = "Image Horizon Pixel Pack"
#     ESDName = ""
#     UDSName = ""


@UASLocalMetadataSet.add_parser
class CornerLatitudePoint1Full(MappedElementParser):
    key = b'\x52'
    TAG = 82
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 07 01 00"
    LDSName = "Corner Latitude Point 1 (Full)"
    ESDName = "SAR Latitude 4"
    UDSName = "Corner Latitude Point 1 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class CornerLongitudePoint1Full(MappedElementParser):
    key = b'\x53'
    TAG = 83
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0B 01 00"
    LDSName = "Corner Longitude Point 1 (Full)"
    ESDName = "SAR Longitude 4"
    UDSName = "Corner Longitude Point 1 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class CornerLatitudePoint2Full(MappedElementParser):
    key = b'\x54'
    TAG = 84
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 08 01 00"
    LDSName = "Corner Latitude Point 2 (Full)"
    ESDName = "SAR Latitude 1"
    UDSName = "Corner Latitude Point 2 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class CornerLongitudePoint2Full(MappedElementParser):
    key = b'\x55'
    TAG = 85
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0C 01 00"
    LDSName = "Corner Longitude Point 2 (Full)"
    ESDName = "SAR Longitude 1"
    UDSName = "Corner Longitude Point 2 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class CornerLatitudePoint3Full(MappedElementParser):
    key = b'\x56'
    TAG = 86
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 09 01 00"
    LDSName = "Corner Latitude Point 3 (Full)"
    ESDName = "SAR Latitude 2"
    UDSName = "Corner Latitude Point 3 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class CornerLongitudePoint3Full(MappedElementParser):
    key = b'\x57'
    TAG = 87
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0D 01 00"
    LDSName = "Corner Longitude Point 3 (Full)"
    ESDName = "SAR Longitude 2"
    UDSName = "Corner Longitude Point 3 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class CornerLatitudePoint4Full(MappedElementParser):
    key = b'\x58'
    TAG = 88
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0A 01 00"
    LDSName = "Corner Latitude Point 4 (Full)"
    ESDName = "SAR Latitude 3"
    UDSName = "Corner Latitude Point 4 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class CornerLongitudePoint4Full(MappedElementParser):
    key = b'\x59'
    TAG = 89
    UDSKey = "06 0E 2B 34 01 01 01 03 07 01 02 01 03 0E 01 00"
    LDSName = "Corner Longitude Point 4 (Full)"
    ESDName = "SAR Longitude 3"
    UDSName = "Corner Longitude Point 4 (Decimal Degrees)"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-180, 180)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class PlatformPitchAngleFull(MappedElementParser):
    key = b'\x5A'
    TAG = 90
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 05 00 00 00"
    LDSName = "Platform Pitch Angle (Full)"
    ESDName = "UAV Pitch (INS)"
    UDSName = "Platform Pitch Angle"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class PlatformRollAngleFull(MappedElementParser):
    key = b'\x5B'
    TAG = 91
    UDSKey = "06 0E 2B 34 01 01 01 07 07 01 10 01 04 00 00 00"
    LDSName = "Platform Roll Angle (Full)"
    ESDName = "UAV Roll (INS)"
    UDSName = "Platform Roll Angle"
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class PlatformAngleOfAttackFull(MappedElementParser):
    key = b'\x5C'
    TAG = 92
    UDSKey = "-"
    LDSName = "Platform Angle of Attack (Full)"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'


@UASLocalMetadataSet.add_parser
class PlatformSideslipAngleFull(MappedElementParser):
    key = b'\x5D'
    TAG = 93
    UDSKey = "-"
    LDSName = "Platform Sideslip Angle (Full)"
    ESDName = ""
    UDSName = ""
    _domain = (-(2 ** 31 - 1), 2 ** 31 - 1)
    _range = (-90, 90)
    units = 'degrees'

# @UASLocalMetadataSet.add_parser
# class MIISCoreIdentifier(StringElementParser):
#     key = b'\x5E'
#     TAG = 94
#     UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 04 05 03 00 00 00"
#     LDSName = "MIIS Core Identifier"
#     ESDName = ""
#     UDSName = "Motion Imagery Identification System Core"

# @UASLocalMetadataSet.add_parser
# class SARMotionImageryLocalSet(StringElementParser):
#     key = b'\x5F'
#     TAG = 95
#     UDSKey = "06 0E 2B 34 02 0B 01 01 0E 01 03 03 0D 00 00 00"
#     LDSName = "SAR Motion Imagery Local Set"
#     ESDName = ""
#     UDSName = "SAR Motion Imagery Local Set"


@UASLocalMetadataSet.add_parser
class TargetWidthExtended(MappedElementParser):
    key = b'\x60'
    TAG = 96
    UDSKey = "06 0E 2B 34 01 01 01 01 07 01 09 02 01 00 00 00"
    LDSName = "Target Width Extended"
    ESDName = "Target Width"
    UDSName = "Target Width"
    _domain = (0, 2 ** 8 - 1)
    _range = (0, 2 ** 8 - 1)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class DensityAltitudeExtended(MappedElementParser):
    key = b'\x67'
    TAG = 103
    UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 01 01 10 00 00 00"
    LDSName = "Density Altitude Extended"
    ESDName = "Density Altitude"
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 40000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class SensorEllipsoidHeightExtended(MappedElementParser):
    key = b'\x68'
    TAG = 104
    UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 02 01 82 47 00 00"
    LDSName = "Sensor Ellipsoid Height Extended"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 40000)
    units = 'meters'


@UASLocalMetadataSet.add_parser
class AlternatePlatformEllipsoidHeightExtended(MappedElementParser):
    key = b'\x69'
    TAG = 105
    UDSKey = "06 0E 2B 34 01 01 01 01 0E 01 02 01 82 48 00 00"
    LDSName = " Alternate Platform Ellipsoid Height Extended"
    ESDName = ""
    UDSName = ""
    _domain = (0, 2 ** 16 - 1)
    _range = (-900, 40000)
    units = 'meters'
