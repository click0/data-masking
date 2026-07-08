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

from datamasking.masking.constants import (
    __version__, __author__, __contact__, __phone__, __license__, __year__,
)

__all__ = ["__version__", "__author__", "__contact__", "__license__", "__year__"]
