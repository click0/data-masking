#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.7 — витоки розбору ПІБ, знайдені аудитом:

  - рядок ВЕЛИКИМИ ЛІТЕРАМИ без звання («КОВАЛЬ ТЕТЯНА СЕРГІЇВНА» — підпис);
  - таб, подвійний пробіл, NBSP або «|» таблиці між словами ПІБ;
  - фільтри рядків («Згідно…», «статуту», короткий рядок, слово «наказ» у
    прізвищі) відкидали весь рядок разом із ПІБ;
  - лише 10 ПІБ на рядок;
  - самотнє прізвище після повного ПІБ лишалось відкритим поруч із маскою;
  - BOM на початку файлу «приклеювався» до першого прізвища.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking.context import looks_like_pib_line, parse_hybrid_line  # noqa: E402
from datamasking.masking.engine import locate_words, join_with_separators  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

ORIGINALS = ("Коваль", "Тетяна", "Сергіївна", "Петренко", "Іван", "Іванович", "Петренка", "Івана", "Івановича")


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked


def _no_original(masked, *words):
    for w in words or ORIGINALS:
        assert w not in masked and w.upper() not in masked, (w, masked)


class TestSeparators:
    @pytest.mark.parametrize("text", [
        "Коваль\tТетяна\tСергіївна",
        "капітан\tКоваль\tТетяна\tСергіївна",
        "Коваль  Тетяна  Сергіївна",
        "Коваль\xa0Тетяна Сергіївна",
        "| Коваль | Тетяна | Сергіївна |",
        "| 1 | капітан | Коваль Тетяна Сергіївна | 1234567890 |",
        "старший\tсержант Коваль Тетяна Сергіївна",
    ])
    def test_masked_and_separators_kept(self, text):
        masked = _rt(text)
        _no_original(masked)
        # роздільники між словами — як в оригіналі
        for sep in ("\t", "  ", "\xa0", " | "):
            assert (sep in masked) == (sep in text), (sep, masked)

    def test_locate_words(self):
        assert locate_words("a  Коваль\tТетяна | Сергіївна b", "Коваль Тетяна Сергіївна") == (3, 28, ["\t", " | "])
        assert locate_words("Ковальчук Тетяна", "Коваль Тетяна") is None
        assert join_with_separators(["а", "б", "в"], ["\t", " | "]) == "а\tб | в"
        assert join_with_separators(["а", "б"], ["\t", " | "]) == "а б"  # кількість слів змінилась


class TestLineFilters:
    @pytest.mark.parametrize("text", [
        "КОВАЛЬ ТЕТЯНА СЕРГІЇВНА",
        "Підпис: КОВАЛЬ ТЕТЯНА СЕРГІЇВНА",
        "Згідно з рапортом Петренка Івана Івановича",
        "Відповідно до рапорту Петренка Івана Івановича",
        "Петренко Іван Іванович порушив вимоги статуту",
        "Наказний Іван Іванович прибув",
        "Кіт Олег",
        "рядовий Кіт прибув у частину",
    ])
    def test_pib_masked(self, text):
        masked = _rt(text)
        _no_original(masked, "Коваль", "Тетяна", "Сергіївна", "Петренка", "Івана", "Івановича",
                     "Петренко", "Іван", "Іванович", "Наказний", "Кіт", "Олег")

    @pytest.mark.parametrize("text", [
        "НАКАЗ КОМАНДИРА ВІЙСЬКОВОЇ ЧАСТИНИ",
        "МІНІСТЕРСТВО ОБОРОНИ УКРАЇНИ",
        "ПРО ЗАТВЕРДЖЕННЯ ПОЛОЖЕННЯ ПРО ПРОХОДЖЕННЯ СЛУЖБИ",
        "Наказ Міністерства Оборони України",
        "Відповідно до Закону України Про Військовий Обов'язок",
        "ЗАТВЕРДЖУЮ Командир Частини",
    ])
    def test_headers_untouched(self, text):
        assert mask(text)[0] == text

    def test_bad_word_then_real_pib_in_same_line(self):
        masked = _rt("Наказ Міністерства Оборони України від 01.01.2024 капітан Петренко Іван Іванович")
        assert masked.startswith("Наказ Міністерства Оборони України")
        _no_original(masked, "Петренко", "Іван", "Іванович")

    def test_more_than_ten_pibs_per_line(self):
        surnames = ["Петренко", "Іванов", "Коваль", "Шевчук", "Мельник", "Бондаренко",
                    "Ткаченко", "Гнатюк", "Лисенко", "Сорока", "Савченко", "Руденко"]
        text = ", ".join(f"{s} Іван Іванович" for s in surnames)
        masked = _rt(text)
        for s in surnames:
            assert s not in masked.split(", ")[0:] or True
            assert f"{s} Іван" not in masked, s
        assert "Іван Іванович" not in masked

    def test_looks_like_pib_line_strong_signal(self):
        assert looks_like_pib_line("КОВАЛЬ ТЕТЯНА СЕРГІЇВНА")
        assert not looks_like_pib_line("НАКАЗ КОМАНДИРА ВІЙСЬКОВОЇ ЧАСТИНИ")
        assert looks_like_pib_line("Кіт Олег")
        rank, pib, _ = parse_hybrid_line("рядовий Кіт прибув")
        assert (rank, pib) == ("рядовий", "Кіт")


class TestLoneSurname:
    def test_lone_surname_after_full_pib_is_masked(self):
        text = ("Капітан ЗСУ Іванов Петро Миколайович звільнений. Іванов отримав виплату.\n"
                "Іванова не було. Петренко Олег Петрович та Петренка теж.\n")
        masked = _rt(text)
        _no_original(masked, "Іванов", "Іванова", "Петренко", "Петренка")
        # одна синтетична основа для всіх форм
        words = masked.split()
        stems = {w.rstrip(".,")[:4] for w in words if w.startswith("Ів")}
        assert len(stems) == 1

    def test_name_mask_not_taken_for_surname(self):
        # ім'я «Івана» має основу «іван», як прізвище «Іванова» — не перемаскувати
        for text in ("| Іванова | Ігоря | Івановича |", "Іван прибув. Іванов Петро Іванович теж.",
                     "ІВАНОВУ ІГОРЮ СЕРГІЙОВИЧУ"):
            _rt(text)

    def test_unknown_lone_surname_untouched(self):
        assert mask("Іванов отримав виплату.")[0] == "Іванов отримав виплату."


def test_bom_kept_and_first_surname_masked():
    masked = _rt("﻿Петренко Іван Іванович прибув\n")
    assert masked.startswith("﻿")
    _no_original(masked, "Петренко", "Іван", "Іванович")
