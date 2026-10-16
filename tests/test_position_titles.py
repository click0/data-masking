#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.17 — назва посади чи підрозділу капсом бралась за ПІБ: «на посаду
МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ» →
«на посаду МАСАҐАНИКОМ ІГОР ОРЕСТОВИЧ …». Два правила: три і більше слів
капсом без по батькові й без звання — не ПІБ; закінчення слів мають
відповідати ролям (ім'я не на -ого/-ому, прізвище на -ом лише з іменем в
орудному, -ння/-ття/-ість — не імена).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking.context import parse_hybrid_line, roles_plausible  # noqa: E402
from datamasking.masking.language import looks_like_name  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

TITLE = ("на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ\n"
         "ІНЖЕНЕРНО-МАСКУВАЛЬНОЇ РОТИ ВІЙСЬКОВОЇ ЧАСТИНИ А1234")


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


def _people(mapping):
    return {cat: set(mapping["mappings"].get(cat, {})) for cat in ("surname", "name", "patronymic")}


class TestPositionTitles:
    def test_counter_example_is_not_a_name(self):
        masked, mapping = _rt(TITLE)
        assert masked.startswith(TITLE[:-5]), masked  # усе, крім номера в/ч, без змін
        assert not any(_people(mapping).values()), _people(mapping)
        assert set(mapping["mappings"]["military_unit"]) == {"А1234"}

    def test_title_and_real_name_on_one_line(self):
        text = "Призначити на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ солдата ПЕТРЕНКА ОЛЕГА ПЕТРОВИЧА"
        masked, mapping = _rt(text)
        assert masked.startswith("Призначити на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ")
        assert "ПЕТРЕНК" not in masked and "ОЛЕГА" not in masked and "ПЕТРОВИЧА" not in masked
        assert _people(mapping) == {"surname": {"ПЕТРЕНКА"}, "name": {"ОЛЕГА"}, "patronymic": {"петровича"}}

    @pytest.mark.parametrize("text", [
        "на посаду Маскувальником Імітаційного Відділення",
        "на посаду НАЧАЛЬНИКОМ ШТАБУ",
        "НАЧАЛЬНИКОМ ШТАБУ ВІЙСЬКОВОЇ ЧАСТИНИ",
        "про Призначення Відділення",
    ])
    def test_titles_untouched(self, text):
        masked, mapping = _rt(text)
        assert masked == text
        assert not any(_people(mapping).values())

    def test_adjective_before_name_is_dropped(self):
        masked, mapping = _rt("Старшого Петро Іванович прибув")
        assert masked.startswith("Старшого ") and "Петро" not in masked and "Іванович" not in masked
        assert not mapping["mappings"]["surname"]
        masked, mapping = _rt("Начальником Петро Іванович")
        assert masked.startswith("Начальником ") and not mapping["mappings"]["surname"]


class TestRealNamesStillMasked:
    @pytest.mark.parametrize("text,kept", [
        ("ПЕТРЕНКО ОЛЕГ ПЕТРОВИЧ", ""),
        ("ОЛЕГУ ПЕТРОВИЧУ ПЕТРЕНКУ", ""),
        ("ПІДПИС КОВАЛЬ ТЕТЯНА СЕРГІЇВНА", "ПІДПИС "),
        ("КОВАЛЬ ТЕТЯНА", ""),
        ("ІВАНОВ ІВАН ІВАНОВИЧ", ""),
        ("Іван ПЕТРЕНКО", ""),
        ("рядового МАЗУРЕНКА та солдата КОВАЛЕНКА", ""),
        ("Ковальського Олега Петровича призначити", ""),
        ("Петренком Олегом Петровичем підписано", ""),
        ("Положення Петренко Олег Петрович", "Положення "),
        ("Відповідальність Коваль Тетяни Сергіївни", "Відповідальність "),
    ])
    def test_masked(self, text, kept):
        masked, mapping = _rt(text)
        assert masked.startswith(kept)
        for w in ("ПЕТРЕНК", "Петренк", "ОЛЕГ", "Олег", "КОВАЛЬ", "Коваль", "ТЕТЯН", "Тетян", "ІВАНОВ ", "ІВАН ",
                  "МАЗУРЕНК", "КОВАЛЕНК", "Ковальськ", "Іван "):
            assert w not in masked, (w, masked)
        assert mapping["mappings"]["surname"], masked


class TestHelpers:
    def test_looks_like_name_rejects_abstract_nouns(self):
        for w in ("Відділення", "Призначення", "Відповідальність", "Життя", "ВІДДІЛЕННЯ"):
            assert not looks_like_name(w), w
        for w in ("Петренко", "Ілля", "Коломієць", "Ткач"):
            assert looks_like_name(w), w

    def test_roles_plausible(self):
        assert not roles_plausible(["МАСКУВАЛЬНИКОМ", "ІМІТАЦІЙНОГО"])
        assert not roles_plausible(["Начальником", "Петро"])
        assert not roles_plausible(["Старшого", "Петро", "Іванович"])
        assert not roles_plausible(["Ковальського", "Олег", "Петрович"])
        assert roles_plausible(["Ковальського", "Олега", "Петровича"])
        assert roles_plausible(["Петренком", "Олегом", "Петровичем"])
        assert roles_plausible(["Петренко", "Олег", "Петрович"])
        assert roles_plausible(["Коваль", "Тетяна"])
        assert roles_plausible(["Шолом", "Олег", "Петрович"])  # коротке прізвище на -ом — не орудний
        assert roles_plausible(["Іванов"])

    def test_parse_skips_caps_block(self):
        assert parse_hybrid_line("на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ВЗВОДУ")[1] is None
        assert parse_hybrid_line("ПІДПИС КОВАЛЬ ТЕТЯНА СЕРГІЇВНА")[1] == "КОВАЛЬ ТЕТЯНА СЕРГІЇВНА"
        assert parse_hybrid_line("солдата МАСКУВАЛЬНИКА ПЕТРА ІВАНОВИЧА")[1] == "МАСКУВАЛЬНИКА ПЕТРА ІВАНОВИЧА"
