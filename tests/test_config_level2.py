#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Опції конфігурації рівня 2 (v3.0.28) — див. docs/TODO-config-options.md.

Конфігурація — через ./config.py (без pyyaml); шифрування — зі skipif.
"""
import os
import string
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking import _fsutil  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.mask_personal import ipn_checksum, is_valid_ipn  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402

try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
needs_crypto = pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")

VALID_IPN = "318471069" + str(ipn_checksum("318471069"))
TEXT = (
    f"капітан Петренко Іван Іванович, ІПН {VALID_IPN}\n"
    "у довідках №273; згідно з наказом командира від 12.03.2024 № 125; рапорт №44\n"
    "сержант Коваль П.П.\n"
)


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)

    def _run(config=None, extra=(), text=TEXT, out="out.txt", raw=None):
        if config is not None:
            (tmp_path / "config.py").write_text(f"CONFIG = {config!r}\n", encoding="utf-8")
        (tmp_path / "in.txt").write_bytes(raw if raw is not None else text.encode("utf-8"))
        rc = mask_cli.main(["-i", "in.txt", "-o", out, "--no-report", *extra])
        cap = capsys.readouterr()
        path = tmp_path / out
        result = path.read_bytes() if path.exists() else b""
        return rc, result, cap.out, cap.err

    return _run


def _txt(b: bytes) -> str:
    return b.decode("utf-8")


# ---------------------------------------------------------------------------
# 13. Склад згенерованого пароля
# ---------------------------------------------------------------------------
class TestPasswordComposition:
    def _password(self, config):
        return mask_cli.generate_password_from_config(mask_cli.ConfigLoader().load() if config is None else config)

    def _cfg(self, tmp_path, monkeypatch, data):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.py").write_text(f"CONFIG = {data!r}\n", encoding="utf-8")
        return mask_cli.ConfigLoader().load()

    def test_minimums(self, tmp_path, monkeypatch):
        cfg = self._cfg(tmp_path, monkeypatch, {"security": {"password_generation": {
            "min_uppercase": 5, "min_lowercase": 5, "min_digits": 5, "min_special": 5}}})
        for _ in range(20):
            pw = mask_cli.generate_password_from_config(cfg)
            assert len(pw) == 24
            assert sum(c in string.ascii_uppercase for c in pw) >= 5
            assert sum(c in string.ascii_lowercase for c in pw) >= 5
            assert sum(c in string.digits for c in pw) >= 5
            assert sum(c in "!@#$%^&*" for c in pw) >= 5

    @pytest.mark.parametrize("section", ["security", "top"])
    def test_no_special_chars(self, tmp_path, monkeypatch, section):
        data = ({"security": {"password_generation": {"use_special_chars": False}}} if section == "security"
                else {"password_generation": {"use_special_chars": False}})
        cfg = self._cfg(tmp_path, monkeypatch, data)
        for _ in range(20):
            assert not any(c in "!@#$%^&*" for c in mask_cli.generate_password_from_config(cfg))

    @pytest.mark.parametrize("pg", [
        {"min_digits": 30},                                   # більше за довжину
        {"use_special_chars": False, "min_special": 1},       # суперечність
        {"min_uppercase": -1},
    ])
    def test_impossible_policy_is_config_error(self, run, pg):
        rc, out, stdout, _ = run({"security": {"password_generation": pg}})
        assert rc == 1 and out == b""


# ---------------------------------------------------------------------------
# 14–15. Логування
# ---------------------------------------------------------------------------
class TestLogging:
    def test_custom_file_format(self, run, tmp_path):
        rc, *_ = run({"logging": {"file": "m.log", "format": "CUSTOM|%(levelname)s|%(message)s"}})
        assert rc == 0
        assert "CUSTOM|INFO|" in (tmp_path / "m.log").read_text(encoding="utf-8")

    def test_bad_format_falls_back(self, run, tmp_path):
        rc, _, _, err = run({"logging": {"file": "m.log", "format": "%(nosuchfield)q"}})
        assert rc == 0 and "logging.format is invalid" in err

    def test_rotation(self, run, tmp_path):
        import logging.handlers
        rc, *_ = run({"logging": {"file": "m.log", "max_log_size_mb": 1, "log_rotation_count": 3}})
        assert rc == 0
        handlers = [h for h in logging.getLogger("data_masking").handlers
                    if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert handlers and handlers[0].maxBytes == 1024 * 1024 and handlers[0].backupCount == 3

    def test_performance(self, run, tmp_path):
        rc, *_ = run({"logging": {"file": "m.log", "log_performance": True}})
        assert "Performance: read" in (tmp_path / "m.log").read_text(encoding="utf-8")

    def test_sensitive_data_hidden_by_default(self, capsys, monkeypatch):
        from datamasking.masking import mask_military
        from tests.test_initials import make_masking_dict

        def boom(_):
            raise ValueError("forced")
        monkeypatch.setattr(mask_military, "get_deterministic_seed", boom)
        _cfg.DEBUG_MODE = True
        assert mask_military.mask_date("12.03.2024", make_masking_dict(), {}) == "12.03.2024"
        out = capsys.readouterr().out
        assert "error parsing a date" in out and "12.03.2024" not in out
        _cfg.LOG_SENSITIVE_DATA = True
        mask_military.mask_date("12.03.2024", make_masking_dict(), {})
        assert "12.03.2024" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 16. Кодування
# ---------------------------------------------------------------------------
class TestEncoding:
    SRC = "капітан Петренко Іван Іванович, ІПН 1234567890\n"

    def test_cp1251_rejected_by_default(self, run):
        rc, out, stdout, _ = run({}, raw=self.SRC.encode("cp1251"))
        assert rc == 1 and out == b""

    @pytest.mark.parametrize("enc", ["cp1251", "auto", "CP1251"])
    def test_cp1251_roundtrip(self, run, tmp_path, enc):
        rc, out, stdout, _ = run({"system": {"encoding": enc}}, raw=self.SRC.encode("cp1251"))
        assert rc == 0
        text = out.decode("cp1251")
        assert "Петренко" not in text and "Input encoding: cp1251" in stdout
        mapping = next(tmp_path.glob("masking_map_*.json"))
        # unmask без жодної конфігурації: кодування — з mapping
        (tmp_path / "config.py").unlink()
        assert unmask_cli.main(["out.txt", "--map", mapping.name, "--output", "rec.txt"]) == 0
        assert (tmp_path / "rec.txt").read_bytes() == self.SRC.encode("cp1251")

    def test_utf8_input_unchanged_mapping(self, run, tmp_path):
        rc, *_ = run({"system": {"encoding": "auto"}}, raw=self.SRC.encode("utf-8"))
        import json
        mapping = json.loads(next(tmp_path.glob("masking_map_*.json")).read_text(encoding="utf-8"))
        assert rc == 0 and "input_encoding" not in mapping

    @pytest.mark.parametrize("cfg", [
        {"system": {"encoding": "no-such-codec"}},
        {"system": {"encoding": "cp1252"}},                    # не в allowed_encodings
        {"validation": {"allowed_encodings": []}, "system": {"encoding": "auto"}},
    ])
    def test_bad_settings(self, run, cfg):
        rc, out, *_ = run(cfg)
        assert rc == 1 and out == b""


# ---------------------------------------------------------------------------
# 17–18. Прізвища / по батькові окремо; номери документів
# ---------------------------------------------------------------------------
class TestPibAndDocumentFlags:
    def test_surnames_off(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_surnames": False}})
        text = _txt(out)
        assert "Петренко" in text and "Іван Іванович" not in text and "Коваль" in text

    def test_patronymics_off(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_patronymics": False}})
        text = _txt(out)
        assert "Петренко" not in text and "Іванович" in text

    def test_names_off_legacy_turns_off_all(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_names": False}})
        text = _txt(out)
        assert "Петренко Іван Іванович" in text and "Коваль П.П." in text

    def test_only_surnames_via_cli(self, run):
        rc, out, *_ = run({}, extra=["--only", "surname"])
        text = _txt(out)
        assert "Петренко" not in text and "Іван Іванович" in text

    def test_exclude_patronymic_now_works(self, run):
        rc, out, *_ = run({}, extra=["--exclude", "patronymic"])
        text = _txt(out)
        assert "Петренко" not in text and "Іванович" in text

    def test_names_group_is_whole_pib(self, run):
        rc, out, *_ = run({}, extra=["--only", "names"])
        assert "Петренко" not in _txt(out) and "Іванович" not in _txt(out)

    def test_document_numbers_separate_from_orders(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_document_numbers": False}})
        text = _txt(out)
        assert "№273" in text and "№44" in text and "№ 125" not in text

    def test_orders_off_documents_on(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_orders": False, "enable_document_numbers": True}})
        text = _txt(out)
        assert "№ 125" in text and "№273" not in text

    def test_documents_follow_orders_by_default(self, run):
        rc, out, *_ = run({"masking_rules": {"enable_orders": False}})
        text = _txt(out)
        assert "№ 125" in text and "№273" in text


# ---------------------------------------------------------------------------
# 19–20. Суворий режим; тимчасові файли
# ---------------------------------------------------------------------------
class TestStrictAndTemp:
    @pytest.mark.parametrize("section", ["system", "validation"])
    def test_strict_unknown_key_is_error(self, run, section):
        rc, out, stdout, _ = run({section: {"strict_mode": True}, "masking_rules": {"enable_rankz": True}})
        assert rc == 1 and out == b"" and "strict_mode" in stdout

    def test_strict_config_warning_is_error(self, run):
        rc, out, stdout, _ = run({"system": {"strict_mode": True, "version": "v99"}})
        assert rc == 1 and out == b"" and "config is for version v99" in stdout

    def test_strict_unmask_unrestored(self, run, tmp_path, capsys):
        rc, *_ = run({})
        mapping = next(tmp_path.glob("masking_map_*.json"))
        # прибираємо одне значення з тексту — воно не відновиться
        out = (tmp_path / "out.txt").read_text(encoding="utf-8").split("\n")
        (tmp_path / "out.txt").write_text("\n".join(out[1:]), encoding="utf-8")
        (tmp_path / "config.py").write_text("CONFIG = {'system': {'strict_mode': True}}\n", encoding="utf-8")
        assert unmask_cli.main(["out.txt", "--map", mapping.name, "--output", "rec.txt"]) == 1
        assert "were not restored" in capsys.readouterr().out
        assert (tmp_path / "rec.txt").exists()

    def test_temp_dir(self, run, tmp_path):
        import tempfile
        (tmp_path / "tmpd").mkdir()
        rc, *_ = run({"system": {"temp_dir": str(tmp_path / "tmpd")}})
        assert rc == 0 and tempfile.tempdir == str(tmp_path / "tmpd")
        rc, out, *_ = run({"system": {"temp_dir": str(tmp_path / "missing")}}, out="o2.txt")
        assert rc == 1 and out == b""

    def test_secure_delete_overwrites_failed_temp(self, tmp_path, monkeypatch):
        seen = {}
        real_replace = os.replace

        def failing_replace(src, dst):
            seen["content"] = Path(src).read_bytes()
            raise OSError("boom")
        monkeypatch.setattr(os, "replace", failing_replace)
        opened = []
        real_open = open

        def spy_open(file, mode="r", *a, **kw):
            if "r+b" in mode:
                opened.append(file)
            return real_open(file, mode, *a, **kw)
        monkeypatch.setattr("builtins.open", spy_open)
        _fsutil.SECURE_DELETE_TEMP = True
        with pytest.raises(OSError):
            _fsutil.atomic_write_private(tmp_path / "m.json", b"secret mapping")
        assert opened, "temp file was not overwritten"
        assert not list(tmp_path.glob(".m.json.*"))
        monkeypatch.setattr(os, "replace", real_replace)

    def test_secure_delete_off(self, run):
        rc, *_ = run({"security": {"secure_delete_temp": False}})
        assert rc == 0 and _fsutil.SECURE_DELETE_TEMP is False


# ---------------------------------------------------------------------------
# 21–22. Контрольна сума ІПН; розмір дайджесту
# ---------------------------------------------------------------------------
class TestIpnAndDigest:
    def test_checksum_off_by_default_keeps_masks(self, run):
        rc, out, *_ = run({})
        ipn = next(w.strip(",") for w in _txt(out).split() if w.strip(",").isdigit() and len(w.strip(",")) == 10)
        assert ipn != VALID_IPN and ipn[-1] == VALID_IPN[-1]

    def test_checksum_on(self, run):
        rc, out, *_ = run({"validation": {"validate_ipn_checksum": True}})
        ipn = next(w.strip(",") for w in _txt(out).split() if w.strip(",").isdigit() and len(w.strip(",")) == 10)
        assert ipn != VALID_IPN and is_valid_ipn(ipn)

    def test_digest_64_is_default(self, run):
        rc, out_default, *_ = run({})
        rc, out_64, *_ = run({"system": {"hash_digest_size": 64}}, out="o2.txt")
        assert out_default == out_64

    def test_digest_changes_masks(self, run):
        rc, out_default, *_ = run({})
        rc, out_8, *_ = run({"system": {"hash_digest_size": 8}}, out="o2.txt")
        assert rc == 0 and out_default != out_8

    @pytest.mark.parametrize("cfg", [
        {"system": {"hash_digest_size": 0}},
        {"system": {"hash_digest_size": 65}},
        {"system": {"hash_algorithm": "sha256", "hash_digest_size": 8}},
    ])
    def test_bad_digest(self, run, cfg):
        rc, out, *_ = run(cfg)
        assert rc == 1 and out == b""


# ---------------------------------------------------------------------------
# 23–25. Довжина імен; ініціали; суворий формат ПІБ
# ---------------------------------------------------------------------------
class TestNameRecognition:
    def test_min_name_length_two(self, run):
        rc, out, *_ = run({"validation": {"min_name_length": 2}}, text="капітан Ус Іван Іванович\n")
        assert "Ус " not in _txt(out)

    def test_default_min_length_keeps_two_letter_words(self, run):
        rc, out, *_ = run({}, text="капітан Ус Іван Іванович\n")
        assert rc == 0  # поведінка за замовчуванням не змінилась (3 літери)

    def test_max_name_length(self, run):
        long_name = "Петренко" + "о" * 20
        rc, out, *_ = run({"validation": {"max_name_length": 10}}, text=f"капітан {long_name} Іван Іванович\n")
        assert long_name in _txt(out)

    def test_bad_lengths(self, run):
        rc, out, *_ = run({"validation": {"min_name_length": 10, "max_name_length": 5}})
        assert rc == 1 and out == b""

    def test_initials_off(self, run):
        text = "сержант Коваль П.П.\nдокумент підписав Ткач О.І.\n"
        rc, out, _, err = run({"validation": {"allow_abbreviated_patronymic": False}}, text=text)
        result = _txt(out)
        assert "П.П." in result and "Ткач О.І." in result     # ініціали і ПІБ без звання — відкриті
        assert "Коваль" not in result                         # прізвище після звання — маскується
        assert "allow_abbreviated_patronymic is false" in err

    def test_strict_pib_format(self, run):
        text = "капітан Петренко Іван Іванович\nрядовий Коваль прибув\nсержант Ткач Олег\n"
        rc, out, _, err = run({"validation": {"strict_pib_format": True}}, text=text)
        result = _txt(out)
        assert "Петренко" not in result
        assert "Коваль" in result and "Ткач Олег" in result
        assert "strict_pib_format is true" in err
