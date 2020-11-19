#!/usr/bin/python2
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+

from __future__ import absolute_import
from __future__ import print_function

import cabarchive as cab
import struct
import sys


def main():

    if len(sys.argv) == 1:
        print("No input files given")
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
                buf = buf[:offset] + struct.pack('<I', e[3]) + buf[offset + 4:]

        # save file
        f = open(arg, 'wb')
        f.write(buf);
        f.close();


if __name__ == "__main__":
    main()
