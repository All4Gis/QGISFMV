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


class ParserTestCase(unittest.TestCase):
    pass


class ParserSingleShort(ParserTestCase):
    def setUp(self):
        self.key = b'\x02'
        self.length = b'\x08'
        self.value = b'\x00\x04\x60\x50\x58\x4E\x01\x80'

        self.packet = self.key + self.length + self.value

        from QGIS_FMV.klvdata.klvparser import KLVParser
        self.parser = KLVParser(self.packet, key_length=1)

    def test_key(self):
        key, value = next(self.parser)
        self.assertEqual(key, self.key)

    def test_value(self):
        key, value = next(self.parser)
        self.assertEqual(value, self.value)


class ParserSingleLong(ParserTestCase):
    def setUp(self):
        self.packet = bytes()

        # Sample data from MISB ST 0902.5
        with open('./data/DynamicConstantMISMMSPacketData.bin', 'rb') as f:
            self.packet = f.read()

        self.key = self.packet[0:16]
        assert len(self.key) == 16
        self.length = self.packet[16:18]
        assert len(self.length) == 2
        self.value = self.packet[18:]

        from QGIS_FMV.klvdata.klvparser import KLVParser
        self.parser = KLVParser(self.packet, key_length=16)

    def test_key(self):
        key, value = next(self.parser)
        self.assertEqual(key, self.key)

    def test_value(self):
        key, value = next(self.parser)
        self.assertEqual(value, self.value)


if __name__ == "__main__":
    unittest.main()
