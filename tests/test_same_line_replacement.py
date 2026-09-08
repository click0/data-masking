#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Кілька звань/ПІБ в одному рядку: заміни не мають влучати одна в одну (v3.0.14).

До 3.0.14 рушій підставляв маску через final_line.replace(rank, mask, 1) —
«перше входження» в уже частково замаскованому рядку. Коли маска одного
звання містила форму іншого звання з того ж рядка (рядовий → старший солдат,
солдат → рядовий), друга заміна псувала першу:

    довідках №273 рядового МАЗУРЕНКА та солдата КОВАЛЕНКА
    → довідках №857 старшого рядового МАЗИДЕНКА та солдата КОВИЛЕНКА

«старшого рядового» — неіснуюче звання, «солдата» лишилось відкритим,
а unmask повертав «старшого солдата» замість «рядового».
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamasking.masking.mask_military import get_rank_in_case  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402


def _roundtrip(text: str):
    masked, md = mask(text)
    restored, _ = unmask_text_v2(masked, md, check_mapping_version(md))
    return masked, md, restored


class TestCrossMaskedRanksOnOneLine:
    LINE = "довідках №273 рядового МАЗУРЕНКА та солдата КОВАЛЕНКА"

    def test_masks_are_crossed_in_this_fixture(self):
        # Фікстура має сенс лише поки маски перехрещуються: маска «рядовий»
        # містить «солдат», а маска «солдат» — «рядовий». Якщо ієрархія/зсув
        # зміняться, тест треба перебудувати
        _, md, _ = _roundtrip(self.LINE)
        ranks = md["mappings"]["rank"]
        assert "солдат" in ranks["рядовий"]["masked_as"]
        assert "рядовий" in ranks["солдат"]["masked_as"]

    def test_each_rank_gets_its_own_mask(self):
        masked, md, _ = _roundtrip(self.LINE)
        ranks = md["mappings"]["rank"]
        first = get_rank_in_case(ranks["рядовий"]["masked_as"], "genitive")
        second = get_rank_in_case(ranks["солдат"]["masked_as"], "genitive")
        words = masked.split()
        assert words[2:4] == first.split(), masked
        assert words[6:7] == second.split(), masked
        assert "старшого рядового" not in masked
        assert "солдата КОВ" not in masked  # друге звання не лишилось відкритим

    def test_no_original_leaks(self):
        masked, _, _ = _roundtrip(self.LINE)
        for leak in ["МАЗУРЕНКА", "КОВАЛЕНКА", "№273"]:
            assert leak not in masked

    def test_roundtrip(self):
        _, _, restored = _roundtrip(self.LINE)
        assert restored == self.LINE

    def test_reverse_order_roundtrip(self):
        line = "рапорт солдата КОВАЛЕНКА щодо рядового МАЗУРЕНКА"
        masked, _, restored = _roundtrip(line)
        assert "старшого рядового" not in masked
        assert restored == line


class TestManyItemsOnOneLine:
    @pytest.mark.parametrize("line", [
        "рядовий Іванов Іван Іванович, солдат Петров Петро Петрович, старший солдат Сидоров Сидір Сидорович",
        "рядового Мазуренка та солдата Коваленка і старшого солдата Бондаренка",
        "капітан Петренко Іван Іванович та капітан Іванов Петро Петрович",
        "старший солдат Ткач Олег Ігорович; рядовий Ґудзь Ігор Олегович",
    ])
    def test_roundtrip_and_no_leak(self, line):
        masked, md, restored = _roundtrip(line)
        assert restored == line
        for original in md["mappings"]["surname"]:
            assert original not in masked

    def test_same_rank_twice(self):
        line = "рядовий Іванов Іван Іванович та рядовий Петров Петро Петрович"
        masked, md, restored = _roundtrip(line)
        assert restored == line
        masked_rank = md["mappings"]["rank"]["рядовий"]["masked_as"]
        assert masked.count(masked_rank) == 2

    def test_no_placeholder_survives(self):
        for line in ["рядовий Іванов Іван Іванович та солдат Петров", "капітан Петренко Іван"]:
            masked, _, _ = _roundtrip(line)
            assert "___" not in masked
