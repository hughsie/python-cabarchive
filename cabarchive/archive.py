#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=protected-access

import os
import struct
import fnmatch
import zlib
import ntpath

from typing import Optional, List

from cabarchive.file import CabFile
from cabarchive.errors import CorruptionError, NotSupportedError


FMT_CFHEADER = "<4sxxxxIxxxxIxxxxBBHHHHH"
FMT_CFFOLDER = "<IHH"
FMT_CFFILE = "<IIHHHH"
FMT_CFDATA = "<IHH"


def _chunkify(arr: bytes, size: int) -> List[bytearray]:
    """ Split up a bytestream into chunks """
    arrs = []
    for i in range(0, len(arr), size):
        chunk = bytearray(arr[i : i + size])
        arrs.append(chunk)
    return arrs


def _checksum_compute(content: bytes, seed: int = 0) -> int:
    """ Compute the MS cabinet checksum """
    csum = seed
    chunks = _chunkify(content, 4)
    for chunk in chunks:
        if len(chunk) == 4:
            ul = chunk[0]
            ul |= chunk[1] << 8
            ul |= chunk[2] << 16
            ul |= chunk[3] << 24
        else:
            # WTF: I can only assume this is a typo from the original
            # author of the cabinet file specification
            if len(chunk) == 3:
                ul = (chunk[0] << 16) | (chunk[1] << 8) | chunk[2]
            elif len(chunk) == 2:
                ul = (chunk[0] << 8) | chunk[1]
            elif len(chunk) == 1:
                ul = chunk[0]
        csum ^= ul
    return csum


class CabArchive(dict):
    """An object representing a Microsoft Cab archive """

    def __init__(self, buf: Optional[bytes] = None, flattern: bool = False):
        """ Parses a MS Cabinet archive """
        dict.__init__(self)

        self.set_id: int = 0
        self._folder_data: List[bytearray] = []
        self._is_multi_folder: bool = False
        self._flattern: bool = flattern

        # load archive
        if buf:
            self.parse(buf)

    def __setitem__(self, key: str, val: CabFile) -> None:
        assert isinstance(key, str)
        assert isinstance(val, CabFile)
        val.filename = key
        dict.__setitem__(self, key, val)

    def _parse_cffile(self, buf: bytes, offset: int) -> int:
        """ Parse a CFFILE entry """
        fmt = "<I"  # uncompressed size
        fmt += "I"  # uncompressed offset of this file in the folder
        fmt += "H"  # index into the CFFOLDER area
        fmt += "H"  # date
        fmt += "H"  # time
        fmt += "H"  # attribs
        try:
            vals = struct.unpack_from(fmt, buf, offset)
        except struct.error as e:
            raise CorruptionError from e

        # parse filename
        offset += struct.calcsize(fmt)
        filename = ""
        for i in range(0, 255):
            if buf[offset + i] == 0x0:
                filename = buf[offset : offset + i].decode()
                break

        # add file
        f = CabFile()
        f._date_decode(vals[3])
        f._time_decode(vals[4])
        f._attr_decode(vals[5])
        try:
            f.buf = bytes(self._folder_data[vals[2]][vals[1] : vals[1] + vals[0]])
        except IndexError as e:
            raise CorruptionError( "Failed to get buf for {}: {}".format(filename, vals)) from e
        if len(f) != vals[0]:
            raise CorruptionError(
                "Corruption inside archive, %s is size %i but "
                "expected size %i" % (filename, len(f), vals[0])
            )
        if self._flattern:
            filename = ntpath.basename(filename)
        self[filename] = f

        # return offset to next entry
        return 16 + i + 1

    def _parse_cffolder(self, buf: bytes, idx: int, offset: int) -> None:
        """ Parse a CFFOLDER entry """
        fmt = "<I"  # offset to CFDATA
        fmt += "H"  # number of CFDATA blocks
        fmt += "H"  # compression type
        try:
            vals = struct.unpack_from(fmt, buf, offset)
        except struct.error as e:
            raise CorruptionError from e

        # no data blocks?
        if vals[1] == 0:
            raise CorruptionError("No CFDATA blocks")

        # no compression is supported
        if vals[2] == 0:
            is_zlib = False
        elif vals[2] == 1:
            is_zlib = True
        else:
            raise NotSupportedError("Compression type not supported")

        # not supported
        if is_zlib and self._is_multi_folder:
            raise NotSupportedError(
                "Compression unsupported in multi-folder archive: "
                "set FolderSizeThreshold=0 in the .ddf file"
            )

        # parse CDATA
        self._folder_data.append(bytearray())
        offset = vals[0]
        for _ in range(vals[1]):
            offset += self._parse_cfdata(buf, idx, offset, is_zlib)

    def _parse_cfdata(self, buf: bytes, idx: int, offset: int, is_zlib: bool) -> int:
        """ Parse a CFDATA entry """
        fmt = "<I"  # checksum
        fmt += "H"  # compressed bytes
        fmt += "H"  # uncompressed bytes
        try:
            vals = struct.unpack_from(fmt, buf, offset)
        except struct.error as e:
            raise CorruptionError from e
        if not is_zlib and vals[1] != vals[2]:
            raise CorruptionError("Mismatched data %i != %i" % (vals[1], vals[2]))
        hdr_sz = struct.calcsize(fmt)
        newbuf = buf[offset + hdr_sz : offset + hdr_sz + vals[1]]

        # decompress Zlib data after removing *another* header...
        if is_zlib:
            if newbuf[:2] != b"CK":
                raise CorruptionError(
                    "Compression header invalid {}".format(newbuf[:2].decode())
                )
            decompress = zlib.decompressobj(-zlib.MAX_WBITS)
            try:
                buf = decompress.decompress(newbuf[2:])
                buf += decompress.flush()
            except zlib.error as e:
                raise CorruptionError("Failed to decompress") from e
        else:
            buf = newbuf

        # check checksum
        if vals[0] != 0:
            checksum = _checksum_compute(newbuf)
            hdr = bytearray(struct.pack("<HH", len(newbuf), len(buf)))
            checksum = _checksum_compute(hdr, checksum)
            if checksum != vals[0]:
                raise CorruptionError("Invalid checksum", offset, vals[0], checksum)

        assert len(buf) == vals[2]
        self._folder_data[idx] += buf
        return vals[1] + hdr_sz

    def parse(self, buf: bytes) -> None:
        """ Parse .cab data """

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
        #        fmt += 'H'      # reserved cab size
        #        fmt += 'B'      # reserved folder size
        #        fmt += 'B'      # reserved block size
        #        fmt += 'B'      # per-cabinet reserved area
        try:
            vals = struct.unpack_from(fmt, buf, 0)
        except struct.error as e:
            raise CorruptionError from e

        # debugging
        if os.getenv("PYTHON_CABARCHIVE_DEBUG"):
            print("CFHEADER", vals)

        # check magic bytes
        if vals[0] != b"MSCF":
            raise NotSupportedError("Data is not application/vnd.ms-cab-compressed")

        # check size matches
        if vals[1] != len(buf):
            raise CorruptionError("Cab file internal size does not match data")

        # check version
        if vals[4] != 1 or vals[3] != 3:
            raise NotSupportedError(
                "Version {}.{} not supported".format(vals[4], vals[3])
            )

        # chained cabs not supported
        if vals[9] != 0:
            raise NotSupportedError("Chained cab file not supported")

        # verify we actually have data
        nr_files = vals[6]
        if nr_files == 0:
            raise CorruptionError("The cab file is empty")

        # verify we got complete data
        off_cffile = vals[2]
        if off_cffile > len(buf):
            raise CorruptionError("Cab file corrupt")

        # chained cabs not supported
        if vals[7] != 0:
            raise CorruptionError("Expected header flags to be cleared")

        # read this so we can do round-trip
        self.set_id = vals[8]

        # we don't support compressed folders in multi-folder archives
        if vals[5] > 1:
            self._is_multi_folder = True

        # parse CFFOLDER
        offset = struct.calcsize(fmt)
        for i in range(vals[5]):
            self._parse_cffolder(buf, i, offset)
            offset += struct.calcsize(FMT_CFFOLDER)

        # parse CFFILEs
        for i in range(0, nr_files):
            off_cffile += self._parse_cffile(buf, off_cffile)

    def find_file(self, glob: str) -> Optional[CabFile]:
        """ Gets a file from the archive using a glob """
        for fn in self:
            if fnmatch.fnmatch(fn, glob):
                return self[fn]
        return None

    def find_files(self, glob: str) -> List[CabFile]:
        """ Gets files from the archive using a glob """
        arr = []
        for fn in self:
            if fnmatch.fnmatch(fn, glob):
                arr.append(self[fn])
        return arr

    def save(self, compress: bool = False, sort: bool = True) -> bytes:
        """ Returns cabinet file data """

        # sort files before export
        cffiles: List[CabFile] = []
        if sort:
            for fn in sorted(self.keys()):
                cffiles.append(self[fn])
        else:
            cffiles.extend(self.values())

        # create linear CFDATA block
        cfdata_linear = bytearray()
        for f in cffiles:
            if f.buf:
                cfdata_linear += f.buf

        # _chunkify and compress with a fixed size
        chunks = _chunkify(cfdata_linear, 0x8000)
        if compress:
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
            archive_size += struct.calcsize(FMT_CFFILE) + len(f._filename_win32.encode()) + 1
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
            len(self),  # no of CFFILEs
            0,  # flags
            self.set_id,  # setID
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
            compress,
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

    def __repr__(self) -> str:
        return "CabArchive({})".format([str(self[cabfile]) for cabfile in self])
