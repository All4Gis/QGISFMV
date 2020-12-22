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
# SOFTWARE.

import unittest


class DateTime(unittest.TestCase):
    def test_datetime_decode_encode(self):
        from QGIS_FMV.klvdata.common import datetime_to_bytes
        from QGIS_FMV.klvdata.common import bytes_to_datetime

        self.assertEqual(
            datetime_to_bytes(bytes_to_datetime(b'\x00\x04\x60\x50\x58\x4E\x01\x80')),
            b'\x00\x04\x60\x50\x58\x4E\x01\x80')


class BERLength(unittest.TestCase):
    def test_ber_decode_encode(self):
        from QGIS_FMV.klvdata.common import ber_decode
        from QGIS_FMV.klvdata.common import ber_encode

        # BER Short Form
        self.assertEqual(ber_encode(ber_decode(b'\x00')), b'\x00')
        self.assertEqual(ber_encode(ber_decode(b'\x01')), b'\x01')
        self.assertEqual(ber_encode(ber_decode(b'\x08')), b'\x08')
        self.assertEqual(ber_encode(ber_decode(b'\x7F')), b'\x7F')

        # BER Long Form
        self.assertEqual(ber_encode(ber_decode(b'\x81\x80')), b'\x81\x80')
        self.assertEqual(ber_encode(ber_decode(b'\x81\xFF')), b'\x81\xFF')
        self.assertEqual(ber_encode(ber_decode(b'\x82\xFF\xFF')), b'\x82\xFF\xFF')
        self.assertEqual(ber_encode(ber_decode(b'\x83\xFF\xFF\xFF')), b'\x83\xFF\xFF\xFF')

        # BER encode using the fewest possible bytes
        self.assertEqual(ber_encode(ber_decode(b'\x80')), b'\x00')
        self.assertEqual(ber_encode(ber_decode(b'\x81\x00')), b'\x00')
        self.assertEqual(ber_encode(ber_decode(b'\x81\x01')), b'\x01')
        self.assertEqual(ber_encode(ber_decode(b'\x81\x7F')), b'\x7F')

    def test_ber_encode_decode(self):
        from QGIS_FMV.klvdata.common import ber_decode
        from QGIS_FMV.klvdata.common import ber_encode

        self.assertEqual(ber_decode(ber_encode(0)), 0)
        self.assertEqual(ber_decode(ber_encode(1)), 1)
        self.assertEqual(ber_decode(ber_encode(8)), 8)
        self.assertEqual(ber_decode(ber_encode(127)), 127)
        self.assertEqual(ber_decode(ber_encode(128)), 128)
        self.assertEqual(ber_decode(ber_encode(254)), 254)
        self.assertEqual(ber_decode(ber_encode(255)), 255)
        self.assertEqual(ber_decode(ber_encode(256)), 256)
        self.assertEqual(ber_decode(ber_encode(900)), 900)
        self.assertEqual(ber_decode(ber_encode(9000)), 9000)
        self.assertEqual(ber_decode(ber_encode(90000)), 90000)
        self.assertEqual(ber_decode(ber_encode(900000)), 900000)

    def test_ber_decode_error(self):
        from QGIS_FMV.klvdata.common import ber_decode

        with self.assertRaises(ValueError):
            ber_decode(b'\x00\x00')

        with self.assertRaises(ValueError):
            ber_decode(b'\x00\x08')

        with self.assertRaises(ValueError):
            ber_decode(b'\x80\x00')

        with self.assertRaises(ValueError):
            ber_decode(b'\x81')

        with self.assertRaises(ValueError):
            ber_decode(b'\x82\xFF')


class Strings(unittest.TestCase):
    def test_string_decode_encode(self):
        from QGIS_FMV.klvdata.common import bytes_to_str
        from QGIS_FMV.klvdata.common import str_to_bytes

        self.assertEqual(
            str_to_bytes(bytes_to_str(b'\x50\x72\x65\x64\x61\x74\x6F\x72')),
            b'\x50\x72\x65\x64\x61\x74\x6F\x72')


class HexStrings(unittest.TestCase):
    def test_string_decode_encode(self):
        from QGIS_FMV.klvdata.common import bytes_to_hexstr
        from QGIS_FMV.klvdata.common import hexstr_to_bytes

        self.assertEqual(
            hexstr_to_bytes(bytes_to_hexstr(b'\x50\x72\x65\x64\x61\x74\x6F\x72')),
            b'\x50\x72\x65\x64\x61\x74\x6F\x72')

        self.assertEqual(
            bytes_to_hexstr(hexstr_to_bytes('06 0E 2B 34 - 02 0B 01 01 – 0E 01 03 01 - 01 00 00 00')),
            '06 0E 2B 34 02 0B 01 01 0E 01 03 01 01 00 00 00')


class FixedPoint(unittest.TestCase):
    def test_bytes_unsigned(self):
        from QGIS_FMV.klvdata.common import bytes_to_float
        self.assertAlmostEqual(
            bytes_to_float(b'\x00\x00', _domain=(0, 2 ** 16 - 1), _range=(0, 360)),
            0.0)

        self.assertAlmostEqual(
            bytes_to_float(b'\x71\xC2', _domain=(0, 2 ** 16 - 1), _range=(0, 360)),
            159.974, 3)

        self.assertAlmostEqual(
            bytes_to_float(b'\xFF\xFF', _domain=(0, 2 ** 16 - 1), _range=(0, 360)),
            360.0)

    def test_bytes_signed(self):
        from QGIS_FMV.klvdata.common import bytes_to_float
        self.assertAlmostEqual(
            bytes_to_float(b'\x80\x01', _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)),
            -20.0)

        self.assertAlmostEqual(
            bytes_to_float(b'\x00\x00', _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)),
            0.0)

        self.assertAlmostEqual(
            bytes_to_float(b'\xFD\x3D', _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)), -0.4315,
            3)

        self.assertAlmostEqual(
            bytes_to_float(b'\x7F\xFF', _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)),
            20.0, 7)

    def test_bytes_error(self):
        from QGIS_FMV.klvdata.common import bytes_to_float

        with self.assertRaises(ValueError):
            bytes_to_float(b'\x7F\xFF\xFF', _domain=(-(2 ** 15 - 1), 2 ** 15 - 1), _range=(-20, 20))

    def test_float_unsigned(self):
        from QGIS_FMV.klvdata.common import float_to_bytes

        with self.subTest("Unsigned 0.0"):
            self.assertEqual(
                float_to_bytes(0.0, _domain=(0, 2 ** 16 - 1), _range=(0, 360)),
                b'\x00\x00')

        with self.subTest("Unsigned 159.974"):
            self.assertEqual(
                float_to_bytes(159.974, _domain=(0, 2 ** 16 - 1), _range=(0, 360)),
                b'\x71\xC2')

        with self.subTest("Unsigned 360.0"):
            self.assertEqual(
                float_to_bytes(360.0, _domain=(0, 2 ** 16 - 1), _range=(0, 360)),
                b'\xFF\xFF')

    def test_float_signed(self):
        from QGIS_FMV.klvdata.common import float_to_bytes

        with self.subTest("Signed -20.0"):
            self.assertEqual(
                float_to_bytes(-20.0, _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)),
                b'\x80\x01')

        with self.subTest("Signed 0.0"):
            self.assertEqual(
                float_to_bytes(0.0, _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)),
                b'\x00\x00')

        with self.subTest("Signed -0.4315"):
            self.assertEqual(
                float_to_bytes(-0.4315, _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)),
                b'\xFD\x3D')

        with self.subTest("Signed 20.0"):
            self.assertEqual(
                float_to_bytes(20.0, _domain=(-(2**15-1), 2**15-1), _range=(-20, 20)),
                b'\x7F\xFF')


class Checksum(unittest.TestCase):
    def test_basic1(self):
        # Sample data from MISB ST 0902.5. DynamicConstantMISMMSPacketData not used
        # because there was an error in ST 0902.5 example such that checksum would
        # not validate as written. DynamicConstantMISMMSPacketData included in the
        # samples directory of this module's test is patched to correct the value.
        with open('./data/DynamicOnlyMISMMSPacketData.bin', 'rb') as f:
            packet = f.read()

        from QGIS_FMV.klvdata.common import packet_checksum
        self.assertEqual(packet_checksum(packet), b'\xC8\x50')

    def test_basic2(self):
        # Sample data from MISB ST 0902.5. DynamicConstantMISMMSPacketData is patched
        # to obtain correct checksum.
        with open('./data/DynamicConstantMISMMSPacketData.bin', 'rb') as f:
            packet = f.read()

        from QGIS_FMV.klvdata.common import packet_checksum
        self.assertEqual(packet_checksum(packet), b'\x3E\x1e')


if __name__ == "__main__":
    unittest.main()

