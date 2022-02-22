#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=protected-access,too-few-public-methods

from typing import List, Optional, TYPE_CHECKING
import struct
import zlib
import ntpath

from cabarchive.file import CabFile
from cabarchive.utils import FMT_CFFOLDER, FMT_CFHEADER_RESERVE, _checksum_compute
from cabarchive.errors import CorruptionError, NotSupportedError

if TYPE_CHECKING:
    from cabarchive.archive import CabArchive

COMPRESSION_MASK_TYPE = 0x000F
COMPRESSION_TYPE_NONE = 0x0000
COMPRESSION_TYPE_MSZIP = 0x0001
COMPRESSION_TYPE_QUANTUM = 0x0002
COMPRESSION_TYPE_LZX = 0x0003


class CabArchiveParser:
    def __init__(self, cfarchive: "CabArchive", flattern: bool = False):

        self.cfarchive: "CabArchive" = cfarchive
        self.flattern: bool = flattern
        self._folder_data: List[bytearray] = []
        self._buf: bytes = b""
        self._header_reserved: bytes = b""
        self._zdict: Optional[bytes] = None
        self._rsvd_block: int = 0

    def parse_cffile(self, offset: int) -> int:
        """Parse a CFFILE entry"""
        fmt = "<I"  # uncompressed size
        fmt += "I"  # uncompressed offset of this file in the folder
        fmt += "H"  # index into the CFFOLDER area
        fmt += "H"  # date
        fmt += "H"  # time
        fmt += "H"  # attribs
        try:
            (usize, uoffset, index, date, time, fattr) = struct.unpack_from(
                fmt, self._buf, offset
            )
        except struct.error as e:
            raise CorruptionError from e

        # parse filename
        offset += struct.calcsize(fmt)
        filename = ""
        for i in range(0, 255):
            if self._buf[offset + i] == 0x0:
                filename = self._buf[offset : offset + i].decode()
                break

        # add file
        f = CabFile()
        f._date_decode(date)
        f._time_decode(time)
        f._attr_decode(fattr)
        try:
            f.buf = bytes(self._folder_data[index][uoffset : uoffset + usize])
        except IndexError as e:
            raise CorruptionError("Failed to get buf for {}".format(filename)) from e
        if len(f) != usize:
            raise CorruptionError(
                "Corruption inside archive, %s is size %i but "
                "expected size %i" % (filename, len(f), usize)
            )
        if self.flattern:
            filename = ntpath.basename(filename)
        self.cfarchive[filename] = f

        # return offset to next entry
        return 16 + i + 1

    def parse_cffolder(self, idx: int, offset: int) -> None:
        """Parse a CFFOLDER entry"""
        fmt = "<I"  # offset to CFDATA
        fmt += "H"  # number of CFDATA blocks
        fmt += "H"  # compression type
        try:
            (offset, ndatab, compression) = struct.unpack_from(fmt, self._buf, offset)
            compression &= COMPRESSION_MASK_TYPE
        except struct.error as e:
            raise CorruptionError from e

        # no data blocks?
        if ndatab == 0:
            raise CorruptionError("No CFDATA blocks")

        # no compression is supported
        if compression not in [COMPRESSION_TYPE_NONE, COMPRESSION_TYPE_MSZIP]:
            if compression == COMPRESSION_TYPE_QUANTUM:
                raise NotSupportedError("Quantum compression not supported")
            if compression == COMPRESSION_TYPE_LZX:
                raise NotSupportedError("LZX compression not supported")
            raise NotSupportedError(
                "Compression type 0x{:x} not supported".format(compression)
            )

        # parse CDATA
        self._folder_data.append(bytearray())
        for _ in range(ndatab):
            offset += self.parse_cfdata(idx, offset, compression)

    def parse_cfdata(self, idx: int, offset: int, compression: int) -> int:
        """Parse a CFDATA entry"""
        fmt = "<I"  # checksum
        fmt += "H"  # compressed bytes
        fmt += "H"  # uncompressed bytes
        try:
            (checksum, blob_comp, blob_uncomp) = struct.unpack_from(
                fmt, self._buf, offset
            )
        except struct.error as e:
            raise CorruptionError from e
        if compression == COMPRESSION_TYPE_NONE and blob_comp != blob_uncomp:
            raise CorruptionError("Mismatched data %i != %i" % (blob_comp, blob_uncomp))
        hdr_sz = struct.calcsize(fmt) + self._rsvd_block
        buf_cfdata = self._buf[offset + hdr_sz : offset + hdr_sz + blob_comp]

        # verify checksum
        if checksum != 0:
            checksum_actual = _checksum_compute(buf_cfdata)
            hdr = bytearray(struct.pack("<HH", blob_comp, blob_uncomp))
            checksum_actual = _checksum_compute(hdr, checksum_actual)
            if checksum_actual != checksum:
                raise CorruptionError(
                    "Invalid checksum at {:x}, expected {:x}, got {:x}".format(
                        offset, checksum, checksum_actual
                    )
                )

        # decompress Zlib data after removing *another* header...
        if compression == COMPRESSION_TYPE_MSZIP:
            if buf_cfdata[:2] != b"CK":
                raise CorruptionError(
                    "Compression header invalid {}".format(buf_cfdata[:2].decode())
                )
            assert self._zdict is not None
            decompress = zlib.decompressobj(-zlib.MAX_WBITS, zdict=self._zdict)
            try:
                buf = decompress.decompress(buf_cfdata[2:])
                buf += decompress.flush()
            except zlib.error as e:
                raise CorruptionError("Failed to decompress") from e
            self._zdict = buf
        else:
            buf = buf_cfdata

        assert len(buf) == blob_uncomp
        self._folder_data[idx] += buf
        return blob_comp + hdr_sz

    def parse(self, buf: bytes) -> None:

        # used as internal state
        self._buf = buf
        if self._zdict is None:
            self._zdict = b""

        offset: int = 0

        # read the file header
        fmt = "<4s"  # signature
        fmt += "xxxx"  # reserved1
        fmt += "I"  # size
        fmt += "xxxx"  # reserved2
        fmt += "I"  # offset to CFFILE
        fmt += "xxxx"  # reserved3
        fmt += "BB"  # version minor, major
        fmt += "H"  # no of CFFOLDERs
        fmt += "H"  # no of CFFILEs
        fmt += "H"  # flags
        fmt += "H"  # setID
        fmt += "H"  # cnt of cabs in set
        try:
            (
                signature,
                size,
                off_cffile,
                version_minor,
                version_major,
                nr_folders,
                nr_files,
                flags,
                set_id,
                idx_cabinet,
            ) = struct.unpack_from(fmt, self._buf, 0)
        except struct.error as e:
            raise CorruptionError from e
        offset += struct.calcsize(fmt)

        # check magic bytes
        if signature != b"MSCF":
            raise NotSupportedError("Data is not application/vnd.ms-cab-compressed")

        # check size matches
        if size > len(self._buf):
            raise CorruptionError(
                "File size 0x{:x} does not match header 0x{:x} (delta 0x{:x})".format(
                    len(self._buf), size, len(self._buf) - size
                )
            )

        # check version
        if version_major != 1 or version_minor != 3:
            raise NotSupportedError(
                "Version {}.{} not supported".format(version_major, version_minor)
            )

        # chained cabs not supported
        if idx_cabinet != 0:
            raise NotSupportedError("Chained cab file not supported")

        # verify we actually have data
        if nr_files == 0:
            raise CorruptionError("The cab file is empty")

        # verify we got complete data
        if off_cffile > len(self._buf):
            raise CorruptionError("Cab file corrupt")

        # reserved sizes
        if flags & 0x0004:
            try:
                (rsvd_hdr, rsvd_folder, rsvd_block) = struct.unpack_from(
                    FMT_CFHEADER_RESERVE, self._buf, offset
                )
            except struct.error as e:
                raise CorruptionError from e
            offset += struct.calcsize(FMT_CFHEADER_RESERVE)
            self._header_reserved = buf[offset : offset + rsvd_hdr]
            offset += rsvd_hdr
            self._rsvd_block = rsvd_block
        else:
            rsvd_folder = 0
            self._rsvd_block = 0

        # read this so we can do round-trip
        self.cfarchive.set_id = set_id

        # parse CFFOLDER
        for i in range(nr_folders):
            self.parse_cffolder(i, offset)
            offset += struct.calcsize(FMT_CFFOLDER) + rsvd_folder

        # parse CFFILEs
        for i in range(0, nr_files):
            off_cffile += self.parse_cffile(off_cffile)

        # allow reuse
        self._zdict = None
