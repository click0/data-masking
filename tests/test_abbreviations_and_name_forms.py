#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.6:
  - ТВО і ТРО — вбудовані абревіатури (не маскуються як прізвище);
  - абревіатура з переліку не є частиною ПІБ: «ТРО Петренко Іван Іванович»
    маскується цілком (раніше «Іванович» лишався відкритим);
  - маска імені/по батькові не є тим самим ім'ям в іншому відмінку
    (раніше «Олега» → «Олег», «Петра» → «Петро»).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.language import same_name_forms  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402


def _roundtrip(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text
    return masked


@pytest.mark.parametrize("abbr", ["тво", "тро"])
def test_builtin(abbr):
    assert abbr in _cfg.ABBREVIATION_WHITELIST


@pytest.mark.parametrize("text", [
    "Доповідаю: ТРО Петренко Іван Іванович прибув.",
    "ТВО Петренко Іван Іванович",
    "ТВО командира роти капітан Петренко Іван Іванович",
    "ЗСУ Петренко Іван Іванович",
    "бійці ТРО Мазуренко Олег Петрович та Коваль Іван Іванович",
])
def test_abbreviation_before_name_is_kept_and_name_fully_masked(text):
    masked = _roundtrip(text)
    for abbr in ("ТРО", "ТВО", "ЗСУ"):
        if abbr in text:
            assert abbr in masked
    for word in ("Петренко", "Іван", "Іванович", "Мазуренко", "Олег", "Петрович", "Коваль"):
        if word in text:
            assert word not in masked.split() and word + "," not in masked


class TestNameForms:
    @pytest.mark.parametrize("a,b,same", [
        ("Олег", "Олега", True), ("Петро", "Петра", True), ("Юрій", "Юрія", True),
        ("Марія", "Марії", True), ("Ігора", "Ігоря", True), ("Роман", "Романа", True),
        ("Олексій", "Олександра", False), ("Ігор", "Івана", False), ("Олег", "Олег", True),
        ("Ян", "Яна", False),
    ])
    def test_same_name_forms(self, a, b, same):
        assert same_name_forms(a, b) is same

    @pytest.mark.parametrize("name", [
        "Олега", "Івана", "Петра", "Андрія", "Сергія", "Миколи", "Василя", "Олександра",
        "Дмитра", "Юрія", "Богдана", "Тараса", "Романа", "Віктора", "Ігоря",
    ])
    def test_genitive_name_mask_is_another_name(self, name):
        masked = _roundtrip(f"капітана Коваленка {name} Петровича")
        mask_name = masked.split()[2]
        assert not same_name_forms(mask_name, name), f"{name} -> {mask_name}"

    @pytest.mark.parametrize("text", [
        "капітана Коваленка Олега Петровича", "капітану Коваленку Олегу Петровичу",
        "солдата Коваленко Марії Петрівни", "солдатом Коваленко Марією Іванівною",
    ])
    def test_patronymic_mask_is_another_patronymic(self, text):
        masked = _roundtrip(text)
        orig_pat, mask_pat = text.split()[-1], masked.split()[-1]
        assert not same_name_forms(mask_pat, orig_pat)
