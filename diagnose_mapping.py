#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entry-script wrapper (v3.0): код переїхав у datamasking.diagnose.

Скрипт лишається підтримуваною точкою входу (python diagnose_mapping.py ...)
та ціллю PyInstaller-збірки. Для імпортів використовуйте datamasking.diagnose.
"""

from datamasking.diagnose import *  # noqa: F401,F403
from datamasking.diagnose import main

if __name__ == "__main__":
    main()
