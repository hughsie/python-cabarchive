#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=protected-access,too-few-public-methods

import struct

from typing import List

FMT_CFHEADER = "<4sxxxxIxxxxIxxxxBBHHHHH"
FMT_CFHEADER_RESERVE = "<HBB"
FMT_CFFOLDER = "<IHH"
FMT_CFFILE = "<IIHHHH"
FMT_CFDATA = "<IHH"


def _chunkify(arr: bytes, size: int) -> List[bytes]:
    """Split up a bytestream into chunks"""
    arrs = []
    for i in range(0, len(arr), size):
        arrs.append(arr[i : i + size])
    return arrs


def _checksum_compute(buf: bytes, seed: int = 0) -> int:
    """Compute the MS cabinet checksum"""
    csum: int = seed
    for offset in range(0, len(buf), 4):
        try:
            (ul,) = struct.unpack_from("<I", buf, offset)
        except struct.error:
            left: int = len(buf) - offset
            # WTF: I can only assume this is a typo from the original
            # author of the cabinet file specification
            if left == 3:
                ul = (buf[offset + 0] << 16) | (buf[offset + 1] << 8) | buf[offset + 2]
            elif left == 2:
                ul = (buf[offset + 0] << 8) | buf[offset + 1]
            elif left == 1:
                ul = buf[offset + 0]
        csum ^= ul
    return csum
