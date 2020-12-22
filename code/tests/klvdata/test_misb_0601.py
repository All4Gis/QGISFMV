#!/usr/bin/env python3

# The MIT License (MIT)
#
# Copyright (c) 2017 Matthew Pare (paretech@gmail.com)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software'), to deal
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

import unittest

from QGIS_FMV.klvdata.common import hexstr_to_bytes


class ParserSingleShort(unittest.TestCase):
    def test_checksum(self):
        # See MISB ST0902.5
        interpretation = "0xAA43"
        tlv_hex_bytes = hexstr_to_bytes('01 02 AA 43')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import Checksum
        self.assertEqual(str(Checksum(value).value), interpretation)
        self.assertEqual(bytes(Checksum(value)), tlv_hex_bytes)

    def test_precisiontimestamp(self):
        # See MISB ST0902.5
        interpretation = "2009-01-12 22:08:22+00:00"
        tlv_hex_bytes = hexstr_to_bytes('02 08 00 04 60 50 58 4E 01 80')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import PrecisionTimeStamp
        self.assertEqual(str(PrecisionTimeStamp(value).value), interpretation)
        self.assertEqual(bytes(PrecisionTimeStamp(value)), tlv_hex_bytes)

        # See MISB ST0601.9
        interpretation = "2008-10-24 00:13:29.913000+00:00"
        tlv_hex_bytes = hexstr_to_bytes('02 08 00 04 59 F4 A6 AA 4A A8')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import PrecisionTimeStamp
        self.assertEqual(str(PrecisionTimeStamp(value).value), interpretation)
        self.assertEqual(bytes(PrecisionTimeStamp(value)), tlv_hex_bytes)

    def test_MissionID(self):
        # See MISB ST0902.5
        interpretation = "Mission 12"
        tlv_hex_bytes = hexstr_to_bytes('03 0A 4D 69 73 73 69 6F 6E 20 31 32')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import MissionID
        self.assertEqual(str(MissionID(value).value), interpretation)
        self.assertEqual(bytes(MissionID(value)), tlv_hex_bytes)

        # See MISB ST0601.9
        interpretation = "MISSION01"
        tlv_hex_bytes = hexstr_to_bytes('03 09 4D 49 53 53 49 4F 4E 30 31')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import MissionID
        self.assertEqual(str(MissionID(value).value), interpretation)
        self.assertEqual(bytes(MissionID(value)), tlv_hex_bytes)

    def test_PlatformTailNumber(self):
        # See MISB ST0601.9
        interpretation = "AF-101"
        tlv_hex_bytes = hexstr_to_bytes('04 06 41 46 2D 31 30 31')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import PlatformTailNumber
        self.assertEqual(str(PlatformTailNumber(value).value), interpretation)
        self.assertEqual(bytes(PlatformTailNumber(value)), tlv_hex_bytes)

    def test_PlatformHeadingAngle(self):

        # See MISB ST0601.9
        # @TODO: Limit display precision and add units as per example.
        interpretation = "159.97436484321355"
        tlv_hex_bytes = hexstr_to_bytes('05 02 71 C2')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import PlatformHeadingAngle
        self.assertEqual(str(PlatformHeadingAngle(value).value), interpretation)
        self.assertEqual(bytes(PlatformHeadingAngle(value)), tlv_hex_bytes)
        self.assertAlmostEqual(float(PlatformHeadingAngle(value).value), 159.974, 3)

    def test_PlatformPitchAngle(self):
        # See MISB ST0601.9
        # @TODO: Limit display precision and add units as per example.
        interpretation = "-0.4315317239905987"
        tlv_hex_bytes = hexstr_to_bytes('06 02 FD 3D')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0601 import PlatformPitchAngle
        self.assertEqual(str(PlatformPitchAngle(value).value), interpretation)
        self.assertEqual(bytes(PlatformPitchAngle(value)), tlv_hex_bytes)
        self.assertAlmostEqual(float(PlatformPitchAngle(value).value), -0.4315, 4)

    def test_PlatformRollAngle(self):
        example_value = 3.405814
        example_ls_packet = hexstr_to_bytes('07 02 08 b8')
        interpretation_string = "3.4058656575212893"

        from QGIS_FMV.klvdata.misb0601 import PlatformRollAngle
        self.assertEqual(bytes(PlatformRollAngle(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformRollAngle(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(PlatformRollAngle(example_ls_packet[2:]).value), interpretation_string)

    def test_PlatformTrueAirspeed(self):
        example_value = 147
        example_ls_packet = hexstr_to_bytes('08 01 93')
        interpretation_string = "147.0"

        from QGIS_FMV.klvdata.misb0601 import PlatformTrueAirspeed
        self.assertEqual(bytes(PlatformTrueAirspeed(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformTrueAirspeed(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(PlatformTrueAirspeed(example_ls_packet[2:]).value), interpretation_string)

    def test_PlatformIndicatedAirspeed(self):
        example_value = 159
        example_ls_packet = hexstr_to_bytes('09 01 9f')
        interpretation_string = "159.0"

        from QGIS_FMV.klvdata.misb0601 import PlatformIndicatedAirspeed
        self.assertEqual(bytes(PlatformIndicatedAirspeed(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformIndicatedAirspeed(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(PlatformIndicatedAirspeed(example_ls_packet[2:]).value), interpretation_string)

    def test_PlatformDesignation(self):
        example_value_string = 'MQ1-B'
        example_ls_packet = hexstr_to_bytes('0A 05 4D 51 31 2D 42')

        from QGIS_FMV.klvdata.misb0601 import PlatformDesignation
        self.assertEqual(bytes(PlatformDesignation(example_value_string)), example_ls_packet)
        self.assertEqual(bytes(PlatformDesignation(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(PlatformDesignation(example_ls_packet[2:]).value), example_value_string)

    def test_ImageSourceSensor(self):
        example_value_string = 'EO'
        example_ls_packet = hexstr_to_bytes('0B 02 45 4f')

        from QGIS_FMV.klvdata.misb0601 import ImageSourceSensor
        self.assertEqual(bytes(ImageSourceSensor(example_value_string)), example_ls_packet)
        self.assertEqual(bytes(ImageSourceSensor(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(ImageSourceSensor(example_ls_packet[2:]).value), example_value_string)

    def test_ImageCoordinateSystem(self):
        example_value_string = 'WGS-84'
        example_ls_packet = hexstr_to_bytes('0C 06 57 47 53 2d 38 34')

        from QGIS_FMV.klvdata.misb0601 import ImageCoordinateSystem
        self.assertEqual(bytes(ImageCoordinateSystem(example_value_string)), example_ls_packet)
        self.assertEqual(bytes(ImageCoordinateSystem(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(ImageCoordinateSystem(example_ls_packet[2:]).value), example_value_string)

    def test_SensorLatitude(self):
        example_value = 60.1768229669783
        example_ls_packet = hexstr_to_bytes('0D 04 55 95 B6 6D')
        interpretation_string = "60.176822966978335"

        from QGIS_FMV.klvdata.misb0601 import SensorLatitude
        self.assertEqual(bytes(SensorLatitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorLatitude(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(SensorLatitude(example_ls_packet[2:]).value), interpretation_string)

    def test_SensorLongitude(self):
        example_value = 128.426759042045
        example_ls_packet = hexstr_to_bytes('0E 04 5B 53 60 c4')
        interpretation_string = "128.42675904204452"

        from QGIS_FMV.klvdata.misb0601 import SensorLongitude
        self.assertEqual(bytes(SensorLongitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorLongitude(example_ls_packet[2:])), example_ls_packet)
        self.assertEqual(str(SensorLongitude(example_ls_packet[2:]).value), interpretation_string)

    def test_SensorTrueAltitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 14190.72
        example_ls_packet = hexstr_to_bytes('0F 02 c2 21')

        from QGIS_FMV.klvdata.misb0601 import SensorTrueAltitude
        self.assertEqual(bytes(SensorTrueAltitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorTrueAltitude(example_ls_packet[2:])), example_ls_packet)

    def test_SensorHorizontalFieldOfView(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 144.5713
        example_ls_packet = hexstr_to_bytes('10 02 cd 9c')

        from QGIS_FMV.klvdata.misb0601 import SensorHorizontalFieldOfView
        self.assertEqual(bytes(SensorHorizontalFieldOfView(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorHorizontalFieldOfView(example_ls_packet[2:])), example_ls_packet)

    def test_SensorVerticalFieldOfView(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 152.6436
        example_ls_packet = hexstr_to_bytes('11 02 d9 17')

        from QGIS_FMV.klvdata.misb0601 import SensorVerticalFieldOfView
        self.assertEqual(bytes(SensorVerticalFieldOfView(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorVerticalFieldOfView(example_ls_packet[2:])), example_ls_packet)

    def test_SensorRelativeAzimuthAngle(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 160.719211474396
        example_ls_packet = hexstr_to_bytes('12 04 72 4a 0a 20')

        from QGIS_FMV.klvdata.misb0601 import SensorRelativeAzimuthAngle
        self.assertEqual(bytes(SensorRelativeAzimuthAngle(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorRelativeAzimuthAngle(example_ls_packet[2:])), example_ls_packet)

    def test_SensorRelativeElevationAngle(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -168.792324833941
        example_ls_packet = hexstr_to_bytes('13 04 87 f8 4b 86')

        from QGIS_FMV.klvdata.misb0601 import SensorRelativeElevationAngle
        self.assertEqual(bytes(SensorRelativeElevationAngle(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorRelativeElevationAngle(example_ls_packet[2:])), example_ls_packet)

    def test_SensorRelativeRollAngle(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 176.865437690572
        example_ls_packet = hexstr_to_bytes('14 04 7d c5 5e ce')

        from QGIS_FMV.klvdata.misb0601 import SensorRelativeRollAngle
        self.assertEqual(bytes(SensorRelativeRollAngle(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorRelativeRollAngle(example_ls_packet[2:])), example_ls_packet)

    def test_SlantRange(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 68590.9832
        example_ls_packet = hexstr_to_bytes('15 04 03 83 09 26')

        from QGIS_FMV.klvdata.misb0601 import SlantRange
        self.assertEqual(bytes(SlantRange(example_value)), example_ls_packet)
        self.assertEqual(bytes(SlantRange(example_ls_packet[2:])), example_ls_packet)

    def test_TargetWidth(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 722.8199
        example_ls_packet = hexstr_to_bytes('16 02 12 81')

        from QGIS_FMV.klvdata.misb0601 import TargetWidth
        self.assertEqual(bytes(TargetWidth(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetWidth(example_ls_packet[2:])), example_ls_packet)

    def test_FrameCenterLatitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -10.5423886331461
        example_ls_packet = hexstr_to_bytes('17 04 f1 01 a2 29')

        from QGIS_FMV.klvdata.misb0601 import FrameCenterLatitude
        self.assertEqual(bytes(FrameCenterLatitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(FrameCenterLatitude(example_ls_packet[2:])), example_ls_packet)

    def test_FrameCenterLongitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 29.157890122923
        example_ls_packet = hexstr_to_bytes('18 04 14 bc 08 2b')

        from QGIS_FMV.klvdata.misb0601 import FrameCenterLongitude
        self.assertEqual(bytes(FrameCenterLongitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(FrameCenterLongitude(example_ls_packet[2:])), example_ls_packet)

    def test_FrameCenterElevation(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 3216.037
        example_ls_packet = hexstr_to_bytes('19 02 34 f3')

        from QGIS_FMV.klvdata.misb0601 import FrameCenterElevation
        self.assertEqual(bytes(FrameCenterElevation(example_value)), example_ls_packet)
        self.assertEqual(bytes(FrameCenterElevation(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLatitudePoint1(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_latitude = -10.5423886331461
        example_value = -10.579637999887 - frame_center_latitude
        example_ls_packet = hexstr_to_bytes('1a 02 c0 6e')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLatitudePoint1
        self.assertEqual(bytes(OffsetCornerLatitudePoint1(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLatitudePoint1(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLongitudePoint1(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_longitude = 29.157890122923
        example_value = 29.1273677986333 - frame_center_longitude
        example_ls_packet = hexstr_to_bytes('1b 02 cb e9')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLongitudePoint1
        self.assertEqual(bytes(OffsetCornerLongitudePoint1(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLongitudePoint1(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLatitudePoint2(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_latitude = -10.5423886331461
        example_value = -10.5661816260963 - frame_center_latitude
        example_ls_packet = hexstr_to_bytes('1c 02 d7 65')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLatitudePoint2
        self.assertEqual(bytes(OffsetCornerLatitudePoint2(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLatitudePoint2(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLongitudePoint2(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_longitude = 29.157890122923
        example_value = 29.140824172424 - frame_center_longitude
        example_ls_packet = hexstr_to_bytes('1d 02 e2 e0')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLongitudePoint2
        self.assertEqual(bytes(OffsetCornerLongitudePoint2(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLongitudePoint2(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLatitudePoint3(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_latitude = -10.5423886331461
        example_value = -10.5527275411938 - frame_center_latitude
        example_ls_packet = hexstr_to_bytes('1e 02 ee 5b')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLatitudePoint3
        self.assertEqual(bytes(OffsetCornerLatitudePoint3(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLatitudePoint3(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLongitudePoint3(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_longitude = 29.157890122923
        example_value = 29.1542782573265 - frame_center_longitude
        example_ls_packet = hexstr_to_bytes('1f 02 f9 d6')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLongitudePoint3
        self.assertEqual(bytes(OffsetCornerLongitudePoint3(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLongitudePoint3(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLatitudePoint4(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_latitude = -10.5423886331461
        example_value = -10.5392711674031 - frame_center_latitude
        example_ls_packet = hexstr_to_bytes('20 02 05 52')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLatitudePoint4
        self.assertEqual(bytes(OffsetCornerLatitudePoint4(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLatitudePoint4(example_ls_packet[2:])), example_ls_packet)

    def test_OffsetCornerLongitudePoint4(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        frame_center_longitude = 29.157890122923
        example_value = 29.1677346311172 - frame_center_longitude
        example_ls_packet = hexstr_to_bytes('21 02 10 cd')

        from QGIS_FMV.klvdata.misb0601 import OffsetCornerLongitudePoint4
        self.assertEqual(bytes(OffsetCornerLongitudePoint4(example_value)), example_ls_packet)
        self.assertEqual(bytes(OffsetCornerLongitudePoint4(example_ls_packet[2:])), example_ls_packet)

    def test_IcingDetected(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 155
        example_ls_packet = hexstr_to_bytes('22 01 9b')

        from QGIS_FMV.klvdata.misb0601 import IcingDetected
        self.assertEqual(bytes(IcingDetected(example_value)), example_ls_packet)
        self.assertEqual(bytes(IcingDetected(example_ls_packet[2:])), example_ls_packet)

    def test_WindDirection(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 235.924
        example_ls_packet = hexstr_to_bytes('23 02 a7 c4')

        from QGIS_FMV.klvdata.misb0601 import WindDirection
        self.assertEqual(bytes(WindDirection(example_value)), example_ls_packet)
        self.assertEqual(bytes(WindDirection(example_ls_packet[2:])), example_ls_packet)

    def test_WindSpeed(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 69.80392
        example_ls_packet = hexstr_to_bytes('24 01 b2')

        from QGIS_FMV.klvdata.misb0601 import WindSpeed
        self.assertEqual(bytes(WindSpeed(example_value)), example_ls_packet)
        self.assertEqual(bytes(WindSpeed(example_ls_packet[2:])), example_ls_packet)

    def test_StaticPressure(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 3725.185
        example_ls_packet = hexstr_to_bytes('25 02 be ba')

        from QGIS_FMV.klvdata.misb0601 import StaticPressure
        self.assertEqual(bytes(StaticPressure(example_value)), example_ls_packet)
        self.assertEqual(bytes(StaticPressure(example_ls_packet[2:])), example_ls_packet)

    def test_DensityAltitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 14818.68
        example_ls_packet = hexstr_to_bytes('26 02 CA 35')

        from QGIS_FMV.klvdata.misb0601 import DensityAltitude
        self.assertEqual(bytes(DensityAltitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(DensityAltitude(example_ls_packet[2:])), example_ls_packet)

    def test_OutsideAirTemperature(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 84
        example_ls_packet = hexstr_to_bytes('27 01 54')

        from QGIS_FMV.klvdata.misb0601 import OutsideAirTemperature
        self.assertEqual(bytes(OutsideAirTemperature(example_value)), example_ls_packet)
        self.assertEqual(bytes(OutsideAirTemperature(example_ls_packet[2:])), example_ls_packet)

    def test_TargetLocationLatitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -79.1638500518929
        example_ls_packet = hexstr_to_bytes('28 04 8F 69 52 62')

        from QGIS_FMV.klvdata.misb0601 import TargetLocationLatitude
        self.assertEqual(bytes(TargetLocationLatitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetLocationLatitude(example_ls_packet[2:])), example_ls_packet)

    def test_TargetLocationLongitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 166.400812960416
        example_ls_packet = hexstr_to_bytes('29 04 76 54 57 F2')

        from QGIS_FMV.klvdata.misb0601 import TargetLocationLongitude
        self.assertEqual(bytes(TargetLocationLongitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetLocationLongitude(example_ls_packet[2:])), example_ls_packet)

    def test_TargetLocationElevation(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 18389.05
        example_ls_packet = hexstr_to_bytes('2A 02 F8 23')

        from QGIS_FMV.klvdata.misb0601 import TargetLocationElevation
        self.assertEqual(bytes(TargetLocationElevation(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetLocationElevation(example_ls_packet[2:])), example_ls_packet)

    def test_TargetTrackGateWidth(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 6
        example_ls_packet = hexstr_to_bytes('2B 01 03')

        from QGIS_FMV.klvdata.misb0601 import TargetTrackGateWidth
        self.assertEqual(bytes(TargetTrackGateWidth(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetTrackGateWidth(example_ls_packet[2:])), example_ls_packet)

    def test_TargetTrackGateHeight(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 30
        example_ls_packet = hexstr_to_bytes('2C 01 0F')

        from QGIS_FMV.klvdata.misb0601 import TargetTrackGateHeight
        self.assertEqual(bytes(TargetTrackGateHeight(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetTrackGateHeight(example_ls_packet[2:])), example_ls_packet)

    def test_TargetErrorEstimateCE90(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 425.21515
        example_ls_packet = hexstr_to_bytes('2D 02 1A 95')

        from QGIS_FMV.klvdata.misb0601 import TargetErrorEstimateCE90
        self.assertEqual(bytes(TargetErrorEstimateCE90(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetErrorEstimateCE90(example_ls_packet[2:])), example_ls_packet)

    def test_TargetErrorEstimateLE90(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 608.92309
        example_ls_packet = hexstr_to_bytes('2E 02 26 11')

        from QGIS_FMV.klvdata.misb0601 import TargetErrorEstimateLE90
        self.assertEqual(bytes(TargetErrorEstimateLE90(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetErrorEstimateLE90(example_ls_packet[2:])), example_ls_packet)

    def test_GenericFlagData01(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 49
        example_ls_packet = hexstr_to_bytes('2F 01 31')

        from QGIS_FMV.klvdata.misb0601 import GenericFlagData01
        self.assertEqual(bytes(GenericFlagData01(example_value)), example_ls_packet)
        self.assertEqual(bytes(GenericFlagData01(example_ls_packet[2:])), example_ls_packet)

    # Tag 48 (0x30) Security (MISB ST 0102) Local Set

    def test_DifferentialPressure(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 1191.958
        example_ls_packet = hexstr_to_bytes('31 02 3D 07')

        from QGIS_FMV.klvdata.misb0601 import DifferentialPressure
        self.assertEqual(bytes(DifferentialPressure(example_value)), example_ls_packet)
        self.assertEqual(bytes(DifferentialPressure(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformAngleOfAttack(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -8.670177
        example_ls_packet = hexstr_to_bytes('32 02 C8 83')

        from QGIS_FMV.klvdata.misb0601 import PlatformAngleOfAttack
        self.assertEqual(bytes(PlatformAngleOfAttack(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformAngleOfAttack(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformVerticalSpeed(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -61.88693
        example_ls_packet = hexstr_to_bytes('33 02 D3 FE')

        from QGIS_FMV.klvdata.misb0601 import PlatformVerticalSpeed
        self.assertEqual(bytes(PlatformVerticalSpeed(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformVerticalSpeed(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformSideslipAngle(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -5.082475
        example_ls_packet = hexstr_to_bytes('34 02 DF 79')

        from QGIS_FMV.klvdata.misb0601 import PlatformSideslipAngle
        self.assertEqual(bytes(PlatformSideslipAngle(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformSideslipAngle(example_ls_packet[2:])), example_ls_packet)

    def test_AirfieldBarometricPressure(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 2088.96
        example_ls_packet = hexstr_to_bytes('35 02 6A F4')

        from QGIS_FMV.klvdata.misb0601 import AirfieldBarometricPressure
        self.assertEqual(bytes(AirfieldBarometricPressure(example_value)), example_ls_packet)
        self.assertEqual(bytes(AirfieldBarometricPressure(example_ls_packet[2:])), example_ls_packet)

    def test_AirfieldElevation(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 8306.806
        example_ls_packet = hexstr_to_bytes('36 02 76 70')

        from QGIS_FMV.klvdata.misb0601 import AirfieldElevation
        self.assertEqual(bytes(AirfieldElevation(example_value)), example_ls_packet)
        self.assertEqual(bytes(AirfieldElevation(example_ls_packet[2:])), example_ls_packet)

    def test_RelativeHumidity(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 50.58823
        example_ls_packet = hexstr_to_bytes('37 01 81')

        from QGIS_FMV.klvdata.misb0601 import RelativeHumidity
        self.assertEqual(bytes(RelativeHumidity(example_value)), example_ls_packet)
        self.assertEqual(bytes(RelativeHumidity(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformGroundSpeed(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 140
        example_ls_packet = hexstr_to_bytes('38 01 8C')

        from QGIS_FMV.klvdata.misb0601 import PlatformGroundSpeed
        self.assertEqual(bytes(PlatformGroundSpeed(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformGroundSpeed(example_ls_packet[2:])), example_ls_packet)

    def test_GroundRange(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 3506979.0316
        example_ls_packet = hexstr_to_bytes('39 04 b3 8e ac f1')

        from QGIS_FMV.klvdata.misb0601 import GroundRange
        self.assertEqual(bytes(GroundRange(example_value)), example_ls_packet)
        self.assertEqual(bytes(GroundRange(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformFuelRemaining(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 6420.539
        example_ls_packet = hexstr_to_bytes('3A 02 A4 5D')

        from QGIS_FMV.klvdata.misb0601 import PlatformFuelRemaining
        self.assertEqual(bytes(PlatformFuelRemaining(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformFuelRemaining(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformCallSign(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = "TOP GUN"
        example_ls_packet = hexstr_to_bytes('3B 07 54 4F 50 20 47 55 4E')

        from QGIS_FMV.klvdata.misb0601 import PlatformCallSign
        self.assertEqual(bytes(PlatformCallSign(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformCallSign(example_ls_packet[2:])), example_ls_packet)

    def test_WeaponLoad(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 45016
        example_ls_packet = hexstr_to_bytes('3C 02 AF D8')

        from QGIS_FMV.klvdata.misb0601 import WeaponLoad
        self.assertEqual(bytes(WeaponLoad(example_value)), example_ls_packet)
        self.assertEqual(bytes(WeaponLoad(example_ls_packet[2:])), example_ls_packet)

    def test_WeaponFired(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 186
        example_ls_packet = hexstr_to_bytes('3D 01 BA')

        from QGIS_FMV.klvdata.misb0601 import WeaponFired
        self.assertEqual(bytes(WeaponFired(example_value)), example_ls_packet)
        self.assertEqual(bytes(WeaponFired(example_ls_packet[2:])), example_ls_packet)

    def test_LaserPRFCode(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 50895
        example_ls_packet = hexstr_to_bytes('3E 02 C6 CF')

        from QGIS_FMV.klvdata.misb0601 import LaserPRFCode
        self.assertEqual(bytes(LaserPRFCode(example_value)), example_ls_packet)
        self.assertEqual(bytes(LaserPRFCode(example_ls_packet[2:])), example_ls_packet)

    def test_SensorFieldOfViewName(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 209
        example_ls_packet = hexstr_to_bytes('3F 01 D1')

        from QGIS_FMV.klvdata.misb0601 import SensorFieldOfViewName
        self.assertEqual(bytes(SensorFieldOfViewName(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorFieldOfViewName(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformMagneticHeading(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 311.8682
        example_ls_packet = hexstr_to_bytes('40 02 DD C5')

        from QGIS_FMV.klvdata.misb0601 import PlatformMagneticHeading
        self.assertEqual(bytes(PlatformMagneticHeading(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformMagneticHeading(example_ls_packet[2:])), example_ls_packet)


    def test_UASLSVersionNumber(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 232
        example_ls_packet = hexstr_to_bytes('41 01 E8')
 
        from QGIS_FMV.klvdata.misb0601 import UASLSVersionNumber
        self.assertEqual(bytes(UASLSVersionNumber(example_value)), example_ls_packet)
        self.assertEqual(bytes(UASLSVersionNumber(example_ls_packet[2:])), example_ls_packet)

    # Tag 66 (0x42) Target Location Covariance Matrix

    def test_AlternatePlatformLatitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -86.041207348947
        example_ls_packet = hexstr_to_bytes('43 04 85 A1 5A 39')

        from QGIS_FMV.klvdata.misb0601 import AlternatePlatformLatitude
        self.assertEqual(bytes(AlternatePlatformLatitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(AlternatePlatformLatitude(example_ls_packet[2:])), example_ls_packet)

    def test_AlternatePlatformLongitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 0.155527554524842
        example_ls_packet = hexstr_to_bytes('44 04 00 1C 50 1C')

        from QGIS_FMV.klvdata.misb0601 import AlternatePlatformLongitude
        self.assertEqual(bytes(AlternatePlatformLongitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(AlternatePlatformLongitude(example_ls_packet[2:])), example_ls_packet)

    def test_AlternatePlatformAltitude(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 9.445334
        example_ls_packet = hexstr_to_bytes('45 02 0B B3')

        from QGIS_FMV.klvdata.misb0601 import AlternatePlatformAltitude
        self.assertEqual(bytes(AlternatePlatformAltitude(example_value)), example_ls_packet)
        self.assertEqual(bytes(AlternatePlatformAltitude(example_ls_packet[2:])), example_ls_packet)

    def test_AlternatePlatformName(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 'APACHE'
        example_ls_packet = hexstr_to_bytes('46 06 41 50 41 43 48 45')

        from QGIS_FMV.klvdata.misb0601 import AlternatePlatformName
        self.assertEqual(bytes(AlternatePlatformName(example_value)), example_ls_packet)
        self.assertEqual(bytes(AlternatePlatformName(example_ls_packet[2:])), example_ls_packet)

    def test_AlternatePlatformHeading(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 32.60242
        example_ls_packet = hexstr_to_bytes('47 02 17 2F')

        from QGIS_FMV.klvdata.misb0601 import AlternatePlatformHeading
        self.assertEqual(bytes(AlternatePlatformHeading(example_value)), example_ls_packet)
        self.assertEqual(bytes(AlternatePlatformHeading(example_ls_packet[2:])), example_ls_packet)

    def test_EventStartTime(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = '1995-04-16 12:44:54.670901+00:00'
        example_ls_packet = hexstr_to_bytes('48 08 00 02 D5 CF 4D DC 9A 35')

        from QGIS_FMV.klvdata.misb0601 import EventStartTime
        # Taking time from string not supported at this time. Use datetime instead.
        # self.assertEqual(bytes(EventStartTime(example_value)), example_ls_packet)
        self.assertEqual(bytes(EventStartTime(example_ls_packet[2:])), example_ls_packet)

    # Tag 73 (0x49) RVT (MISB ST 0806) Local Set

    # Tag 74 (0x4A) VMTI (MISB ST 0903) Local Set

    def test_SensorEllipsoidHeightConversion(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 14190.72
        example_ls_packet = hexstr_to_bytes('4B 02 C2 21')

        from QGIS_FMV.klvdata.misb0601 import SensorEllipsoidHeightConversion
        self.assertEqual(bytes(SensorEllipsoidHeightConversion(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorEllipsoidHeightConversion(example_ls_packet[2:])), example_ls_packet)

    def test_AlternatePlatformEllipsoidHeight(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 9.445334
        example_ls_packet = hexstr_to_bytes('4C 02 0B B3')

        from QGIS_FMV.klvdata.misb0601 import AlternatePlatformEllipsoidHeight
        self.assertEqual(bytes(AlternatePlatformEllipsoidHeight(example_value)), example_ls_packet)
        self.assertEqual(bytes(AlternatePlatformEllipsoidHeight(example_ls_packet[2:])), example_ls_packet)

    def test_OperationalMode(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = b'\x00'
        example_ls_packet = hexstr_to_bytes('4D 01 00')

        from QGIS_FMV.klvdata.misb0601 import OperationalMode
        self.assertEqual(bytes(OperationalMode(example_value)), example_ls_packet)
        self.assertEqual(bytes(OperationalMode(example_ls_packet[2:])), example_ls_packet)

    def test_FrameCenterHeightAboveEllipsoid(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 9.445334
        example_ls_packet = hexstr_to_bytes('4E 02 0B B3')

        from QGIS_FMV.klvdata.misb0601 import FrameCenterHeightAboveEllipsoid
        self.assertEqual(bytes(FrameCenterHeightAboveEllipsoid(example_value)), example_ls_packet)
        self.assertEqual(bytes(FrameCenterHeightAboveEllipsoid(example_ls_packet[2:])), example_ls_packet)

    def test_SensorNorthVelocity(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -327
        example_ls_packet = hexstr_to_bytes('4F 02 80 01')

        from QGIS_FMV.klvdata.misb0601 import SensorNorthVelocity
        self.assertEqual(bytes(SensorNorthVelocity(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorNorthVelocity(example_ls_packet[2:])), example_ls_packet)

    def test_SensorEastVelocity(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -327
        example_ls_packet = hexstr_to_bytes('50 02 80 01')

        from QGIS_FMV.klvdata.misb0601 import SensorEastVelocity
        self.assertEqual(bytes(SensorEastVelocity(example_value)), example_ls_packet)
        self.assertEqual(bytes(SensorEastVelocity(example_ls_packet[2:])), example_ls_packet)

    # Tag 81 (0x51) Image Horizon Pixel Pack

    def test_CornerLatitudePoint1Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -10.579637999887
        example_ls_packet = hexstr_to_bytes('52 04 F0 F4 12 44')

        from QGIS_FMV.klvdata.misb0601 import CornerLatitudePoint1Full
        self.assertEqual(bytes(CornerLatitudePoint1Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLatitudePoint1Full(example_ls_packet[2:])), example_ls_packet)

    def test_CornerLongitudePoint1Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 29.1273677986333
        example_ls_packet = hexstr_to_bytes('53 04 14 B6 79 B9')

        from QGIS_FMV.klvdata.misb0601 import CornerLongitudePoint1Full
        self.assertEqual(bytes(CornerLongitudePoint1Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLongitudePoint1Full(example_ls_packet[2:])), example_ls_packet)

    def test_CornerLatitudePoint2Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -10.5661816260963
        example_ls_packet = hexstr_to_bytes('54 04 F0 F8 F8 7E')

        from QGIS_FMV.klvdata.misb0601 import CornerLatitudePoint2Full
        self.assertEqual(bytes(CornerLatitudePoint2Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLatitudePoint2Full(example_ls_packet[2:])), example_ls_packet)

    def test_CornerLongitudePoint2Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 29.140824172424
        example_ls_packet = hexstr_to_bytes('55 04 14 B8 EC D6')

        from QGIS_FMV.klvdata.misb0601 import CornerLongitudePoint2Full
        self.assertEqual(bytes(CornerLongitudePoint2Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLongitudePoint2Full(example_ls_packet[2:])), example_ls_packet)

    def test_CornerLatitudePoint3Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -10.5527275411938
        example_ls_packet = hexstr_to_bytes('56 04 F0 FD DE 81')

        from QGIS_FMV.klvdata.misb0601 import CornerLatitudePoint3Full
        self.assertEqual(bytes(CornerLatitudePoint3Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLatitudePoint3Full(example_ls_packet[2:])), example_ls_packet)

    def test_CornerLongitudePoint3Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 29.1542782573265
        example_ls_packet = hexstr_to_bytes('57 04 14 BB 5F D8')

        from QGIS_FMV.klvdata.misb0601 import CornerLongitudePoint3Full
        self.assertEqual(bytes(CornerLongitudePoint3Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLongitudePoint3Full(example_ls_packet[2:])), example_ls_packet)

    def test_CornerLatitudePoint4Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -10.5392711674031
        example_ls_packet = hexstr_to_bytes('58 04 F1 02 C4 BB')

        from QGIS_FMV.klvdata.misb0601 import CornerLatitudePoint4Full
        self.assertEqual(bytes(CornerLatitudePoint4Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLatitudePoint4Full(example_ls_packet[2:])), example_ls_packet)

    def test_CornerLongitudePoint4Full(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 29.1677346311172
        example_ls_packet = hexstr_to_bytes('59 04 14 BD D2 F5')

        from QGIS_FMV.klvdata.misb0601 import CornerLongitudePoint4Full
        self.assertEqual(bytes(CornerLongitudePoint4Full(example_value)), example_ls_packet)
        self.assertEqual(bytes(CornerLongitudePoint4Full(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformPitchAngleFull(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -0.4315251
        example_ls_packet = hexstr_to_bytes('5A 04 FF 62 E2 F2')

        from QGIS_FMV.klvdata.misb0601 import PlatformPitchAngleFull
        self.assertEqual(bytes(PlatformPitchAngleFull(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformPitchAngleFull(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformRollAngleFull(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = 3.405814
        example_ls_packet = hexstr_to_bytes('5B 04 04 D8 04 DF')

        from QGIS_FMV.klvdata.misb0601 import PlatformRollAngleFull
        self.assertEqual(bytes(PlatformRollAngleFull(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformRollAngleFull(example_ls_packet[2:])), example_ls_packet)

    def test_PlatformAngleOfAttackFull(self):
        # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
        example_value = -8.670177
        example_ls_packet = hexstr_to_bytes('5C 04 F3 AB 48 EF')

        from QGIS_FMV.klvdata.misb0601 import PlatformAngleOfAttackFull
        self.assertEqual(bytes(PlatformAngleOfAttackFull(example_value)), example_ls_packet)
        self.assertEqual(bytes(PlatformAngleOfAttackFull(example_ls_packet[2:])), example_ls_packet)

#     def test_PlatformSideslipAngleFull(self):
#         # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
#         example_value = 'x'
#         example_ls_packet = hexstr_to_bytes('5D 04 00 00 00 00')
# 
#         from QGIS_FMV.klvdata.misb0601 import PlatformSideslipAngleFull
#         self.assertEqual(bytes(PlatformSideslipAngleFull(example_value)), example_ls_packet)
#         self.assertEqual(bytes(PlatformSideslipAngleFull(example_ls_packet[2:])), example_ls_packet)

    # Tag 94 (0x5E) MIIS Core Identifier (MISB ST 1204)

    # Tag 95 (0x5F) SAR Motion Imagery (MISB ST 1206) Local Set

    # TODO : MAKE IMAPB CONVERSION
    
#     def test_TargetWidthExtended(self):
#         # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
#         example_value = 13898.5463
#         example_ls_packet = hexstr_to_bytes('60 03 00 D9 2A')
#  
#         from QGIS_FMV.klvdata.misb0601 import TargetWidthExtended
#         self.assertEqual(bytes(TargetWidthExtended(example_value)), example_ls_packet)
#         self.assertEqual(bytes(TargetWidthExtended(example_ls_packet[2:])), example_ls_packet)

    # Tag 97 (0x61) Range Image (MISB ST 1002) Local Set

    # Tag 98 (0x62) Geo-Registration (MISB ST 1601) Local Set

    # Tag 99 (0x63) Composite Imaging (MISB ST 1602) Local Set

    # Tag 100 (0x64) Segment (MISB ST 1607) Local Set

    # Tag 101 (0x65) Amend (MISB ST 1607) Local Set

    # Tag 102 (0x66) SDCC-FLP (MISB ST 1010)

#     TODO : MAKE IMAPB CONVERSION
#     def test_DensityAltitudeExtended(self):
#         # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
#         example_value = 23456.24
#         example_ls_packet = hexstr_to_bytes('67 03 2F 92 1E')
#  
#         from QGIS_FMV.klvdata.misb0601 import DensityAltitudeExtended
#         self.assertEqual(bytes(DensityAltitudeExtended(example_value)), example_ls_packet)
#         self.assertEqual(bytes(DensityAltitudeExtended(example_ls_packet[2:])), example_ls_packet)
#     TODO : MAKE IMAPB CONVERSION
#     def test_SensorEllipsoidHeightExtended(self):
#         # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
#         example_value = 23456.24
#         example_ls_packet = hexstr_to_bytes('68 03 2F 92 1E')
#  
#         from QGIS_FMV.klvdata.misb0601 import SensorEllipsoidHeightExtended
#         self.assertEqual(bytes(SensorEllipsoidHeightExtended(example_value)), example_ls_packet)
#         self.assertEqual(bytes(SensorEllipsoidHeightExtended(example_ls_packet[2:])), example_ls_packet)
#     TODO : MAKE IMAPB CONVERSION
#     def test_AlternatePlatformEllipsoidHeightExtended(self):
#         # Example value and packet per MISB ST 0601.11, Section 8 "Conversions and Mappings of Metadata Types".
#         example_value = 23456.24
#         example_ls_packet = hexstr_to_bytes('69 03 2F 92 1E')
#  
#         from QGIS_FMV.klvdata.misb0601 import AlternatePlatformEllipsoidHeightExtended
#         self.assertEqual(bytes(AlternatePlatformEllipsoidHeightExtended(example_value)), example_ls_packet)
#         self.assertEqual(bytes(AlternatePlatformEllipsoidHeightExtended(example_ls_packet[2:])), example_ls_packet)


if __name__ == '__main__':
    unittest.main()
