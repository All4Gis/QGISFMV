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

from abc import ABCMeta
from abc import abstractmethod
from collections import OrderedDict
from pprint import pformat

from QGIS_FMV.klvdata.element import Element
from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.klvparser import KLVParser


try:
    from pydevd import *
except ImportError:
    None


class SetParser(Element, metaclass=ABCMeta):
    """Parsable Element. Not intended to be used directly. Always as super class."""
    _unknown_element = UnknownElement

    def __init__(self, value, key_length=1):
        """All parser needs is the value, no other information"""
        super().__init__(self.key, value)
        self.key_length = key_length
        self.items = OrderedDict()
        self.parse()

        self._PlatformHeadingAngle = None
        self._SensorLatitude = None
        self._SensorLongitude = None
        self._SensorTrueAltitude = None
        self._SensorHorizontalFieldOfView = None
        self._SensorVerticalFieldOfView = None
        self._targetWidth = None
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
            except KeyError:
                self.items[key] = self._unknown_element(key, value)

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

        def repeat(items, indent=1):
            for item in items:
                try:
                    metadata[item.TAG] = (item.LDSName, str(item.value.value))
                    if item.TAG == 5:
                        self.SetPlatformHeadingAngle(item.value.value)
                    if item.TAG == 13:
                        self.SetSensorLatitude(item.value.value)
                    elif item.TAG == 14:
                        self.SetSensorLongitude(item.value.value)
                    elif item.TAG == 15:
                        self.SetSensorTrueAltitude(item.value.value)
                    elif item.TAG == 16:
                        self.SetSensorHorizontalFieldOfView(item.value.value)
                    elif item.TAG == 17:
                        self.SetSensorVerticalFieldOfView(item.value.value)
                    elif item.TAG == 18:
                        self.SetSensorRelativeAzimuthAngle(item.value.value)
                    elif item.TAG == 22:
                        self.SettargetWidth(item.value.value)
                    elif item.TAG == 26:
                        self.SetOffsetCornerLatitudePoint1(item.value.value)
                    elif item.TAG == 27:
                        self.SetOffsetCornerLongitudePoint1(item.value.value)
                    elif item.TAG == 28:
                        self.SetOffsetCornerLatitudePoint2(item.value.value)
                    elif item.TAG == 29:
                        self.SetOffsetCornerLongitudePoint2(item.value.value)
                    elif item.TAG == 30:
                        self.SetOffsetCornerLatitudePoint3(item.value.value)
                    elif item.TAG == 31:
                        self.SetOffsetCornerLongitudePoint3(item.value.value)
                    elif item.TAG == 32:
                        self.SetOffsetCornerLatitudePoint4(item.value.value)
                    elif item.TAG == 33:
                        self.SetOffsetCornerLongitudePoint4(item.value.value)
                    elif item.TAG == 23:
                        self.SetFrameCenterLatitude(item.value.value)
                    elif item.TAG == 24:
                        self.SetFrameCenterLongitude(item.value.value)
                    elif item.TAG == 82:
                        self.SetCornerLatitudePoint1Full(item.value.value)
                    elif item.TAG == 83:
                        self.SetCornerLongitudePoint1Full(item.value.value)
                    elif item.TAG == 84:
                        self.SetCornerLatitudePoint2Full(item.value.value)
                    elif item.TAG == 85:
                        self.SetCornerLongitudePoint2Full(item.value.value)
                    elif item.TAG == 86:
                        self.SetCornerLatitudePoint3Full(item.value.value)
                    elif item.TAG == 87:
                        self.SetCornerLongitudePoint3Full(item.value.value)
                    elif item.TAG == 88:
                        self.SetCornerLatitudePoint4Full(item.value.value)
                    elif item.TAG == 89:
                        self.SetCornerLongitudePoint4Full(item.value.value)
                except:
                    None
                if hasattr(item, 'items'):
                    repeat(item.items.values(), indent + 1)
        repeat(self.items.values())
        return OrderedDict(metadata)

    # ------------ START Setters/Getters ------------
    def GetPlatformHeadingAngle(self):
        return self._PlatformHeadingAngle

    def SetPlatformHeadingAngle(self, value):
        self._PlatformHeadingAngle = float(value)

    def GetSensorLatitude(self):
        return self._SensorLatitude

    def SetSensorLatitude(self, value):
        self._SensorLatitude = float(value)

    def GetSensorLongitude(self):
        return self._SensorLongitude

    def SetSensorLongitude(self, value):
        self._SensorLongitude = float(value)

    def GetSensorTrueAltitude(self):
        return self._SensorTrueAltitude

    def SetSensorTrueAltitude(self, value):
        self._SensorTrueAltitude = float(value)

    def GetSensorHorizontalFieldOfView(self):
        return self._SensorHorizontalFieldOfView

    def SetSensorHorizontalFieldOfView(self, value):
        self._SensorHorizontalFieldOfView = float(value)

    def GetSensorVerticalFieldOfView(self):
        return self._SensorVerticalFieldOfView

    def SetSensorVerticalFieldOfView(self, value):
        self._SensorVerticalFieldOfView = float(value)

    def GetSensorRelativeAzimuthAngle(self):
        return self._SensorRelativeAzimuthAngle

    def SetSensorRelativeAzimuthAngle(self, value):
        self._SensorRelativeAzimuthAngle = float(value)

    def GettargetWidth(self):
        return self._targetWidth

    def SettargetWidth(self, value):
        self._targetWidth = float(value)

    def GetOffsetCornerLatitudePoint1(self):
        return self._OffsetCornerLatitudePoint1

    def SetOffsetCornerLatitudePoint1(self, value):
        self._OffsetCornerLatitudePoint1 = float(value)

    def GetOffsetCornerLongitudePoint1(self):
        return self._OffsetCornerLongitudePoint1

    def SetOffsetCornerLongitudePoint1(self, value):
        self._OffsetCornerLongitudePoint1 = float(value)

    def GetOffsetCornerLatitudePoint2(self):
        return self._OffsetCornerLatitudePoint2

    def SetOffsetCornerLatitudePoint2(self, value):
        self._OffsetCornerLatitudePoint2 = float(value)

    def GetOffsetCornerLongitudePoint2(self):
        return self._OffsetCornerLongitudePoint2

    def SetOffsetCornerLongitudePoint2(self, value):
        self._OffsetCornerLongitudePoint2 = float(value)

    def GetOffsetCornerLatitudePoint3(self):
        return self._OffsetCornerLatitudePoint3

    def SetOffsetCornerLatitudePoint3(self, value):
        self._OffsetCornerLatitudePoint3 = float(value)

    def GetOffsetCornerLongitudePoint3(self):
        return self._OffsetCornerLongitudePoint3

    def SetOffsetCornerLongitudePoint3(self, value):
        self._OffsetCornerLongitudePoint3 = float(value)

    def GetOffsetCornerLatitudePoint4(self):
        return self._OffsetCornerLatitudePoint4

    def SetOffsetCornerLatitudePoint4(self, value):
        self._OffsetCornerLatitudePoint4 = float(value)

    def GetOffsetCornerLongitudePoint4(self):
        return self._OffsetCornerLongitudePoint4

    def SetOffsetCornerLongitudePoint4(self, value):
        self._OffsetCornerLongitudePoint4 = float(value)

    def GetFrameCenterLatitude(self):
        return self._FrameCenterLatitude

    def SetFrameCenterLatitude(self, value):
        self._FrameCenterLatitude = float(value)

    def GetFrameCenterLongitude(self):
        return self._FrameCenterLongitude

    def SetFrameCenterLongitude(self, value):
        self._FrameCenterLongitude = float(value)

    def GetCornerLatitudePoint1Full(self):
        return self._CornerLatitudePoint1Full

    def SetCornerLatitudePoint1Full(self, value):
        self._CornerLatitudePoint1Full = float(value)

    def GetCornerLongitudePoint1Full(self):
        return self._CornerLongitudePoint1Full

    def SetCornerLongitudePoint1Full(self, value):
        self._CornerLongitudePoint1Full = float(value)

    def GetCornerLatitudePoint2Full(self):
        return self._CornerLatitudePoint2Full

    def SetCornerLatitudePoint2Full(self, value):
        self._CornerLatitudePoint2Full = float(value)

    def GetCornerLongitudePoint2Full(self):
        return self._CornerLongitudePoint2Full

    def SetCornerLongitudePoint2Full(self, value):
        self._CornerLongitudePoint2Full = float(value)

    def GetCornerLatitudePoint3Full(self):
        return self._CornerLatitudePoint3Full

    def SetCornerLatitudePoint3Full(self, value):
        self._CornerLatitudePoint3Full = float(value)

    def GetCornerLongitudePoint3Full(self):
        return self._CornerLongitudePoint3Full

    def SetCornerLongitudePoint3Full(self, value):
        self._CornerLongitudePoint3Full = float(value)

    def GetCornerLatitudePoint4Full(self):
        return self._CornerLatitudePoint4Full

    def SetCornerLatitudePoint4Full(self, value):
        self._CornerLatitudePoint4Full = float(value)

    def GetCornerLongitudePoint4Full(self):
        return self._CornerLongitudePoint4Full

    def SetCornerLongitudePoint4Full(self, value):
        self._CornerLongitudePoint4Full = float(value)

    # ------------ END Setters/Getters ------------

    def structure(self):
        ''' Return metadata structure'''
        print(str(type(self)))

        def repeat(items, indent=1):
            for item in items:
                print(indent * "\t" + str(type(item)))
                if hasattr(item, 'items'):
                    repeat(item.items.values(), indent + 1)

        repeat(self.items.values())


def str_dict(values):
    out = []

    def per_item(value, indent=0):
        for item in value:
            if isinstance(item):
                out.append(indent * "\t" + str(item))
            else:
                out.append(indent * "\t" + str(item))

    per_item(values)

    return '\n'.join(out)
