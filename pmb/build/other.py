# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pmb.helpers import logging
import os
from pathlib import Path
import shlex
import datetime
from typing import List

import pmb.chroot
from pmb.core.types import PmbArgs
import pmb.helpers.file
import pmb.helpers.git
import pmb.helpers.pmaports
import pmb.helpers.run
import pmb.parse.arch
import pmb.parse.apkindex
import pmb.parse.version
from pmb.core import Chroot


def copy_to_buildpath(args: PmbArgs, package, chroot: Chroot=Chroot.native()):
    # Sanity check
    aport = pmb.helpers.pmaports.find(args, package)
    if not os.path.exists(aport / "APKBUILD"):
        raise ValueError(f"Path does not contain an APKBUILD file: {aport}")

    # Clean up folder
    build = chroot / "home/pmos/build"
    if build.exists():
        pmb.helpers.run.root(args, ["rm", "-rf", build])

    # Copy aport contents with resolved symlinks
    pmb.helpers.run.root(args, ["mkdir", "-p", build])
    for entry in aport.iterdir():
        file = entry.name
        # Don't copy those dirs, as those have probably been generated by running `abuild`
        # on the host system directly and not cleaning up after itself.
        # Those dirs might contain broken symlinks and cp fails resolving them.
        if file in ["src", "pkg"]:
            logging.warning(f"WARNING: Not copying {file}, looks like a leftover from abuild")
            continue
        pmb.helpers.run.root(args, ["cp", "-rL", aport / file, build / file])

    pmb.chroot.root(args, ["chown", "-R", "pmos:pmos",
                           "/home/pmos/build"], chroot)


def is_necessary(args: PmbArgs, arch, apkbuild, indexes=None):
    """
    Check if the package has already been built. Compared to abuild's check,
    this check also works for different architectures.

    :param arch: package target architecture
    :param apkbuild: from pmb.parse.apkbuild()
    :param indexes: list of APKINDEX.tar.gz paths
    :returns: boolean
    """
    package = apkbuild["pkgname"]
    version_pmaports = apkbuild["pkgver"] + "-r" + apkbuild["pkgrel"]
    msg = "Build is necessary for package '" + package + "': "

    # Get version from APKINDEX
    index_data = pmb.parse.apkindex.package(args, package, arch, False,
                                            indexes)
    if not index_data:
        logging.debug(msg + "No binary package available")
        return True

    # Can't build pmaport for arch: use Alpine's package (#1897)
    if arch and not pmb.helpers.pmaports.check_arches(apkbuild["arch"], arch):
        logging.verbose(f"{package}: build is not necessary, because pmaport"
                        " can't be built for {arch}. Using Alpine's binary"
                        " package.")
        return False

    # a) Binary repo has a newer version
    version_binary = index_data["version"]
    if pmb.parse.version.compare(version_binary, version_pmaports) == 1:
        logging.warning(f"WARNING: about to install {package} {version_binary}"
                        f" (local pmaports: {version_pmaports}, consider"
                        " 'pmbootstrap pull')")
        return False

    # b) Local pmaports has a newer version
    if version_pmaports != version_binary:
        logging.debug(f"{msg}binary package out of date (binary: "
                      f"{version_binary}, local pmaports: {version_pmaports})")
        return True

    # Local pmaports and binary repo have the same version
    return False


def index_repo(args: PmbArgs, arch=None):
    """
    Recreate the APKINDEX.tar.gz for a specific repo, and clear the parsing
    cache for that file for the current pmbootstrap session (to prevent
    rebuilding packages twice, in case the rebuild takes less than a second).

    :param arch: when not defined, re-index all repos
    """
    pmb.build.init(args)

    channel = pmb.config.pmaports.read_config(args)["channel"]
    pkgdir = (pmb.config.work / "packages" / channel)
    paths: List[Path] = []
    if arch:
        paths = [pkgdir / arch]
    else:
        paths = pkgdir.glob("*")

    for path in paths:
        if path.is_dir():
            path_arch = path.name
            path_repo_chroot = Path("/home/pmos/packages/pmos/") / path_arch
            logging.debug("(native) index " + path_arch + " repository")
            description = str(datetime.datetime.now())
            commands = [
                # Wrap the index command with sh so we can use '*.apk'
                ["sh", "-c", "apk -q index --output APKINDEX.tar.gz_"
                 " --description " + shlex.quote(description) + ""
                 " --rewrite-arch " + shlex.quote(path_arch) + " *.apk"],
                ["abuild-sign", "APKINDEX.tar.gz_"],
                ["mv", "APKINDEX.tar.gz_", "APKINDEX.tar.gz"]
            ]
            for command in commands:
                pmb.chroot.user(args, command, working_dir=path_repo_chroot)
        else:
            logging.debug(f"NOTE: Can't build index for: {path}")
        pmb.parse.apkindex.clear_cache(path / "APKINDEX.tar.gz")


def configure_abuild(args: PmbArgs, chroot: Chroot, verify=False):
    """
    Set the correct JOBS count in abuild.conf

    :param verify: internally used to test if changing the config has worked.
    """
    path = chroot / "etc/abuild.conf"
    prefix = "export JOBS="
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith(prefix):
                continue
            if line != (prefix + args.jobs + "\n"):
                if verify:
                    raise RuntimeError(f"Failed to configure abuild: {path}"
                                       "\nTry to delete the file"
                                       "(or zap the chroot).")
                pmb.chroot.root(args, ["sed", "-i", "-e",
                                       f"s/^{prefix}.*/{prefix}{args.jobs}/",
                                       "/etc/abuild.conf"],
                                chroot)
                configure_abuild(args, chroot, True)
            return
    pmb.chroot.root(args, ["sed", "-i", f"$ a\\{prefix}{args.jobs}", "/etc/abuild.conf"], chroot)


def configure_ccache(args: PmbArgs, chroot: Chroot=Chroot.native(), verify=False):
    """
    Set the maximum ccache size

    :param verify: internally used to test if changing the config has worked.
    """
    # Check if the settings have been set already
    arch = pmb.parse.arch.from_chroot_suffix(args, chroot)
    path = pmb.config.work / f"cache_ccache_{arch}" / "ccache.conf"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                if line == ("max_size = " + args.ccache_size + "\n"):
                    return
    if verify:
        raise RuntimeError(f"Failed to configure ccache: {path}\nTry to"
                           " delete the file (or zap the chroot).")

    # Set the size and verify
    pmb.chroot.user(args, ["ccache", "--max-size", args.ccache_size],
                    chroot)
    configure_ccache(args, chroot, True)
