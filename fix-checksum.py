#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+

import cabarchive as cab
import struct
import sys

from typing import Any, Optional, Dict, List


def main():

    if len(sys.argv) == 1:
        print("No input files given")
        return 1

    for arg in sys.argv[1:]:

        # load file
        arc = cab.CabArchive()
        with open(arg, "rb") as f:
            buf = f.read()

        # parse cabinet, repeating until all the checksums are fixed
        while True:
            try:
                arc.parse(buf)
                break
            except cab.CorruptionError as e:
                offset = e[1]
                buf = buf[:offset] + struct.pack("<I", e[3]) + buf[offset + 4 :]

        # save file
        with open(arg, "wb") as f:
            f.write(buf)


if __name__ == "__main__":
    main()
