#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Статистика розмаскування (v3.1.2): «пропущено» — лише маски з mapping, для
яких не знайшлося оригіналу. Справжні звання, які не маскувались
(--exclude rank, enable_ranks: false, --only …), — не пропуск: раніше вони
роздували «пропущено», а строгий режим data-unmask завершувався з кодом 1,
хоча текст відновлено точно.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

TEXT = ("капітан Петренко Іван Іванович прибув. ІПН 1234567890.\n"
        "Старшому лейтенанту Коваленку Олегу Петровичу оголосити подяку.\n")


def _unmask(masked, mapping):
    return unmask_text_v2(masked, mapping, check_mapping_version(mapping))


def test_full_masking_has_no_skips():
    masked, mapping = mask(TEXT)
    restored, stats = _unmask(masked, mapping)
    assert restored == TEXT and stats["skipped_count"] == 0


def test_unmasked_ranks_are_not_skips():
    _cfg.MASK_RANKS = False  # conftest відновлює налаштування після тесту
    masked, mapping = mask(TEXT)
    assert "капітан" in masked and "Старшому лейтенанту" in masked
    restored, stats = _unmask(masked, mapping)
    assert restored == TEXT
    assert stats["skipped_count"] == 0 and stats["restored_count"] > 0


def test_extra_occurrences_of_a_mask_still_count():
    masked, mapping = mask(TEXT)
    rank_mask = masked.split()[0]
    _, stats = _unmask(masked + rank_mask + "\n", mapping)
    assert stats["skipped_count"] == 1


@pytest.mark.parametrize("extra", [["--exclude", "rank"], ["--only", "ipn"]])
def test_strict_unmask_succeeds_without_rank_masking(tmp_path, monkeypatch, capsys, extra):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "in.txt").write_text(TEXT, encoding="utf-8")
    assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", *extra]) == 0
    mapping = sorted(tmp_path.glob("masking_map_*.json"))[-1]
    (tmp_path / "config.py").write_text("CONFIG = {'system': {'strict_mode': True}}\n", encoding="utf-8")
    rc = unmask_cli.main(["out.txt", "--map", str(mapping), "--output", "back.txt"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert (tmp_path / "back.txt").read_text(encoding="utf-8") == TEXT
