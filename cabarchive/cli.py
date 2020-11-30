#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=wrong-import-position

import sys
import os
import argparse
import tempfile
import subprocess
import glob

sys.path.append(os.path.realpath("."))

from cabarchive import CabArchive, CabFile, NotSupportedError


def repack(arc: CabArchive, arg: str) -> None:
    with tempfile.TemporaryDirectory("cabarchive") as tmpdir:
        print("Extracting to {}".format(tmpdir))
        subprocess.call(["cabextract", "--fix", "--quiet", "--directory", tmpdir, arg])
        for fn in glob.iglob(os.path.join(tmpdir, "**"), recursive=True):
            try:
                with open(fn, "rb") as f:
                    fn_noprefix = fn[len(tmpdir) + 1 :]
                    print("Adding: {}".format(fn_noprefix))
                    arc[fn_noprefix] = CabFile(f.read())
            except IsADirectoryError as _:
                pass


def main():

    parser = argparse.ArgumentParser(description="Process cabinet archives.")
    parser.add_argument(
        "--decompress",
        action="store_true",
        help="decompress the archives",
        default=False,
    )
    parser.add_argument(
        "--autorepack",
        action="store_true",
        help="Repack using cabextract when required",
        default=False,
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show the files inside the archive",
        default=True,
    )
    parser.add_argument(
        "--outdir",
        type=str,
        help="Specify the output directory for decompression",
        default=".",
    )

    if len(sys.argv) == 1:
        print("No input files given")
        return 1

    args, argv = parser.parse_known_args()
    for arg in argv:
        arc = CabArchive()
        try:
            with open(arg, "rb") as f:
                arc.parse(f.read())
        except NotSupportedError as e:
            if not args.autorepack:
                print("Failed to parse: {}; perhaps try --autorepack".format(str(e)))
                return 1
            repack(arc, arg)
        print("Parsing {}:".format(arg))
        if args.info:
            for fn in arc:
                print(fn)
        if args.decompress:
            for fn in arc:
                path = os.path.join(args.outdir, fn)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    print("Writing {}:".format(fn))
                    f.write(arc[fn].buf)

    return 0


if __name__ == "__main__":
    main()
