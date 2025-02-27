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

sys.path.append(os.path.realpath("."))

from cabarchive import CabArchive, NotSupportedError


def main():
    parser = argparse.ArgumentParser(description="Process cabinet archives.")
    parser.add_argument(
        "--decompress",
        action="store_true",
        help="decompress the archives",
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
            print(f"Failed to parse: {str(e)}")
            return 1
        print(f"Parsing {arg}:")
        if args.info:
            for fn in arc:
                print(fn)
        if args.decompress:
            for fn in arc:
                path = os.path.join(args.outdir, fn)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    print(f"Writing {fn}:")
                    f.write(arc[fn].buf)

    return 0


if __name__ == "__main__":
    main()
