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
from QGIS_FMV.klvdata.elementparser import BytesElementParser
from QGIS_FMV.klvdata.misb0601 import UASLocalMetadataSet
from QGIS_FMV.klvdata.setparser import SetParser

_classifying_country_coding = {
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

_object_country_coding = {
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
    key, name = b'\x30', "Security Local Metadata Set"
    LDSName = "Security Local Metadata Set"
    key_length = 1                                                 
    parsers = {}

    _unknown_element = UnknownElement


@SecurityLocalMetadataSet.add_parser
class SecurityClassification(BytesElementParser):
    """MISB ST0102 Security Classification value interpretation parser.

    The Security Classification metadata element contains a value
    representing the entire security classification of the file in
    accordance with U.S. and NATO classification guidance.
    """
    key = b'\x01'
    LDSName = "Security Classification"
    _classification = {
        b'\x01': 'UNCLASSIFIED',
        b'\x02': 'RESTRICTED',
        b'\x03': 'CONFIDENTIAL',
        b'\x04': 'SECRET',
        b'\x05': 'TOP SECRET',
    }
