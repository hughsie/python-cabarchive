#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Richard Hughes <richard@hughsie.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA

from __future__ import absolute_import
from __future__ import print_function

import datetime


def _is_ascii(text):
    """ Check if a string is ASCII only """
    return all(ord(c) < 128 for c in text)


class CabFile(object):

    """An object representing a file in a Cab archive """

    def __init__(self, filename, contents=None):
        self.filename = filename
        self.contents = contents
        self.date = datetime.date.today()
        self.time = datetime.datetime.now().time()
        self.is_readonly = False  # file is read-only
        self.is_hidden = False  # file is hidden
        self.is_system = False  # file is a system file
        self.is_arch = True  # file modified since last backup
        self.is_exec = False  # file is executable
        self.is_name_utf8 = not _is_ascii(filename)

    def _attr_encode(self):
        """ Get attributes on the file """
        attr = 0x00
        if self.is_readonly:
            attr += 0x01
        if self.is_hidden:
            attr += 0x02
        if self.is_system:
            attr += 0x04
        if self.is_arch:
            attr += 0x20
        if self.is_exec:
            attr += 0x40
        if self.is_name_utf8:
            attr += 0x80
        return attr

    def _attr_decode(self, attr):
        """ Set attributes on the file """
        self.is_readonly = bool(attr & 0x01)
        self.is_hidden = bool(attr & 0x02)
        self.is_system = bool(attr & 0x04)
        self.is_arch = bool(attr & 0x20)
        self.is_exec = bool(attr & 0x40)
        self.is_name_utf8 = bool(attr & 0x80)

    def _date_decode(self, val):
        """ Decode the MSCAB 32-bit date format """
        self.date = datetime.date(1980 + ((val & 0xfe00) >> 9),
                                  (val & 0x01e0) >> 5,
                                  val & 0x001f)

    def _time_decode(self, val):
        """ Decode the MSCAB 32-bit time format """
        self.time = datetime.time((val & 0xf800) >> 11,
                                  (val & 0x07e0) >> 5,
                                  (val & 0x001f) * 2)

    def _date_encode(self):
        """ Encode the MSCAB 32-bit date format """
        return ((self.date.year - 1980) << 9) + (self.date.month << 5) + self.date.day

    def _time_encode(self):
        """ Encode the MSCAB 32-bit time format """
        return (self.time.hour << 11) + (self.time.minute << 5) + (self.time.second / 2)

    def __str__(self):
        return self.filename

    def __repr__(self):
        return self.__str__()
