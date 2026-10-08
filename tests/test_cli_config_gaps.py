#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.10 — конфігурація, CLI та обробка помилок (аудит, частина 4):

  - рядок "false"/"true" у YAML приводиться до bool (а не bool("false") → True);
  - невалідні hash_algorithm / allowed_encodings / бите mapping — чиста
    помилка, а не traceback; null → значення за замовчуванням;
  - --password без --encrypt — помилка використання;
  - data-unmask: -o не перезаписує файли без --force і не збігається з
    mapping; результат 0600; logging.* з конфігурації; JSON зі статистикою
    та --to-version; автопошук .enc і ланцюгів; mapping без версії;
  - звіт при --re-mask — за першим проходом; diagnose повертає код виходу.
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras.config import Config  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.engine import unmask_json_chain_with_stats  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from datamasking.unmasking.io import validate_mapping_schema  # noqa: E402

TEXT = "капітан Коваль Тетяна Сергіївна, ІПН 1234567890\nмайор Іванов Петро Олегович\n"


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "in.txt").write_text(TEXT, encoding="utf-8")
    return tmp_path


def _config(workdir, data):
    (workdir / "config.py").write_text(f"CONFIG = {data!r}\n", encoding="utf-8")


def _mask(extra=()):
    return mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--force", "--no-local-config", *extra])


def _mapping(workdir):
    maps = sorted(workdir.glob("masking_map_*.json")) + sorted(workdir.glob("masking_chain_*.json"))
    return maps[-1]


class TestTypeCoercion:
    def test_string_false_disables(self):
        cfg = Config.from_dict({"masking_rules": {"enable_ranks": "false"}, "security": {"encrypt_output": "False"},
                                "system": {"strict_mode": "true", "max_file_size_mb": "50"}})
        assert cfg.masking_rules.enable_ranks is False and cfg.security.encrypt_output is False
        assert cfg.system.strict_mode is True and cfg.system.max_file_size_mb == 50

    def test_invalid_bool_string_is_error(self):
        with pytest.raises(ValueError, match="masking_rules.enable_ranks must be true or false"):
            Config.from_dict({"masking_rules": {"enable_ranks": "maybe"}})

    def test_cli_string_false(self, workdir, capsys):
        _config(workdir, {"masking_rules": {"enable_ranks": "false"}, "security": {"encrypt_output": "false"}})
        assert _mask() == 0
        out = (workdir / "out.txt").read_text(encoding="utf-8")
        assert "капітан" in out and not list(workdir.glob("*.enc"))


class TestConfigErrors:
    @pytest.mark.parametrize("data,fragment", [
        ({"system": {"hash_algorithm": "md6"}}, "hash_algorithm"),
        ({"validation": {"allowed_encodings": True}}, "allowed_encodings"),
        ({"validation": {"max_input_size_mb": "abc"}}, "max_input_size_mb"),
        ({"masking_rules": {"surname_prefix_length": True}}, "surname_prefix_length"),
        ({"security": {"password_file": True}, "encrypt_output": False}, "password_file"),
    ])
    def test_clean_error_no_traceback(self, workdir, capsys, data, fragment):
        extra = []
        if "password_file" in str(data):
            pytest.importorskip("cryptography")  # --encrypt потребує cryptography
            data = {"security": {"password_file": True}}
            extra = ["--encrypt"]
        _config(workdir, data)
        rc = _mask(extra)
        out = capsys.readouterr()
        assert rc in (1, 2)
        assert "Traceback" not in out.out + out.err
        assert fragment in out.out + out.err

    def test_null_means_default(self, workdir):
        _config(workdir, {"remask": {"max_passes": None}, "validation": {"min_date_year": None, "max_date_year": None}})
        assert _mask() == 0


class TestMaskCliFlags:
    def test_password_without_encrypt_is_usage_error(self, workdir, capsys):
        assert _mask(["--password", "secret"]) == 2
        assert "--encrypt" in capsys.readouterr().out
        assert not list(workdir.glob("masking_map_*"))

    def test_both_password_flags(self, workdir, capsys):
        assert _mask(["--encrypt", "--password", "a", "--password-env", "X"]) == 2

    def test_short_c_flag(self, workdir):
        (workdir / "c.py").write_text("CONFIG = {}\n", encoding="utf-8")
        pytest.importorskip("yaml")
        (workdir / "c.yaml").write_text("masking_rules:\n  enable_ranks: false\n", encoding="utf-8")
        assert _mask(["-c", "c.yaml"]) == 0
        assert "капітан" in (workdir / "out.txt").read_text(encoding="utf-8")

    def test_remask_report_counts_first_pass(self, workdir):
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--re-mask", "5", "--no-local-config"])
        assert rc == 0
        report = sorted(workdir.glob("masking_report_*.txt"))[-1].read_text(encoding="utf-8")
        m = re.search(r"УНІКАЛЬНИХ[^\n]*?(\d+)", report)
        assert m and int(m.group(1)) < 20, report[:800]


class TestUnmaskCli:
    def _mask_and_map(self, workdir, extra=()):
        assert _mask(extra) == 0
        return _mapping(workdir)

    def test_output_safety(self, workdir, capsys):
        mapping = self._mask_and_map(workdir)
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "-o", str(mapping), "--no-local-config"]) == 2
        json.loads(mapping.read_text(encoding="utf-8"))  # mapping неушкоджений
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "-o", "out.txt", "--no-local-config"]) == 2
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "-o", "rec.txt", "--no-local-config"]) == 0
        if os.name != "nt":
            assert (workdir / "rec.txt").stat().st_mode & 0o777 == 0o600
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "-o", "rec.txt", "--no-local-config"]) == 2
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "-o", "rec.txt", "--force", "--no-local-config"]) == 0
        assert (workdir / "rec.txt").read_text(encoding="utf-8") == TEXT

    def test_default_output_name_has_suffix(self, workdir):
        mapping = self._mask_and_map(workdir)
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "--no-local-config"]) == 0
        names = [p.name for p in workdir.glob("input_recovery_*.txt")]
        assert names and re.fullmatch(r"input_recovery_\d{8}_\d{6}_\d{3}\.txt", names[0])

    @pytest.mark.parametrize("extra", [[], ["--re-mask", "2"]])
    def test_auto_map_lookup(self, workdir, extra):
        assert mask_cli.main(["-i", "in.txt", "--no-report", "--no-local-config", *extra]) == 0
        out = sorted(workdir.glob("output_*.txt"))[-1]
        assert unmask_cli.main([str(out), "-o", "rec.txt", "--no-local-config"]) == 0
        assert (workdir / "rec.txt").read_text(encoding="utf-8") == TEXT

    def test_logging_from_config(self, workdir, capsys):
        mapping = self._mask_and_map(workdir)
        _config(workdir, {"logging": {"level": "DEBUG", "file": "um.log"}})
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "-o", "rec.txt", "--no-local-config"]) == 0
        assert (workdir / "um.log").exists()
        _config(workdir, {"logging": {"enabled": False}})
        capsys.readouterr()
        assert unmask_cli.main(["out.txt", "--map", str(mapping), "-o", "rec2.txt", "--no-local-config"]) == 0
        assert "INFO" not in capsys.readouterr().err

    def test_size_limit_from_config(self, workdir, capsys):
        mapping = self._mask_and_map(workdir)
        (workdir / "big.txt").write_text(TEXT * 20000, encoding="utf-8")  # > 1 МБ
        _config(workdir, {"validation": {"max_input_size_mb": 1}})
        assert unmask_cli.main(["big.txt", "--map", str(mapping), "-o", "rec.txt", "--no-local-config"]) == 1
        assert "exceeds" in capsys.readouterr().out

    def test_json_strict_and_to_version(self, workdir, capsys):
        src = {"a": TEXT.splitlines()[0], "b": [TEXT.splitlines()[1]]}
        (workdir / "src.json").write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
        assert mask_cli.main(["-i", "src.json", "-o", "out.json", "--no-report", "--no-local-config"]) == 0
        mapping = _mapping(workdir)
        _config(workdir, {"validation": {"strict_mode": True}})
        assert unmask_cli.main(["out.json", "--map", str(mapping), "-o", "r.json", "--no-local-config"]) == 0
        assert json.loads((workdir / "r.json").read_text(encoding="utf-8")) == src
        (workdir / "config.py").unlink()
        assert mask_cli.main(["-i", "src.json", "-o", "outc.json", "--no-report", "--re-mask", "2", "--no-local-config"]) == 0
        chain = sorted(workdir.glob("masking_chain_*.json"))[-1]
        assert unmask_cli.main(["outc.json", "--map", str(chain), "--to-version", "1", "-o", "tv1.json", "--no-local-config"]) == 0
        tv1 = json.loads((workdir / "tv1.json").read_text(encoding="utf-8"))
        assert tv1 != src
        # tv1 — стан після 1-го проходу: відкочується лише ним
        chain_data = json.loads(chain.read_text(encoding="utf-8"))
        chain_data["passes"] = chain_data["passes"][:1]
        data, stats = unmask_json_chain_with_stats(tv1, chain_data, 0)
        assert data == src and stats["restored_count"] > 0

    def test_broken_mapping_clean_error(self, workdir, capsys):
        mapping = self._mask_and_map(workdir)
        data = json.loads(mapping.read_text(encoding="utf-8"))
        for bad in ({"surname": "x"}, {"surname": {"Коваль": {"masked_as": None, "instances": [1]}}},
                    {"surname": {"Коваль": {"masked_as": "Ковар", "instances": "1"}}}):
            d = dict(data)
            d["mappings"] = dict(data["mappings"])
            d["mappings"].update(bad)
            (workdir / "bad.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            rc = unmask_cli.main(["out.txt", "--map", "bad.json", "-o", "rb.txt", "--force", "--no-local-config"])
            out = capsys.readouterr()
            assert rc == 1 and "Traceback" not in out.out + out.err
        with pytest.raises(ValueError):
            validate_mapping_schema({"passes": [1, 2]})

    def test_mapping_without_version_still_restores(self, workdir):
        mapping = self._mask_and_map(workdir)
        data = json.loads(mapping.read_text(encoding="utf-8"))
        data["version"] = "garbage"
        assert check_mapping_version(data) == "v2.1"
        (workdir / "g.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        assert unmask_cli.main(["out.txt", "--map", "g.json", "-o", "rg.txt", "--no-local-config"]) == 0
        assert (workdir / "rg.txt").read_text(encoding="utf-8") == TEXT

    def test_nothing_restored_warning(self, workdir, capsys):
        mapping = self._mask_and_map(workdir)
        (workdir / "other.txt").write_text("зовсім інший текст без масок\n", encoding="utf-8")
        assert unmask_cli.main(["other.txt", "--map", str(mapping), "-o", "ro.txt", "--no-local-config"]) == 0
        assert "Жодного значення не відновлено" in capsys.readouterr().err


def test_diagnose_exit_codes(workdir, monkeypatch, capsys):
    from datamasking import diagnose
    monkeypatch.setattr(sys, "argv", ["diagnose", "nope.json"])
    assert diagnose.main() == 1
    monkeypatch.setattr(sys, "argv", ["diagnose"])
    assert diagnose.main() == 1  # жодного mapping у теці
