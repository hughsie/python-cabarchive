#!/usr/bin/python2
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

import struct
import fnmatch
import zlib
import datetime

from file import CabFile
from errors import *

FMT_CFHEADER = '<4sxxxxIxxxxIxxxxBBHHHHH'
FMT_CFFOLDER = 'IHH'
FMT_CFFILE = 'IIHHHH'
FMT_CFDATA = 'IHH'

def _chunkify(arr, size):
    """ Split up a bytestream into chunks """
    arrs = []
    while len(arr) > size:
        pice = arr[:size]
        arrs.append(pice)
        arr = arr[size:]
    arrs.append(arr)
    return arrs

def _checksum_compute(content, seed=0):
    """ Compute the MSCAB "checksum" """
    csum = seed
    chunks = _chunkify(content, 4)
    for chunk in chunks:
        ul = 0
        for i in range(0, min(len(chunk), 4)):
            ul += chunk[i] << (8 * i)
        csum ^= ul
    return csum

class CabArchive(object):
    """An object representing a Microsoft Cab archive """

    def __init__(self):
        """ Set defaults """
        self.files = []
        self.set_id = 0
        self._buf_file = None
        self._buf_data = bytearray()
        self._nr_blocks = 0
        self._off_cfdata = 0
        self.is_compressed = False

    def add_file(self, cffile):
        """ Add file to archive """

        # remove old file if already present
        for tmp in self.files:
            if tmp.filename == cffile.filename:
                self.files.remove(tmp)
                break

        # add object
        self.files.append(cffile)

    def _parse_cffile(self, offset):
        """ Parse a CFFILE entry """
        fmt = 'I'       # uncompressed size
        fmt += 'I'      # uncompressed offset of this file in the folder
        fmt += 'H'      # index into the CFFOLDER area
        fmt += 'H'      # date
        fmt += 'H'      # time
        fmt += 'H'      # attribs
        try:
            vals = struct.unpack_from(fmt, self._buf_file, offset)
        except struct.error as e:
            raise CorruptionError(str(e))

        # parse filename
        offset += struct.calcsize(fmt)
        filename = ''
        for i in range(0, 255):
            filename_c = self._buf_file[offset + i]
            if filename_c == b'\0':
                break
            filename += filename_c

        # add file
        f = CabFile(filename)
        f._date_decode(vals[3])
        f._time_decode(vals[4])
        f._attr_decode(vals[5])
        f.contents = self._buf_data[vals[1]:vals[1] + vals[0]]
        if len(f.contents) != vals[0]:
            raise CorruptionError('Corruption inside archive')
        self.files.append(f)

        # return offset to next entry
        return 16 + len(filename) + 1

    def _parse_cffolder(self, offset):
        """ Parse a CFFOLDER entry """
        fmt = 'I'       # offset to CFDATA
        fmt += 'H'      # number of CFDATA blocks
        fmt += 'H'      # compression type
        try:
            vals = struct.unpack_from(fmt, self._buf_file, offset)
        except struct.error as e:
            raise CorruptionError(str(e))

        # the start of CFDATA
        self._off_cfdata = vals[0]

        # no data blocks?
        self._nr_blocks = vals[1]
        if self._nr_blocks == 0:
            raise CorruptionError('No CFDATA blocks')

        # no compression is supported
        if vals[2] == 0:
            self.is_compressed = False
        elif vals[2] == 1:
            self.is_compressed = True
        else:
            raise NotSupportedError('Compression type not supported')

    def _parse_cfdata(self, offset):
        """ Parse a CFDATA entry """
        fmt = 'xxxx'    # checksum
        fmt += 'H'      # compressed bytes
        fmt += 'H'      # uncompressed bytes
        try:
            vals = struct.unpack_from(fmt, self._buf_file, offset)
        except struct.error as e:
            raise CorruptionError(str(e))
        if not self.is_compressed and vals[0] != vals[1]:
            raise CorruptionError('Mismatched data %i != %i' % (vals[0], vals[1]))
        hdr_sz = struct.calcsize(fmt)
        newbuf = self._buf_file[offset + hdr_sz:offset + hdr_sz + vals[0]]

        # decompress Zlib data after removing *another* header...
        if self.is_compressed:
            if newbuf[0] != 'C' or newbuf[1] != 'K':
                raise CorruptionError('Compression header invalid')
            decompress = zlib.decompressobj(-zlib.MAX_WBITS)
            newbuf = decompress.decompress(newbuf[2:])
            newbuf += decompress.flush()

        assert len(newbuf) == vals[1]
        self._buf_data += newbuf
        return vals[1] + hdr_sz

    def parse(self, buf):
        """ Parse .cab data """

        # slurp the whole buffer at once
        self._buf_file = buf

        # read the file header
        fmt = '<4s'     # signature
        fmt += 'xxxx'   # reserved1
        fmt += 'I'      # size
        fmt += 'xxxx'   # reserved2
        fmt += 'I'      # offset to CFFILE
        fmt += 'xxxx'   # reserved3
        fmt += 'BB'     # version minor, major
        fmt += 'H'      # no of CFFOLDERs
        fmt += 'H'      # no of CFFILEs
        fmt += 'H'      # flags
        fmt += 'H'      # setID
        fmt += 'H'      # cnt of cabs in set
#        fmt += 'H'      # reserved cab size
#        fmt += 'B'      # reserved folder size
#        fmt += 'B'      # reserved block size
#        fmt += 'B'      # per-cabinet reserved area
        try:
            vals = struct.unpack_from(fmt, self._buf_file, 0)
        except struct.error as e:
            raise CorruptionError(str(e))

        # check magic bytes
        if vals[0] != b'MSCF':
            raise NotSupportedError('Data is not application/vnd.ms-cab-compressed')

        # check size matches
        if vals[1] != len(self._buf_file):
            raise CorruptionError('Cab file internal size does not match data')

        # check version
        if vals[4] != 1  or vals[3] != 3:
            raise NotSupportedError('Version %i.%i not supported' % (vals[4], vals[3]))

        # only one folder supported
        if vals[5] != 1:
            raise NotSupportedError('Only one folder supported')

        # chained cabs not supported
        if vals[9] != 0:
            raise NotSupportedError('Chained cab file not supported')

        # verify we actually have data
        nr_files = vals[6]
        if nr_files == 0:
            raise CorruptionError('The cab file is empty')

        # verify we got complete data
        off_cffile = vals[2]
        if off_cffile > len(self._buf_file):
            raise CorruptionError('Cab file corrupt')

        # chained cabs not supported
        if vals[7] != 0:
            raise CorruptionError('Expected header flags to be cleared')

        # parse CFFOLDER
        self._parse_cffolder(struct.calcsize(fmt))

        # parse CDATA
        offset = self._off_cfdata
        for i in range(0, self._nr_blocks):
            offset += self._parse_cfdata(offset)

        # parse CFFILEs
        for i in range(0, nr_files):
            off_cffile += self._parse_cffile(off_cffile)

    def parse_file(self, filename):
        """ Parse a .cab file """
        self.parse(open(filename, 'rb').read())

    def find_file(self, glob):
        """ Gets a file from the archive using a glob """
        for cf in self.files:
            if fnmatch.fnmatch(cf.filename, glob):
                return cf
        return None

    def save(self, compressed=False):
        """ Returns cabinet file data """

        # create linear CFDATA block
        cfdata_linear = bytearray()
        for f in self.files:
            cfdata_linear += f.contents

        # _chunkify
        cf_data_chunks = _chunkify(cfdata_linear, 0xffff - 8)

        # create header
        archive_size = struct.calcsize(FMT_CFHEADER)
        archive_size += struct.calcsize(FMT_CFFOLDER)
        for f in self.files:
            archive_size += struct.calcsize(FMT_CFFILE) + len(f.filename) + 1
        for chunk in cf_data_chunks:
            archive_size += struct.calcsize(FMT_CFDATA) + len(chunk)
        offset = struct.calcsize(FMT_CFHEADER)
        offset += struct.calcsize(FMT_CFFOLDER)
        data = struct.pack(FMT_CFHEADER,
                           'MSCF',                      # signature
                           archive_size,                # complete size
                           offset,                      # offset to CFFILE
                           3, 1,                        # ver minor major
                           1,                           # no of CFFOLDERs
                           len(self.files),             # no of CFFILEs
                           0,                           # flags
                           self.set_id,                 # setID
                           0)                           # cnt of cabs in set

        # create folder
        for f in self.files:
            offset += struct.calcsize(FMT_CFFILE)
            offset += len(f.filename) + 1
        data += struct.pack(FMT_CFFOLDER,
                            offset,                     # offset to CFDATA
                            len(cf_data_chunks),        # number of CFDATA blocks
                            compressed)                 # compression type

        # create each CFFILE
        index_into = 0
        for f in self.files:
            data += struct.pack(FMT_CFFILE,
                                len(f.contents),        # uncompressed size
                                index_into,             # uncompressed offset
                                0,                      # index into CFFOLDER
                                f._date_encode(),       # date
                                f._time_encode(),       # time
                                f._attr_encode())       # attribs
            data += f.filename + b'\0'
            index_into += len(f.contents)

        # create each CFDATA
        for chunk in cf_data_chunks:

            # compress
            if compressed:
                chunk_compressed = bytearray('CK') + zlib.compress(str(chunk))
            else:
                chunk_compressed = chunk

            # first do the 'checksum' on the data, then the partial
            # header. slightly crazy, but anyway
            checksum = _checksum_compute(chunk_compressed)
            hdr_random = bytearray(struct.pack('HH',
                                               len(chunk_compressed),
                                               len(chunk)))
            checksum = _checksum_compute(hdr_random, checksum)
            data += struct.pack(FMT_CFDATA,
                                checksum,               # checksum
                                len(chunk_compressed),  # compressed bytes
                                len(chunk))             # uncompressed bytes
            data += chunk

        # return bytearray
        return data

    def save_file(self, filename, compressed=False):
        """ Saves a cabinet file to disk """
        data = self.save(compressed)
        open(filename, 'wb').write(data)
