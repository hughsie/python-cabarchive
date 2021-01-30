#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=protected-access

import fnmatch

from typing import Optional, List

from cabarchive.file import CabFile
from cabarchive.parser import CabArchiveParser
from cabarchive.writer import CabArchiveWriter


class CabArchive(dict):
    """This instance allows parsing or writing a MS Cabinet archive.

    You can treat the CabArchive instance like a dictionary when reading
    and writing archives.

    For instance, loading an archive:

    .. code-block:: python

        with open("test.cab", "rb") as f:
            arc = CabArchive(f.read())
        cff = arc["test.txt"]
        print("filename", cff.filename)     # "test.txt"
        print("contents", cff.buf)          # b"test123"
        print("created", cff.date.year)     # 2015
        for fn in arc:
            print(fn)                       # "test.txt"

    ...or creating and saving an archive:

    .. code-block:: python

        arc = CabArchive()
        arc["test.txt"] = CabFile("test123".encode())
        with open("test.cab", "wb") as f:
            f.write(arc.save())
    """

    def __init__(self, buf: Optional[bytes] = None, flattern: bool = False):
        """Creates a CabArchive instance.

        Args:
            self: A CabArchive instance.
            buf: Binary blob loaded from disk.
            flattern: Disregard archive directory structure wen loading.

        Raises:
            CorruptionError: The cab file was invalid or corrupt.
            NotSupportedError: The format was not supported, e.g. unknown compression.
        """
        dict.__init__(self)

        self.set_id: int = 0  #: The "Set ID" used for multi-file archives

        # load archive
        if buf:
            CabArchiveParser(self, flattern=flattern).parse(buf)

    def __setitem__(self, key: str, val: CabFile) -> None:
        assert isinstance(key, str)
        assert isinstance(val, CabFile)
        val.filename = key
        dict.__setitem__(self, key, val)

    def parse(self, buf: bytes) -> None:
        """Parse .cab binary data

        Args:
            self: A CabArchive instance.
            bytes: Binary blob loaded from disk.

        Raises:
            CorruptionError: The cab file was invalid or corrupt.
            NotSupportedError: The format was not supported, e.g. unknown compression.

        """
        CabArchiveParser(self).parse(buf)

    def find_file(self, glob: str) -> Optional[CabFile]:
        """Gets a file from the archive using a glob.

        Args:
            self: A CabArchive instance.
            glob: File glob, e.g. ``*.txt``
        Returns:
            The first CabFile that matches the filename glob, or None.
        """
        for fn in self:
            if fnmatch.fnmatch(fn, glob):
                return self[fn]
        return None

    def find_files(self, glob: str) -> List[CabFile]:
        """Gets files from the archive using a glob.

        Args:
            self: A CabArchive instance.
            glob: File glob, e.g. ``*.txt``
        Returns:
            All CabFile object that matches the filename glob, or None.
        """
        arr = []
        for fn in self:
            if fnmatch.fnmatch(fn, glob):
                arr.append(self[fn])
        return arr

    def save(self, compress: bool = False, sort: bool = True) -> bytes:
        """Returns cabinet file data, optionally compressed

        Args:
            self: A CabArchive instance.
            compress: If the binary data should be compressed.
            sort: If the file lists should be sorted in a predictable order
        Returns:
            The blob of memory that can be written to disk.
        """
        return CabArchiveWriter(self, compress=compress, sort=sort).write()

    def __repr__(self) -> str:
        return "CabArchive({})".format([str(self[cabfile]) for cabfile in self])
