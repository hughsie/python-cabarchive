#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import print_function

from setuptools import setup

# note: this is a repeat of the README, to evolve, good enough for now.
long_desc = '''
If you want to parse Microsoft Cabinet files in Python you probably
should just install gcab, and use the GObjectIntrospection bindings
for that. GCab is a much better library than this and handles many more
kinds of archive.

If GCab is not available to you (e.g. you're trying to run in an
OpenShift instance on RHEL 6.2), this project might be somewhat useful.

Contributors welcome, either adding new functionality or fixing bugs.

See also: https://msdn.microsoft.com/en-us/library/bb417343.aspx
'''

setup(
    name='cabarchive',
    version='0.1.0',
    license='LGPL-2.1-or-later',
    description='A pure-python library for creating and extracting cab files',
    long_description=long_desc,
    author='Richard Hughes',
    author_email='richard@hughsie.com',
    url='https://github.com/hughsie/python-cabarchive',
    packages=['cabarchive', ],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities',
        'Topic :: System :: Archiving',
    ],
    keywords=['cabextract', 'cab', 'archive', 'extract'],
)
