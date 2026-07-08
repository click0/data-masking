#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEPRECATED compatibility shim (v3.0): пакет переїхав у datamasking.masking.

Старі імпорти (import masking / from masking.engine import ...) працюють,
але видадуть DeprecationWarning. Використовуйте datamasking.masking.
"""

import importlib as _importlib
import sys as _sys
import warnings as _warnings

_warnings.warn(
    "top-level package 'masking' is deprecated since 3.0; "
    "use 'datamasking.masking' instead",
    DeprecationWarning,
    stacklevel=2,
)

_TARGET = "datamasking.masking"
_SUBMODULES = (
    "constants", "helpers", "language", "context",
    "mask_personal", "mask_military", "engine", "cli",
)

_real = _importlib.import_module(_TARGET)

# Аліаси підмодулів: import masking.constants має повертати ТОЙ САМИЙ
# об'єкт модуля, що й datamasking.masking.constants (єдиний стан —
# критично для "живих" прапорців MASK_* у constants).
for _sub in _SUBMODULES:
    _mod = _importlib.import_module(f"{_TARGET}.{_sub}")
    _sys.modules[f"{__name__}.{_sub}"] = _mod
    globals()[_sub] = _mod

# Публічні імена самого пакета (main, __version__, ...)
globals().update({
    _k: _v for _k, _v in vars(_real).items()
    if _k not in {
        "__name__", "__file__", "__path__", "__package__",
        "__spec__", "__loader__", "__builtins__", "__doc__",
    }
})
