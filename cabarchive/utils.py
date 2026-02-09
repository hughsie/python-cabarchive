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


def _chunkify(arr: bytes, size: int) -> List[memoryview]:
    """Split up a bytestream into chunks"""
    arrs = []
    arr_mv = memoryview(arr)
    for i in range(0, len(arr), size):
        arrs.append(arr_mv[i : i + size])
    return arrs


def _checksum_compute(buf: bytes, seed: int = 0) -> int:
    """Compute the MS cabinet checksum"""
    csum: int = seed
    n_words = len(buf) // 4

    # process complete 4-byte words in chunks to minimise struct calls
    chunk_sz = 256
    pos = 0
    while pos + chunk_sz <= n_words:
        words = struct.unpack_from(f"<{chunk_sz}I", buf, pos << 2)
        for ul in words:
            csum ^= ul
        pos += chunk_sz
    if pos < n_words:
        rest = n_words - pos
        words = struct.unpack_from(f"<{rest}I", buf, pos << 2)
        for ul in words:
            csum ^= ul

    # tail: 1–3 bytes (spec quirk)
    tail = n_words << 2
    left = len(buf) - tail
    if left == 3:
        csum ^= (buf[tail] << 16) | (buf[tail + 1] << 8) | buf[tail + 2]
    elif left == 2:
        csum ^= (buf[tail] << 8) | buf[tail + 1]
    elif left == 1:
        csum ^= buf[tail]
    return csum
