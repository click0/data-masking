#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
datamasking — маскування/розмаскування конфіденційних даних
українських військових документів.

Підпакети:
    datamasking.masking    — рушій маскування (constants, engine, cli, ...)
    datamasking.unmasking  — відновлення даних з mapping-файлів
    datamasking.extras     — опційні модулі (config, security, selective,
                             re_mask, tools, masking_logger, password_generator)
    datamasking.rank_data  — словники військових звань та відмінків

Запуск:
    python -m datamasking mask [args]
    python -m datamasking unmask [args]

Історична пласка структура (import masking / unmasking / modules /
rank_data / data_masking / unmask_data) працює через кореневі shim-и
до кінця циклу 3.x.
"""

from datamasking._version import __version__

# Метадані живуть у masking.constants, але той тягне faker (створює
# Faker('uk_UA') при імпорті). Ліниве делегування (PEP 562) лишає
# `import datamasking` та легкі підмодулі (diagnose) без важких
# залежностей — diagnose_mapping.py має працювати на чистому stdlib.
_METADATA = frozenset({"__author__", "__contact__", "__phone__", "__license__", "__year__"})


def __getattr__(name):
    if name in _METADATA:
        from datamasking.masking import constants as _cfg
        return getattr(_cfg, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["__version__", "__author__", "__contact__", "__license__", "__year__"]
