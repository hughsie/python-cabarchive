#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=protected-access,too-few-public-methods

from typing import List

FMT_CFHEADER = "<4sxxxxIxxxxIxxxxBBHHHHH"
FMT_CFHEADER_RESERVE = "<HBB"
FMT_CFFOLDER = "<IHH"
FMT_CFFILE = "<IIHHHH"
FMT_CFDATA = "<IHH"


def _chunkify(arr: bytes, size: int) -> List[bytearray]:
    """Split up a bytestream into chunks"""
    arrs = []
    for i in range(0, len(arr), size):
        chunk = bytearray(arr[i : i + size])
        arrs.append(chunk)
    return arrs


def _checksum_compute(content: bytes, seed: int = 0) -> int:
    """Compute the MS cabinet checksum"""
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
