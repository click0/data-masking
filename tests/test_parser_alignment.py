#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер рядків зі званням + ПІБ: вирівнювання слів і супутні витоки (v3.0.18).

Знайдено фазингом (випадкові рядки зі званнями, ПІБ, ініціалами, номерами,
датами → mask → unmask): до 3.0.18 на 3000 документах ~65% не відновлювались
дослівно і ~50% мали відкрите прізвище в масці. Причини:

  1. Позиція звання рахувалась за словами normalize_string(line), а ПІБ
     брався за словами line.split(); нормалізація розбиває «Г.Г.», «т.ч.»
     на кілька слів → після них індекс зсувався, і за звання бралось
     сусіднє слово («сержанта Мазуренка», «Коваля»). Те саме з номером на
     початку рядка («1 рядовий Іванов …» — прізвище випадало з ПІБ).
  2. Звання шукалось без межі слова («майора» всередині «генерал-майора»).
  3. Прізвище, вже замасковане фазою ініціалів («Коваль П.П.» → «Ковар
     К.К.»), маскувалось удруге, якщо після звання стояло лише воно.
  4. Перевірка «це вже маска» дивилась і на маски імен, які можуть
     збігтися зі справжнім ім'ям далі в рядку («Олега» → «Олег») → справжній
     ПІБ вважався замаскованим і лишався відкритим.
  5. Рядки, що починаються з «Відповідно / Згідно / На підставі», не
     маскувались узагалі, навіть зі званням і ПІБ.
"""
import random
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamasking.masking.context import parse_hybrid_line  # noqa: E402
from datamasking.rank_data import RANK_DECLENSIONS  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

_LETTER = "А-ЯІЇЄҐа-яіїєґ'’"


def _roundtrip(text: str):
    masked, md = mask(text)
    restored, _ = unmask_text_v2(masked, md, check_mapping_version(md))
    return masked, md, restored


def _leaks(masked: str, words) -> list:
    return [w for w in words
            if re.search(rf"(?<![{_LETTER}])({re.escape(w)}|{re.escape(w.upper())})(?![{_LETTER}])", masked)]


class TestParserAlignment:
    @pytest.mark.parametrize("line,rank,pib", [
        # ініціали перед званням зсували індекс
        ("Ґудзь П.П. та майора Коваля Івана Івановича", "майора", "Коваля Івана Івановича"),
        ("т.ч. капітан Петренко Олег Ігорович", "капітан", "Петренко Олег Ігорович"),
        # номер на початку рядка (без крапки) — прізвище випадало з ПІБ
        ("1 рядовий Іванов Іван Іванович", "рядовий", "Іванов Іван Іванович"),
        ("12 старший сержант Коваль Петро Петрович", "старший сержант", "Коваль Петро Петрович"),
        # звання — лише цілим словом
        ("рапорт генерал-майора Петренка Івана Івановича", "генерал-майора", "Петренка Івана Івановича"),
    ])
    def test_rank_and_pib_are_real_words(self, line, rank, pib):
        found_rank, found_pib, _ = parse_hybrid_line(line)
        assert (found_rank, found_pib) == (rank, pib)

    def test_initials_before_several_ranks(self):
        text = ("від 12.03.2024 сержант Ґудзь П.П. згідно з наказом №3898 молодшого сержанта "
                "Мазуренка Олега Олеговича та майора Коваля Івана Івановича довідках №2523 "
                "майора Шевчука Івана Івановича")
        masked, _, restored = _roundtrip(text)
        assert restored == text
        assert "___" not in masked
        assert not _leaks(masked, ["Ґудзь", "Мазуренка", "Коваля", "Шевчука"])


class TestNoDoubleMasking:
    @pytest.mark.parametrize("text", [
        "сержант Коваль П.П.",
        "рапорт сержант Коваль П.П.",
        "довідках №12 сержанта Ткача та сержант Коваль П.П.",
    ])
    def test_initials_surname_masked_once(self, text):
        masked, md, restored = _roundtrip(text)
        assert restored == text
        surnames = md["mappings"]["surname"]
        masks = {v["masked_as"] for v in surnames.values()}
        # жодна маска не є ключем (маска маски)
        assert not masks & set(surnames), surnames


class TestNameMaskCollision:
    def test_real_name_equal_to_other_mask_is_still_masked(self):
        text = ("щодо старший сержант Лисенко А.А. рапорт старшого сержанта Ткача Олега Олеговича "
                "згідно з наказом №1 старший сержант Ґудзь Олег Олегович")
        masked, _, restored = _roundtrip(text)
        assert restored == text
        assert not _leaks(masked, ["Лисенко", "Ткача", "Ґудзь"])


class TestOfficialOpeners:
    @pytest.mark.parametrize("text,surname", [
        ("Відповідно до рапорту старшого сержанта Мазуренка Івана Петровича", "Мазуренка"),
        ("На підставі наказу командира капітан Петренко Олег Ігорович прибув", "Петренко"),
        ("Згідно з наказом №4183 лейтенант Мазуренко Петро Петрович", "Мазуренко"),
    ])
    def test_rank_line_with_opener_is_masked(self, text, surname):
        masked, _, restored = _roundtrip(text)
        assert surname not in masked
        assert restored == text

    @pytest.mark.parametrize("text", [
        "Відповідно до Статуту внутрішньої служби Збройних Сил України",
        "Згідно з вимогами статуту рядовий склад зобов'язаний виконувати накази",
        "Згідно з наказом Міністерства оборони України солдат має право на відпустку",
        "Згідно з Положенням про проходження громадянами України військової служби майор",
    ])
    def test_official_text_without_pib_untouched(self, text):
        assert mask(text)[0] == text


# ---------------------------------------------------------------------------
# Property-тест: детермінований генератор рядків (як у фазингу, що знайшов
# баги вище). 200 документів — ~1 c; повний прогін на 10 000 — 0 збоїв.
# ---------------------------------------------------------------------------
_SURN = {
    "Мазуренко": "Мазуренка", "Коваленко": "Коваленка", "Петренко": "Петренка",
    "Іванов": "Іванова", "Коваль": "Коваля", "Ткач": "Ткача", "Ґудзь": "Ґудзя",
    "Бондаренко": "Бондаренка", "Кравчук": "Кравчука", "Мельник": "Мельника",
    "Шевчук": "Шевчука", "Сидоренко": "Сидоренка", "Олійник": "Олійника",
}
_NAMES = [("Іван", "Івана", "Іванович", "Івановича"), ("Петро", "Петра", "Петрович", "Петровича"),
          ("Олег", "Олега", "Олегович", "Олеговича"), ("Андрій", "Андрія", "Андрійович", "Андрійовича")]
_RANKS = ["рядовий", "солдат", "старший солдат", "молодший сержант", "сержант",
          "старший сержант", "лейтенант", "старший лейтенант", "капітан", "майор"]
_FILL = ["довідках №%d", "рапорт", "та", "щодо", "згідно з наказом №%d", "і", ",",
         "від 12.03.2024", "у в/ч А%04d"]


def _item(rnd):
    r, (s, s_gen), n = rnd.choice(_RANKS), rnd.choice(list(_SURN.items())), rnd.choice(_NAMES)
    up = rnd.random() < .3
    k = rnd.randrange(4)
    if k == 0:
        return f"{RANK_DECLENSIONS[r]['genitive']} {s_gen.upper() if up else s_gen}"
    if k == 1:
        return f"{r} {s.upper() if up else s} {n[0]} {n[2]}"
    if k == 2:
        return f"{RANK_DECLENSIONS[r]['genitive']} {s_gen} {n[1]} {n[3]}"
    return f"{r} {s} {n[0][0]}.{n[2][0]}."


def _line(rnd):
    parts = []
    for _ in range(rnd.randint(1, 4)):
        f = rnd.choice(_FILL)
        parts.append(f % rnd.randint(1, 9999) if "%" in f else f)
        parts.append(_item(rnd))
    return " ".join(parts)


@pytest.mark.parametrize("seed_block", range(4))
def test_random_documents_roundtrip_without_leaks(seed_block):
    all_forms = list(_SURN) + list(_SURN.values())
    for i in range(seed_block * 50, seed_block * 50 + 50):
        rnd = random.Random(i)
        text = "\n".join(_line(rnd) for _ in range(rnd.randint(1, 3)))
        masked, _, restored = _roundtrip(text)
        assert restored == text, f"seed {i}:\n{text}\n{masked}\n{restored}"
        assert not _leaks(masked, all_forms), f"seed {i}:\n{text}\n{masked}"
        assert "___" not in masked, f"seed {i}: {masked}"
