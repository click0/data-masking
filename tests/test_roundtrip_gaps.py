#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.9 — розмаскування повертало не оригінал (аудит, частина 3):

  - маска збігалась зі словом/числом документа, яке не маскується (звання
    без ПІБ, число, дата закону, ім'я окремо) — unmask міняв їх місцями;
  - одне ім'я в Title і UPPER: маскер рахував входження окремо, unmask
    зливав без урахування регістру; ВЕЛИКА форма прізвища діставала іншу основу;
  - звання в лапках у непрямому відмінку маскувалось двічі;
  - «№ 45-ЦІ» (літери поза [А-Яа-я]) обрізалось; місяць з великої літери в
    текстовій даті; пробіли в ініціалах зводились до одного;
  - звання бралось за першим входженням у рядку, а не суміжним із ПІБ.
"""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import surname as _surname  # noqa: E402
from datamasking.masking.context import parse_hybrid_line  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, stats = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


class TestMaskCollisions:
    def test_rank_mask_avoids_unmasked_rank_in_document(self):
        masked, mapping = _rt("Командир роти капітан\nмайор Петренко Іван Іванович")
        assert masked.startswith("Командир роти капітан\n")
        assert mapping["mappings"]["rank"]["майор"]["masked_as"] != "капітан"

    def test_order_number_mask_avoids_number_in_document(self):
        masked, mapping = _rt("Видано 778 одиниць. Наказ № 123.")
        assert "778 одиниць" in masked and "№ 778" not in masked

    def test_name_mask_avoids_word_in_document(self):
        masked, mapping = _rt("Ім'я: Ігор\nПетренко Іван Іванович")
        assert mapping["mappings"]["name"]["Іван"]["masked_as"] != "Ігор"

    def test_date_mask_avoids_legal_act_date(self):
        text = "Згідно із Законом України від 01.03.2025 № 1 капітан Петренко Іван Іванович народився 10.03.2025"
        masked, mapping = _rt(text)
        assert "від 01.03.2025" in masked
        assert mapping["mappings"]["date"]["10.03.2025"]["masked_as"] != "01.03.2025"

    def test_document_contains(self):
        _surname.enter_document("Наказ № 778 від 01.03.2025 капітан")
        try:
            assert _surname.document_contains("778") and _surname.document_contains("капітан")
            assert _surname.document_contains("01.03.2025") and _surname.document_contains("КАПІТАН")
            assert not _surname.document_contains("77") and not _surname.document_contains("капіта")
        finally:
            _surname.exit_document()
        assert not _surname.document_contains("778")


class TestCaseVariants:
    def test_title_and_upper_name_instances(self):
        text = ("капітан Сидоренко Петро Іванович\nкапітан СИДОРЕНКО ПЕТРО ІВАНОВИЧ\n"
                "капітан Сидоренко Петро Іванович\n")
        _rt(text)
        _rt("рядовий ПЕТРЕНКО ІВАН ІВАНОВИЧ\nрядовий Петренко Іван Іванович")

    def test_upper_surname_shares_stem(self):
        masked, mapping = _rt("ПЕТРЕНКО І.І.\nПетренко І.І.")
        masks = {k: v["masked_as"] for k, v in mapping["mappings"]["surname"].items()}
        assert masks["ПЕТРЕНКО"].lower() == masks["Петренко"].lower()


class TestOtherRoundTrips:
    @pytest.mark.parametrize("text", [
        "«сержанта» Петренка Івана Івановича",
        "наказ № 45-ЦІ від 01.02.2025",
        "«06» Жовтня 2025 року наказ",
        "старший  сержант Петренко Іван Іванович",
        "О.П.Петренко прибув",
        "О. П.  Петренко прибув",
        "Петренко  О.  П. прибув",
        "Петренко\xa0О.П. прибув",
        "Петренко О.П. та О.П. Коваль",
        "Петренко О.П",
    ])
    def test_roundtrip(self, text):
        masked, _ = _rt(text)
        for w in ("Петренк", "Коваль", "45-ЦІ", "Жовтня"):
            assert w not in masked or w == "Жовтня" and "Жовтня" not in masked

    def test_quoted_rank_masked_once(self):
        masked, mapping = _rt("«сержанта» Петренка Івана Івановича")
        assert len(mapping["mappings"]["rank"]) == 1

    def test_capitalised_month_keeps_case(self):
        masked, _ = _rt("«06» Жовтня 2025 року наказ")
        assert re.search(r"» [А-ЯІЇЄҐ][а-яіїєґ]+ \d{4} року", masked), masked


class TestAdjacentRank:
    def test_rank_belongs_to_adjacent_pib_only(self):
        text = ("рядовий склад зобов'язаний; солдат має право. "
                "рядовий Петренко Іван Іванович і солдат Коваль Олег Петрович")
        masked, mapping = _rt(text)
        assert masked.startswith("рядовий склад зобов'язаний; солдат має право. ")
        assert "Петренко" not in masked and "Коваль" not in masked
        assert set(mapping["mappings"]["rank"]) == {"рядовий", "солдат"}

    def test_parse_uses_adjacent_rank(self):
        rank, pib, _ = parse_hybrid_line("рядовий склад і солдат Коваль Олег Петрович")
        assert (rank, pib) == ("солдат", "Коваль Олег Петрович")
        rank, pib, _ = parse_hybrid_line("рядовий склад і Коваль Олег Петрович")
        assert (rank, pib) == ("", "Коваль Олег Петрович")

    def test_rank_with_modifier_adjacent(self):
        masked, _ = _rt("капітан у відставці Петренко Іван Іванович та Коваль Олег Петрович")
        assert "у відставці" in masked and "капітан" not in masked.split(" у відставці")[0]
