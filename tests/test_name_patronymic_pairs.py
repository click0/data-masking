#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.13 — розбір ПІБ без прізвища («Шановний Олегу Петровичу!»), порядку
«Ім'я По батькові Прізвище» і слова з великої перед повним ПІБ («Заява
Петренка Олега Петровича»). До того ім'я діставало маску прізвища (з його
першими літерами), по батькові — маску імені, а справжнє по батькові після
«Заява Прізвище Ім'я» лишалось відкритим.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking.context import (  # noqa: E402
    assign_pib_roles, has_full_pib, has_name_patronymic_pair, is_name_patronymic_pair,
    is_patronymic_word, looks_like_pib_line, parse_hybrid_line,
)
from datamasking.masking.declension import analyze_name, analyze_patronymic, VOCATIVE  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


class TestHelpers:
    def test_patronymic_word(self):
        assert is_patronymic_word("Петровичу") and is_patronymic_word("Сергіївну,") and is_patronymic_word("Ілліча")
        assert not is_patronymic_word("Петренко") and not is_patronymic_word("петровичу")
        # кличний — лише після відомого імені
        assert is_patronymic_word("Петрівно", "Тетяно") and is_patronymic_word("Івановичу", "Петре")
        assert not is_patronymic_word("Петрівно") and not is_patronymic_word("Рівно", "Згідно")
        assert not is_patronymic_word("Дивно", "Петренко")

    def test_pair(self):
        assert is_name_patronymic_pair("Олегу", "Петровичу!")
        assert is_name_patronymic_pair("Тетяно", "Петрівно")
        assert is_name_patronymic_pair("Олега", "Петровича")
        assert not is_name_patronymic_pair("Петренко", "Олег")
        assert not is_name_patronymic_pair("Петрович", "Іванович")
        assert not is_name_patronymic_pair("ЗСУ", "Петровичу")

    def test_line_signals(self):
        assert has_name_patronymic_pair("Шановний Олегу Петровичу!".split())
        assert not has_name_patronymic_pair("Згідно з рапортом Рівно Дивно".split())
        assert has_full_pib("ОЛЕГУ ПЕТРОВИЧУ ПЕТРЕНКУ".split())
        assert has_full_pib("Тетяні Петрівні Коваль".split())
        assert not has_full_pib("Згідно Рівно Дивно Петренко".split())
        assert looks_like_pib_line("Згідно Петро Іванович")
        assert looks_like_pib_line("ОЛЕГУ ПЕТРОВИЧУ ПЕТРЕНКУ")

    @pytest.mark.parametrize("parts,expected", [
        (["Петренко", "Олег", "Петрович"], ("Петренко", "Олег", "Петрович", ["surname", "name", "patronymic"])),
        (["Іван", "ПЕТРЕНКО"], ("ПЕТРЕНКО", "Іван", "", ["name", "surname", "patronymic"])),
        (["Коваль", "Тетяна"], ("Коваль", "Тетяна", "", ["surname", "name", "patronymic"])),
        (["Олегу", "Петровичу"], (None, "Олегу", "Петровичу", ["name", "patronymic"])),
        (["Тетяно", "Петрівно"], (None, "Тетяно", "Петрівно", ["name", "patronymic"])),
        (["Олегу", "Петровичу", "Петренку"], ("Петренку", "Олегу", "Петровичу", ["name", "patronymic", "surname"])),
        (["ОЛЕГУ", "ПЕТРОВИЧУ", "ПЕТРЕНКУ"], ("ПЕТРЕНКУ", "ОЛЕГУ", "ПЕТРОВИЧУ", ["name", "patronymic", "surname"])),
        # третє слово теж схоже на по батькові: прізвище — не відоме ім'я
        (["Олег", "Петрович", "Іванович"], ("Іванович", "Олег", "Петрович", ["name", "patronymic", "surname"])),
        (["Петренко", "Олег", "Петрович", "Іванович"], ("Петренко", "Олег", "Петрович", ["surname", "name", "patronymic"])),
    ])
    def test_roles(self, parts, expected):
        assert assign_pib_roles(parts) == expected

    def test_parse_window_shift(self):
        assert parse_hybrid_line("Заява Петренка Олега Петровича")[1] == "Петренка Олега Петровича"
        assert parse_hybrid_line("Характеристика Коваль Тетяни Сергіївни")[1] == "Коваль Тетяни Сергіївни"
        assert parse_hybrid_line("Витяг Петренко Олег Петрович")[1] == "Петренко Олег Петрович"
        # після звання вікно не зсувається
        assert parse_hybrid_line("капітан Петренко Олег Петрович")[:2] == ("капітан", "Петренко Олег Петрович")


class TestMasking:
    @pytest.mark.parametrize("text,kept", [
        ("Шановний Олегу Петровичу!", "Шановний "),
        ("Шановний Петре Івановичу!", "Шановний "),
        ("Шановна Тетяно Петрівно!", "Шановна "),
        ("Вельмишановний Іване Івановичу,", "Вельмишановний "),
        ("Пане Олегу Петровичу!", "Пане "),
        ("Олег Петрович повідомив про виконання.", " повідомив про виконання."),
        ("за підписом Олега Петровича", "за підписом "),
        ("Доповідь Тетяни Петрівни заслухано.", "Доповідь "),
        ("Згідно Петро Іванович", "Згідно "),
    ])
    def test_pair_without_surname(self, text, kept):
        masked, mapping = _rt(text)
        assert kept in masked, masked
        assert not mapping["mappings"]["surname"], mapping["mappings"]["surname"]
        assert len(mapping["mappings"]["name"]) == 1 and len(mapping["mappings"]["patronymic"]) == 1
        for w in ("Олег", "Петр", "Тетян", "Іван"):
            assert w not in masked, masked

    def test_pair_masks_keep_case_and_gender(self):
        masked, mapping = _rt("Шановна Тетяно Петрівно!")
        name_mask, pat_mask = masked.split()[1], masked.split()[2].rstrip("!")
        assert analyze_name(name_mask, "female").case == VOCATIVE, name_mask
        pf = analyze_patronymic(pat_mask)
        assert (pf.gender, pf.case) == ("female", VOCATIVE), pat_mask
        masked, mapping = _rt("Шановний Петре Івановичу!")
        assert analyze_name(masked.split()[1], "male").case == VOCATIVE, masked
        assert masked.split()[2].endswith("у!")

    @pytest.mark.parametrize("text", [
        "ОЛЕГУ ПЕТРОВИЧУ ПЕТРЕНКУ",
        "Олегу Петровичу Петренку",
        "полковнику Олегу Петровичу Петренку",
        "Тетяні Петрівні Коваль",
    ])
    def test_name_first_order(self, text):
        masked, mapping = _rt(text)
        for w in ("Олег", "ОЛЕГ", "Петрович", "ПЕТРОВИЧ", "Петренк", "ПЕТРЕНК", "Тетян", "Петрівн", "Коваль"):
            assert w not in masked, masked
        words = masked.split()
        surname_masks = {v["masked_as"] for v in mapping["mappings"]["surname"].values()}
        assert words[-1] in surname_masks, (masked, surname_masks)
        assert len(mapping["mappings"]["patronymic"]) == 1 and len(mapping["mappings"]["name"]) == 1
        assert masked.isupper() == text.isupper()

    @pytest.mark.parametrize("text,prefix", [
        ("Заява Петренка Олега Петровича", "Заява "),
        ("Рапорт Петренка Олега Петровича про відпустку", "Рапорт "),
        ("Характеристика Коваль Тетяни Сергіївни", "Характеристика "),
        ("Протокол Петренко Олег Петрович", "Протокол "),
        ("Витяг з наказу Петренко Олег Петрович", "Витяг з наказу "),
    ])
    def test_word_before_full_name(self, text, prefix):
        masked, mapping = _rt(text)
        assert masked.startswith(prefix), masked
        for w in ("Петренк", "Коваль", "Олег", "Тетян", "Петрович", "Сергіївн"):
            assert w not in masked, masked
        assert set(mapping["mappings"]["surname"]) and set(mapping["mappings"]["patronymic"])
        # вікно зсунулось: ніщо з документних слів не потрапило в mapping
        for cat in ("surname", "name", "patronymic"):
            for key in mapping["mappings"][cat]:
                assert key.lower() not in ("заява", "рапорт", "характеристика", "протокол", "витяг"), (cat, key)

    def test_abbreviation_before_full_name_without_exclusion(self):
        # «ДШВ» не в переліку, але повне ПІБ після нього все одно маскується цілком
        masked, mapping = _rt("Доповідаю: ДШВ Петренко Іван Іванович прибув.")
        assert masked.startswith("Доповідаю: ДШВ ") and "Іванович" not in masked and "Петренко" not in masked

    def test_ordinary_lines_unchanged(self):
        assert mask("Згідно з рапортом Рівно Дивно")[0] == "Згідно з рапортом Рівно Дивно"
        assert mask("Шановний пане Олегу!")[0] == "Шановний пане Олегу!"

    def test_standard_order_still_works(self):
        masked, mapping = _rt("рядовий Петренко Олег Петрович, Коваль Тетяна Сергіївна")
        assert set(mapping["mappings"]["surname"]) == {"Петренко", "Коваль"}
        assert set(mapping["mappings"]["name"]) == {"Олег", "Тетяна"}
        assert set(mapping["mappings"]["patronymic"]) == {"петрович", "сергіївна"}

    def test_pair_consistent_with_full_name(self):
        text = "капітан Петренко Олег Петрович доповів.\nШановний Олегу Петровичу!\nОлег Петрович вибув."
        masked, mapping = _rt(text)
        lines = masked.split("\n")
        nom_name, nom_pat = lines[0].split()[2], lines[0].split()[3]
        assert lines[2].startswith(f"{nom_name} {nom_pat} ")
        assert lines[1].startswith("Шановний ")
        # давальний імені та по батькові побудовано від тих самих називних
        dat_name, dat_pat = lines[1].split()[1], lines[1].split()[2].rstrip("!")
        assert dat_pat == nom_pat + "у"
        assert dat_name[:3] == nom_name[:3] and dat_name != nom_name
