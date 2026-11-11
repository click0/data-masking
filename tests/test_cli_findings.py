#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки аудиту CLI та вводу-виводу (після 3.1.20).

  - system.encoding: auto читав UTF-16 як cp1251 — нічого не маскувалось,
    exit 0;
  - --only / --exclude не керували номерами документів («довідка № 4567»);
  - unmask вибирав JSON чи текст за суфіксом замаскованого файлу, а mask —
    за суфіксом вхідного; JSON з BOM відхилявся;
  - unmask не дозволяв підняти ліміт розміру понад 100 МБ;
  - security.encrypt_output: true + --password відхилялось;
  - пошкоджений заголовок .enc формату 2, --init-config у неіснуючу теку —
    traceback;
  - пароль не в UTF-8 лишав замаскований файл без mapping;
  - звіт показував запитану кількість проходів --re-mask, а не виконану;
  - «-o» — жорстке посилання на вхід — перезаписувало оригінал;
  - порожній masked_as вставляв оригінал між усіма символами;
  - коди виходу unmask для неправильного використання — 1 замість 2.
"""
import codecs
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking import _textio  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.io import validate_mapping_schema  # noqa: E402

try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
needs_crypto = pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")

DOC = ("Сидоренко Олександр Петрович, ІПН 1234567890, народився 12.05.1990.\r\n"
       "Старший сержант Коваленко Іван Іванович, в/ч А1234.\r\n")


@pytest.fixture
def cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def _config(path: Path, data) -> None:
    path.joinpath("config.py").write_text(f"CONFIG = {data!r}\n", encoding="utf-8")


def _map(path: Path) -> str:
    return str(next(path.glob("masking_map_*")))


class TestEncodingAuto:
    @pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"])
    def test_bom_round_trip(self, cwd, codec):
        bom = "\ufeff".encode(codec)
        _config(cwd, {"system": {"encoding": "auto"}})
        raw = bom + DOC.encode(codec)
        (cwd / "in.txt").write_bytes(raw)
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report"]) == 0
        masked = (cwd / "out.txt").read_bytes()
        assert masked.startswith(bom)
        assert "Сидоренко" not in masked.decode(codec)
        assert unmask_cli.main(["out.txt", "--map", _map(cwd), "-o", "rec.txt"]) == 0
        assert (cwd / "rec.txt").read_bytes() == raw

    def test_nul_is_not_cp1251(self, tmp_path):
        path = tmp_path / "in.txt"
        path.write_bytes(DOC.encode("utf-16-le"))  # без BOM
        with pytest.raises(UnicodeDecodeError, match="NUL"):
            _textio.read_text(path, "auto", ("utf-8", "cp1251", "latin-1"))

    def test_plain_files_unchanged(self, tmp_path):
        path = tmp_path / "in.txt"
        path.write_bytes(DOC.encode("cp1251"))
        assert _textio.read_text(path, "auto", ("utf-8", "cp1251"))[1] == "cp1251"
        path.write_bytes(codecs.BOM_UTF8 + DOC.encode("utf-8"))
        assert _textio.read_text(path, "auto", ("utf-8", "cp1251")) == ("﻿" + DOC, "utf-8")


class TestSelectiveDocumentNumbers:
    TEXT = "Видано довідку № 4567 солдату Коваленку Івану Івановичу.\nРапорт № 891 подано.\n"

    @pytest.mark.parametrize("flags", [("--only", "surname"), ("--exclude", "order_number")])
    def test_document_numbers_follow_orders(self, cwd, flags):
        (cwd / "in.txt").write_text(self.TEXT, encoding="utf-8")
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", *flags]) == 0
        out = (cwd / "out.txt").read_text(encoding="utf-8")
        assert "№ 4567" in out and "№ 891" in out and "Коваленку" not in out


class TestJsonFormat:
    def test_text_written_as_json_name(self, cwd):
        (cwd / "in.txt").write_bytes(DOC.encode("utf-8"))
        assert mask_cli.main(["-i", "in.txt", "-o", "out.json", "--no-report"]) == 0
        assert unmask_cli.main(["out.json", "--map", _map(cwd), "-o", "rec.txt"]) == 0
        assert (cwd / "rec.txt").read_bytes() == DOC.encode("utf-8")

    def test_json_written_as_txt_name(self, cwd):
        data = {"a": "Перший рядок\nСтарший сержант Коваленко Іван Іванович"}
        (cwd / "src.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        assert mask_cli.main(["-i", "src.json", "-o", "masked.txt", "--no-report"]) == 0
        assert unmask_cli.main(["masked.txt", "--map", _map(cwd), "-o", "rec.txt"]) == 0
        assert json.loads((cwd / "rec.txt").read_text(encoding="utf-8")) == data

    def test_json_with_bom(self, cwd):
        data = {"a": "солдат Петренко Іван Іванович"}
        (cwd / "in.json").write_bytes(codecs.BOM_UTF8 + json.dumps(data, ensure_ascii=False).encode("utf-8"))
        assert mask_cli.main(["-i", "in.json", "-o", "out.json", "--no-report"]) == 0
        assert "Петренко" not in (cwd / "out.json").read_text(encoding="utf-8")
        assert unmask_cli.main(["out.json", "--map", _map(cwd), "-o", "rec.json"]) == 0
        assert json.loads((cwd / "rec.json").read_text(encoding="utf-8")) == data


class TestLimitsAndPaths:
    def test_unmask_size_limit_follows_validation(self):
        class Section:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        class Cfg:
            validation = Section(max_input_size_mb=200)
            system = Section(max_file_size_mb=None)
        assert unmask_cli._size_limit(Cfg()) == 200 * 1024 * 1024
        Cfg.system = Section(max_file_size_mb=150)
        assert unmask_cli._size_limit(Cfg()) == 150 * 1024 * 1024

    @needs_crypto
    def test_encrypt_output_with_password(self, cwd):
        _config(cwd, {"security": {"encrypt_output": True}})
        (cwd / "in.txt").write_bytes(DOC.encode("utf-8"))
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--password", "Pw-123456"]) == 0
        assert list(cwd.glob("masking_map_*.enc")) and not list(cwd.glob("masking_map_*.json"))

    def test_password_without_encrypt_still_usage_error(self, cwd):
        (cwd / "in.txt").write_bytes(DOC.encode("utf-8"))
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--password", "x"]) == 2

    @needs_crypto
    def test_non_utf8_password(self, cwd):
        (cwd / "in.txt").write_bytes(DOC.encode("utf-8"))
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--encrypt",
                              "--password", "pa\udcffss"]) == 2
        assert not (cwd / "out.txt").exists()

    @pytest.mark.parametrize("target", ["nodir/c.yaml", "."])
    def test_init_config_bad_target(self, cwd, capsys, target):
        assert mask_cli.main(["--init-config", "-c", target, "--force"]) == 1
        assert "cannot write" in capsys.readouterr().out

    def test_report_shows_executed_passes(self, cwd):
        (cwd / "in.txt").write_bytes(DOC.encode("utf-8"))
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--re-mask", "50"]) == 0
        report = next(cwd.glob("masking_report_*.txt")).read_text(encoding="utf-8")
        assert "(10 проходів)" in report

    @pytest.mark.skipif(not hasattr(os, "link"), reason="no hard links")
    def test_hard_link_to_input(self, cwd):
        (cwd / "in.txt").write_bytes(DOC.encode("utf-8"))
        os.link(cwd / "in.txt", cwd / "link.txt")
        assert mask_cli.main(["-i", "in.txt", "-o", "link.txt", "--force", "--no-report"]) == 2
        assert (cwd / "in.txt").read_bytes() == DOC.encode("utf-8")


class TestUnmaskInputs:
    @pytest.mark.parametrize("mapping", [
        {"version": "2.1", "mappings": {"surname": {"Коваленко": {"masked_as": "", "instances": [1]}}}},
        {"mappings": {"surname": {"Коваленко": ""}}},
    ])
    def test_empty_mask_rejected(self, mapping):
        with pytest.raises(ValueError, match="empty"):
            validate_mapping_schema(mapping)

    def test_usage_exit_codes(self, cwd, monkeypatch):
        (cwd / "masked.txt").write_text("x", encoding="utf-8")
        assert unmask_cli.main(["masked.txt"]) == 2
        (cwd / "m.json").write_text('{"version": "2.1", "mappings": {}}', encoding="utf-8")
        monkeypatch.delenv("NO_SUCH_VAR", raising=False)
        assert unmask_cli.main(["masked.txt", "--map", "m.json", "--password-env", "NO_SUCH_VAR"]) == 2


class TestEncHeader:
    @needs_crypto
    @pytest.mark.parametrize("header", [
        {"v": 2, "kdf": "scrypt", "salt_length": 16},
        {"v": 2, "kdf": "pbkdf2", "salt_length": 16, "iterations": [1]},
        {"v": 2, "kdf": "pbkdf2", "salt_length": 16, "iterations": 1e300},
    ])
    def test_crafted_header_is_a_file_error(self, cwd, capsys, header):
        hb = json.dumps(header).encode("ascii")
        (cwd / "m.enc").write_bytes(b"DMENC2" + len(hb).to_bytes(2, "big") + hb + os.urandom(16 + 12 + 64))
        (cwd / "masked.txt").write_text("x", encoding="utf-8")
        assert unmask_cli.main(["masked.txt", "--map", "m.enc", "--password", "pw", "-o", "r.txt"]) == 1
        assert "Traceback" not in capsys.readouterr().err
