#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Richard Hughes <richard@hughsie.com>
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

import cabarchive as cab
import struct
import sys

def main():

    if len(sys.argv) == 1:
        print "No input files given"
        return 1

    for arg in sys.argv[1:]:

        # load file
        arc = cab.CabArchive()
        f = open(arg, 'rb')
        buf = f.read()

        # parse cabinet, repeating until all the checksums are fixed
        while True:
            try:
                arc.parse(buf)
                break
            except cab.CorruptionError as e:
                offset = e[1]
                buf = buf[:offset] + struct.pack('<I', e[3]) + buf[offset+4:]

        # save file
        f = open(arg, 'wb')
        f.write(buf);
        f.close();

if __name__ == "__main__":
    main()
