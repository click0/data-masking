#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Витоки розпізнавання ПІБ/дат (аудит 3.0.0, пункт 4) — v3.0.3.

Кожен кейс тут до 3.0.3 лишав персональні дані відкритими або ламав
roundtrip.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_initials import mask  # noqa: E402
from datamasking.masking.language import detect_gender_by_patronymic, looks_like_name  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402


def roundtrip(text):
    m, md = mask(text)
    r, _ = unmask_text_v2(m, md, check_mapping_version(md))
    return m, md, r


class TestHyphenatedSurname:
    def test_masked_and_restored(self):
        t = "сержант Петренко-Іванова Марія Олегівна прибула"
        m, md, r = roundtrip(t)
        assert "Петренко" not in m and "Іванова" not in m and "Марія" not in m
        assert r == t

    def test_structure_kept(self):
        _, md, _ = roundtrip("капітан Нечуй-Левицький Іван Петрович")
        masked = md["mappings"]["surname"]["Нечуй-Левицький"]["masked_as"]
        assert masked.count("-") == 1
        a, b = masked.split("-")
        assert a[0].isupper() and b[0].isupper()
        assert "нечуй" not in masked.lower() and "левицьк" not in masked.lower()

    def test_looks_like_name(self):
        assert looks_like_name("Петренко-Іванова")
        assert looks_like_name("Нечуй-Левицький")
        assert not looks_like_name("Петренко-наказу")  # друга частина — службове слово


class TestInitialsThenFullPib:
    def test_full_pib_after_initials_is_masked(self):
        t = "Іванов П.А. підписав. Іванов Петро Андрійович присутній."
        m, md, r = roundtrip(t)
        assert "Іванов" not in m and "Петро" not in m and "Андрійович" not in m
        assert r == t

    def test_reverse_order_still_works(self):
        t = "Іванов Петро Андрійович присутній. Іванов П.А. підписав."
        m, md, r = roundtrip(t)
        assert "Іванов" not in m
        assert r == t

    def test_second_person_on_same_line(self):
        t = "Сидоренко О.В. та Коваленко Ігор Іванович погодили."
        m, md, r = roundtrip(t)
        assert "Сидоренко" not in m and "Коваленко" not in m
        assert r == t


class TestRankPlusSurnameOnly:
    @pytest.mark.parametrize("t", [
        "рядовий Іванов прибув у розташування",
        "капітан Петренко доповів",
        "Наказ підполковнику Сидоренку оголосити",
    ])
    def test_surname_after_rank_masked(self, t):
        m, md, r = roundtrip(t)
        for w in ("Іванов", "Петренко", "Сидоренку"):
            assert w not in m
        assert r == t

    def test_no_false_positive_without_rank(self):
        # Без звання одне слово з великої — не ПІБ (не змінюємо поведінку)
        t = "Командир Петренко доповів"
        m, _, _ = roundtrip(t)
        assert m == t


class TestSurnameEqualsRankWord:
    def test_rank_like_surname_masked(self):
        t = "капітан Майор Іван Іванович та майор Капітан Петро Петрович"
        m, md, r = roundtrip(t)
        assert "Майор Іван" not in m and "Капітан Петро" not in m
        assert "Іван Іванович" not in m and "Петро Петрович" not in m
        assert r == t

    def test_plain_rank_still_masked_as_rank(self):
        m, md, _ = roundtrip("капітан Петренко Іван Сергійович")
        assert "капітан" in md["mappings"]["rank"]


class TestQuotedTextDates:
    @pytest.mark.parametrize("t", [
        '«31» грудня 2025 року',
        '"31" грудня 2025 року',
        'від «31» грудня 2025 року №5',
        '« 06 » жовтня 2025 року',
        '«31» грудня 2025 року та «31» грудня 2025 року',
        '31 грудня 2025 року',
    ])
    def test_roundtrip(self, t):
        m, md, r = roundtrip(t)
        assert "грудня 2025" not in m and "жовтня 2025" not in m
        assert r == t, f"{t!r} -> {m!r} <- {r!r}"

    def test_quotes_kept_in_masked_text(self):
        m, _, _ = roundtrip('«31» грудня 2025 року')
        assert m.startswith("«") and "»" in m


class TestPatronymicGender:
    @pytest.mark.parametrize("p,g", [
        ("Їжакевич", "male"), ("Ілліч", "male"), ("Кузьмич", "male"), ("Лукич", "male"),
        ("Гуревича", "male"), ("Петрович", "male"), ("Олегівна", "female"), ("Іллівна", "female"),
    ])
    def test_detect(self, p, g):
        assert detect_gender_by_patronymic(p) == g

    def test_masked_patronymic_keeps_gender(self):
        _, md, _ = roundtrip("полковник Гудзь Євген Їжакевич")
        masked = md["mappings"]["patronymic"]["їжакевич"]["masked_as"]
        assert masked.lower().endswith("ич"), masked


class TestUppercasePib:
    def test_surname_first_when_all_caps(self):
        t = "ЛЕЙТЕНАНТ ІВАНОВ ПЕТРО МИКОЛАЙОВИЧ"
        m, md, r = roundtrip(t)
        assert "ІВАНОВ" in md["mappings"]["surname"]
        assert "ПЕТРО" in md["mappings"]["name"]
        assert m.isupper()
        assert r == t

    def test_mixed_case_emphasised_surname_still_name_first(self):
        _, md, _ = roundtrip("капітан Іван ПЕТРЕНКО Сергійович")
        assert "ПЕТРЕНКО" in md["mappings"]["surname"]
        assert "Іван" in md["mappings"]["name"]


class TestNameNeverMapsToItself:
    """Марія/Юлія/Катерина/Тетяна/Ірина — єдині кандидатки на свою літеру в
    білому списку — до 3.0.3 мапились самі на себе (витік імені)."""

    @pytest.mark.parametrize("name", [
        "Марія", "Юлія", "Катерина", "Тетяна", "Ірина", "Оксана", "Анна",
        "Іван", "Петро", "Максим", "Юрій", "Тарас", "Ярослав",
    ])
    def test_nominative(self, name):
        _, md, _ = roundtrip(f"капітан Коваленко {name} Петрович" if name in
                             ("Іван", "Петро", "Максим", "Юрій", "Тарас", "Ярослав")
                             else f"сержант Коваленко {name} Петрівна")
        masked = md["mappings"]["name"][name]["masked_as"]
        assert masked.lower() != name.lower(), f"{name} mapped to itself"

    @pytest.mark.parametrize("t", [
        "сержанту Коваленко Марії Іванівні",
        "з сержантом Коваленко Марією Іванівною",
        "сержанта Коваленко Марії Іванівни",
    ])
    def test_oblique_cases_roundtrip(self, t):
        m, md, r = roundtrip(t)
        assert "Марі" not in m
        assert r == t


class TestNoNewFalsePositives:
    @pytest.mark.parametrize("t", [
        "Повідомляємо Вам, що відповідно до пункту 15 розділу XII Інструкції",
        "Наказ Міністерства оборони України від 01.01.2025",
        "Просимо Вас надати необхідні документи до кінця тижня",
        "Головне управління розвідки повідомляє",
    ])
    def test_official_text_untouched(self, t):
        m, _, _ = roundtrip(t.replace("01.01.2025", "01.01.2025"))
        # дата може змінитись — порівнюємо без неї
        assert m.split(" від ")[0] == t.split(" від ")[0]
