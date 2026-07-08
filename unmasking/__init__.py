#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEPRECATED compatibility shim (v3.0): пакет переїхав у datamasking.unmasking.

Старі імпорти (import unmasking / from unmasking.engine import ...) працюють,
але видадуть DeprecationWarning. Використовуйте datamasking.unmasking.
"""

import importlib as _importlib
import sys as _sys
import warnings as _warnings

_warnings.warn(
    "top-level package 'unmasking' is deprecated since 3.0; "
    "use 'datamasking.unmasking' instead",
    DeprecationWarning,
    stacklevel=2,
)

_TARGET = "datamasking.unmasking"
_SUBMODULES = ("helpers", "engine", "io", "cli")

_real = _importlib.import_module(_TARGET)

for _sub in _SUBMODULES:
    _mod = _importlib.import_module(f"{_TARGET}.{_sub}")
    _sys.modules[f"{__name__}.{_sub}"] = _mod
    globals()[_sub] = _mod

globals().update({
    _k: _v for _k, _v in vars(_real).items()
    if _k not in {
        "__name__", "__file__", "__path__", "__package__",
        "__spec__", "__loader__", "__builtins__", "__doc__",
    }
})
