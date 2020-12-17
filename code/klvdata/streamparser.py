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

from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.klvparser import KLVParser

try:
    from pydevd import *
except ImportError:
    None


class StreamParser:
    parsers = {}

    def __init__(self, source):
        self.source = source

        # All keys in parser are expected to be 16 bytes long.
        self.iter_stream = KLVParser(self.source, key_length=16)

    def __iter__(self):
        return self

    def __next__(self):
        key, value = next(self.iter_stream)
#         qgsu.showUserAndLogMessage(
#              "", "Streamparser key: " + str(key) + " value: " + str(value), onlyLog=True)
        if key in self.parsers:
            return self.parsers[key](value)
        else:
            # Even if KLV is not known, make best effort to parse and preserve.
            # Element is an abstract super class, do not create instances on
            # Element.
            return UnknownElement(key, value)

    @classmethod
    def add_parser(cls, obj):
        """Decorator method used to register a parser to the class parsing repertoire.

        obj is required to implement key attribute supporting bytes as returned by KLVParser key.
        """

        cls.parsers[bytes(obj.key)] = obj

        return obj
