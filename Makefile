# Copyright (C) 2019 Richard Hughes <richard@hughsie.com>
# SPDX-License-Identifier: GPL-2.0+

VENV=./env
PYTHON=$(VENV)/bin/python
PYTEST=$(VENV)/bin/pytest
PYLINT=$(VENV)/bin/pylint
MYPY=$(VENV)/bin/mypy
CODESPELL=$(VENV)/bin/codespell
PIP=$(VENV)/bin/pip
BLACK=$(VENV)/bin/black
STUBGEN=$(VENV)/bin/stubgen

setup:
	virtualenv ./env

$(PYTEST):
	$(PIP) install pytest-cov pylint

$(MYPY):
	$(PIP) install mypy

$(STUBGEN):
	$(PIP) install stubgen

$(BLACK):
	$(PIP) install black

check: $(PYTEST) $(MYPY)
	$(MYPY) .
	$(PYTEST) .
	$(PYLINT) --rcfile pylintrc cabarchive/*.py *.py

blacken:
	find cabarchive -name '*.py' -exec $(BLACK) {} \;

pkg: $(STUBGEN)
	$(STUBGEN) --output . --package cabarchive
	$(PYTHON) setup.py sdist bdist_wheel
