#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки другого прогону фазера (після 3.1.20): числові типи, JSON,
обрамлення слів.

  - маска військового квитка (змінюються 2 цифри з 6), БР-номера, паспорта,
    ІПН, військової частини могла збігтися з оригіналом — номер лишався
    відкритим (квиток — у ~1 % випадків, «№5дск» — у кожному десятому);
  - маска номера наказу «1» збігалась із частиною відкритого «п. 1.2»;
  - JSON: номери входжень масок спільні для документа, а unmask рахував
    їх для кожного рядка з нуля;
  - інфінітив на початку пункту («Видати Петренку Івану») ставав прізвищем;
  - ПІБ у дужках: «(Петренко» не було словом ПІБ (прізвище лишалось
    відкритим), а «Петрович)» було — разом із дужкою, що зникала;
  - «*старший матрос …*»: звання знаходилось без першого слова, і unmask
    не відновлював «*старший моряк»;
  - текстова дата: місяць з великої чи капсом повертався малими літерами,
    а «123 травня 2025» маскувалось як «23 травня» і не відновлювалось.
"""
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking.engine import mask_json_recursive  # noqa: E402
from datamasking.masking.mask_military import (  # noqa: E402
    mask_br_number, mask_military_unit,
)
from datamasking.masking.mask_personal import (  # noqa: E402
    mask_ipn, mask_military_id, mask_passport_id,
)
from datamasking.unmasking.engine import unmask_json_with_stats, unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import make_masking_dict, mask  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


def _absent(masked, *words):
    for w in words:
        assert w not in masked, (w, masked)


def _json_rt(data):
    mapping = make_masking_dict()
    counters = {}
    masked = mask_json_recursive(data, mapping, counters)
    mapping["instance_tracking"] = counters
    # Як у CLI: замаскований JSON записується у файл і читається назад
    masked = json.loads(json.dumps(masked, ensure_ascii=False))
    restored, stats = unmask_json_with_stats(masked, mapping, check_mapping_version(mapping))
    assert restored == data, (masked, restored)
    return masked, stats


class TestMaskNeverEqualsOriginal:
    @pytest.mark.parametrize("func, make", [
        (mask_military_id, lambda r: f"АА {r.randint(100000, 999999)}"),
        (mask_military_id, lambda r: f"мт-{r.randint(100000, 999999)}"),
        (mask_military_id, lambda r: str(r.randint(100000, 999999))),
        (mask_passport_id, lambda r: str(r.randint(10 ** 8, 10 ** 9 - 1))),
        (mask_ipn, lambda r: str(r.randint(10 ** 9, 10 ** 10 - 1))),
        (mask_military_unit, lambda r: f"А{r.randint(1000, 9999)}"),
        (mask_br_number, lambda r: f"№{r.randint(1, 99)}дск"),
        (mask_br_number, lambda r: f"№БР-{r.randint(1, 9)}/{r.randint(1, 9)}-К"),
    ])
    def test_random_values(self, func, make):
        rng = random.Random(7)
        for _ in range(1500):
            original = make(rng)
            mapping = make_masking_dict()
            mapping["mappings"].setdefault("br_number", {})
            assert func(original, mapping, {}) != original, original

    @pytest.mark.parametrize("text, secret", [
        ("військовий квиток АА 585285", "585285"),
        ("посвідчення мт-767843 військовий квиток АА 585285", "585285"),
        ("військовий квиток КВ 740021", "740021"),
    ])
    def test_military_id_in_text(self, text, secret):
        masked, _ = _rt(text)
        _absent(masked, secret)

    def test_first_mask_unchanged(self):
        # Повторні спроби — лише коли перша маска не годиться: маски, що
        # й так відрізнялись від оригіналу, лишились тими самими
        # (значення — як у 3.1.20)
        assert mask_military_id("АА 123456", make_masking_dict(), {}) == "АА 129256"
        assert mask_military_unit("А1234", make_masking_dict(), {}) == "А9377"
        assert mask_passport_id("123456789", make_masking_dict(), {}) == "123775719"
        assert mask_ipn("1234567890", make_masking_dict(), {}) == "1233548730"
        mapping = make_masking_dict()
        mapping["mappings"].setdefault("br_number", {})
        assert mask_br_number("№БР-123/45-К", mapping, {}) == "№БР-632/58-К"


class TestNumberInsideOpenNumber:
    @pytest.mark.parametrize("text", [
        "582 одиниць і п. 1.2 і військової частини В8363\n"
        "військової частини К2059 і наказ № 2 та наказ № 2\n",
        "п. 1.2 та 2024-2025 роки; наказ № 2 від сьогодні, наказ № 3, наказ № 4, "
        "наказ № 5, наказ № 6",
    ])
    def test_roundtrip(self, text):
        _rt(text)


class TestJson:
    def test_shared_mask_across_strings(self):
        _json_rt({"orders": [f"наказ № {i}" for i in range(1, 25)]})

    def test_open_number_in_another_string(self):
        _json_rt({"b": "п. 4", "a": "наказ № 2", "c": ["наказ № 6", {"x": "п. 1.2"}], "n": 5, "z": None})

    def test_names_across_strings(self):
        masked, stats = _json_rt({
            "a": "Звернення до Іване Петровичу",
            "b": "Надати відпустку солдату Петренку Івану Петровичу",
            "c": "Шановний Іване Петровичу!",
        })
        assert "Петренк" not in json.dumps(masked, ensure_ascii=False)
        assert stats["skipped_count"] == 0

    @pytest.mark.parametrize("data", [
        {"one": "солдат Петренко Іван Петрович"},
        ["", "солдат Петренко Іван Петрович", "", "Петренко"],
        {"k": [], "m": {}, "s": "без даних"},
        "солдат Петренко Іван Петрович",
    ])
    def test_shapes(self, data):
        _json_rt(data)


class TestInfinitiveNotSurname:
    @pytest.mark.parametrize("text, verb, secrets", [
        ("Видати Петренку Івану", "Видати", ("Петренк", "Івану")),
        ("Надати Петренку Івану відпустку", "Надати", ("Петренк", "Івану")),
        ("Наказати Коваленку Петру", "Наказати", ("Коваленк", "Петру")),
        ("Зарахувати Мельника Олега до списків", "Зарахувати", ("Мельник", "Олега")),
        ("Видати ПЕТРЕНКУ ІВАНУ ПЕТРОВИЧУ посвідчення", "Видати", ("ПЕТРЕНК", "ІВАНУ")),
    ])
    def test_verb_kept(self, text, verb, secrets):
        masked, _ = _rt(text)
        assert masked.startswith(verb + " "), masked
        _absent(masked, *secrets)


class TestBrackets:
    @pytest.mark.parametrize("text, wrap", [
        ("(Петренко Іван Петрович)", "()"),
        ("[Петренко Іван Петрович]", "[]"),
        ("{Петренко Іван Петрович}", "{}"),
        ("/Петренко Іван Петрович/", "//"),
        ("*Петренко Іван Петрович*", "**"),
        ("(сержант Петренко Іван Петрович)", "()"),
        ("Наказ (щодо Петренка Івана Петровича) виконати", None),
        ("сержант (Петренко Іван Петрович), ІПН 1234567890", None),
        ("(сержант Петренко)", "()"),
        ("(сержант Петренко Іван Петрович), (солдат Коваль Олег Олегович)", None),
    ])
    def test_masked_and_kept(self, text, wrap):
        masked, _ = _rt(text)
        _absent(masked, "Петренк", "Іван", "Петрович", "Коваль")
        if wrap:
            assert masked[0] == wrap[0] and masked[-1] == wrap[1], masked
        assert masked.count("(") == text.count("(") and masked.count(")") == text.count(")")

    def test_pib_ends_at_closing_bracket(self):
        masked, mapping = _rt("(Петренко Іван Петрович) Коваль")
        assert all(")" not in k for cat in mapping["mappings"].values() for k in cat)


class TestWrappedNavalRank:
    @pytest.mark.parametrize("text", [
        "/старшому моряку Ярославу Юрійовичу Петренку оголосити подяку./",
        "*старший матрос Кравченко Олександр Богданович доповів*",
        "*старший матрос Бондар Ігор Андрійович, РНОКПП 8984085240*",
        "року *старший матрос Пилип'юк Любов Богданівна,",
    ])
    def test_roundtrip(self, text):
        _rt(text)


class TestTextDates:
    @pytest.mark.parametrize("text", [
        "06 Жовтня 2025 р.",
        "06 ЖОВТНЯ 2025 РОКУ",
        "«06» ЖОВТНЯ 2025 та «06» Жовтня 2025 і 06 жовтня 2025",
        "«06» жовтня 2025 року та 06 жовтня 2025 року",
    ])
    def test_month_case_restored(self, text):
        masked, _ = _rt(text)
        _absent(masked.lower(), "жовтня")

    @pytest.mark.parametrize("text", ["123 травня 2025", "1 травня 20251"])
    def test_not_part_of_longer_number(self, text):
        masked, _ = _rt(text)
        assert masked == text
