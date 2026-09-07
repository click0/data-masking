#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entry point for running data-masking as a module.

Usage:
    python . mask [args]          # з кореня репозиторію
    python . unmask [args]
    python . --version
    python -m datamasking mask    # після pip install (або з кореня репо)

If no subcommand is given, defaults to 'mask' mode.
"""

import sys


def main():
    args = sys.argv[1:]

    if args and args[0] == '--version':
        from datamasking.masking.constants import __version__
        print(f"data-masking {__version__}")
        return 0

    if args and args[0] == 'unmask':
        sys.argv = [sys.argv[0]] + args[1:]
        from datamasking.unmasking.cli import main as unmask_main
        return unmask_main()
    elif args and args[0] == 'mask':
        sys.argv = [sys.argv[0]] + args[1:]
        from datamasking.masking.cli import main as mask_main
        return mask_main()
    else:
        # Default: masking mode (backward compatible)
        from datamasking.masking.cli import main as mask_main
        return mask_main()


if __name__ == "__main__":
    sys.exit(main())
