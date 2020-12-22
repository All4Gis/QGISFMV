#!/usr/bin/env python3

#  The MIT License (MIT)
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


class ElementTLV(unittest.TestCase):
    def test_key(self):
        from QGIS_FMV.klvdata.element import UnknownElement
        self.assertEqual(
            UnknownElement(b'\x02', b'\x00\x04\x60\x50\x58\x4E\x01\x80').key,
            b'\x02')

    def test_length(self):
        from QGIS_FMV.klvdata.element import UnknownElement
        self.assertEqual(
            UnknownElement(b'\x02', b'\x00\x04\x60\x50\x58\x4E\x01\x80').length,
            b'\x08')

    def test_value(self):
        from QGIS_FMV.klvdata.element import UnknownElement
        self.assertEqual(
            UnknownElement(b'\x02', b'\x00\x04\x60\x50\x58\x4E\x01\x80').value,
            b'\x00\x04\x60\x50\x58\x4E\x01\x80')

    def test_packet(self):
        from QGIS_FMV.klvdata.element import UnknownElement
        self.assertEqual(
            bytes(UnknownElement(b'\x02', b'\x00\x04\x60\x50\x58\x4E\x01\x80')),
            b'\x02\x08\x00\x04\x60\x50\x58\x4E\x01\x80')

    def test_name(self):
        from QGIS_FMV.klvdata.element import UnknownElement
        self.assertEqual(
            UnknownElement(b'\x02', b'\x00\x04\x60\x50\x58\x4E\x01\x80').name,
            "UnknownElement")

    def test_str(self):
        from QGIS_FMV.klvdata.element import UnknownElement

        self.assertEqual(
            str(UnknownElement(b'\x02', b'\x00\x04\x60\x50\x58\x4E\x01\x80')),
            "UnknownElement: (b'\\x02', 8, b'\\x00\\x04`PXN\\x01\\x80')")

    def test_repr(self):
        from QGIS_FMV.klvdata.element import UnknownElement
        self.assertIsInstance(
            eval(repr(UnknownElement(b'\x02', b'\x00\x04\x60\x50\x58\x4E\x01\x80'))),
            UnknownElement)


if __name__ == "__main__":
    unittest.main()
