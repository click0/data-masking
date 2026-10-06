#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Дати народження маскуються; попередження про ключі конфігурації, що не діють (v3.0.22).

1. До 3.0.22 is_valid_date() пропускала лише роки 2015–2035 (межі ЗСУВУ дат
   документів): «12.05.1985 р.н.» лишалось відкритим поруч із замаскованим ПІБ.
   Плюс зсув вибирався з −30..+30, тож ~1,6% дат не змінювались зовсім.
   Тепер: розпізнаються 1900–2100, зсув ніколи не нульовий, маски дат
   2015–2035 не змінились (крім колишніх нульових зсувів), а дати
   нормативних актів («Закону України від 06.12.1991») не чіпаються.
2. Ключі конфігурації, які ні на що не впливають, раніше мовчки
   ігнорувались (застарілий приклад на 81 ключ «працював», діяли 16).
   Тепер — одне попередження на файл у stderr, з підказкою.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras.config import (  # noqa: E402
    ConfigLoader, ignored_config_keys, format_ignored_keys_warning,
)
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.mask_military import mask_date  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask, make_masking_dict  # noqa: E402

try:
    import yaml  # noqa: F401
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
needs_yaml = pytest.mark.skipif(not _HAS_YAML, reason="pyyaml not installed")


def _roundtrip(text):
    masked, md = mask(text)
    restored, _ = unmask_text_v2(masked, md, check_mapping_version(md))
    return masked, restored


# ---------------------------------------------------------------------------
# 1. Дати
# ---------------------------------------------------------------------------
class TestBirthDates:
    @pytest.mark.parametrize("text,date", [
        ("Петренко Іван Іванович, 12.05.1985 р.н., ІПН 1234567890", "12.05.1985"),
        ("дата народження 03.11.1999", "03.11.1999"),
        ("народився 01.01.1950", "01.01.1950"),
        ("капітан Коваль Петро Іванович (31.12.2001 р.н.)", "31.12.2001"),
    ])
    def test_birth_date_masked_and_restored(self, text, date):
        masked, restored = _roundtrip(text)
        assert date not in masked
        assert restored == text

    def test_birth_date_not_pulled_into_document_range(self):
        # 1985 не «підтягується» до 2015: лишається правдоподібною датою народження
        result = mask_date("12.05.1985", make_masking_dict(), {})
        assert result[-4:] in {"1984", "1985", "1986"}

    def test_dates_never_left_unchanged(self):
        # раніше randint(-30, 30) давав нульовий зсув ≈ 1 раз із 61
        for year in (1950, 1985, 2003, 2016, 2024, 2034):
            for month in range(1, 13):
                for day in (1, 9, 17, 28):
                    d = f"{day:02d}.{month:02d}.{year}"
                    assert mask_date(d, make_masking_dict(), {}) != d, d

    @pytest.mark.parametrize("original,expected", [
        # маски v3.0.21 для дат документів (2015–2035) не змінились
        ("11.03.2027", "15.02.2027"), ("21.01.2017", "24.01.2017"),
        ("27.09.2018", "07.10.2018"), ("12.10.2016", "03.10.2016"),
        ("17.04.2016", "27.03.2016"), ("03.07.2028", "04.06.2028"),
        ("03.04.2017", "13.03.2017"), ("18.07.2016", "20.07.2016"),
    ])
    def test_document_date_masks_unchanged(self, original, expected):
        assert mask_date(original, make_masking_dict(), {}) == expected

    def test_document_dates_stay_in_range(self):
        for d in ("02.01.2015", "15.01.2015", "28.12.2035", "20.12.2035"):
            year = int(mask_date(d, make_masking_dict(), {})[-4:])
            assert _cfg.DATE_SHIFT_YEAR_MIN <= year <= _cfg.DATE_SHIFT_YEAR_MAX


class TestLegalActDates:
    @pytest.mark.parametrize("text,date", [
        ("відповідно до Закону України від 06.12.1991 № 1932-XII", "06.12.1991"),
        ("згідно з Указом Президента України від 24.02.2022 № 64/2022", "24.02.2022"),
        ("Кодексу України про адміністративні правопорушення від 07.12.1984", "07.12.1984"),
        ("Конституції України від 28.06.1996", "28.06.1996"),
        ("постанова Кабінету Міністрів України від 6 грудня 1991 року", "6 грудня 1991 року"),
    ])
    def test_legal_act_date_kept(self, text, date):
        masked, restored = _roundtrip(text)
        assert date in masked
        assert restored == text

    @pytest.mark.parametrize("text,date", [
        ("наказом командира в/ч А1234 від 12.03.2024 № 125", "12.03.2024"),
        ("рапорт від 05.02.2023", "05.02.2023"),
        ("закон суворий, але 12.05.1985 р.н. — дата народження", "12.05.1985"),
    ])
    def test_other_dates_still_masked(self, text, date):
        masked, restored = _roundtrip(text)
        assert date not in masked
        assert restored == text


# ---------------------------------------------------------------------------
# 2. Попередження про ключі, що не діють
# ---------------------------------------------------------------------------
OLD_STYLE = {
    "system": {"version": "v2.6.0", "hash_algorithm": "blake2b", "backup_enabled": True},
    "security": {"encrypt_output": False, "scrypt_n": 16384,
                 "password_generation": {"enabled": True, "min_digits": 2}},
    "masking_rules": {"enable_dates": False, "enable_surnames": True},
    "remask": {"enabled": True, "max_passes": 5},
}


class TestIgnoredKeys:
    def test_detects_unknown_and_schema_only_keys(self):
        assert ignored_config_keys(OLD_STYLE) == [
            "system.version", "system.backup_enabled",
            "security.scrypt_n", "security.password_generation.enabled",
            "security.password_generation.min_digits",
            "masking_rules.enable_surnames",
            "remask.enabled", "remask.max_passes",
        ]

    def test_effective_only_file_is_clean(self):
        assert ignored_config_keys({"masking_rules": {"enable_dates": False},
                                    "system": {"faker_locale": "uk_UA"}}) == []

    def test_non_dict_section(self):
        assert ignored_config_keys({"router_rules": "mask"}) == ["router_rules"]

    def test_warning_text_is_bounded(self):
        keys = [f"s.k{i}" for i in range(65)]
        msg = format_ignored_keys_warning("config.yaml", keys)
        assert "65 key(s)" in msg and "(+55 more)" in msg and "--init-config" in msg
        assert "s.k10" not in msg


@needs_yaml
class TestWarningsInCli:
    OLD_YAML = (
        "system:\n  version: v2.6.0\n  backup_enabled: true\n"
        "masking_rules:\n  enable_dates: false\n  enable_document_numbers: false\n"
        "remask:\n  max_passes: 5\n"
    )

    def test_loader_reports_yaml_keys(self, tmp_path):
        p = tmp_path / "c.yaml"
        p.write_text(self.OLD_YAML, encoding="utf-8")
        loader = ConfigLoader(str(p))
        cfg = loader.load()
        assert cfg.masking_rules.enable_dates is False  # діючі ключі застосовано
        assert loader.ignored_keys == ["system.version", "system.backup_enabled",
                                       "masking_rules.enable_document_numbers", "remask.max_passes"]
        assert loader.ignored_source == str(p)

    def test_mask_cli_warns_once_and_still_works(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "c.yaml").write_text(self.OLD_YAML, encoding="utf-8")
        (tmp_path / "in.txt").write_bytes("капітан Петренко Іван Іванович, 12.03.2024\n".encode("utf-8"))
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--config", "c.yaml"])
        err = capsys.readouterr().err
        assert rc == 0
        assert err.count("have no effect") == 1
        assert "4 key(s)" in err and "remask.max_passes" in err
        out = (tmp_path / "out.txt").read_bytes().decode("utf-8")
        assert "12.03.2024" in out  # enable_dates: false подіяв

    def test_mask_cli_silent_for_effective_only_file(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "in.txt").write_bytes("капітан Петренко Іван Іванович\n".encode("utf-8"))
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report",
                            "--config", str(ROOT / "docs" / "config-examples" / "share.yaml")])
        assert rc == 0
        assert "have no effect" not in capsys.readouterr().err

    def test_unmask_cli_warns(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "in.txt").write_bytes("капітан Петренко Іван Іванович\n".encode("utf-8"))
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report"]) == 0
        (tmp_path / "c.yaml").write_text(self.OLD_YAML, encoding="utf-8")
        capsys.readouterr()
        mapping = next(tmp_path.glob("masking_map_*.json")).name
        rc = unmask_cli.main(["out.txt", "--map", mapping, "--output", "rec.txt", "-c", "c.yaml"])
        assert rc == 0
        assert "have no effect" in capsys.readouterr().err
        assert (tmp_path / "rec.txt").read_bytes().decode("utf-8") == "капітан Петренко Іван Іванович\n"


def test_python_config_dead_keys_reported(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.py").write_text(
        "CONFIG = {'system': {'hash_algorithm': 'sha256', 'strict_mode': True}}\n", encoding="utf-8")
    loader = ConfigLoader()
    assert loader.load().system.hash_algorithm == "sha256"
    assert loader.ignored_keys == ["system.strict_mode"]
    assert loader.ignored_source == "config.py"
