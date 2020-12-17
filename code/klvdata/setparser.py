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
import sys
from abc import ABCMeta
from abc import abstractmethod
from collections import OrderedDict
from pprint import pformat
from QGIS_FMV.utils.QgsUtils import QgsUtils as qgsu
from QGIS_FMV.klvdata.element import Element
from QGIS_FMV.klvdata.klvparser import KLVParser

try:
    from pydevd import *
except ImportError:
    None


class SetParser(Element):
    """Parsable Element. Not intended to be used directly. Always as super class."""
    __metaclass__ = ABCMeta

    def __init__(self, value, key_length=1):
        """All parser needs is the value, no other information"""
        super().__init__(self.key, value)
        self.items = OrderedDict()
        self.parse()

        self._PlatformTailNumber = None
        self._PlatformHeadingAngle = None
        self._ImageSourceSensor = None
        self._SensorLatitude = None
        self._SensorLongitude = None
        self._SensorTrueAltitude = None
        self._SensorHorizontalFieldOfView = None
        self._SensorVerticalFieldOfView = None
        self._targetWidth = None
        self._slantRange = None
        self._SensorRelativeAzimuthAngle = None
        self._OffsetCornerLatitudePoint1 = None
        self._OffsetCornerLongitudePoint1 = None
        self._OffsetCornerLatitudePoint2 = None
        self._OffsetCornerLongitudePoint2 = None
        self._OffsetCornerLatitudePoint3 = None
        self._OffsetCornerLongitudePoint3 = None
        self._OffsetCornerLatitudePoint4 = None
        self._OffsetCornerLongitudePoint4 = None
        self._FrameCenterLatitude = None
        self._FrameCenterLongitude = None
        self._FrameCenterElevation = None
        self._CornerLatitudePoint1Full = None
        self._CornerLongitudePoint1Full = None
        self._CornerLatitudePoint2Full = None
        self._CornerLongitudePoint2Full = None
        self._CornerLatitudePoint3Full = None
        self._CornerLongitudePoint3Full = None
        self._CornerLatitudePoint4Full = None
        self._CornerLongitudePoint4Full = None

    def __getitem__(self, key):
        """Return element provided bytes key.

        For consistency of this collection of modules, __getitem__ does not
        attempt to add convenience of being able to index by the int equivalent.
        Instead, the user should pass keys with method bytes.
        """
        return self.items[bytes(key)]

    def parse(self):
        """Parse the parent into items. Called on init and modification of parent value.

        If a known parser is not available for key, parse as generic KLV element.
        """
        for key, value in KLVParser(self.value, self.key_length):
            try:
                self.items[key] = self.parsers[key](value)
            except (KeyError, TypeError, ValueError):
                self.items[key] = self._unknown_element(key, value)
            except Exception:
                # None
                qgsu.showUserAndLogMessage("", "Value cannot be read for Tag: " + str(int.from_bytes(key, byteorder=sys.byteorder)) + " value: " + str(value), onlyLog=True)

    @classmethod
    def add_parser(cls, obj):
        """Decorator method used to register a parser to the class parsing repertoire.

        obj is required to implement key attribute supporting bytes as returned by KLVParser key.
        """

        # If sublcass of ElementParser does not implement key, dict accepts key of
        # type property object. bytes(obj.key) will raise TypeError. ElementParser
        # requires key as abstract property but no raise until instantiation which
        # does not occur because the value is never recalled and instantiated from
        # parsers.
        cls.parsers[bytes(obj.key)] = obj

        return obj

    @property
    @classmethod
    @abstractmethod
    def parsers(cls):
        # Property must define __getitem__
        pass

    @parsers.setter
    @classmethod
    @abstractmethod
    def parsers(cls):
        # Property must define __setitem__
        pass

    def __repr__(self):
        return pformat(self.items, indent=1)

    def __str__(self):
        return str_dict(self.items)

    def MetadataList(self):
        ''' Return metadata dictionary'''
        metadata = {}

        def repeat(items, indent=1, parentTAG=0):
            for item in items:
                try:
                    if not hasattr(item.value, 'value'):
                        continue
                    if not parentTAG:
                        metadata[item.TAG] = (item.LDSName, str(item.value.value))
                        if item.TAG == 4:
                            self.PlatformTailNumber = item.value.value
                        elif item.TAG == 5:
                            self.PlatformHeadingAngle = item.value.value
                        elif item.TAG == 11:
                            self.ImageSourceSensor = item.value.value
                        elif item.TAG == 13:
                            self.SensorLatitude = item.value.value
                        elif item.TAG == 14:
                            self.SensorLongitude = item.value.value
                        elif item.TAG == 15:
                            self.SensorTrueAltitude = item.value.value
                        elif item.TAG == 16:
                            self.SensorHorizontalFieldOfView = item.value.value
                        elif item.TAG == 17:
                            self.SensorVerticalFieldOfView = item.value.value
                        elif item.TAG == 18:
                            self.SensorRelativeAzimuthAngle = item.value.value
                        elif item.TAG == 21:
                            self.SlantRange = item.value.value
                        elif item.TAG == 22:
                            self.targetWidth = item.value.value
                        elif item.TAG == 23:
                            self.FrameCenterLatitude = item.value.value
                        elif item.TAG == 24:
                            self.FrameCenterLongitude = item.value.value
                        elif item.TAG == 25:
                            self.FrameCenterElevation = item.value.value
                        elif item.TAG == 26:
                            self.OffsetCornerLatitudePoint1 = item.value.value
                        elif item.TAG == 27:
                            self.OffsetCornerLongitudePoint1 = item.value.value
                        elif item.TAG == 28:
                            self.OffsetCornerLatitudePoint2 = item.value.value
                        elif item.TAG == 29:
                            self.OffsetCornerLongitudePoint2 = item.value.value
                        elif item.TAG == 30:
                            self.OffsetCornerLatitudePoint3 = item.value.value
                        elif item.TAG == 31:
                            self.OffsetCornerLongitudePoint3 = item.value.value
                        elif item.TAG == 32:
                            self.OffsetCornerLatitudePoint4 = item.value.value
                        elif item.TAG == 33:
                            self.OffsetCornerLongitudePoint4 = item.value.value
                        elif item.TAG == 82:
                            self.CornerLatitudePoint1Full = item.value.value
                        elif item.TAG == 83:
                            self.CornerLongitudePoint1Full = item.value.value
                        elif item.TAG == 84:
                            self.CornerLatitudePoint2Full = item.value.value
                        elif item.TAG == 85:
                            self.CornerLongitudePoint2Full = item.value.value
                        elif item.TAG == 86:
                            self.CornerLatitudePoint3Full = item.value.value
                        elif item.TAG == 87:
                            self.CornerLongitudePoint3Full = item.value.value
                        elif item.TAG == 88:
                            self.CornerLatitudePoint4Full = item.value.value
                        elif item.TAG == 89:
                            self.CornerLongitudePoint4Full = item.value.value
                    else:
                        metadata[parentTAG][len(metadata[parentTAG]) - 1][item.TAG] = (item.LDSName, item.ESDName, item.UDSName, str(item.value.value))

                except Exception:
                    qgsu.showUserAndLogMessage("", "Value cannot be read: " + str(item.value.value), onlyLog=True)
                    continue
                if hasattr(item, 'items'):
                    metadata[item.TAG] = (item.LDSName, item.ESDName, item.UDSName, {})
                    repeat(item.items.values(), indent + 1, item.TAG)

        repeat(self.items.values())
        return OrderedDict(metadata)

    # ------------ START Setters/Getters ------------
    @property
    def PlatformTailNumber(self):
        return self._PlatformTailNumber

    @PlatformTailNumber.setter
    def PlatformTailNumber(self, value):
        self._PlatformTailNumber = value

    @property
    def PlatformHeadingAngle(self):
        return self._PlatformHeadingAngle

    @PlatformHeadingAngle.setter
    def PlatformHeadingAngle(self, value):
        self._PlatformHeadingAngle = float(value)

    @property
    def ImageSourceSensor(self):
        return self._ImageSourceSensor

    @ImageSourceSensor.setter
    def ImageSourceSensor(self, value):
        self._ImageSourceSensor = value

    @property
    def SensorLatitude(self):
        return self._SensorLatitude

    @SensorLatitude.setter
    def SensorLatitude(self, value):
        self._SensorLatitude = float(value)

    @property
    def SensorLongitude(self):
        return self._SensorLongitude

    @SensorLongitude.setter
    def SensorLongitude(self, value):
        self._SensorLongitude = float(value)

    @property
    def SensorTrueAltitude(self):
        return self._SensorTrueAltitude

    @SensorTrueAltitude.setter
    def SensorTrueAltitude(self, value):
        self._SensorTrueAltitude = float(value)

    @property
    def SensorHorizontalFieldOfView(self):
        return self._SensorHorizontalFieldOfView

    @SensorHorizontalFieldOfView.setter
    def SensorHorizontalFieldOfView(self, value):
        self._SensorHorizontalFieldOfView = float(value)

    @property
    def SensorVerticalFieldOfView(self):
        return self._SensorVerticalFieldOfView

    @SensorVerticalFieldOfView.setter
    def SensorVerticalFieldOfView(self, value):
        self._SensorVerticalFieldOfView = float(value)

    @property
    def SensorRelativeAzimuthAngle(self):
        return self._SensorRelativeAzimuthAngle

    @SensorRelativeAzimuthAngle.setter
    def SensorRelativeAzimuthAngle(self, value):
        self._SensorRelativeAzimuthAngle = float(value)

    @property
    def SlantRange(self):
        return self._slantRange

    @SlantRange.setter
    def SlantRange(self, value):
        self._slantRange = float(value)

    @property
    def targetWidth(self):
        return self._targetWidth

    @targetWidth.setter
    def targetWidth(self, value):
        self._targetWidth = float(value)

    @property
    def OffsetCornerLatitudePoint1(self):
        return self._OffsetCornerLatitudePoint1

    @OffsetCornerLatitudePoint1.setter
    def OffsetCornerLatitudePoint1(self, value):
        self._OffsetCornerLatitudePoint1 = float(value)

    @property
    def OffsetCornerLongitudePoint1(self):
        return self._OffsetCornerLongitudePoint1

    @OffsetCornerLongitudePoint1.setter
    def OffsetCornerLongitudePoint1(self, value):
        self._OffsetCornerLongitudePoint1 = float(value)

    @property
    def OffsetCornerLatitudePoint2(self):
        return self._OffsetCornerLatitudePoint2

    @OffsetCornerLatitudePoint2.setter
    def OffsetCornerLatitudePoint2(self, value):
        self._OffsetCornerLatitudePoint2 = float(value)

    @property
    def OffsetCornerLongitudePoint2(self):
        return self._OffsetCornerLongitudePoint2

    @OffsetCornerLongitudePoint2.setter
    def OffsetCornerLongitudePoint2(self, value):
        self._OffsetCornerLongitudePoint2 = float(value)

    @property
    def OffsetCornerLatitudePoint3(self):
        return self._OffsetCornerLatitudePoint3

    @OffsetCornerLatitudePoint3.setter
    def OffsetCornerLatitudePoint3(self, value):
        self._OffsetCornerLatitudePoint3 = float(value)

    @property
    def OffsetCornerLongitudePoint3(self):
        return self._OffsetCornerLongitudePoint3

    @OffsetCornerLongitudePoint3.setter
    def OffsetCornerLongitudePoint3(self, value):
        self._OffsetCornerLongitudePoint3 = float(value)

    @property
    def OffsetCornerLatitudePoint4(self):
        return self._OffsetCornerLatitudePoint4

    @OffsetCornerLatitudePoint4.setter
    def OffsetCornerLatitudePoint4(self, value):
        self._OffsetCornerLatitudePoint4 = float(value)

    @property
    def OffsetCornerLongitudePoint4(self):
        return self._OffsetCornerLongitudePoint4

    @OffsetCornerLongitudePoint4.setter
    def OffsetCornerLongitudePoint4(self, value):
        self._OffsetCornerLongitudePoint4 = float(value)

    @property
    def FrameCenterLatitude(self):
        return self._FrameCenterLatitude

    @FrameCenterLatitude.setter
    def FrameCenterLatitude(self, value):
        self._FrameCenterLatitude = float(value)

    @property
    def FrameCenterLongitude(self):
        return self._FrameCenterLongitude

    @FrameCenterLongitude.setter
    def FrameCenterLongitude(self, value):
        self._FrameCenterLongitude = float(value)

    @property
    def FrameCenterElevation(self):
        return self._FrameCenterElevation

    @FrameCenterElevation.setter
    def FrameCenterElevation(self, value):
        self._FrameCenterElevation = float(value)

    @property
    def CornerLatitudePoint1Full(self):
        return self._CornerLatitudePoint1Full

    @CornerLatitudePoint1Full.setter
    def CornerLatitudePoint1Full(self, value):
        self._CornerLatitudePoint1Full = float(value)

    @property
    def CornerLongitudePoint1Full(self):
        return self._CornerLongitudePoint1Full

    @CornerLongitudePoint1Full.setter
    def CornerLongitudePoint1Full(self, value):
        self._CornerLongitudePoint1Full = float(value)

    @property
    def CornerLatitudePoint2Full(self):
        return self._CornerLatitudePoint2Full

    @CornerLatitudePoint2Full.setter
    def CornerLatitudePoint2Full(self, value):
        self._CornerLatitudePoint2Full = float(value)

    @property
    def CornerLongitudePoint2Full(self):
        return self._CornerLongitudePoint2Full

    @CornerLongitudePoint2Full.setter
    def CornerLongitudePoint2Full(self, value):
        self._CornerLongitudePoint2Full = float(value)

    @property
    def CornerLatitudePoint3Full(self):
        return self._CornerLatitudePoint3Full

    @CornerLatitudePoint3Full.setter
    def CornerLatitudePoint3Full(self, value):
        self._CornerLatitudePoint3Full = float(value)

    @property
    def CornerLongitudePoint3Full(self):
        return self._CornerLongitudePoint3Full

    @CornerLongitudePoint3Full.setter
    def CornerLongitudePoint3Full(self, value):
        self._CornerLongitudePoint3Full = float(value)

    @property
    def CornerLatitudePoint4Full(self):
        return self._CornerLatitudePoint4Full

    @CornerLatitudePoint4Full.setter
    def CornerLatitudePoint4Full(self, value):
        self._CornerLatitudePoint4Full = float(value)

    @property
    def CornerLongitudePoint4Full(self):
        return self._CornerLongitudePoint4Full

    @CornerLongitudePoint4Full.setter
    def CornerLongitudePoint4Full(self, value):
        self._CornerLongitudePoint4Full = float(value)

    # ------------ END Setters/Getters ------------

    def structure(self):
        ''' Return metadata structure'''
        def repeat(items, indent=1):
            for item in items:
                if hasattr(item, 'items'):
                    repeat(item.items.values(), indent + 1)

        repeat(self.items.values())


def str_dict(values):
    out = []

    def per_item(value, indent=0):
        for item in value:
            if isinstance(item, Element):
                out.append(indent * "\t" + str(item))
            else:
                out.append(indent * "\t" + str(item))

    per_item(values)

    return '\n'.join(out)
