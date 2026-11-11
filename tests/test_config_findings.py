#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки аудиту конфігурації (після 3.1.20).

  - маску custom-шаблону / always_mask фаза ПІБ маскувала ще раз, і unmask
    не повертав оригінал; шаблон «[A-Z]{3,}» знаходив службовий токен
    захищеної фрази, і фраза зникала;
  - exclusions не знаходили слів з іншим апострофом (’ ʼ замість ');
  - скопійований шаблон config_local стирав спільні exclusions;
  - невідоме булеве значення в ENV ставало false (шифрування вимикалось);
  - config.yaml (max_name_length: 50) маскував не так, як запуск без нього;
  - traceback замість помилки конфігурації: hash_algorithm у верхньому
    регістрі, backup_suffix зі «/», logging.level не рядок, ключ секції не
    рядок;
  - router_rules.skip_types вимикав enable_* того самого файлу;
    masking_rules.preserve_case перекривав ENV; password_generation:
    "false" ігнорувався; 2.9 у цілому ключі ставало 2; --re-mask множив
    лічильник warn; порожня секція — «ключ без дії» (strict_mode падав);
  - diagnose: битий файл давав exit 0 або traceback.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking import diagnose  # noqa: E402
from datamasking.extras.config import ConfigLoader, ignored_config_keys  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking import exclusions as _excl  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
needs_yaml = pytest.mark.skipif(not _HAS_YAML, reason="pyyaml not installed")


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


def _exclusions(section):
    ex = _excl.build(section)
    _cfg.ABBREVIATION_WHITELIST = ex.abbreviations
    _cfg.EXCLUDE_WORDS_LOWER = ex.words_lower
    _cfg.CUSTOM_PATTERNS = ex.skip_patterns + _cfg.CUSTOM_PATTERNS + ex.mask_patterns


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)

    def _run(config=None, extra=(), text="сержант Петренко Іван Іванович прибув.\n", out="out.txt"):
        if config is not None:
            (tmp_path / "config.py").write_text(f"CONFIG = {config!r}\n", encoding="utf-8")
        (tmp_path / "in.txt").write_text(text, encoding="utf-8")
        rc = mask_cli.main(["-i", "in.txt", "-o", out, "--no-report", *extra])
        cap = capsys.readouterr()
        path = tmp_path / out
        return rc, path.read_text(encoding="utf-8") if path.exists() else "", cap.out, cap.err

    return _run


class TestCustomMasksNotMaskedTwice:
    @pytest.mark.parametrize("text", [
        "Доповідь подав сержант Сокіл.",
        "Позивний Сокіл, сержант Сокіл, СОКІЛ.",
    ])
    def test_always_mask(self, text):
        _exclusions({"always_mask": ["Сокіл"]})
        masked, mapping = _rt(text)
        assert "Сокіл" not in masked and "СОКІЛ" not in masked
        assert set(mapping["mappings"].get("surname", {})) == set(), mapping["mappings"]

    def test_mask_pattern_does_not_hit_kept_phrase(self):
        from datamasking.masking import custom as _custom
        _cfg.CUSTOM_PATTERNS = _custom.compile_patterns(["[A-Z]{3,}"])
        _exclusions({"phrases": ["Верховн* Рад*"]})
        masked, mapping = _rt("Звернення до Верховна Рада, позивний ABC.")
        assert masked.startswith("Звернення до Верховна Рада, позивний ")
        assert "ABC" not in masked
        assert set(mapping["mappings"]["custom"]) == {"ABC"}


class TestApostropheVariants:
    TEXT = "Позивний Дем'ян, позивний Дем’ян, позивний Демʼян прибули."

    def test_always_mask(self):
        _exclusions({"always_mask": ["Дем'ян"]})
        masked, _ = _rt(self.TEXT)
        assert "Дем" not in masked

    @pytest.mark.parametrize("section", [
        {"phrases": ["Дем'янів Лаз"]},
        {"phrases": ["Дем’янів Лаз"]},
        {"words": ["Дем'янів"]},
        {"words": ["Демʼянів"]},
    ])
    def test_kept(self, section):
        _exclusions(section)
        text = "в урочище Дем'янів Лаз.\nв урочище Дем’янів Лаз.\nв урочище Демʼянів Лаз."
        masked, _ = _rt(text)
        assert masked == text

    def test_describe_lists_word_once(self):
        assert "дем'янів" in _excl.describe(_excl.build({"words": ["Дем’янів"]}))
        assert "дем’янів" not in _excl.describe(_excl.build({"words": ["Дем’янів"]}))

    def test_remove_any_spelling(self):
        ex = _excl.build({"words": ["Дем'янів"], "remove": ["Дем’янів"]})
        assert "дем'янів" in ex.words_lower  # remove діє лише на вбудовані
        assert _excl.apostrophe_variants(["a'b"]) == {"a'b", "a’b", "aʼb"}


@needs_yaml
class TestLocalTemplate:
    def test_keeps_shared_exclusions(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        data = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        data["exclusions"]["always_mask"] = ["Сокіл"]
        (tmp_path / "config.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        (tmp_path / "config_local.yaml").write_bytes((ROOT / "config_local.example.yaml").read_bytes())
        os.chmod(tmp_path / "config_local.yaml", 0o600)
        (tmp_path / "in.txt").write_text("Доповідь подав сержант Сокіл.\n", encoding="utf-8")
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report"]) == 0
        assert "Loaded local config from config_local.yaml" in capsys.readouterr().out
        assert "Сокіл" not in (tmp_path / "out.txt").read_text(encoding="utf-8")

    def test_root_config_has_no_name_length_limit(self):
        data = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
        assert data["validation"]["max_name_length"] is None


class TestValues:
    def test_env_bool_unknown_word_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.py").write_text(
            "CONFIG = {'security': {'encrypt_output': True}}\n", encoding="utf-8")
        monkeypatch.setenv("DATA_MASKING_ENCRYPT_OUTPUT", "y")
        assert ConfigLoader().load().security.encrypt_output is True
        monkeypatch.setenv("DATA_MASKING_ENCRYPT_OUTPUT", " No ")
        assert ConfigLoader().load().security.encrypt_output is False

    def test_hash_algorithm_any_case(self, run):
        rc, out, *_ = run({"system": {"hash_algorithm": "SHA256"}})
        assert rc == 0 and "Петренко" not in out

    def test_backup_suffix_with_separator(self, run):
        run()
        rc, _out, stdout, _err = run({"system": {"backup_enabled": True, "backup_suffix": "/x"}},
                                     extra=("--force",))
        assert rc == 1 and "system.backup_suffix" in stdout

    @pytest.mark.parametrize("level", [10, True, "verbose"])
    def test_logging_level(self, run, level):
        rc, _out, _stdout, err = run({"logging": {"level": level}})
        assert rc == 0 and "logging.level must be one of" in err

    @pytest.mark.parametrize("section", [{1: True}, {True: 1}, {"__class__": "x"}])
    def test_non_field_keys(self, run, section):
        rc, _out, _stdout, err = run({"masking_rules": section})
        assert rc == 0 and "have no effect" in err

    def test_non_field_key_unmask(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.py").write_text("CONFIG = {'logging': {1: 2}}\n", encoding="utf-8")
        assert ConfigLoader().load() is not None

    @pytest.mark.parametrize("key, value", [
        ("system", {"hash_digest_size": 2.9}),
        ("validation", {"min_name_length": 2.5}),
    ])
    def test_fractional_int(self, run, key, value):
        rc, _out, stdout, _err = run({key: value})
        assert rc == 1 and "must be an integer" in stdout


class TestSemantics:
    TEXT = "Сержант Петренко Іван Іванович, ІПН 1234567890, дата 01.10.2025.\n"

    def test_skip_types_and_enable_flags(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_ipn": False, "enable_names": False},
                           "router_rules": {"skip_types": ["date"]}}, text=self.TEXT)
        assert rc == 0
        assert "Петренко Іван Іванович" in out and "1234567890" in out and "01.10.2025" in out

    def test_skip_types_still_excludes_enabled_type(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_dates": True, "enable_date_text": True},
                           "router_rules": {"skip_types": ["date"]}}, text=self.TEXT)
        assert rc == 0 and "01.10.2025" in out and "Петренко" not in out

    def test_cli_only_wins_over_enable_flags(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_ipn": False}}, text=self.TEXT,
                          extra=("--only", "ipn"))
        assert rc == 0 and "1234567890" not in out and "Петренко" in out

    def test_env_preserve_case_beats_file(self, run, monkeypatch):
        monkeypatch.setenv("DATA_MASKING_PRESERVE_CASE", "false")
        rc, out, *_ = run({"masking_rules": {"preserve_case": True}},
                          text="СЕРЖАНТ Петренко Іван Іванович прибув.\n")
        assert rc == 0 and not out.startswith(("СЕРЖАНТ", "СТАРШИЙ", "МОЛОДШИЙ"))

    def test_password_generation_string(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.py").write_text(
            "CONFIG = {'security': {'password_generation': 'false'}}\n", encoding="utf-8")
        cfg = ConfigLoader().load()
        assert cfg.security.password_generation.enabled is False
        assert cfg.security.password_generation.min_digits is not None

    def test_password_generation_bad_string(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.py").write_text(
            "CONFIG = {'security': {'password_generation': 'maybe'}}\n", encoding="utf-8")
        with pytest.raises(Exception, match="password_generation.enabled"):
            ConfigLoader().load()

    def test_remask_warn_counted_once(self, run):
        rc, _out, _stdout, err = run(
            {"masking_rules": {"custom_patterns": [{"pattern": "ТЕЛ-\\d{4}", "name": "phone", "action": "warn"}]}},
            text="Зв'язок: ТЕЛ-1234, ТЕЛ-5678.\n", extra=("--re-mask", "3"))
        assert rc == 0 and "'phone': 2 match(es)" in err

    @pytest.mark.parametrize("data", [
        {"exclusions": None, "masking_rules": {}},
        {"system": {"strict_mode": True}, "exclusions": None},
    ])
    def test_empty_section(self, data):
        assert ignored_config_keys(data) == []


class TestDiagnose:
    @pytest.mark.parametrize("content", [
        "{broken", "[1, 2]", '{"mappings": null}', '{"mappings": {"surname": [1]}}', "garbage",
    ])
    def test_bad_file_exit_1(self, tmp_path, monkeypatch, content):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "m.json").write_text(content, encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["diagnose", "m.json"])
        assert diagnose.main() == 1

    def test_compare_without_masked_as(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        entry = {"mappings": {"surname": {"A": {"instances": [1]}}}}
        for name in ("a.json", "b.json"):
            (tmp_path / name).write_text(json.dumps(entry), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["diagnose", "a.json", "b.json"])
        assert diagnose.main() == 0

    def test_compare_bad_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.json").write_text('{"mappings": {}}', encoding="utf-8")
        (tmp_path / "b.json").write_text("{broken", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["diagnose", "a.json", "b.json"])
        assert diagnose.main() == 1
