#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEPRECATED compatibility shim (v3.0): модуль переїхав у datamasking.rank_data.

Старий імпорт (from rank_data import RANKS_LIST) працює, але видасть
DeprecationWarning. Використовуйте datamasking.rank_data.
"""

import importlib as _importlib
import sys as _sys
import warnings as _warnings

_warnings.warn(
    "top-level module 'rank_data' is deprecated since 3.0; "
    "use 'datamasking.rank_data' instead",
    DeprecationWarning,
    stacklevel=2,
)

# Підміна себе реальним модулем: єдиний об'єкт, всі імена
# (включно з підкресленими на кшталт _DECLENSION_FORMS_LIST) доступні.
_sys.modules[__name__] = _importlib.import_module("datamasking.rank_data")
