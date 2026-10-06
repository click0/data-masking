#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Назви органів влади не маскуються як ПІБ (v3.0.24)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_initials import mask  # noqa: E402


@pytest.mark.parametrize("text", [
    "Кабінет Міністрів України постановляє",
    "постанова Кабінету Міністрів України від 6 грудня 1991 року",
    "доручити Кабінетові Міністрів України",
    "за рішенням, ухваленим Кабінетом Міністрів",
    "у Кабінеті Міністрів України",
    "КАБІНЕТ МІНІСТРІВ УКРАЇНИ",
])
def test_cabinet_of_ministers_in_every_case_is_kept(text):
    assert mask(text)[0] == text


def test_name_on_the_same_line_still_masked():
    masked, _ = mask("постанова Кабінету Міністрів; капітан Петренко Іван Іванович")
    assert masked.startswith("постанова Кабінету Міністрів; ")
    assert "Петренко" not in masked
