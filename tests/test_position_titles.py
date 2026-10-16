#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.17–3.1.18 — назви посад і підрозділів капсом брались за ПІБ: «на посаду
МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ» →
«на посаду МАСАҐАНИКОМ ІГОР ОРЕСТОВИЧ …». Правила: три і більше слів капсом
поспіль без по батькові й без звання — не ПІБ (блок рахується в обидва боки);
закінчення слів мають відповідати ролям (ім'я не на -ого/-ому, на -их/-ів —
лише відоме; прізвище на -ом лише з іменем в орудному; -ння/-ття/-ість — не
імена); два слова капсом без звання — ПІБ лише з відомим іменем; рядок
капсом із відомим іменем — не заголовок.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking.context import (  # noqa: E402
    looks_like_pib_line, parse_hybrid_line, roles_plausible,
)
from datamasking.masking.language import looks_like_name  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

COUNTER_EXAMPLE = ("на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ\n"
                   "ІНЖЕНЕРНО-МАСКУВАЛЬНОЇ РОТИ ВІЙСЬКОВОЇ ЧАСТИНИ А1234")

# Назви посад і підрозділів капсом — так їх пишуть у наказах по особовому складу
TITLES_CAPS = [
    "на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ",
    "на посаду КОМАНДИРА ВІДДІЛЕННЯ ІНЖЕНЕРНО-САПЕРНОГО ВЗВОДУ",
    "призначити на посаду ЗАСТУПНИКА КОМАНДИРА БАТАЛЬЙОНУ З ОЗБРОЄННЯ",
    "СТРІЛЬЦЕМ-САНІТАРОМ МЕХАНІЗОВАНОГО ВІДДІЛЕННЯ",
    "на посаду ВОДІЯ АВТОМОБІЛЬНОГО ВІДДІЛЕННЯ РОТИ МАТЕРІАЛЬНОГО ЗАБЕЗПЕЧЕННЯ",
    "призначити НАЧАЛЬНИКОМ ІНЖЕНЕРНОЇ СЛУЖБИ",
    "на посаду ОПЕРАТОРА ВІДДІЛЕННЯ БЕЗПІЛОТНИХ АВІАЦІЙНИХ КОМПЛЕКСІВ",
    "звільнити з посади КОМАНДИРА МЕХАНІЗОВАНОГО ВЗВОДУ МЕХАНІЗОВАНОЇ РОТИ",
    "на посаду РАДІОТЕЛЕФОНІСТА ВЗВОДУ ЗВ'ЯЗКУ",
    "на посаду ГРАНАТОМЕТНИКА МЕХАНІЗОВАНОГО ВІДДІЛЕННЯ",
    "з посади СТАРШОГО ОПЕРАТОРА РОЗРАХУНКУ",
    "на посаду ПОМІЧНИКА ГРАНАТОМЕТНИКА",
    "на посаду СТАРШОГО ІНСПЕКТОРА ГРУПИ",
    "на посаду НАЧАЛЬНИКОМ ШТАБУ",
    "НАЧАЛЬНИКОМ ШТАБУ ВІЙСЬКОВОЇ ЧАСТИНИ",
    "на посаду механіка-водія ТАНКОВОГО ВЗВОДУ ТАНКОВОЇ РОТИ",
    "на посаду КУЛЕМЕТНИКА МЕХАНІЗОВАНОГО ВІДДІЛЕННЯ МЕХАНІЗОВАНОГО ВЗВОДУ",
    "на посаду САНІТАРНОГО ІНСТРУКТОРА РОТИ",
    "на посаду ТЕХНІКА РОТИ ЗАБЕЗПЕЧЕННЯ",
    "ТИМЧАСОВО ВИКОНУЮЧИМ ОБОВ'ЯЗКИ НАЧАЛЬНИКА СЛУЖБИ",
    "на посаду НАВІДНИКА",
    "перемістити на посаду ГОЛОВНОГО СЕРЖАНТА РОТИ ВОГНЕВОЇ ПІДТРИМКИ",
]

TITLES_TITLE_CASE = [
    "на посаду Маскувальником Імітаційного Відділення",
    "на посаду Оператора Відділення Безпілотних Авіаційних Комплексів",
    "на посаду Старшого Техніка Роти",
    "про Призначення Відділення",
    "Стрільцем Механізованого Відділення",
]

HEADINGS = [
    "НАКАЗ КОМАНДИРА ВІЙСЬКОВОЇ ЧАСТИНИ (по стройовій частині)",
    "ПРО ЗАРАХУВАННЯ ДО СПИСКІВ ОСОБОВОГО СКЛАДУ",
    "ВИКЛЮЧИТИ ЗІ СПИСКІВ ОСОБОВОГО СКЛАДУ ЧАСТИНИ",
    "МІНІСТЕРСТВО ОБОРОНИ УКРАЇНИ",
    "ПРО ЗАТВЕРДЖЕННЯ ПОЛОЖЕННЯ ПРО ПРОХОДЖЕННЯ СЛУЖБИ",
    "нагородити відзнакою ЗА ВІЙСЬКОВУ ДОБЛЕСТЬ",
    "медаллю ЗАХИСНИКУ ВІТЧИЗНИ",
    "ВІРА НАДІЯ ЛЮБОВ",
    "РОЗШИРЕНИЙ ТЕСТ МАСКУВАННЯ ПІБ",
]

# Справжні ПІБ капсом у типових для документів конструкціях
NAMES_CAPS = [
    "ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ",
    "ОЛЕГУ ПЕТРОВИЧУ ПЕТРЕНКУ",
    "ПІДПИС КОВАЛЬ ТЕТЯНА СЕРГІЇВНА",
    "Підпис: КОВАЛЬ ТЕТЯНА СЕРГІЇВНА, 01.02.2025",
    "КОВАЛЬ ТЕТЯНА",
    "ІВАНОВ ІВАН ІВАНОВИЧ",
    "НЕЧУЙ-ЛЕВИЦЬКИЙ ІВАН СЕМЕНОВИЧ",
    "ПІБ: ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ",
    "СОЛДАТ ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ",
    "СТАРШОМУ СЕРЖАНТУ КОВАЛЬ ТЕТЯНІ СЕРГІЇВНІ",
    "сержанта КОВАЛЬ ТЕТЯНИ, солдата ПЕТРЕНКА ОЛЕГА",
    "рядовий ПЕТРЕНКО",
    "рядового ПЕТРЕНКА АЙДЕРА",
    "ШАНОВНИЙ ОЛЕГУ ПЕТРОВИЧУ!",
    "ЗАЯВА ПЕТРЕНКА ОЛЕГА ПЕТРОВИЧА",
    "наказ по особовому складу: КОВАЛЬ ТЕТЯНА СЕРГІЇВНА, ІВАНОВ ПЕТРО СИДОРОВИЧ",
    "«ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ»",
    "ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ, 15.07.1987 р.н.",
    "| 1 | солдат | ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ | 1234567890 |",
    "| КОВАЛЬ ТЕТЯНА | 1234567890 |",
    "ПЕТРЕНКО\tОЛЕГ\tПЕТРОВИЧ",
    "ПЕТРЕНКО О.П.",
    "О.П. ПЕТРЕНКО",
    "КОВАЛЬ ТЕТЯНА — ІВАНОВ ПЕТРО",
    "ПЕТРЕНКО ЗИНОВІЙ",
    "КОВАЛЬ ЯКІВ",
    "ПЕТРЕНКО Олег Петрович та КОВАЛЬ Тетяна Сергіївна",
    "Іван ПЕТРЕНКО",
    "рядового МАЗУРЕНКА та солдата КОВАЛЕНКА",
    "на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ солдата ПЕТРЕНКА ОЛЕГА ПЕТРОВИЧА, ІПН 1234567890",
    "призначити СТРІЛЬЦЕМ МЕХАНІЗОВАНОГО ВІДДІЛЕННЯ рядового КОВАЛЬ ТЕТЯНУ СЕРГІЇВНУ",
    "НАГОРОДИТИ ГРАМОТОЮ ПЕТРЕНКА ОЛЕГА ПЕТРОВИЧА",
]

ORIGINALS = ("ПЕТРЕНК", "Петренк", "ОЛЕГ", "Олег", "КОВАЛЬ", "Коваль", "ТЕТЯН", "Тетян", "ІВАНОВ ", "ІВАН ",
             "НЕЧУЙ", "СЕМЕНОВИЧ", "СЕРГІЇВН", "Сергіївн", "ПЕТРОВИЧ", "Петрович", "МАЗУРЕНК", "КОВАЛЕНК",
             "ЗИНОВІЙ", "ЯКІВ", "АЙДЕР", "СИДОРОВИЧ", "ПЕТРО ")


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


def _people(mapping):
    return {cat: set(mapping["mappings"].get(cat, {})) for cat in ("surname", "name", "patronymic")
            if mapping["mappings"].get(cat)}


def _without_ids(text):
    """Прибирає те, що маскується законно й без ПІБ (номери в/ч, дати, ІПН)."""
    return re.sub(r"\b[АA]\d{4}\b|\b\d{2}\.\d{2}\.\d{4}\b|\b\d{10}\b", "#", text)


class TestCounterExample:
    def test_counter_example_is_not_a_name(self):
        masked, mapping = _rt(COUNTER_EXAMPLE)
        assert _without_ids(masked) == _without_ids(COUNTER_EXAMPLE), masked
        assert not _people(mapping), _people(mapping)
        assert set(mapping["mappings"]["military_unit"]) == {"А1234"}

    def test_title_and_real_name_on_one_line(self):
        text = "Призначити на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ солдата ПЕТРЕНКА ОЛЕГА ПЕТРОВИЧА"
        masked, mapping = _rt(text)
        assert masked.startswith("Призначити на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ")
        assert "ПЕТРЕНК" not in masked and "ОЛЕГА" not in masked and "ПЕТРОВИЧА" not in masked
        assert _people(mapping) == {"surname": {"ПЕТРЕНКА"}, "name": {"ОЛЕГА"}, "patronymic": {"петровича"}}

    def test_whole_order(self):
        text = "\n".join([
            "НАКАЗ",
            "командира військової частини А1234",
            "ПО ОСОБОВОМУ СКЛАДУ",
            "1. Призначити на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ",
            "ІНЖЕНЕРНО-МАСКУВАЛЬНОЇ РОТИ солдата ПЕТРЕНКА ОЛЕГА ПЕТРОВИЧА, ІПН 1234567890.",
            "2. Звільнити з посади СТАРШОГО ОПЕРАТОРА РОЗРАХУНКУ сержанта КОВАЛЬ ТЕТЯНУ СЕРГІЇВНУ.",
            "3. Перемістити на посаду ГОЛОВНОГО СЕРЖАНТА РОТИ ВОГНЕВОЇ ПІДТРИМКИ",
            "старшого сержанта ІВАНОВА ПЕТРА СИДОРОВИЧА.",
            "Командир військової частини А1234",
            "полковник                                   О.П. ГРИЦЕНКО",
        ])
        masked, mapping = _rt(text)
        lines = masked.split("\n")
        assert lines[0] == "НАКАЗ" and lines[2] == "ПО ОСОБОВОМУ СКЛАДУ"
        assert lines[3].startswith("1. Призначити на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ")
        assert lines[4].startswith("ІНЖЕНЕРНО-МАСКУВАЛЬНОЇ РОТИ ")
        assert lines[5].startswith("2. Звільнити з посади СТАРШОГО ОПЕРАТОРА РОЗРАХУНКУ ")
        assert lines[6] == "3. Перемістити на посаду ГОЛОВНОГО СЕРЖАНТА РОТИ ВОГНЕВОЇ ПІДТРИМКИ"
        assert _people(mapping)["surname"] == {"ПЕТРЕНКА", "КОВАЛЬ", "ІВАНОВА", "ГРИЦЕНКО"}
        assert _people(mapping)["name"] == {"ОЛЕГА", "ТЕТЯНУ", "ПЕТРА"}
        assert _people(mapping)["patronymic"] == {"петровича", "сергіївну", "сидоровича"}
        for w in ("ПЕТРЕНК", "КОВАЛЬ", "ІВАНОВ", "ГРИЦЕНК", "ОЛЕГ", "ТЕТЯН", "ПЕТРА", "1234567890"):
            assert w not in masked, (w, masked)


class TestTitlesUntouched:
    @pytest.mark.parametrize("text", TITLES_CAPS)
    def test_caps_title(self, text):
        masked, mapping = _rt(text)
        assert masked == text, masked
        assert not _people(mapping), _people(mapping)

    @pytest.mark.parametrize("text", TITLES_TITLE_CASE)
    def test_title_case_title(self, text):
        masked, mapping = _rt(text)
        assert masked == text, masked
        assert not _people(mapping), _people(mapping)

    @pytest.mark.parametrize("text", HEADINGS)
    def test_heading(self, text):
        masked, mapping = _rt(text)
        assert _without_ids(masked) == _without_ids(text), masked
        assert not _people(mapping), _people(mapping)

    def test_two_titles_in_one_sentence(self):
        text = ("звільнити з посади СТРІЛЬЦЯ МЕХАНІЗОВАНОГО ВІДДІЛЕННЯ та призначити на посаду "
                "КУЛЕМЕТНИКА МЕХАНІЗОВАНОГО ВІДДІЛЕННЯ")
        masked, mapping = _rt(text)
        assert masked == text and not _people(mapping)

    def test_adjective_before_name_is_dropped(self):
        masked, mapping = _rt("Старшого Петро Іванович прибув")
        assert masked.startswith("Старшого ") and "Петро" not in masked and "Іванович" not in masked
        assert "surname" not in _people(mapping)
        masked, mapping = _rt("Начальником Петро Іванович")
        assert masked.startswith("Начальником ") and "surname" not in _people(mapping)


class TestRealNamesStillMasked:
    @pytest.mark.parametrize("text", NAMES_CAPS)
    def test_masked(self, text):
        masked, mapping = _rt(text)
        for w in ORIGINALS:
            assert w not in masked, (w, masked)
        # звертання («ШАНОВНИЙ ОЛЕГУ ПЕТРОВИЧУ!») має лише ім'я з по батькові
        assert mapping["mappings"]["surname"] or mapping["mappings"]["name"], masked

    def test_caps_two_words_need_known_first_name(self):
        # компроміс правила для двох слів капсом без звання: рідкісне ім'я
        # капсом не маскується, у звичайному регістрі чи зі званням — маскується
        assert mask("ПЕТРЕНКО АЙДЕР")[0] == "ПЕТРЕНКО АЙДЕР"
        masked, _ = _rt("Петренко Айдер")
        assert "Петренко" not in masked and "Айдер" not in masked
        masked, _ = _rt("рядового ПЕТРЕНКА АЙДЕРА")
        assert "ПЕТРЕНК" not in masked and "АЙДЕР" not in masked

    def test_name_first_after_caps_words_known_limitation(self):
        # Слово капсом перед порядком «Ім'я По батькові Прізвище» не відрізнити
        # від прізвища: ім'я й по батькові маскуються, прізвище після них — ні
        masked, mapping = _rt("ВРУЧИТИ ГРАМОТУ ОЛЕГУ ПЕТРОВИЧУ ПЕТРЕНКУ")
        assert "ОЛЕГУ" not in masked and "ПЕТРОВИЧУ" not in masked
        assert _people(mapping)["name"] == {"ОЛЕГУ"} and _people(mapping)["patronymic"] == {"петровичу"}

    def test_caps_list_line_is_not_a_heading(self):
        masked, mapping = _rt("КОВАЛЬ ТЕТЯНА — ІВАНОВ ПЕТРО")
        assert _people(mapping) == {"surname": {"КОВАЛЬ", "ІВАНОВ"}, "name": {"ТЕТЯНА", "ПЕТРО"}}
        assert " — " in masked

    @pytest.mark.parametrize("text", [
        "Ковальського Олега Петровича призначити",
        "Петренком Олегом Петровичем підписано",
        "Положення Петренко Олег Петрович",
        "Відповідальність Коваль Тетяни Сергіївни",
        "Коваль Тетяна",
        "Кіт Олег",
    ])
    def test_title_case_names_masked(self, text):
        masked, mapping = _rt(text)
        for w in ("Петренк", "Коваль", "Кіт ", "Олег", "Тетян", "Ковальськ"):
            assert w not in masked, (w, masked)
        assert mapping["mappings"]["surname"], masked


class TestHelpers:
    def test_looks_like_name_rejects_abstract_nouns(self):
        for w in ("Відділення", "Призначення", "Відповідальність", "Життя", "ВІДДІЛЕННЯ", "ЗАБЕЗПЕЧЕННЯ"):
            assert not looks_like_name(w), w
        for w in ("Петренко", "Ілля", "Коломієць", "Ткач", "Яків"):
            assert looks_like_name(w), w

    @pytest.mark.parametrize("words,after_rank,ok", [
        (["МАСКУВАЛЬНИКОМ", "ІМІТАЦІЙНОГО"], False, False),
        (["Начальником", "Петро"], False, False),
        (["Старшого", "Петро", "Іванович"], False, False),
        (["Ковальського", "Олег", "Петрович"], False, False),
        (["Безпілотних", "Авіаційних", "Комплексів"], False, False),
        (["Авіаційних", "Комплексів"], False, False),
        (["ПОМІЧНИКА", "ГРАНАТОМЕТНИКА"], False, False),
        (["ЗАХИСНИКУ", "ВІТЧИЗНИ"], False, False),
        (["ПЕТРЕНКА", "АЙДЕРА"], False, False),
        (["ПЕТРЕНКА", "АЙДЕРА"], True, True),
        (["Петренко", "Айдер"], False, True),
        (["КОВАЛЬ", "ТЕТЯНА"], False, True),
        (["КОВАЛЬ", "ЯКІВ"], False, True),
        (["Коваль", "Яків"], False, True),
        (["Ковальського", "Олега", "Петровича"], False, True),
        (["Петренком", "Олегом", "Петровичем"], False, True),
        (["Петренко", "Олег", "Петрович"], False, True),
        (["Коваль", "Тетяна"], False, True),
        (["Шолом", "Олег", "Петрович"], False, True),
        (["Іванов"], False, True),
        (["ОЛЕГУ", "ПЕТРОВИЧУ"], False, True),
    ])
    def test_roles_plausible(self, words, after_rank, ok):
        assert roles_plausible(words, after_rank) is ok

    def test_parse_skips_caps_blocks(self):
        assert parse_hybrid_line("на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ВЗВОДУ")[1] is None
        assert parse_hybrid_line("з посади СТАРШОГО ОПЕРАТОРА РОЗРАХУНКУ")[1] is None
        assert parse_hybrid_line("ПІДПИС КОВАЛЬ ТЕТЯНА СЕРГІЇВНА")[1] == "КОВАЛЬ ТЕТЯНА СЕРГІЇВНА"
        assert parse_hybrid_line("солдата МАСКУВАЛЬНИКА ПЕТРА ІВАНОВИЧА")[1] == "МАСКУВАЛЬНИКА ПЕТРА ІВАНОВИЧА"
        assert parse_hybrid_line("КОВАЛЬ ТЕТЯНА — ІВАНОВ ПЕТРО")[1] == "КОВАЛЬ ТЕТЯНА"

    def test_caps_line_heading_rule(self):
        assert not looks_like_pib_line("НАКАЗ КОМАНДИРА ВІЙСЬКОВОЇ ЧАСТИНИ")
        assert not looks_like_pib_line("МІНІСТЕРСТВО ОБОРОНИ УКРАЇНИ")
        assert looks_like_pib_line("КОВАЛЬ ТЕТЯНА — ІВАНОВ ПЕТРО")
        assert looks_like_pib_line("ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ")
