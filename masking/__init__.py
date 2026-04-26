#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Masking package — data masking with instance tracking.

Refactored from monolithic data_masking.py in v2.4.0.
"""

from masking.constants import __version__, __author__, __contact__, __license__, __year__


def main():
    """Entry point — lazy import to avoid heavy module loading at import time."""
    from masking.cli import main as _main
    _main()


__all__ = ["__version__", "main"]
