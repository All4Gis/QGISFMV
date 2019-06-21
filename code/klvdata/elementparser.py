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

from QGIS_FMV.klvdata.common import (bytes_to_datetime,
                                     bytes_to_float,
                                     bytes_to_hexstr,
                                     bytes_to_int,
                                     bytes_to_str,
                                     datetime_to_bytes,
                                     float_to_bytes,
                                     str_to_bytes,
                                     ieee754_bytes_to_fp)
from QGIS_FMV.klvdata.element import Element

try:
    from pydevd import *
except ImportError:
    None


class ElementParser(Element):
    """Construct a Element Parser base class.

    Element Parsers are used to enforce the convention that all Element Parsers
    already know the key of the element they are constructing.

    Element Parser is a helper class that simplifies known element definition
    and makes a layer of abstraction for functionality that all known elements
    can share. The parsing interfaces are cleaner and require less coding as
    their definitions (subclasses of Element Parser) do not need to call init
    on super with class key and instance value.
    """
    __metaclass__ = ABCMeta

    def __init__(self, value):
        super().__init__(self.key, value)

    @property
    @classmethod
    @abstractmethod
    def key(cls):
        pass

    def __repr__(self):
        """Return as-code string used to re-create the object."""
        return '{}({})'.format(self.name, bytes(self.value))


class BaseValue():
    __metaclass__ = ABCMeta

    """Abstract base class (superclass) used to insure internal interfaces are maintained."""

    @abstractmethod
    def __bytes__(self):
        """Required by element.Element"""
        pass

    @abstractmethod
    def __str__(self):
        """Required by element.Element"""
        pass


class BytesElementParser(ElementParser):
    __metaclass__ = ABCMeta

    def __init__(self, value):
        super().__init__(BytesValue(value))


class BytesValue(BaseValue):

    def __init__(self, value):
        try:
            self.value = bytes_to_int(value)
        except TypeError:
            self.value = value

    def __bytes__(self):
        return bytes(self.value)

    def __str__(self):
        return bytes_to_hexstr(self.value, start='0x', sep='')


class DateTimeElementParser(ElementParser):
    __metaclass__ = ABCMeta

    def __init__(self, value):
        super().__init__(DateTimeValue(value))


class DateTimeValue(BaseValue):

    def __init__(self, value):
        self.value = bytes_to_datetime(value)

    def __bytes__(self):
        return datetime_to_bytes(self.value)

    def __str__(self):
        return self.value.isoformat(sep=' ')


class StringElementParser(ElementParser):
    __metaclass__ = ABCMeta

    def __init__(self, value):
        super().__init__(StringValue(value))


class StringValue(BaseValue):

    def __init__(self, value):
        try:
            self.value = bytes_to_str(value)
        except TypeError:
            self.value = value

    def __bytes__(self):
        return str_to_bytes(self.value)

    def __str__(self):
        return str(self.value)


class MappedElementParser(ElementParser):
    __metaclass__ = ABCMeta

    def __init__(self, value):
        super().__init__(MappedValue(value, self._domain, self._range))

    @property
    @classmethod
    @abstractmethod
    def _domain(cls):
        pass

    @property
    @classmethod
    @abstractmethod
    def _range(cls):
        pass


class MappedValue(BaseValue):

    def __init__(self, value, _domain, _range):
        self._domain = _domain
        self._range = _range

        try:
            self.value = round(bytes_to_float(
                value, self._domain, self._range), 4)
        except TypeError:
            self.value = value

    def __bytes__(self):
        return float_to_bytes(self.value, self._domain, self._range)

    def __str__(self):
        return format(self.value)

    def __float__(self):
        return self.value


class IEEE754ElementParser(ElementParser):
    __metaclass__ = ABCMeta
    
    def __init__(self, value):
        super().__init__(IEEE754Value(value))


class IEEE754Value(BaseValue):

    def __init__(self, value):
        try:
            self.value = ieee754_bytes_to_fp(value)
        except TypeError:
            self.value = value

    def __bytes__(self):
        # TODO
        return ieee754_double_to_bytes(self.value)

    def __str__(self):
        return str(self.value)
