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
from cabarchive.utils import (
    FMT_CFHEADER,
    FMT_CFHEADER_RESERVE,
    FMT_CFFOLDER,
    FMT_CFFILE,
    FMT_CFDATA,
    _checksum_compute,
)
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
        self._folder_data: List[bytes] = []
        self._buf: bytes = b""
        self._header_reserved: bytes = b""
        self._zdict: Optional[bytes] = None
        self._rsvd_block: int = 0
        self._ndatabsz: int = 0

    def parse_cffile(self, offset: int) -> int:
        """Parse a CFFILE entry"""
        try:
            (usize, uoffset, index, date, time, fattr) = struct.unpack_from(
                FMT_CFFILE, self._buf, offset
            )
        except struct.error as e:
            raise CorruptionError from e

        # parse filename
        offset += struct.calcsize(FMT_CFFILE)
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
            raise CorruptionError(f"Failed to get buf for {filename}") from e
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

    def parse_cffolder(self, offset: int) -> None:
        """Parse a CFFOLDER entry"""
        try:
            (offset, ndatab, compression) = struct.unpack_from(
                FMT_CFFOLDER, self._buf, offset
            )
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
            raise NotSupportedError(f"Compression type 0x{compression:x} not supported")

        # parse CDATA, collect chunks then join once
        chunks: list[bytes] = []
        if self._ndatabsz:
            while offset < self._ndatabsz:
                advance, buf = self.parse_cfdata(offset, compression)
                chunks.append(buf)
                offset += advance
        else:
            for _ in range(ndatab):
                advance, buf = self.parse_cfdata(offset, compression)
                chunks.append(buf)
                offset += advance
        self._folder_data.append(b"".join(chunks))

    def parse_cfdata(self, offset: int, compression: int) -> tuple[int, bytes]:
        """Parse a CFDATA entry. Returns both offset and decompressed data."""
        try:
            (checksum, blob_comp, blob_uncomp) = struct.unpack_from(
                FMT_CFDATA, self._buf, offset
            )
        except struct.error as e:
            raise CorruptionError from e
        if compression == COMPRESSION_TYPE_NONE and blob_comp != blob_uncomp:
            raise CorruptionError("Mismatched data %i != %i" % (blob_comp, blob_uncomp))
        hdr_sz = struct.calcsize(FMT_CFDATA) + self._rsvd_block
        buf_cfdata = memoryview(self._buf)[
            offset + hdr_sz : offset + hdr_sz + blob_comp
        ]

        # verify checksum
        if checksum != 0:
            checksum_actual = _checksum_compute(buf_cfdata)
            hdr = struct.pack("<HH", blob_comp, blob_uncomp)
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
                    f"Compression header invalid {buf_cfdata[:2].tobytes().decode()}"
                )
            if self._zdict is None:
                raise CorruptionError("failed to set up decompressor")
            decompress = zlib.decompressobj(-zlib.MAX_WBITS, zdict=self._zdict)
            try:
                buf = decompress.decompress(buf_cfdata[2:])
                buf += decompress.flush()
            except zlib.error as e:
                raise CorruptionError("Failed to decompress") from e
            self._zdict = buf
        else:
            buf = bytes(buf_cfdata)
        if len(buf) != blob_uncomp:
            raise CorruptionError(
                "decompressor result invalid, expected {:x}, got {:x}".format(
                    blob_uncomp, len(buf)
                )
            )
        return (hdr_sz + blob_comp, buf)

    def parse(self, buf: bytes) -> None:
        # used as internal state
        self._buf = buf
        if self._zdict is None:
            self._zdict = b""

        offset: int = 0

        # read the file header
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
            ) = struct.unpack_from(FMT_CFHEADER, self._buf, 0)
        except struct.error as e:
            raise CorruptionError from e
        offset += struct.calcsize(FMT_CFHEADER)

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
                f"Version {version_major}.{version_minor} not supported"
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

        # if the only folder is >= 2GB then CFFOLDER.ndatab will overflow
        if len(self._buf) >= 0x8000 * 0xFFFF and nr_folders == 1:
            self._ndatabsz = len(self._buf)

        # parse CFFOLDER
        for _ in range(nr_folders):
            self.parse_cffolder(offset)
            offset += struct.calcsize(FMT_CFFOLDER) + rsvd_folder

        # parse CFFILEs
        for _ in range(nr_files):
            off_cffile += self.parse_cffile(off_cffile)

        # allow reuse
        self._zdict = None
