#!/usr/bin/python2
# Copyright (C) 2015 Richard Hughes <richard@hughsie.com>
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
import datetime

def main():

    # parse test files
    for fn in ['data/simple.cab', 'data/compressed.cab']:
        archive = cab.CabArchive()
        archive.parse_file(fn)
        assert len(archive.files) == 1
        cff = archive.files[0]
        assert cff.filename == 'test.txt', cff.filename
        assert cff.contents == 'test'
        assert cff.date.year == 2015

    # create new archive
    archive = cab.CabArchive()
    archive.set_id = 0x0622

    # first example
    cff = cab.CabFile('hello.c')
    cff.contents = '#include <stdio.h>\r\n\r\nvoid main(void)\r\n{\r\n    printf("Hello, world!\\n");\r\n}\r\n'
    cff.date = datetime.date(1997, 3, 12)
    cff.time = datetime.time(11, 13, 52)
    archive.add_file(cff)

    # second example
    cff = cab.CabFile('welcome.c')
    cff.contents = '#include <stdio.h>\r\n\r\nvoid main(void)\r\n{\r\n    printf("Welcome!\\n");\r\n}\r\n\r\n'
    cff.date = datetime.date(1997,3,12)
    cff.time = datetime.time(11, 15, 14)
    archive.add_file(cff)

    # save file
    archive.save_file('/tmp/test.cab')

    # verify
    data = open('/tmp/test.cab').read()
    expected = "\x4D\x53\x43\x46\x00\x00\x00\x00\xFD\x00\x00\x00\x00\x00\x00\x00" \
               "\x2C\x00\x00\x00\x00\x00\x00\x00\x03\x01\x01\x00\x02\x00\x00\x00" \
               "\x22\x06\x00\x00\x5E\x00\x00\x00\x01\x00\x00\x00\x4D\x00\x00\x00" \
               "\x00\x00\x00\x00\x00\x00\x6C\x22\xBA\x59\x20\x00\x68\x65\x6C\x6C" \
               "\x6F\x2E\x63\x00\x4A\x00\x00\x00\x4D\x00\x00\x00\x00\x00\x6C\x22" \
               "\xE7\x59\x20\x00\x77\x65\x6C\x63\x6F\x6D\x65\x2E\x63\x00\xBD\x5A" \
               "\xA6\x30\x97\x00\x97\x00\x23\x69\x6E\x63\x6C\x75\x64\x65\x20\x3C" \
               "\x73\x74\x64\x69\x6F\x2E\x68\x3E\x0D\x0A\x0D\x0A\x76\x6F\x69\x64" \
               "\x20\x6D\x61\x69\x6E\x28\x76\x6F\x69\x64\x29\x0D\x0A\x7B\x0D\x0A" \
               "\x20\x20\x20\x20\x70\x72\x69\x6E\x74\x66\x28\x22\x48\x65\x6C\x6C" \
               "\x6F\x2C\x20\x77\x6F\x72\x6C\x64\x21\x5C\x6E\x22\x29\x3B\x0D\x0A" \
               "\x7D\x0D\x0A\x23\x69\x6E\x63\x6C\x75\x64\x65\x20\x3C\x73\x74\x64" \
               "\x69\x6F\x2E\x68\x3E\x0D\x0A\x0D\x0A\x76\x6F\x69\x64\x20\x6D\x61" \
               "\x69\x6E\x28\x76\x6F\x69\x64\x29\x0D\x0A\x7B\x0D\x0A\x20\x20\x20" \
               "\x20\x70\x72\x69\x6E\x74\x66\x28\x22\x57\x65\x6C\x63\x6F\x6D\x65" \
               "\x21\x5C\x6E\x22\x29\x3B\x0D\x0A\x7D\x0D\x0A\x0D\x0A"
    failures = 0
    for i in range(0, len(data)):
        if data[i] != expected[i]:
            print "@0x%02x got %02x expected %02x" % (i, ord(data[i]), ord(expected[i]))
            failures += 1
    assert failures == 0

    # check we can parse what we just created
    archive = cab.CabArchive()
    archive.parse_file('/tmp/test.cab')

if __name__ == "__main__":
    main()
