#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Опції конфігурації рівня 1 (v3.0.27) — див. docs/TODO-config-options.md.

Конфігурація задається через ./config.py (словник CONFIG), тож тести не
потребують pyyaml і йдуть і в core-only CI. Тести шифрування — зі skipif.
"""
import os
import stat
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402

try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
needs_crypto = pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")

TEXT = (
    "капітан Петренко Іван Іванович, ІПН 1234567890, 12.05.1985 р.н.\n"
    "наказ від \"06\" жовтня 2025 року, від 12.03.2024\n"
)


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)

    def _run(config=None, extra=(), text=TEXT, out="out.txt"):
        if config is not None:
            (tmp_path / "config.py").write_text(f"CONFIG = {config!r}\n", encoding="utf-8")
        (tmp_path / "in.txt").write_bytes(text.encode("utf-8"))
        rc = mask_cli.main(["-i", "in.txt", "-o", out, "--no-report", *extra])
        cap = capsys.readouterr()
        path = tmp_path / out
        result = path.read_bytes().decode("utf-8") if path.exists() else ""
        return rc, result, cap.out, cap.err

    return _run


# ---------------------------------------------------------------------------
# 1. Аліаси вже діючих ключів
# ---------------------------------------------------------------------------
class TestAliases:
    def test_masking_rules_preserve_case_overrides_system(self, run):
        rc, *_ = run({"system": {"preserve_case": True}, "masking_rules": {"preserve_case": False}})
        assert rc == 0 and _cfg.PRESERVE_CASE is False

    def test_system_max_file_size_mb_smaller_limit_wins(self, run):
        big = "капітан Петренко Іван Іванович\n" * 40000  # ≈ 1.6 МБ
        rc, out, stdout, _ = run({"system": {"max_file_size_mb": 1}}, text=big)
        assert rc == 1 and out == ""
        rc, *_ = run({"system": {"max_file_size_mb": 5}, "validation": {"max_input_size_mb": 1}}, text=big)
        assert rc == 1  # менший ліміт (validation) теж діє

    def test_router_only_types(self, run):
        rc, out, stdout, _ = run({"router_rules": {"only_types": ["ipn"]}})
        assert rc == 0
        assert "1234567890" not in out and "Петренко" in out
        assert "router_rules.only_types" in stdout

    def test_router_skip_types(self, run):
        rc, out, *_ = run({"router_rules": {"skip_types": ["dates"]}})
        assert rc == 0
        assert "12.05.1985" in out and "\"06\" жовтня 2025" in out and "Петренко" not in out

    def test_router_both_is_error(self, run):
        rc, out, *_ = run({"router_rules": {"only_types": ["ipn"], "skip_types": ["dates"]}})
        assert rc == 1 and out == ""

    def test_cli_selection_wins_over_router(self, run):
        rc, out, *_ = run({"router_rules": {"only_types": ["ipn"]}}, extra=["--only", "names"])
        assert rc == 0 and "Петренко" not in out and "1234567890" in out


# ---------------------------------------------------------------------------
# 2–4, 12. Пароль: змінна, без автогенерації, файл, перевірка значень
# ---------------------------------------------------------------------------
@needs_crypto
class TestPassword:
    def test_custom_env_var_used_for_mask_and_unmask(self, run, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("MY_MASK_PW", "secret-pass-1")
        cfg = {"security": {"password_env_var": "MY_MASK_PW"}}
        rc, out, _, err = run(cfg, extra=["--encrypt"])
        assert rc == 0 and "Generated password" not in err
        enc = next(tmp_path.glob("masking_map_*.enc"))
        rc = unmask_cli.main(["out.txt", "--map", enc.name, "--output", "rec.txt"])
        assert rc == 0
        assert (tmp_path / "rec.txt").read_bytes().decode("utf-8") == TEXT

    def test_top_level_env_var_from_old_template(self, run, monkeypatch):
        monkeypatch.setenv("OLD_PW", "secret-pass-2")
        rc, _, _, err = run({"password_generation": {"env_var": "OLD_PW"}}, extra=["--encrypt"])
        assert rc == 0 and "Generated password" not in err

    @pytest.mark.parametrize("cfg", [
        {"security": {"auto_generate_password": False}},
        {"security": {"password_generation": {"enabled": False}}},
        {"password_generation": {"enabled": False}},
    ])
    def test_generation_disabled_requires_password(self, run, tmp_path, cfg):
        rc, out, stdout, _ = run(cfg, extra=["--encrypt"])
        assert rc == 2 and out == ""
        assert "needs a password" in stdout
        assert not list(tmp_path.glob("masking_map_*"))

    def test_longest_configured_length_wins(self, run):
        rc, _, _, err = run({"security": {"password_generation": {"length": 40}}}, extra=["--encrypt"])
        assert rc == 0
        lines = err.strip().splitlines()
        password = lines[lines.index(next(ln for ln in lines if "Generated password" in ln)) + 1].strip()
        assert len(password) == 40

    def test_password_file(self, run, tmp_path):
        rc, _, _, err = run({"security": {"password_file": "pw.txt"}}, extra=["--encrypt"])
        assert rc == 0 and "saved to pw.txt" in err
        pw = (tmp_path / "pw.txt").read_text(encoding="utf-8").strip()
        assert len(pw) == 24 and pw in err
        if os.name == "posix":
            assert stat.S_IMODE((tmp_path / "pw.txt").stat().st_mode) == 0o600
        # уже існує — без --force помилка, нічого не записано
        rc, out, stdout, _ = run({"security": {"password_file": "pw.txt"}}, extra=["--encrypt"], out="o2.txt")
        assert rc == 2 and "already exists" in stdout and out == ""
        assert (tmp_path / "pw.txt").read_text(encoding="utf-8").strip() == pw

    def test_password_file_ignored_when_password_given(self, run, tmp_path, monkeypatch):
        monkeypatch.setenv("DATA_MASKING_PASSWORD", "given-pass")
        rc, *_ = run({"security": {"password_file": "pw.txt"}}, extra=["--encrypt"])
        assert rc == 0 and not (tmp_path / "pw.txt").exists()


class TestSingleValueKeys:
    @pytest.mark.parametrize("cfg,needle", [
        ({"security": {"encryption_algorithm": "AES-128-CBC"}}, "encryption_algorithm"),
        ({"security": {"password_generation": {"algorithm": "random"}}}, "password_generation.algorithm"),
        ({"remask": {"chain_format": "yaml"}}, "chain_format"),
    ])
    def test_unsupported_value_is_error(self, run, cfg, needle):
        rc, out, stdout, _ = run(cfg)
        assert rc == 1 and out == "" and needle in stdout

    def test_supported_values_case_insensitive(self, run):
        rc, *_ = run({"security": {"encryption_algorithm": "aes-256-gcm",
                                   "password_generation": {"algorithm": "SECRETS"}},
                      "remask": {"chain_format": "JSON"}})
        assert rc == 0


# ---------------------------------------------------------------------------
# 5. Межі розпізнавання дат
# ---------------------------------------------------------------------------
class TestDateRange:
    def test_min_year_leaves_older_dates(self, run):
        rc, out, *_ = run({"validation": {"min_date_year": 2000}})
        assert rc == 0 and "12.05.1985" in out and "12.03.2024" not in out

    def test_range_off_masks_any_year(self, run):
        rc, out, *_ = run({"validation": {"validate_date_range": False}}, text="дата 01.02.1850\n")
        assert rc == 0 and "01.02.1850" not in out

    @pytest.mark.parametrize("cfg", [
        {"validation": {"min_date_year": 2050, "max_date_year": 2000}},
        {"validation": {"max_date_year": "скоро"}},
        {"validation": {"min_date_year": 0}},
    ])
    def test_bad_range_is_error(self, run, cfg):
        rc, out, *_ = run(cfg)
        assert rc == 1 and out == ""


# ---------------------------------------------------------------------------
# 6–7. Розірвані звання; текстові дати окремо
# ---------------------------------------------------------------------------
class TestEngineToggles:
    def test_rank_line_break_fix_off(self, run, monkeypatch):
        from datamasking.masking import engine
        calls = []
        monkeypatch.setattr(engine, "normalize_broken_ranks", lambda t: calls.append(t) or t)
        run({"masking_rules": {"rank_line_break_fix": False}})
        assert calls == []
        run({"masking_rules": {"rank_line_break_fix": True}}, out="o2.txt")
        assert calls

    def test_date_text_off_numeric_on(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_date_text": False}})
        assert "\"06\" жовтня 2025" in out and "12.03.2024" not in out

    def test_date_text_on_numeric_off(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_dates": False, "enable_date_text": True}})
        assert "\"06\" жовтня 2025" not in out and "12.03.2024" in out

    def test_date_text_follows_dates_by_default(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_dates": False}})
        assert "\"06\" жовтня 2025" in out and "12.03.2024" in out


# ---------------------------------------------------------------------------
# 8. Версія конфігурації
# ---------------------------------------------------------------------------
class TestVersion:
    def test_newer_major_warns(self, run):
        rc, _, _, err = run({"system": {"version": "v9.1.0"}})
        assert rc == 0 and "config is for version v9.1.0" in err

    @pytest.mark.parametrize("v", ["v2.6.0", "3.0.0", "", "unknown"])
    def test_same_or_older_silent(self, run, v):
        rc, _, _, err = run({"system": {"version": v}})
        assert rc == 0 and "config is for version" not in err


# ---------------------------------------------------------------------------
# 9. Логування
# ---------------------------------------------------------------------------
class TestLogging:
    def test_disabled(self, run, monkeypatch):
        seen = []
        monkeypatch.setattr(mask_cli, "setup_logging", lambda **kw: seen.append(kw))
        run({"logging": {"enabled": False}})
        assert seen == []

    def test_cli_flag_overrides_disabled(self, run, monkeypatch, tmp_path):
        rc, *_ = run({"logging": {"enabled": False}}, extra=["--log-file", "cli.log"])
        assert rc == 0 and (tmp_path / "cli.log").exists()

    def test_file_only(self, run, tmp_path):
        rc, _, _, err = run({"logging": {"log_to_console": False, "file": "m.log"}})
        assert rc == 0
        assert "Masking completed" in (tmp_path / "m.log").read_text(encoding="utf-8")
        assert "Masking completed" not in err

    def test_log_to_file_false_ignores_file(self, run, tmp_path):
        rc, *_ = run({"logging": {"file": "m.log", "log_to_file": False}})
        assert rc == 0 and not (tmp_path / "m.log").exists()

    def test_log_to_file_true_without_file_warns(self, run):
        rc, _, _, err = run({"logging": {"log_to_file": True}})
        assert rc == 0 and "logging.file is not set" in err

    def test_statistics_off(self, run):
        rc, _, stdout, _ = run({"logging": {"log_statistics": False}})
        assert rc == 0 and "📊" not in stdout and "Файли збережено" in stdout
        rc, _, stdout, _ = run({}, out="o2.txt")
        assert "📊" in stdout


# ---------------------------------------------------------------------------
# 10. Резервна копія вихідного файлу
# ---------------------------------------------------------------------------
class TestBackup:
    def test_backup_before_force_overwrite(self, run, tmp_path):
        (tmp_path / "out.txt").write_bytes(b"old content")
        rc, out, *_ = run({"system": {"backup_enabled": True, "backup_suffix": ".prev"}}, extra=["--force"])
        assert rc == 0 and out != "old content"
        assert (tmp_path / "out.txt.prev").read_bytes() == b"old content"

    def test_no_backup_by_default(self, run, tmp_path):
        (tmp_path / "out.txt").write_bytes(b"old content")
        rc, *_ = run({}, extra=["--force"])
        assert rc == 0 and not list(tmp_path.glob("out.txt.*"))


# ---------------------------------------------------------------------------
# 11. Перемаскування
# ---------------------------------------------------------------------------
class TestRemask:
    def test_disabled(self, run):
        rc, out, stdout, _ = run({"remask": {"enabled": False}}, extra=["--re-mask", "2"])
        assert rc == 1 and out == "" and "remask.enabled" in stdout

    def test_max_passes_caps(self, run):
        rc, _, stdout, _ = run({"remask": {"max_passes": 3}}, extra=["--re-mask", "5"])
        assert rc == 0 and "capped at 3" in stdout

    @pytest.mark.parametrize("n", [1, 11, "many"])
    def test_bad_max_passes(self, run, n):
        rc, out, *_ = run({"remask": {"max_passes": n}})
        assert rc == 1 and out == ""
