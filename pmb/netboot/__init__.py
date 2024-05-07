# Copyright 2023 Mark Hargreaves, Luca Weiss
# SPDX-License-Identifier: GPL-3.0-or-later
from pmb.helpers import logging
from pathlib import Path
import socket
import time

import pmb.chroot.root
from pmb.core.types import PmbArgs
import pmb.helpers.run
from pmb.core import Chroot


def start_nbd_server(args: PmbArgs, ip="172.16.42.2", port=9999):
    """
    Start nbd server in chroot_native with pmOS rootfs.
    :param ip: IP address to serve nbd server for
    :param port: port of nbd server
    """

    pmb.chroot.apk.install(args, ['nbd'])

    chroot = Chroot.native()

    rootfs_path = Path("/mnt/pmbootstrap/netboot") / f"{args.device}.img"
    if not (chroot / rootfs_path).exists() or args.replace:
        rootfs_path2 = Path("/home/pmos/rootfs") / f"{args.device}.img"
        if not (chroot / rootfs_path2).exists():
            raise RuntimeError("The rootfs has not been generated yet, please "
                               "run 'pmbootstrap install' first.")
        if args.replace and not \
                pmb.helpers.cli.confirm(args, f"Are you sure you want to "
                                              f"replace the rootfs for "
                                              f"{args.device}?"):
            return
        pmb.chroot.root(args, ["cp", rootfs_path2, rootfs_path])
        logging.info(f"NOTE: Copied device image to {pmb.config.work}"
                     f"/images_netboot/. The image will persist \"pmbootstrap "
                     f"zap\" for your convenience. Use \"pmbootstrap netboot "
                     f"serve --help\" for more options.")

    logging.info(f"Running nbd server for {args.device} on {ip} port {port}.")

    while True:
        logging.info("Waiting for postmarketOS device to appear...")

        # Try to bind to the IP ourselves before handing it to nbd-servere
        # This is purely to improve the UX as nbd-server just quits when it
        # cannot bind to an IP address.
        test_socket = socket.socket()
        while True:
            try:
                test_socket.bind((ip, 9998))
            except OSError as e:
                if e.errno != 99:  # Cannot assign requested address
                    raise e
                # Wait a bit before retrying
                time.sleep(0.5)
                continue
            test_socket.close()
            break

        logging.info("Found postmarketOS device, serving image...")
        pmb.chroot.root(
            args, ["nbd-server", f"{ip}@{port}", rootfs_path, "-d"],
            check=False, disable_timeout=True)
        logging.info("nbd-server quit. Connection lost?")
        # On a reboot nbd-server will quit, but the IP address sticks around
        # for a bit longer, so wait.
        time.sleep(5)
