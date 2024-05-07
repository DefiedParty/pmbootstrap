# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
import os
from pathlib import Path
from typing import Optional
from pmb.core.types import PmbArgs
import pmb.parse


def find_path(args: PmbArgs, codename: str, file='') -> Optional[Path]:
    """
    Find path to device APKBUILD under `device/*/device-`.
    :param codename: device codename
    :param file: file to look for (e.g. APKBUILD or deviceinfo), may be empty
    :returns: path to APKBUILD
    """
    g = list((args.aports / "device").glob(f"*/device-{codename}/{file}"))
    if not g:
        return None

    if len(g) != 1:
        raise RuntimeError(codename + " found multiple times in the device"
                           " subdirectory of pmaports")

    return g[0]


def list_codenames(args: PmbArgs, vendor=None, unmaintained=True):
    """
    Get all devices, for which aports are available
    :param vendor: vendor name to choose devices from, or None for all vendors
    :param unmaintained: include unmaintained devices
    :returns: ["first-device", "second-device", ...]
    """
    ret = []
    for path in args.aports.glob("device/*/device-*"):
        if not unmaintained and 'unmaintained' in path.parts:
            continue
        device = os.path.basename(path).split("-", 1)[1]
        if (vendor is None) or device.startswith(vendor + '-'):
            ret.append(device)
    return ret


def list_vendors(args: PmbArgs):
    """
    Get all device vendors, for which aports are available
    :returns: {"vendor1", "vendor2", ...}
    """
    ret = set()
    for path in (args.aports / "device").glob("*/device-*"):
        vendor = path.name.split("-", 2)[1]
        ret.add(vendor)
    return ret


def list_apkbuilds(args: PmbArgs):
    """
    :returns: { "first-device": {"pkgname": ..., "pkgver": ...}, ... }
    """
    ret = {}
    for device in list_codenames(args):
        apkbuild_path = next(args.aports.glob(f"device/*/device-{device}/APKBUILD"))
        ret[device] = pmb.parse.apkbuild(apkbuild_path)
    return ret


def list_deviceinfos(args: PmbArgs):
    """
    :returns: { "first-device": {"name": ..., "screen_width": ...}, ... }
    """
    ret = {}
    for device in list_codenames(args):
        ret[device] = pmb.parse.deviceinfo(args, device)
    return ret
