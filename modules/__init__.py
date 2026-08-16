#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DEPRECATED compatibility shim (v3.0): пакет переїхав у datamasking.extras.

Старі імпорти (from modules.tools import ... / from modules.security
import ...) працюють, але видадуть DeprecationWarning.
Використовуйте datamasking.extras.
"""

import importlib as _importlib
import sys as _sys
import warnings as _warnings

_warnings.warn(
    "top-level package 'modules' is deprecated since 3.0; "
    "use 'datamasking.extras' instead",
    DeprecationWarning,
    stacklevel=2,
)

_TARGET = "datamasking.extras"
_SUBMODULES = (
    "config", "masking_logger", "password_generator", "rank_data",
    "re_mask", "security", "selective", "tools",
)

_real = _importlib.import_module(_TARGET)

# Аліаси підмодулів: from modules.tools import ... повертає той самий
# об'єкт модуля, що й datamasking.extras.tools (єдиний стан).
# Опційні залежності (cryptography, yaml) захищені всередині самих
# модулів try/except-ами, тож імпорт тут безпечний.
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
