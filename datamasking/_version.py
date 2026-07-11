#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Єдине джерело версії пакета.

Файл навмисно без імпортів: setuptools читає значення статично (AST)
через [tool.setuptools.dynamic] у pyproject.toml, не виконуючи пакет
(і не тягнучи faker під час збірки).
"""

__version__ = "3.0.0.dev5"
