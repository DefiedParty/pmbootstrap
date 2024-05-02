# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
""" Tests all functions from pmb.build._package """
import datetime
import glob
import os
import pytest
import shutil
import sys

import pmb_test  # noqa
import pmb_test.git
import pmb.build
import pmb.build._package
import pmb.config
import pmb.config.init
import pmb.helpers.logging


@pytest.fixture
def args(tmpdir, request):
    import pmb.parse
    sys.argv = ["pmbootstrap", "init"]
    args = pmb.parse.arguments()
    args.log = args.work + "/log_testsuite.txt"
    pmb.helpers.logging.init(args)
    request.addfinalizer(pmb.helpers.logging.logfd.close)
    return args


def return_none(*args, **kwargs):
    return None


def return_string(*args, **kwargs):
    return "some/random/path.apk"


def return_true(*args, **kwargs):
    return True


def return_false(*args, **kwargs):
    return False


def return_fake_build_depends(*args, **kwargs):
    """
    Fake return value for pmb.build._package.build_depends:
    depends: ["alpine-base"], depends_built: []
    """
    return (["alpine-base"], [])


def args_patched(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", argv)
    return pmb.parse.arguments()


def test_package(args):
    # First build
    assert pmb.build.package(args, "hello-world", force=True)

    # Package exists
    pmb.helpers.other.cache["built"] = {}
    assert pmb.build.package(args, "hello-world") is None

    # Force building again
    pmb.helpers.other.cache["built"] = {}
    assert pmb.build.package(args, "hello-world", force=True)

    # Build for another architecture
    assert pmb.build.package(args, "hello-world", "armhf", force=True)

    # Upstream package, for which we don't have an aport
    assert pmb.build.package(args, "alpine-base") is None
