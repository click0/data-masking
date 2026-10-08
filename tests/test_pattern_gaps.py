#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.8 — витоки шаблонних типів, знайдені аудитом:

  - дата, приклеєна до літер («31.12.2024р.»), і день/місяць без нуля («1.1.2025»);
  - звання прапорщик / старший прапорщик / ефрейтор / капітан-лейтенант
    маскувались самі в себе або не розпізнавались;
  - БР-номери без «№» («БР 566», «БР-123», перший сегмент «БР 123/45»);
  - бригади в називному відмінку, «93-ї ОМБр», маска = оригінал;
  - ініціали: апостроф «’», подвійне прізвище, без останньої крапки, після «2024 р.»;
  - серія з І/Ї/Є/Ґ («ІВ 123456»), «А 1234» з пробілом, «ІПН1234567890»,
    регістр серії квитка («мт-123456»), «до 150000» — не серія;
  - «№ 123-к» — номер наказу, а не БР;
  - маски імен без «ʼ» (U+02BC) — вихід у cp1251 записується.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.context import analyze_number_sign_context  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

import re  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked


class TestDates:
    @pytest.mark.parametrize("text,date", [
        ("народився 31.12.2024р. у Києві", "31.12.2024"),
        ("дата 31.12.2024року", "31.12.2024"),
        ("з 01.01.2024по 15.03.2024", "01.01.2024"),
        ("(31.12.2024)", "31.12.2024"),
    ])
    def test_date_glued_to_letters(self, text, date):
        masked = _rt(text)
        assert date not in masked
        # контекст навколо дати (літери, дужки, «по») не змінився
        assert re.sub(r"\d{1,2}\.\d{1,2}\.\d{4}", "D", masked) == re.sub(r"\d{1,2}\.\d{1,2}\.\d{4}", "D", text)

    def test_single_digit_day_month(self):
        masked = _rt("1.1.2025 та 5.12.2024")
        assert "1.1.2025" not in masked and "5.12.2024" not in masked
        assert re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4} та \d{1,2}\.\d{1,2}\.\d{4}", masked)

    def test_version_like_number_untouched(self):
        assert mask("версія 1.2.3.2024 ні")[0] == "версія 1.2.3.2024 ні"


class TestRanks:
    @pytest.mark.parametrize("text,rank", [
        ("прапорщик Петренко Іван Іванович", "прапорщик"),
        ("старшого прапорщика Петренка Івана Івановича", "старшого прапорщика"),
        ("ефрейтор Петренко Іван Іванович", "ефрейтор"),
        ("капітан-лейтенант Петренко Іван Іванович", "капітан-лейтенант"),
    ])
    def test_rank_is_masked(self, text, rank):
        masked = _rt(text)
        assert not masked.startswith(rank), masked
        assert "Петренк" not in masked

    def test_hierarchy_contains_new_ranks(self):
        for r in ("ефрейтор", "прапорщик", "старший прапорщик"):
            assert r in _cfg.ARMY_RANKS and r in _cfg.RANK_DECLENSIONS
        assert "капітан-лейтенант" in _cfg.RANK_DECLENSIONS


class TestNumbers:
    @pytest.mark.parametrize("text,original", [
        ("БР 123/45 виконано", "123/45"),
        ("БР-123 виконано", "БР-123"),
        ("БР 566 виконано", "566"),
        ("№БР-123/45 виконано", "123/45"),
        ("№ БР 123/45", "123/45"),
    ])
    def test_br_numbers_fully_masked(self, text, original):
        masked = _rt(text)
        assert original not in masked, masked
        assert "БР" in masked

    @pytest.mark.parametrize("text", [
        "72 окрема механізована бригада", "93-ї ОМБр", "31 ТБр і 126 ОМБр",
        "військовослужбовець 112 ОМБр прибув", "окремої штурмової бригади 3 ні",
    ])
    def test_brigades(self, text):
        masked = _rt(text)
        for num in re.findall(r"\d+", text):
            if "ні" in text and num == "3":
                continue  # номер після назви не маскується (не формат «N бригада»)
            assert not re.search(rf"\b{num}\b", masked), masked

    def test_brigade_mask_never_equals_original(self):
        for n in range(1, 161):
            masked = mask(f"{n} ОМБр")[0]
            assert masked != f"{n} ОМБр", n

    def test_order_with_k_suffix_is_order_not_br(self):
        m = re.search("№", "наказ № 123-к від")
        info = analyze_number_sign_context("наказ № 123-к від", m)
        assert info["type"].startswith("order")
        info = analyze_number_sign_context("наказ № 45дск від", re.search("№", "наказ № 45дск від"))
        assert info["type"].startswith("br")

    def test_order_k_masked_with_br_disabled(self):
        saved = _cfg.MASK_BR_NUMBERS
        _cfg.MASK_BR_NUMBERS = False
        try:
            masked = _rt("наказ № 123-к від 01.02.2025 та наказ № 456")
        finally:
            _cfg.MASK_BR_NUMBERS = saved
        assert "123-к" not in masked and "№ 456" not in masked


class TestInitials:
    @pytest.mark.parametrize("text,surname", [
        ("Лук’янчук І.І. прибув", "Лук’янчук"),
        ("Нечуй-Левицький П.В.", "Нечуй-Левицький"),
        ("Д. О. Нечуй-Левицький", "Нечуй-Левицький"),
        ("Петренко О.П прибув", "Петренко"),
        ("станом на 2024 р. П. Петренко доповів", "Петренко"),
    ])
    def test_masked(self, text, surname):
        masked = _rt(text)
        assert surname not in masked, masked

    def test_missing_final_dot_kept_missing(self):
        masked = _rt("Петренко О.П прибув")
        assert re.search(r" [А-ЯІЇЄҐ]\.[А-ЯІЇЄҐ] прибув$", masked), masked

    def test_subpoint_letter_untouched(self):
        assert mask("п. В. Петренко подано")[0] == "п. В. Петренко подано"


class TestIdentifiers:
    @pytest.mark.parametrize("text,original", [
        ("ІВ 123456 посвідчення", "123456"),
        ("в/ч А 1234 та в/ч А1234", "1234"),
        ("ІПН1234567890 Петренко", "1234567890"),
    ])
    def test_masked(self, text, original):
        masked = _rt(text)
        assert original not in masked, masked

    def test_military_id_series_case_and_separator_kept(self):
        masked = _rt("військовий квиток мт-123456, МТ 654321, АБ-112233")
        assert re.search(r"мт-\d{6}, МТ \d{6}, АБ-\d{6}", masked), masked

    def test_lowercase_word_before_number_is_not_series(self):
        masked = _rt("виплатити до 150000 грн")
        assert masked.startswith("виплатити до ") and masked.endswith(" грн")


class TestEncoding:
    def test_name_masks_use_ascii_apostrophe(self):
        text = "\n".join(f"капітан Петренко Олег {p}" for p in
                         ("Петрович", "Іванович", "Олексійович", "Сергійович", "Миколайович",
                          "Васильович", "Андрійович", "Юрійович", "Богданович", "Романович"))
        masked = _rt(text)
        assert "ʼ" not in masked and "’" not in masked
        masked.encode("cp1251")  # не падає

    def test_cp1251_roundtrip_through_cli(self, tmp_path, monkeypatch, capsys):
        pytest.importorskip("yaml")
        monkeypatch.chdir(tmp_path)
        for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
            monkeypatch.delenv(var, raising=False)
        src = (ROOT / "input_example.txt").read_text(encoding="utf-8")
        (tmp_path / "in.txt").write_bytes(src.encode("cp1251"))
        (tmp_path / "config.yaml").write_text("system:\n  encoding: cp1251\n", encoding="utf-8")
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--no-local-config"])
        assert rc == 0, capsys.readouterr().out
        out = (tmp_path / "out.txt").read_bytes()
        assert out and "Петренко" not in out.decode("cp1251")
        mapping = sorted(tmp_path.glob("masking_map_*.json"))[-1]
        rc = unmask_cli.main(["out.txt", "--map", str(mapping), "--output", "back.txt", "--no-local-config"])
        assert rc == 0
        assert (tmp_path / "back.txt").read_bytes() == src.encode("cp1251")
