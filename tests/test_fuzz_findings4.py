#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки четвертого пошуку помилок (після 3.1.21).

  - невидимий символ (м'який перенос, zero-width space, BOM посеред тексту)
    чи апостроф «‘»/«`» усередині прізвища: фаза «прізвище + ініціали»
    маскувала хвіст, основний розбір — усе слово ще раз, і unmask не
    відновлював оригінал; різні написання діставали різні основи;
  - прізвища на «-ній» (Задорожній / Задорожнього / Задорожнім) і
    «Головата» / «Головатій» — різні синтетичні основи;
  - маска однозначного номера наказу збігалась із відкритим номером пункту;
  - дата після «законодавства», «законних», «закону, рапорт від» лишалась
    відкритою; дата закону з довгою назвою чи «від» на новому рядку — зсувалась;
  - «У 2025 році» маскувалось як номер в/ч; «в/ч А\\xa01234», «в/ч А-1234» — ні;
  - паспорт «АА123456» з --only passport лишався відкритим;
  - текстова дата: «'28' вересня», ««28»вересня» (без пробілу), той самий день;
  - «№ 15.01.2025», «БР566», «БР: 566», «накази № 12, 13 та 14»;
  - CSV через кому і в лапках; файли з самими CR;
  - CLI: --log-file у вхідний файл чи mapping, сторонній JSON як mapping,
    маска з пробілу, кодек base64, глибоко вкладений JSON, -o каталог.
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking import _textio  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.helpers import clean_word  # noqa: E402
from datamasking.masking.mask_military import mask_date_text  # noqa: E402
from datamasking.masking.mask_personal import mask_surname  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from datamasking.unmasking.io import validate_mapping_schema  # noqa: E402
from tests.test_initials import make_masking_dict, mask  # noqa: E402

try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


def _clean(text):
    return clean_word(text).lower()


class TestInvisibleCharacters:
    @pytest.mark.parametrize("text, secret", [
        ("капітан ЗІНЧ​ЕНКО Є.Ю.\n", "зінченко"),
        ("Рапорт капітана медичної служби КРАВ­ЧЕНКО Г.С.\n", "кравченко"),
        ("ЗІНЧ​ЕНКО Є.Ю. прибув\n", "зінченко"),
        ("сержант ДЕМ‘ЯНЧУКУ Т.Р.\n", "дем'янчуку"),
        ("майор П`ЯТНИЧУК В.Ю.\n", "п'ятничук"),
        ("Разом з підполковником Дорошенком-­Ґудзем Іваном Івановичем.\n", "ґудзем"),
        ("Разом з віце-адміралом Дорошенком-​Ґудзем Д.І.\n", "ґудзем"),
        ("‌старший матрос  Поліщук Богдан Ів­анович.\n", "іванович"),
        ("​генерал-лейтенант Си​доров\xa0С.І.\n", "сидоров"),
        ("майор Пет­ренко Іван Петрович\n", "петренко"),
    ])
    def test_masked_and_restored(self, text, secret):
        masked, _ = _rt(text)
        assert secret not in _clean(masked), masked

    def test_bom_inside_text(self):
        _rt("рапорт\n﻿старший матрос\xa0Петренко Наталія Сергіївна.\n"
            "Разом з старшим матросом Петренко Н.С.\n")

    def test_two_spellings_in_one_document(self):
        masked, mapping = _rt("Рапорт підполковника Дороше­нка-Ґудзя Віталія Юрійовича.\n"
                              "Рапорт підполковника Дорошенка-Ґудзя В.Ю.\n")
        masks = {info["masked_as"] for info in mapping["mappings"]["surname"].values()}
        assert len(masks) == 2

    def test_apostrophe_spellings_share_stem(self):
        d = make_masking_dict()
        masks = [mask_surname(f, d, {}).lower() for f in ("Дем‘янчук", "Дем'янчука", "Демʼянчуку", "Дем`янчуком")]
        assert len(os.path.commonprefix(masks)) >= 5, masks

    def test_mask_has_no_invisible_characters(self):
        out = mask_surname("Пет­ренко", make_masking_dict(), {})
        assert not any(ch in out for ch in _cfg.INVISIBLE_CHARS)


class TestAdjectiveSurnameStems:
    @pytest.mark.parametrize("forms", [
        ("Задорожній", "Задорожнього", "Задорожньому", "Задорожнім"),
        ("Задорожнім", "Задорожньому", "Задорожнього", "Задорожній"),
        ("Задорожня", "Задорожньої", "Задорожній", "Задорожньою"),
        ("Головата", "Головатої", "Головатій", "Головатою"),
        ("Головатій", "Головатої", "Головата"),
    ])
    def test_one_stem(self, forms):
        d = make_masking_dict()
        masks = [mask_surname(f, d, {}).lower() for f in forms]
        assert len(os.path.commonprefix(masks)) >= 5, masks
        assert not any("ього" in m or "ьому" in m for m in masks if not m[:-4].endswith("н"))


class TestNumbers:
    def test_single_digit_order_number(self):
        text = "".join(f"{i}. Пункт.\n" for i in range(1, 10)) + "Підстава: наказ № 5.\n"
        masked, _ = _rt(text)
        assert "№ 5." not in masked

    def test_listed_order_numbers(self):
        masked, _ = _rt("накази № 12, 13 та 14 скасувати.\n")
        assert not re.search(r"\b(12|13|14)\b", masked), masked

    @pytest.mark.parametrize("text, kept", [
        ("наказ № 12 та 13 травня\n", "13 травня"),
        ("наказ № 12 і 2025 року\n", "2025 року"),
    ])
    def test_not_a_list(self, text, kept):
        masked, _ = _rt(text)
        assert kept in masked

    def test_date_after_number_sign(self):
        masked, _ = _rt("наказ № 15.01.2025\n")
        assert "01.2025" not in masked and re.search(r"№ \d{2}\.\d{2}\.\d{4}", masked)

    @pytest.mark.parametrize("text, number", [("БР566 видано\n", "566"), ("БР: 567 видано\n", "567"),
                                              ("БР-568 видано\n", "568")])
    def test_br_forms(self, text, number):
        masked, _ = _rt(text)
        assert number not in masked

    def test_years_not_unit_numbers(self):
        text = "У 2025 році прибув. В 2024 р. З 2023 року. А 2000 грн. О 1430 годині.\n"
        assert mask(text)[0] == text

    @pytest.mark.parametrize("text", ["в/ч А\xa01234\n", "в/ч А-1234\n", "в/ч А 1234\n",
                                      "військова частина А 1234\n", "військової частини В 1234\n",
                                      "в/ч А1234\n", "наказ командира А1234\n"])
    def test_unit_numbers(self, text):
        masked, _ = _rt(text)
        assert "1234" not in masked

    def test_old_passport_with_only_passports(self, monkeypatch):
        monkeypatch.setattr(_cfg, "MASK_MILITARY_ID", False)
        masked, _ = _rt("паспорт АА123456, АА 654321\n")
        assert "123456" not in masked and "654321" not in masked


class TestDates:
    @pytest.mark.parametrize("text", [
        "Відповідно до законодавства звільнити від 01.02.2025\n",
        "на підставі закону, рапорт від 01.02.2025\n",
        "відповідно до законних вимог, рапорт від 01.02.2025\n",
    ])
    def test_not_a_legal_act(self, text):
        masked, _ = _rt(text)
        assert "01.02.2025" not in masked

    @pytest.mark.parametrize("text, date", [
        ("Закону України «Про соціальний і правовий захист військовослужбовців та членів їх сімей» "
         "від 20.12.1991\n", "20.12.1991"),
        ("Закону України\nвід 06.12.1991\n", "06.12.1991"),
        # номер закону маскується як номер (зберігати — через custom skip), дата — ні
        ("Закону України № 2232-XII від 25.03.1992\n", "25.03.1992"),
    ])
    def test_legal_act_date_kept(self, text, date):
        assert date in _rt(text)[0]

    @pytest.mark.parametrize("text", ["«28»вересня 2025 року\n", "28вересня 2025\n",
                                      "'28' вересня 2025\n", "‘28’ вересня 2025\n"])
    def test_text_date_forms(self, text):
        masked, _ = _rt(text)
        assert "вересня" not in masked

    @pytest.mark.parametrize("day", ["1", "01", "28", "27", "2"])
    def test_text_date_day_changes(self, day):
        for month in ("січня", "березня", "травня", "вересня", "грудня"):
            for year in ("2023", "2024", "2025"):
                out = mask_date_text(f"{day} {month} {year}", make_masking_dict(), {})
                assert out.split()[0] != day, out

    def test_long_whitespace_is_fast(self):
        import time
        text = " " * 40000 + "28 вересня 2025\n" + "\n" * 20000
        start = time.time()
        _rt(text)
        assert time.time() - start < 10


class TestCsv:
    @pytest.mark.parametrize("text", [
        "Петренко,Іван,Петрович,сержант,1234567890\n",
        "сержант,Петренко,Іван,Петрович\n",
        '"Петренко";"Іван";"Петрович";"сержант"\n',
        '"Петренко","Іван","Петрович"\n',
        '"Петренко Іван Петрович";"сержант"\n',
    ])
    def test_masked_and_separators_kept(self, text):
        masked, _ = _rt(text)
        for word in ("Петренк", "Іван", "Петрович"):
            assert word not in masked, masked
        for sep in ',;"':
            assert masked.count(sep) == text.count(sep)

    def test_prose_comma_still_ends_name(self):
        masked, _ = _rt("Петренко Іван Петрович, сержант\n")
        assert ", сержант" in masked


class TestLineBreaks:
    @pytest.mark.parametrize("nl", ["\r", " "])
    def test_same_as_lf(self, nl):
        text = ("солдат Петренко Іван Петрович\nсолдата Коваля Олега Петровича\n"
                "Призначити Петренка\nІвана Івановича на посаду.\n")
        masked_lf, _ = _rt(text)
        masked, _ = _rt(text.replace("\n", nl))
        assert masked == masked_lf.replace("\n", nl)


@pytest.fixture
def cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "src.txt").write_text("сержант Петренко Іван Петрович, ІПН 1234567890\n", encoding="utf-8")
    return tmp_path


def _masked(cwd):
    assert mask_cli.main(["-i", "src.txt", "-o", "out.txt", "--no-report"]) == 0
    return str(next(cwd.glob("masking_map_*")))


class TestCli:
    def test_log_file_is_input(self, cwd):
        before = (cwd / "src.txt").read_bytes()
        with pytest.raises(SystemExit) as e:
            mask_cli.main(["-i", "src.txt", "-o", "out.txt", "--no-report", "--log-file", "src.txt"])
        assert e.value.code == 2 and (cwd / "src.txt").read_bytes() == before

    def test_log_file_is_mapping(self, cwd):
        mapping = _masked(cwd)
        before = Path(mapping).read_bytes()
        assert unmask_cli.main(["out.txt", "-m", mapping, "-o", "r.txt", "--log-file", mapping]) == 2
        assert Path(mapping).read_bytes() == before

    @pytest.mark.parametrize("data", [{}, {"name": "config"}, {"version": "3.1.21"}])
    def test_not_a_mapping(self, cwd, data):
        _masked(cwd)
        (cwd / "c.json").write_text(json.dumps(data), encoding="utf-8")
        assert unmask_cli.main(["out.txt", "-m", "c.json", "-o", "r.txt"]) == 1

    @pytest.mark.parametrize("bad", [" ", ".", " - "])
    def test_mask_without_letters(self, bad):
        with pytest.raises(ValueError, match="empty"):
            validate_mapping_schema({"mappings": {"surname": {"Коваленко": {"masked_as": bad, "instances": [1]}}}})

    @pytest.mark.parametrize("bad", ["x", [1], [{"mappings": 5}]])
    def test_legacy_re_mask_passes(self, bad):
        with pytest.raises(ValueError):
            validate_mapping_schema({"mappings": {}, "re_mask_passes": bad})

    @pytest.mark.parametrize("codec", ["base64", "rot13", "hex"])
    def test_not_a_text_encoding(self, cwd, codec):
        with pytest.raises(ValueError, match="not a text encoding"):
            _textio.normalize_encoding(codec)
        mapping = _masked(cwd)
        data = json.loads(Path(mapping).read_text(encoding="utf-8"))
        data["input_encoding"] = codec
        Path(mapping).write_text(json.dumps(data), encoding="utf-8")
        assert unmask_cli.main(["out.txt", "-m", mapping, "-o", "r.txt"]) == 1

    def test_mapping_with_bom(self, cwd):
        mapping = _masked(cwd)
        Path(mapping).write_bytes(b"\xef\xbb\xbf" + Path(mapping).read_bytes())
        assert unmask_cli.main(["out.txt", "-m", mapping, "-o", "r.txt"]) == 0
        assert (cwd / "r.txt").read_bytes() == (cwd / "src.txt").read_bytes()

    def test_deep_json(self, cwd):
        (cwd / "deep.json").write_text("[" * 700 + '"Петренко"' + "]" * 700, encoding="utf-8")
        assert mask_cli.main(["-i", "deep.json", "-o", "o.json", "--no-report"]) == 1

    def test_output_directory(self, cwd):
        (cwd / "d").mkdir()
        assert mask_cli.main(["-i", "src.txt", "-o", "d", "--no-report"]) == 2
        assert mask_cli.main(["-i", "src.txt", "-o", "nodir/x.txt", "--no-report"]) == 2
        assert not list(cwd.glob("masking_map_*"))

    def test_auto_mode_honours_output(self, cwd):
        assert mask_cli.main(["-i", "src.txt", "--no-report"]) == 0
        assert unmask_cli.main(["-o", "mine.txt"]) == 0
        assert (cwd / "mine.txt").read_bytes() == (cwd / "src.txt").read_bytes()

    @pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")
    def test_scrypt_work_limit(self):
        from datamasking.extras.security import MappingSecurityManager
        with pytest.raises(ValueError, match="too large"):
            MappingSecurityManager.check_kdf({"kdf": "scrypt", "n": 1 << 20, "r": 8, "p": 16})
        MappingSecurityManager.check_kdf({"kdf": "scrypt", "n": 1 << 14, "r": 8, "p": 1})
