#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015-2020 Richard Hughes <richard@hughsie.com>
#
# SPDX-License-Identifier: LGPL-2.1+
#
# pylint: disable=wrong-import-position

import os
import sys
import unittest
import datetime
import subprocess
import time
import hashlib

# allows us to run this from the project root
sys.path.append(os.path.realpath("."))

from cabarchive import CabArchive, CabFile, CorruptionError
from cabarchive.utils import _checksum_compute


def _check_range(data: bytes, expected: bytes) -> None:
    assert data
    assert expected
    failures = 0
    if len(data) != len(expected):
        print("different sizes, got %i expected %i" % (len(data), len(expected)))
        failures += 1
    for i in range(len(data)):
        if data[i] != expected[i]:
            print("@0x%02x got 0x%02x expected 0x%02x" % (i, data[i], expected[i]))
            failures += 1
            if failures > 10:
                print("More than 10 failures, giving up...")
                break
    assert failures == 0, "Data is not the same"


class TestInfParser(unittest.TestCase):
    def test_checksums(self):

        # test checksum function
        csum = _checksum_compute(b"hello123")
        self.assertEqual(csum, 0x5F5E5407)
        csum = _checksum_compute(b"hello")
        self.assertEqual(csum, 0x6C6C6507)

        # measure speed
        start = time.time()
        with open("data/random.bin", "rb") as f:
            csum = _checksum_compute(f.read())
        print("profile checksum: %fms" % ((time.time() - start) * 1000))

    def test_create_compressed(self):
        cabarchive = CabArchive()

        # make predictable
        dt_epoch = datetime.datetime.fromtimestamp(0, datetime.timezone.utc)
        cabarchive["README.txt"] = CabFile(b"foofoofoofoofoofoofoofoo", mtime=dt_epoch)
        cabarchive["firmware.bin"] = CabFile(
            b"barbarbarbarbarbarbarbar", mtime=dt_epoch
        )
        buf = cabarchive.save(compress=True)
        self.assertEqual(len(buf), 122)
        self.assertEqual(
            hashlib.sha1(buf).hexdigest(), "74e94703c403aa93b16d01b088eb52e3a9c73288"
        )

    def test_values(self):

        # parse junk
        with self.assertRaises(CorruptionError):
            CabArchive().parse(b"hello")
        try:
            self.assertEqual(subprocess.call(["cabextract", "--test", "hello"]), 1)
        except FileNotFoundError as _:
            pass

    def test_simple(self):

        with open("data/simple.cab", "rb") as f:
            old = f.read()
        arc = CabArchive()
        arc.parse(old)
        cff = arc["test.txt"]
        self.assertEqual(cff.filename, "test.txt")
        self.assertEqual(cff.buf, b"test123")
        self.assertEqual(len(cff.buf), 7)
        self.assertEqual(cff.date.year, 2015)
        _check_range(arc.save(), old)

    def test_compressed(self):

        with open("data/compressed.cab", "rb") as f:
            old = f.read()
        arc = CabArchive()
        arc.parse(old)
        cff = arc.find_file("*.txt")
        self.assertEqual(cff.buf, b"test123")
        _check_range(arc.save(compress=True), old)

    def test_utf8(self):

        with open("data/utf8.cab", "rb") as f:
            old = f.read()
        arc = CabArchive()
        arc.parse(old)
        cff = arc.find_file("tést.dat")
        self.assertEqual(cff.filename, "tést.dat")
        self.assertEqual(cff.buf, "tést123".encode())
        self.assertEqual(len(cff.buf), 8)
        self.assertEqual(cff.date.year, 2015)
        _check_range(arc.save(), old)

    def test_large(self):

        with open("data/large.cab", "rb") as f:
            old = f.read()
        arc = CabArchive()
        arc.parse(old)
        cff = arc.find_files("random.bin")[0]
        self.assertEqual(len(cff.buf), 0xFFFFF)
        self.assertEqual(
            hashlib.sha1(cff.buf).hexdigest(),
            "8497fe89c41871e3cbd7955e13321e056dfbd170",
        )
        _check_range(arc.save(), old)

    def test_large_compressed(self):

        with open("data/large-compressed.cab", "rb") as f:
            old = f.read()
        arc = CabArchive()
        arc.parse(old)
        cff = arc.find_files("random.bin")[0]
        self.assertEqual(len(cff.buf), 0xFFFFF)
        self.assertEqual(
            hashlib.sha1(cff.buf).hexdigest(),
            "8497fe89c41871e3cbd7955e13321e056dfbd170",
        )
        _check_range(arc.save(compress=True), old)

    def test_multi_folder(self):

        # open a folder with multiple folders
        arc = CabArchive()
        with open("data/multi-folder.cab", "rb") as f:
            arc.parse(f.read())
        self.assertEqual(len(arc), 2)
        cff = arc.find_file("*.txt")
        self.assertEqual(cff.buf, b"test123")

    def test_ddf_fixed(self):

        arc = CabArchive()
        with open("data/ddf-fixed.cab", "rb") as f:
            arc.parse(f.read())
        self.assertEqual(len(arc), 2)
        cff = arc.find_file("*.txt")
        self.assertEqual(cff.buf, b"test123")

    def test_zdict(self):

        # parse multi folder compressed archive that saves zdict
        arc = CabArchive()
        with open("data/multi-folder-compressed.cab", "rb") as f:
            arc.parse(f.read())
        cff = arc["test\\example.jpg"]
        self.assertEqual(
            hashlib.sha1(cff.buf).hexdigest(),
            "60880cf6f2a93616ba8d965bfbca72a56fb736bb",
        )

    def test_create(self):

        # create new archive
        arc = CabArchive()
        arc.set_id = 0x0622

        # first example
        cff = CabFile()
        cff.buf = (
            b"#include <stdio.h>\r\n\r\nvoid main(void)\r\n"
            b'{\r\n    printf("Hello, world!\\n");\r\n}\r\n'
        )
        cff.date = datetime.date(1997, 3, 12)
        cff.time = datetime.time(11, 13, 52)
        cff.is_arch = True
        arc["hello.c"] = cff

        # second example
        cff = CabFile()
        cff.buf = (
            b"#include <stdio.h>\r\n\r\nvoid main(void)\r\n"
            b'{\r\n    printf("Welcome!\\n");\r\n}\r\n\r\n'
        )
        cff.date = datetime.date(1997, 3, 12)
        cff.time = datetime.time(11, 15, 14)
        cff.is_arch = True
        arc["welcome.c"] = cff

        # verify
        data = arc.save(False)
        with open("/tmp/test.cab", "wb") as f:
            f.write(data)
        expected = (
            b"\x4D\x53\x43\x46\x00\x00\x00\x00\xFD\x00\x00\x00\x00\x00\x00\x00"
            b"\x2C\x00\x00\x00\x00\x00\x00\x00\x03\x01\x01\x00\x02\x00\x00\x00"
            b"\x22\x06\x00\x00\x5E\x00\x00\x00\x01\x00\x00\x00\x4D\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x6C\x22\xBA\x59\x20\x00\x68\x65\x6C\x6C"
            b"\x6F\x2E\x63\x00\x4A\x00\x00\x00\x4D\x00\x00\x00\x00\x00\x6C\x22"
            b"\xE7\x59\x20\x00\x77\x65\x6C\x63\x6F\x6D\x65\x2E\x63\x00\xBD\x5A"
            b"\xA6\x30\x97\x00\x97\x00\x23\x69\x6E\x63\x6C\x75\x64\x65\x20\x3C"
            b"\x73\x74\x64\x69\x6F\x2E\x68\x3E\x0D\x0A\x0D\x0A\x76\x6F\x69\x64"
            b"\x20\x6D\x61\x69\x6E\x28\x76\x6F\x69\x64\x29\x0D\x0A\x7B\x0D\x0A"
            b"\x20\x20\x20\x20\x70\x72\x69\x6E\x74\x66\x28\x22\x48\x65\x6C\x6C"
            b"\x6F\x2C\x20\x77\x6F\x72\x6C\x64\x21\x5C\x6E\x22\x29\x3B\x0D\x0A"
            b"\x7D\x0D\x0A\x23\x69\x6E\x63\x6C\x75\x64\x65\x20\x3C\x73\x74\x64"
            b"\x69\x6F\x2E\x68\x3E\x0D\x0A\x0D\x0A\x76\x6F\x69\x64\x20\x6D\x61"
            b"\x69\x6E\x28\x76\x6F\x69\x64\x29\x0D\x0A\x7B\x0D\x0A\x20\x20\x20"
            b"\x20\x70\x72\x69\x6E\x74\x66\x28\x22\x57\x65\x6C\x63\x6F\x6D\x65"
            b"\x21\x5C\x6E\x22\x29\x3B\x0D\x0A\x7D\x0D\x0A\x0D\x0A"
        )
        _check_range(bytearray(data), bytearray(expected))

        # use cabextract to test validity
        try:
            self.assertEqual(
                subprocess.call(["cabextract", "--test", "/tmp/test.cab"]), 0
            )
        except FileNotFoundError as _:
            pass

        # check we can parse what we just created
        arc = CabArchive()
        with open("/tmp/test.cab", "rb") as f:
            arc.parse(f.read())

        # add an extra file
        arc["test.inf"] = CabFile(b"$CHICAGO$")

        # save with compression
        with open("/tmp/test.cab", "wb") as f:
            f.write(arc.save(True))

        # use cabextract to test validity
        try:
            self.assertEqual(
                subprocess.call(["cabextract", "--test", "/tmp/test.cab"]), 0
            )
        except FileNotFoundError as _:
            pass


if __name__ == "__main__":
    unittest.main()
