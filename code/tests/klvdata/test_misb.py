#!/usr/bin/env python3

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

import unittest

from QGIS_FMV.klvdata.common import bytes_to_hexstr


class ParserSingleShort(unittest.TestCase):
    def test_st0102(self):
        # Test parameters from MISB ST0902.5 Annex C for "Dynamic and Constant" MISMMS Packet Data
        key = b'\x30'
        length = b'\x1c'
        value = b'\x01\x01\x01\x02\x01\x07\x03\x05//USA\x0c\x01\x07\r\x06\x00U\x00S\x00A\x16\x02\x00\n'
        klv = key + length + value

        from QGIS_FMV.klvdata.misb0102 import SecurityLocalMetadataSet

        # Basic Properties
        self.assertEqual(SecurityLocalMetadataSet(value).key, key)
        self.assertEqual(SecurityLocalMetadataSet(value).length, length)
        self.assertEqual(SecurityLocalMetadataSet(value).value, value)
        self.assertEqual(bytes(SecurityLocalMetadataSet(value)), klv)

        # Specific to value under test
        self.assertEqual(len(SecurityLocalMetadataSet(value).items), 6)

    def test_st0601_1(self):
        # This test vector from MISB ST0902.5. Some errors may have been hand corrected.
        # Annex C for "Dynamic and Constant" MISMMS Packet Data.  Sample data from MISB ST 0902.5
        klv = bytes()

        with open('./data/DynamicConstantMISMMSPacketData.bin', 'rb') as f:
            klv = f.read()

        key = klv[0:16]
        assert len(key) == 16
        length = klv[16:18]
        assert len(length) == 2
        value = klv[18:]

        from QGIS_FMV.klvdata.misb0601 import UASLocalMetadataSet
        # from misb0102 import ST0102

        # Basic Properties
        self.assertEqual(UASLocalMetadataSet(value).key, key)
        self.assertEqual(UASLocalMetadataSet(value).length, length)
        self.assertEqual(UASLocalMetadataSet(value).value, value)
        self.assertEqual(bytes(UASLocalMetadataSet(value)), klv)

        # print(ST0601(value))
    def test_st0601_2(self):
        # This test vector is hand generated, containing the MISB ST0601 16 byte key and the
        # MISB ST0102 nested security metadata local set from MISB ST0902.5
        # Annex C for "Dynamic and Constant" MISMMS Packet Data.
        key = b'\x06\x0e+4\x02\x0b\x01\x01\x0e\x01\x03\x01\x01\x00\x00\x00'
        length = b'\x1e'
        value = b'0\x1c\x01\x01\x01\x02\x01\x07\x03\x05//USA\x0c\x01\x07\r\x06\x00U\x00S\x00A\x16\x02\x00\n'
        klv = key + length + value

        from QGIS_FMV.klvdata.misb0601 import UASLocalMetadataSet
        # from misb0102 import ST0102

        # Basic Properties
        self.assertEqual(UASLocalMetadataSet(value).key, key)
        self.assertEqual(UASLocalMetadataSet(value).length, length)
        self.assertEqual(UASLocalMetadataSet(value).value, value)
        self.assertEqual(bytes(UASLocalMetadataSet(value)), klv)

    def test_st0601_timestamp(self):
        key = b'\x02'
        length = b'\x08'
        value = b'\x00\x04\x60\x50\x58\x4E\x01\x80'
        klv = key + length + value

        from QGIS_FMV.klvdata.misb0601 import PrecisionTimeStamp

        # Basic Properties
        self.assertEqual(PrecisionTimeStamp(value).key, key)
        self.assertEqual(PrecisionTimeStamp(value).length, length)
        self.assertEqual(bytes_to_hexstr(bytes(PrecisionTimeStamp(value).value)), bytes_to_hexstr(value))
        self.assertEqual(bytes(PrecisionTimeStamp(value)), klv)

        # Check __str__
        self.assertEqual(str(PrecisionTimeStamp(value)), "PrecisionTimeStamp: (b'\\x02', 8, 2009-01-12 22:08:22+00:00)")

    # def test_st0601_mission(self):
    #     with open('./samples/DynamicConstantMISMMSPacketData.bin', 'rb') as f:
    #         klv = f.read()
    #
    #     key = klv[0:16]
    #     assert len(key) == 16
    #     length = klv[16:18]
    #     assert len(length) == 2
    #     value = klv[18:]
    #
    #     from misb0601 import ST0601
    #
    #     # print(ST0601(value).items)

if __name__ == '__main__':
    unittest.main()

#
# class ParserSingleShort(unittest.TestCase):
#     def setUp(self):
#         self.key = b'\x02'
#         self.length = b'\x08'
#         self.value = b'\x00\x04\x60\x50\x58\x4E\x01\x80'
#
#         self.packet = self.key + self.length + self.value
#
#         from misb0601 import PrecisionTimeStamp
#         self.element = PrecisionTimeStamp(self.value)
#
#     def test_ber_length(self):
#         from common import ber_decode
#         from common import ber_encode
#         self.assertEquals(ber_encode(ber_decode(self.length)), self.length)
#
#     def test_modify_value(self):
#         from datetime import datetime
#         from struct import pack
#
#         time = pack('>Q', int(datetime.utcnow().timestamp()*1e6))
#
#         self.packet = self.key + self.length + time
#         self.element.value = time
#
#         self.assertEquals(bytes(self.element), self.packet)