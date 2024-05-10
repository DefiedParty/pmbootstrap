#!/bin/sh -e
# Description: static type checking for python scripts
# https://postmarketos.org/pmb-ci

if [ "$(id -u)" = 0 ]; then
	set -x
	apk -q add py3-argcomplete py3-mypy py3-lxml
	exec su "${TESTUSER:-build}" -c "sh -e $0"
fi

set -x

# FIXME: adopt --check-untyped-defs (and fix the errors)
mypy --cobertura-xml-report "coverage" pmbootstrap.py
