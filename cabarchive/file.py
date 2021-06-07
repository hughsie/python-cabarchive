#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+

import datetime

from typing import Optional


def _is_ascii(text: str) -> bool:
    """Check if a string is ASCII only"""
    if not text:
        return False
    return all(ord(c) < 128 for c in text)


class CabFile:

    """An object representing a file in a Cab archive

    Any number of CabFile instances can be stored in a CabArchive.
    A new instance can be created with just the data bytes or with an additional
    ``mtime``. If the modification time is not set then the current date and time
    is used, which may be unhelpful if you require a reproducable builds.

    .. code-block:: python

        cff = CabFile(b"test123")

    """

    def __init__(
        self,
        buf: Optional[bytes] = None,
        filename: Optional[str] = None,
        mtime: Optional[datetime.datetime] = None,
    ):
        self.filename = filename  #: filename to use in the archive
        self.buf = buf  #: bytes to use for the file contents
        self.date: Optional[datetime.date]  #: date the file was created
        self.time: Optional[datetime.time]  #: time the file was created
        if mtime:
            self.date = mtime.date()
            self.time = mtime.time()
        else:
            self.date = datetime.date.today()
            self.time = datetime.datetime.now().time()
        self.is_readonly = False  #: set if file is read-only
        self.is_hidden = False  #: set if file is hidden
        self.is_system = False  #: set if file is a system file
        self.is_arch = False  #: set if file modified since last backup
        self.is_exec = False  #: set if file is executable

    def __len__(self) -> int:
        if not self.buf:
            return 0
        return len(self.buf)

    @property
    def filename(self) -> Optional[str]:
        return self._filename

    @filename.setter
    def filename(self, filename: str) -> None:
        self.is_name_utf8 = not _is_ascii(filename)
        self._filename = filename

    @property
    def _filename_win32(self) -> Optional[str]:
        return self._filename.replace("/", "\\")

    def _attr_encode(self) -> int:
        """Get attributes on the file"""
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

    def _attr_decode(self, attr: int) -> None:
        """Set attributes on the file"""
        self.is_readonly = bool(attr & 0x01)
        self.is_hidden = bool(attr & 0x02)
        self.is_system = bool(attr & 0x04)
        self.is_arch = bool(attr & 0x20)
        self.is_exec = bool(attr & 0x40)
        self.is_name_utf8 = bool(attr & 0x80)

    def _date_decode(self, val: int) -> None:
        """Decode the MSCAB 32-bit date format"""
        try:
            self.date = datetime.date(
                1980 + ((val & 0xFE00) >> 9), (val & 0x01E0) >> 5, val & 0x001F
            )
        except ValueError as _:
            self.date = None

    def _time_decode(self, val: int) -> None:
        """Decode the MSCAB 32-bit time format"""
        try:
            self.time = datetime.time(
                (val & 0xF800) >> 11, (val & 0x07E0) >> 5, (val & 0x001F) * 2
            )
        except ValueError as _:
            self.time = None

    def _date_encode(self) -> int:
        """Encode the MSCAB 32-bit date format"""
        if not self.date or self.date.year < 1980:
            return 0
        return ((self.date.year - 1980) << 9) + (self.date.month << 5) + self.date.day

    def _time_encode(self) -> int:
        """Encode the MSCAB 32-bit time format"""
        if not self.time:
            return 0
        return (
            (self.time.hour << 11) + (self.time.minute << 5) + int(self.time.second / 2)
        )

    def __repr__(self) -> str:
        return "CabFile({}:{:x})".format(self.filename, len(self))
