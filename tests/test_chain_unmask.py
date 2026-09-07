#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Колізії підрядків звань при розмаскуванні (аудит 3.0.0, відкритий баг).

Маски різних проходів --re-mask перекриваються як підрядки:
пас 2: «лейтенант → головний майстер-сержант» і «головний майстер-сержант
→ майстер-сержант». Пошук звань у тексті додавав і довгу форму, і коротку
всередині неї, зсуваючи instance-лічильник — окреме «майстер-сержант»
відновлювалось не в те звання (або пропускалось).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamasking.unmasking.engine import unmask_ranks_gender_aware, unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _map(rank_pairs):
    return {
        "version": "3.0.6",
        "mappings": {"rank": {orig: {"masked_as": masked, "instances": [1]} for orig, masked in rank_pairs}},
        "instance_tracking": {},
    }


class TestOverlappingRankMasks:
    def test_short_form_inside_long_form_not_double_counted(self):
        # текст: маска «головний майстер-сержант» (← лейтенант) і окрема маска
        # «майстер-сержант» (← головний майстер-сержант)
        mapping = _map([("лейтенант", "головний майстер-сержант"),
                        ("головний майстер-сержант", "майстер-сержант")])
        text = "головний майстер-сержант Іванов та майстер-сержант Петров"
        restored, stats = unmask_ranks_gender_aware(text, mapping)
        assert restored == "лейтенант Іванов та головний майстер-сержант Петров"
        assert stats["skipped_count"] == 0

    def test_reverse_order_in_text(self):
        mapping = _map([("лейтенант", "головний майстер-сержант"),
                        ("головний майстер-сержант", "майстер-сержант")])
        text = "майстер-сержант Петров та головний майстер-сержант Іванов"
        restored, _ = unmask_ranks_gender_aware(text, mapping)
        assert restored == "головний майстер-сержант Петров та лейтенант Іванов"

    def test_three_level_nesting(self):
        # старший майстер-сержант ⊃ майстер-сержант ⊃ сержант
        mapping = _map([("капітан", "старший майстер-сержант"),
                        ("майор", "майстер-сержант"),
                        ("полковник", "сержант")])
        text = "старший майстер-сержант А, майстер-сержант Б, сержант В"
        restored, stats = unmask_ranks_gender_aware(text, mapping)
        assert restored == "капітан А, майор Б, полковник В"
        assert stats["skipped_count"] == 0


class TestReMaskRoundtrip:
    def test_input_example_two_passes_cli(self, tmp_path, monkeypatch):
        """Реальний сценарій: input_example.txt, --re-mask 2, повне відновлення."""
        monkeypatch.chdir(tmp_path)
        src = (ROOT / "input_example.txt").read_bytes().decode("utf-8")
        (tmp_path / "in.txt").write_bytes(src.encode("utf-8"))
        assert mask_cli.main(["-i", "in.txt", "-o", "m.txt", "--no-report", "--re-mask", "2"]) == 0
        chain = next(tmp_path.glob("masking_chain_*.json"))
        assert unmask_cli.main(["m.txt", "--map", str(chain), "-o", "rec.txt"]) == 0
        # single-pass на тому ж вході для порівняння (нормалізація розірваних
        # рядків однакова в обох режимах)
        assert mask_cli.main(["-i", "in.txt", "-o", "s.txt", "--no-report"]) == 0
        smap = next(tmp_path.glob("masking_map_*.json"))
        assert unmask_cli.main(["s.txt", "--map", str(smap), "-o", "rec_single.txt"]) == 0
        rec_chain = (tmp_path / "rec.txt").read_bytes().decode("utf-8")
        rec_single = (tmp_path / "rec_single.txt").read_bytes().decode("utf-8")
        assert rec_chain == rec_single
        assert rec_chain.casefold() == src.casefold()

    def test_three_passes_engine_level(self):
        from tests.test_initials import mask
        from datamasking.extras.re_mask import MappingChain, make_empty_masking_dict
        from datamasking.masking.engine import mask_text_context_aware
        text = "\n".join([
            "лейтенант Коваленко Ігор Миколайович",
            "капітан Петренко Іван Сергійович",
            "головний майстер-сержант Сидоренко Олег Петрович",
            "майстер-сержант Бондаренко Юрій Іванович",
            "сержант Мельник Тарас Олегович",
        ])
        chain = MappingChain()
        masked = text
        for _ in range(3):
            d = make_empty_masking_dict()
            counters = {}
            masked = mask_text_context_aware(masked, d, counters)
            d["instance_tracking"] = counters
            chain.add_pass(d)
        from datamasking.unmasking.engine import unmask_chain
        restored, _ = unmask_chain(masked, chain.to_dict())
        assert restored == text
