#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entry point for running data-masking as a module.

Usage:
    python -m data-masking mask [args]     # or just: python . mask [args]
    python -m data-masking unmask [args]
    python -m data-masking --version

If no subcommand is given, defaults to 'mask' mode.
"""

import sys


def main():
    args = sys.argv[1:]

    if args and args[0] == '--version':
        from masking.constants import __version__
        print(f"data-masking {__version__}")
        return

    if args and args[0] == 'unmask':
        sys.argv = [sys.argv[0]] + args[1:]
        from unmasking.cli import main as unmask_main
        unmask_main()
    elif args and args[0] == 'mask':
        sys.argv = [sys.argv[0]] + args[1:]
        from masking.cli import main as mask_main
        mask_main()
    else:
        # Default: masking mode (backward compatible)
        from masking.cli import main as mask_main
        mask_main()


if __name__ == "__main__":
    main()
