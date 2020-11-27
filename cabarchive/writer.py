#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=protected-access,too-few-public-methods

from typing import List, TYPE_CHECKING
import struct
import zlib

from cabarchive.file import CabFile
from cabarchive.utils import (
    FMT_CFHEADER,
    FMT_CFFOLDER,
    FMT_CFFILE,
    FMT_CFDATA,
    _chunkify,
    _checksum_compute,
)

if TYPE_CHECKING:
    from cabarchive.archive import CabArchive


class CabArchiveWriter:
    def __init__(
        self, cfarchive: "CabArchive", compress: bool = False, sort: bool = True
    ) -> None:
        self.cfarchive: "CabArchive" = cfarchive
        self.compress: bool = compress
        self.sort: bool = sort

    def write(self) -> bytes:

        # sort files before export
        cffiles: List[CabFile] = []
        if self.sort:
            for fn in sorted(self.cfarchive.keys()):
                cffiles.append(self.cfarchive[fn])
        else:
            cffiles.extend(self.cfarchive.values())

        # create linear CFDATA block
        cfdata_linear = bytearray()
        for f in cffiles:
            if f.buf:
                cfdata_linear += f.buf

        # _chunkify and compress with a fixed size
        chunks = _chunkify(cfdata_linear, 0x8000)
        if self.compress:
            chunks_zlib = []
            for chunk in chunks:
                compressobj = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
                chunk_zlib = bytearray(b"CK")
                chunk_zlib += compressobj.compress(chunk)
                chunk_zlib += compressobj.flush()
                chunks_zlib.append(chunk_zlib)
        else:
            chunks_zlib = chunks

        # create header
        archive_size = struct.calcsize(FMT_CFHEADER)
        archive_size += struct.calcsize(FMT_CFFOLDER)
        for f in cffiles:
            if not f._filename_win32:
                continue
            archive_size += (
                struct.calcsize(FMT_CFFILE) + len(f._filename_win32.encode()) + 1
            )
        for chunk in chunks_zlib:
            archive_size += struct.calcsize(FMT_CFDATA) + len(chunk)
        offset = struct.calcsize(FMT_CFHEADER)
        offset += struct.calcsize(FMT_CFFOLDER)
        data = struct.pack(
            FMT_CFHEADER,
            b"MSCF",  # signature
            archive_size,  # complete size
            offset,  # offset to CFFILE
            3,
            1,  # ver minor major
            1,  # no of CFFOLDERs
            len(self.cfarchive),  # no of CFFILEs
            0,  # flags
            self.cfarchive.set_id,  # setID
            0,
        )  # cnt of cabs in set

        # create folder
        for f in cffiles:
            if not f._filename_win32:
                continue
            offset += struct.calcsize(FMT_CFFILE)
            offset += len(f._filename_win32.encode()) + 1
        data += struct.pack(
            FMT_CFFOLDER,
            offset,  # offset to CFDATA
            len(chunks),  # number of CFDATA blocks
            self.compress,
        )  # compression type

        # create each CFFILE
        index_into = 0
        for f in cffiles:
            if not f._filename_win32:
                continue
            data += struct.pack(
                FMT_CFFILE,
                len(f),  # uncompressed size
                index_into,  # uncompressed offset
                0,  # index into CFFOLDER
                f._date_encode(),  # date
                f._time_encode(),  # time
                f._attr_encode(),
            )  # attribs
            data += f._filename_win32.encode() + b"\0"
            index_into += len(f)

        # create each CFDATA
        for i in range(0, len(chunks)):
            chunk = chunks[i]
            chunk_zlib = chunks_zlib[i]

            # first do the 'checksum' on the data, then the partial
            # header. slightly crazy, but anyway
            checksum = _checksum_compute(chunk_zlib)
            hdr = bytearray(struct.pack("<HH", len(chunk_zlib), len(chunk)))
            checksum = _checksum_compute(hdr, checksum)
            data += struct.pack(
                FMT_CFDATA,
                checksum,  # checksum
                len(chunk_zlib),  # compressed bytes
                len(chunk),
            )  # uncompressed bytes
            data += chunk_zlib

        # return bytearray
        return data
