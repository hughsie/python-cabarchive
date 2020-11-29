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

from cabarchive import CabArchive


def main():

    parser = argparse.ArgumentParser(description="Process cabinet archives.")
    parser.add_argument(
        "--decompress", type=bool, help="decompress the archives", default=False
    )
    parser.add_argument(
        "--info", type=bool, help="Show the files inside the archive", default=True
    )
    parser.add_argument(
        "--outdir", type=str, help="Specify the output directory", default="."
    )

    if len(sys.argv) == 1:
        print("No input files given")
        return 1

    args, argv = parser.parse_known_args()
    for arg in argv:
        arc = CabArchive()
        print("Parsing {}:".format(arg))
        with open(arg, "rb") as f:
            arc.parse(f.read())
        if args.info:
            for fn in arc:
                print(fn)
        if args.decompress:
            for fn in arc:
                with open(os.path.join(args.outdir, fn), "wb") as f:
                    print("Writing {}:".format(fn))
                    f.write(arc[fn].buf)

    return 0


if __name__ == "__main__":
    main()
