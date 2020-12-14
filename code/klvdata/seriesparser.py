#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pprint import pformat
from abc import ABCMeta
from abc import abstractmethod
from collections import OrderedDict
from QGIS_FMV.klvdata.element import Element
from QGIS_FMV.klvdata.element import UnknownElement
from QGIS_FMV.klvdata.klvparser import KLVParser

try:
    from pydevd import *
except ImportError:
    None

class SeriesParser(Element):
    """Parsable Element. Not intended to be used directly. Always as super class."""
    _unknown_element = UnknownElement
    __metaclass__ = ABCMeta

    def __init__(self, value, key_length=1):
        super().__init__(self.key, value)
        self.key_length = key_length
        self.items = OrderedDict()
        self.parse()

    def parse(self):
        """Parse the parent into items. Called on init and modification of parent value.

        If a known parser is not available for key, parse as generic KLV element.
        """
        for i, (_, value) in enumerate(KLVParser(self.value, 0)):
            elem = self.parser(value)
            self.items[elem.key] = elem

    @classmethod
    def set_parser(cls, obj):
        """Decorator method used to register a parser to the class parsing repertoire.

        obj is required to implement key attribute supporting bytes as returned by KLVParser key.
        """

        # If sublcass of ElementParser does not implement key, dict accepts key of
        # type property object. bytes(obj.key) will raise TypeError. ElementParser
        # requires key as abstract property but no raise until instantiation which
        # does not occur because the value is never recalled and instantiated from
        # parsers.
        cls.parser = obj

        return obj

    @property
    @classmethod
    @abstractmethod
    def parser(cls):
        # Property must define __getitem__
        pass

    @parser.setter
    @classmethod
    @abstractmethod
    def parser(cls):
        # Property must define __setitem__
        pass

    def __repr__(self):
        return pformat(self.items, indent=1)

    def __str__(self):
        return str_dict(self.items)

    def MetadataList(self):
        ''' Return metadata dictionary'''
        metadata = {}
        for key in self.items:
            item = self.items[key]
            try:
                if hasattr(item, 'items'):
                    name = item.name if hasattr(item, 'name') else ''
                    metadata[key] = (name, '', '', item.MetadataList())
                else:
                    metadata[key] = (item.LDSName, item.ESDName, item.UDSName, str(item.value))
            except:
                None
        return OrderedDict(metadata)

    def structure(self):
        print(str(type(self)))

        def repeat(items, indent=1):
            for item in items:
                print(indent * "\t" + str(type(item)))
                if hasattr(item, 'items'):
                    repeat(item.items.values(), indent+1)

        repeat(self.items.values())


def str_dict(values):
    out = []

    def per_item(value, indent=0):
        for item in value:
            out.append(indent * "\t" + str(item))
            if hasattr(item, 'items'):
                per_item(item.items, indent + 1)

    per_item(values)

    return '\n'.join(out)