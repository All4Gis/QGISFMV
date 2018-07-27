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

from QGIS_FMV.klvdata.common import ber_encode


# Proposed alternate names, "BaseElement" of modules "bases".
class Element(metaclass=ABCMeta):
    """Construct a key, length, value tuplet.

    Elements provide the basic mechanisms to constitute the basic encoding
    requirements of key, length, value tuplet as specified by STMPE 336.

    The length is dynamically calculated based off the value.

    Attributes:
        key
        value

    Properties:
        name: If name is set return name, else return class name.
        length: Length is calculated based off value.
    """

    def __init__(self, key, value):
        self.key = key
        self.value = value

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def length(self):
        """bytes: Return the BER encoded byte length of self.value."""
        return ber_encode(len(self))

    def __bytes__(self):
        """Return the MISB encoded representation of a Key, Length, Value element."""
        return bytes(self.key) + bytes(self.length) + bytes(self.value)

    def __len__(self):
        """Return the byte length of self.value."""
        return len(bytes(self.value))

    @abstractmethod
    def __repr__(self):
        pass

    def __str__(self):
        return "{}: ({}, {}, {})".format(self.name, self.key, len(self), self.value)


class UnknownElement(Element):
    def __repr__(self):
        """Return as-code string used to re-create the object."""
        args = ', '.join(map(repr, (bytes(self.key), bytes(self.value))))
        return '{}({})'.format(self.__class__.__name__, args)
