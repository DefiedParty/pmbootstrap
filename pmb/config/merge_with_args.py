# Copyright 2023 Oliver Smith
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import pmb.config
from pmb.core.types import PmbArgs


def merge_with_args(args: PmbArgs):
    """
    We have the internal config (pmb/config/__init__.py) and the user config
    (usually ~/.config/pmbootstrap.cfg, can be changed with the '-c'
    parameter).

    Args holds the variables parsed from the commandline (e.g. -j fills out
    args.jobs), and values specified on the commandline count the most.

    In case it is not specified on the commandline, for the keys in
    pmb.config.config_keys, we look into the value set in the the user config.

    When that is empty as well (e.g. just before pmbootstrap init), or the key
    is not in pmb.config_keys, we use the default value from the internal
    config.
    """
    # Use defaults from the user's config file
    cfg = pmb.config.load(args)
    for key in cfg["pmbootstrap"]:
        if key not in args or getattr(args, key) is None:
            value = cfg["pmbootstrap"][key]
            if key in pmb.config.defaults:
                default = pmb.config.defaults[key]
                if isinstance(default, bool):
                    value = (value.lower() == "true")
            setattr(args, key, value)
    setattr(args, 'selected_providers', cfg['providers'])

    # Use defaults from pmb.config.defaults
    for key, value in pmb.config.defaults.items():
        if key not in args or getattr(args, key) is None:
            setattr(args, key, value)

    pmb.config.work_dir(Path(cfg["pmbootstrap"]["work"]))

    # Make sure args.aports is a Path object
    setattr(args, "aports", Path(args.aports))

    # args.work is deprecated!
    delattr(args, "work")
