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
    key_length = 1
    TAG = 48
    UDSKey = hexstr_to_bytes(
        '06 0E 2B 34 - 02 03 01 01 – 0E 01 03 03 - 02 00 00 00')
    LDSName = "Security Local Metadata Set"
    ESDName = ""
    UDSName = ""

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
    TAG = 1
    UDSKey = "-"
    LDSName = "Security Classification"
    ESDName = ""
    UDSName = ""

    _classification = {
        b'\x01': 'UNCLASSIFIED',
        b'\x02': 'RESTRICTED',
        b'\x03': 'CONFIDENTIAL',
        b'\x04': 'SECRET',
        b'\x05': 'TOP SECRET',
    }


@SecurityLocalMetadataSet.add_parser
class ClassifyingCountryAndReleasingInstructionCCM(BytesElementParser):
    """
    """
    key = b'\x02'
    TAG = 2
    UDSKey = "-"
    LDSName = "Classifying Country And Releasing Instruction Country Coding Method"
    ESDName = ""
    UDSName = ""

    _classification = _classifying_country_coding


@SecurityLocalMetadataSet.add_parser
class ClassifyingCountry(StringElementParser):
    """
    """
    key = b'\x03'
    TAG = 3
    UDSKey = "-"
    LDSName = "Classifying Country"
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class SecuritySCISHIInformation(StringElementParser):
    """
    """
    key = b'\x04'
    TAG = 4
    UDSKey = "-"
    LDSName = 'Security-SCI/SHI Information'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class Caveats(StringElementParser):
    """
    """
    key = b'\x05'
    TAG = 5
    UDSKey = "-"
    LDSName = 'Caveats'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class ReleasingInstructions(StringElementParser):
    """
    """
    key = b'\x06'
    TAG = 6
    UDSKey = "-"
    LDSName = 'Releasing Instructions'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class ClassifiedBy(StringElementParser):
    """
    """
    key = b'\x07'
    TAG = 7
    UDSKey = "-"
    LDSName = 'Classified By'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class DerivedFrom(StringElementParser):
    """
    """
    key = b'\x08'
    TAG = 8
    UDSKey = "-"
    LDSName = 'Derived From'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class ClassificationReason(StringElementParser):
    """
    """
    key = b'\x09'
    TAG = 9
    UDSKey = "-"
    LDSName = 'Classification Reason'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class DeclassificationDate(StringElementParser):
    """
    """
    key = b'\x0A'
    TAG = 10
    UDSKey = "-"
    LDSName = 'Declassification Date'
    ESDName = ""
    UDSName = ""
    min_length, max_length = 8, 8


@SecurityLocalMetadataSet.add_parser
class ClassificationAndMarkingSystem(StringElementParser):
    """
    """
    key = b'\x0B'
    TAG = 11
    UDSKey = "-"
    LDSName = 'Classification And Marking System'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class ObjectCountryCodingMethod(BytesElementParser):
    """
    """
    key = b'\x0C'
    TAG = 12
    UDSKey = "-"
    LDSName = 'Object Country Coding Method'
    ESDName = ""
    UDSName = ""

    _classification = _object_country_coding


@SecurityLocalMetadataSet.add_parser
class ObjectCountryCodes(StringElementParser):
    """
    """
    key = b'\x0D'
    TAG = 13
    UDSKey = "-"
    LDSName = 'Object Country Codes'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class ClassificationComments(StringElementParser):
    """
    """
    key = b'\x0E'
    TAG = 14
    UDSKey = "-"
    LDSName = 'Classification Comments'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class Version(BytesElementParser):
    """
    """
    key = b'\x16'
    TAG = 22
    UDSKey = "-"
    LDSName = 'Version'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class ClassifyingCountryAndReleasingInstructionCCMVD(StringElementParser):
    """
    """
    key = b'\x17'
    TAG = 23
    UDSKey = "-"
    LDSName = 'Classifying Country And Releasing Instruction Country Coding Method Version Date'
    ESDName = ""
    UDSName = ""


@SecurityLocalMetadataSet.add_parser
class ClassifyingCountryCodeMethodVersionDate(StringElementParser):
    """
    """
    key = b'\x18'
    TAG = 24
    UDSKey = "-"
    LDSName = 'Classifying Country Code Method Version Date'
    ESDName = ""
    UDSName = ""
