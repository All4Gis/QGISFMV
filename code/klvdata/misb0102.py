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
from QGIS_FMV.klvdata.elementparser import StringElementParser
from QGIS_FMV.klvdata.misb0601 import UASLocalMetadataSet
from QGIS_FMV.klvdata.setparser import SetParser
from QGIS_FMV.klvdata.streamparser import StreamParser
from QGIS_FMV.klvdata.elementparser import EnumElementParser
from QGIS_FMV.klvdata.elementparser import StringElementParser
from QGIS_FMV.klvdata.elementparser import IntegerElementParser

class UnknownElement(UnknownElement):
    pass


@UASLocalMetadataSet.add_parser
class SecurityLocalMetadataSet(SetParser):
    """MISB ST0102 Security Metadata nested local set parser.

    The Security Metdata set comprise information needed to
    comply with CAPCO, DoD Information Security Program and
    other normatively referenced security directives.

    Must be a subclass of Element or duck type Element.
    """
    key = b'\x30'
    name = "Security Local Metadata Set"
    parsers = {}

    _unknown_element = UnknownElement


@SecurityLocalMetadataSet.add_parser
class SecurityClassification(EnumElementParser):
    """MISB ST0102 Security Classification value interpretation parser.

    The Security Classification metadata element contains a value
    representing the entire security classification of the file in
    accordance with U.S. and NATO classification guidance.
    """
    key = b'\x01'
    TAG = 1
    UDSKey = "-"
    LDSName = "Security Classification"
    ESDName = "Security Classification"
    UDSName = ""

    _enum = {
        b'\x01': 'UNCLASSIFIED',
        b'\x02': 'RESTRICTED',
        b'\x03': 'CONFIDENTIAL',
        b'\x04': 'SECRET',
        b'\x05': 'TOP SECRET',
    }

@SecurityLocalMetadataSet.add_parser
class ClassifyingCountryCoding(EnumElementParser):
    key = b'\x02'
    TAG = 2
    UDSKey = "-"
    LDSName = "Classifying Country and Releasing Instructions Coding"
    ESDName = "Classifying Country Coding"
    UDSName = ""

    _enum = {
        b'\x01': 'ISO-3166 Two Letter',
        b'\x02': 'ISO-3166 Three Letter',
        b'\x03': 'FIPS 10-4 Two Letter',
        b'\x04': 'FIPS 10-4 Four Letter',
        b'\x05': 'ISO-3166 Numeric',
        b'\x06': '1059 Two Letter',
        b'\x07': '1059 Three Letter',
        b'\x08': 'Omitted Value',
        b'\x09': 'Omitted Value',
        b'\x0A': 'FIPS 10-4 Mixed',
        b'\x0B': 'ISO 3166 Mixed',
        b'\x0C': 'STANAG 1059 Mixed',
        b'\x0D': 'GENC Two Letter',
        b'\x0E': 'GENC Three Letter',
        b'\x0F': 'GENC Numeric',
        b'\x10': 'GENC Mixed',
    }

@SecurityLocalMetadataSet.add_parser
class ClassifyingCountry(StringElementParser):
    key = b'\x03'
    TAG = 3
    UDSKey = "-"
    LDSName = "Classifying Country"
    ESDName = "Classifying Country"
    UDSName = ""
    min_length, max_length = 0, 6

@SecurityLocalMetadataSet.add_parser
class SecurityInformation(StringElementParser):
    key = b'\x04'
    TAG = 4
    UDSKey = "-"
    LDSName = "Security-SCI/SHI Information"
    ESDName = "Security-SCI/SHI Information"
    UDSName = ""

    _encoding = 'iso646_us'
    min_length, max_length = 0, 40

@SecurityLocalMetadataSet.add_parser
class Caveats(StringElementParser):
    key = b'\x05'
    TAG = 5
    UDSKey = "-"
    LDSName = "Caveats"
    ESDName = "Caveats"
    UDSName = ""

    _encoding = 'iso646_us'
    min_length, max_length = 0, 32

@SecurityLocalMetadataSet.add_parser
class ReleasingInstructions(StringElementParser):
    key = b'\x06'
    TAG = 6
    UDSKey = "-"
    LDSName = "Releasing Instructions"
    ESDName = "Releasing Instructions"
    UDSName = ""
    
    _encoding = 'iso646_us'
    min_length, max_length = 0, 40

@SecurityLocalMetadataSet.add_parser
class ObjectCountryMethod(EnumElementParser):
    key = b'\x0C'
    TAG = 12
    UDSKey = "-"
    LDSName = "Object Country Method"
    ESDName = "Object Country Method"
    UDSName = ""
    _enum = {
        b'\x01': 'ISO-3166 Two Letter',
        b'\x02': 'ISO-3166 Three Letter',
        b'\x03': 'ISO-3166 Numeric',
        b'\x04': 'FIPS 10-4 Two Letter',
        b'\x05': 'FIPS 10-4 Four Letter',
        b'\x06': '1059 Two Letter',
        b'\x07': '1059 Three Letter',
        b'\x08': 'Omitted Value',
        b'\x09': 'Omitted Value',
        b'\x0A': 'Omitted Value',
        b'\x0B': 'Omitted Value',
        b'\x0C': 'Omitted Value',
        b'\x0D': 'GENC Two Letter',
        b'\x0E': 'GENC Three Letter',
        b'\x0F': 'GENC Numeric',
        b'\x40': 'GENC AdminSub',
    }

@SecurityLocalMetadataSet.add_parser
class ObjectCountryCodes(StringElementParser):
    key = b'\x0D'
    TAG = 13
    UDSKey = "-"
    LDSName = "Object Country Codes"
    ESDName = "Object Country Codes"
    UDSName = ""

    _encoding = 'UTF-16-BE'
    min_length, max_length = 0, 40

@SecurityLocalMetadataSet.add_parser
class SecurityMetadataVersion(IntegerElementParser):
    key = b'\x16'
    TAG = 22
    UDSKey = "-"
    LDSName = "Security Metadata Version"
    ESDName = "Security Metadata Version"
    UDSName = ""
    
    _signed = False
    _size = 2
