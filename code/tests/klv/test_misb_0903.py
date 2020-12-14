#!/usr/bin/env python3

import unittest

from QGIS_FMV.klvdata.common import hexstr_to_bytes


class ParserSingleShort(unittest.TestCase):

    def test_checksum(self):
        # See MISB ST0903.5
        interpretation = "0xAA43"
        tlv_hex_bytes = hexstr_to_bytes('01 02 AA 43')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0903 import Checksum
        self.assertEqual(str(Checksum(value).value), interpretation)
        self.assertEqual(bytes(Checksum(value)), tlv_hex_bytes)

    def test_precisiontimestamp(self):
        # See MISB ST0903.5
        interpretation = "2009-01-12 22:08:22+00:00"
        tlv_hex_bytes = hexstr_to_bytes('02 08 00 04 60 50 58 4E 01 80')
        value = tlv_hex_bytes[2:]

        from QGIS_FMV.klvdata.misb0903 import PrecisionTimeStamp
        self.assertEqual(str(PrecisionTimeStamp(value).value), interpretation)
        self.assertEqual(bytes(PrecisionTimeStamp(value)), tlv_hex_bytes)

    def test_NumberDetectedTargets(self):
        # Example value and packet per MISB ST 0903.5, Section 8.1 "VMTI Local Set".
        example_value = 28
        example_ls_packet = hexstr_to_bytes('05 03 00 00 1C')

        from QGIS_FMV.klvdata.misb0903 import NumberDetectedTargets
        self.assertEqual(bytes(NumberDetectedTargets(example_value)), example_ls_packet)
        self.assertEqual(bytes(NumberDetectedTargets(example_ls_packet[2:])), example_ls_packet)


    def test_NumberReportedTargets(self):
        # Example value and packet per MISB ST 0903.5, Section 8.1 "VMTI Local Set".
        example_value = 14
        example_ls_packet = hexstr_to_bytes('06 03 00 00 0E')

        from QGIS_FMV.klvdata.misb0903 import NumberReportedTargets
        self.assertEqual(bytes(NumberReportedTargets(example_value)), example_ls_packet)
        self.assertEqual(bytes(NumberReportedTargets(example_ls_packet[2:])), example_ls_packet)

    def test_FrameWidth(self):
        # Example value and packet per MISB ST 0903.5, Section 8.1 "VMTI Local Set".
        example_value = 1920
        example_ls_packet = hexstr_to_bytes('08 03 00 07 80')

        from QGIS_FMV.klvdata.misb0903 import FrameWidth
        self.assertEqual(bytes(FrameWidth(example_value)), example_ls_packet)
        self.assertEqual(bytes(FrameWidth(example_ls_packet[2:])), example_ls_packet)

    def test_FrameHeight(self):
        # Example value and packet per MISB ST 0903.5, Section 8.1 "VMTI Local Set".
        example_value = 1080
        example_ls_packet = hexstr_to_bytes('09 03 00 04 38')

        from QGIS_FMV.klvdata.misb0903 import FrameHeight
        self.assertEqual(bytes(FrameHeight(example_value)), example_ls_packet)
        self.assertEqual(bytes(FrameHeight(example_ls_packet[2:])), example_ls_packet)

    def test_SourceSensor(self):
        # Example value and packet per MISB ST 0903.5, Section 8.1 "VMTI Local Set".
        example_value = "EO Nose"
        example_ls_packet = hexstr_to_bytes('0A 07 45 4F 20 4E 6F 73 65')

        from QGIS_FMV.klvdata.misb0903 import SourceSensor
        self.assertEqual(bytes(SourceSensor(example_value)), example_ls_packet)
        self.assertEqual(bytes(SourceSensor(example_ls_packet[2:])), example_ls_packet)

    def test_CentroidPixel(self):
        # Example value and packet per MISB ST 0903.5, Section 8.2 "VTarget Pack".
        example_value = 409600
        example_ls_packet = hexstr_to_bytes('01 03 06 40 00')

        from QGIS_FMV.klvdata.misb0903 import CentroidPixel
        self.assertEqual(bytes(CentroidPixel(example_value)), example_ls_packet)
        self.assertEqual(bytes(CentroidPixel(example_ls_packet[2:])), example_ls_packet)

    def test_BoundingBoxTopLeftPixel(self):
        # Example value and packet per MISB ST 0903.5, Section 8.2 "VTarget Pack".
        example_value = 409600
        example_ls_packet = hexstr_to_bytes('02 03 06 40 00')

        from QGIS_FMV.klvdata.misb0903 import BoundingBoxTopLeftPixel
        self.assertEqual(bytes(BoundingBoxTopLeftPixel(example_value)), example_ls_packet)
        self.assertEqual(bytes(BoundingBoxTopLeftPixel(example_ls_packet[2:])), example_ls_packet)

    def test_BoundingBoxBottomRightPixel(self):
        # Example value and packet per MISB ST 0903.5, Section 8.2 "VTarget Pack".
        example_value = 409600
        example_ls_packet = hexstr_to_bytes('03 03 06 40 00')

        from QGIS_FMV.klvdata.misb0903 import BoundingBoxBottomRightPixel
        self.assertEqual(bytes(BoundingBoxBottomRightPixel(example_value)), example_ls_packet)
        self.assertEqual(bytes(BoundingBoxBottomRightPixel(example_ls_packet[2:])), example_ls_packet)

    def test_DetectionCount(self):
        # Example value and packet per MISB ST 0903.5, Section 8.2 "VTarget Pack".
        example_value = 2765
        example_ls_packet = hexstr_to_bytes('06 02 0A CD')

        from QGIS_FMV.klvdata.misb0903 import DetectionCount
        self.assertEqual(bytes(DetectionCount(example_value)), example_ls_packet)
        self.assertEqual(bytes(DetectionCount(example_ls_packet[2:])), example_ls_packet)

    def test_TargetIntensity(self):
        # Example value and packet per MISB ST 0903.5, Section 8.2 "VTarget Pack".
        example_value = 13140
        example_ls_packet = hexstr_to_bytes('09 03 00 33 54')

        from QGIS_FMV.klvdata.misb0903 import TargetIntensity
        self.assertEqual(bytes(TargetIntensity(example_value)), example_ls_packet)
        self.assertEqual(bytes(TargetIntensity(example_ls_packet[2:])), example_ls_packet)

    def test_TargetLocation(self):
        
        example_value = (38.725267, -9.150019, 2095)
        example_ls_packet = hexstr_to_bytes('40 5c d5 8c 36 ae 6a c6 0B B3')

        from QGIS_FMV.klvdata.misb0903 import TargetLocation
        self.assertEqual(bytes(TargetLocation(example_ls_packet))[2:], example_ls_packet)

if __name__ == '__main__':
    unittest.main()