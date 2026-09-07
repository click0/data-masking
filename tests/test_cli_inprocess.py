#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
In-process CLI тести: mask → unmask через `main(argv)` без subprocess.

Навіщо: інтеграційні тести через subprocess не вимірюються coverage
(cli.py ~13%), і саме тому три критичні дефекти CLI (plaintext-mapping
поруч із .enc, невідновлюваний .enc, --only без ефекту) жили роками.
Кожен тест тут — реальний файловий roundtrip у tmp_path.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402

# Текст, що відновлюється БАЙТ-В-БАЙТ (без склеювання розірваних рядків)
SAMPLE = (
    "Капітан Петренко Іван Сергійович, ІПН 1234567890, паспорт 123456789.\n"
    "Наказ №123 від 01.01.2025 по в/ч А1234.\n"
    "Сержант Коваленко Марія Іванівна прибула 15.03.2025.\n"
)
_FLAGS = [n for n in dir(_cfg) if n.startswith("MASK_")]


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Кожен тест — у власному cwd, з відновленням прапорців MASK_* і env."""
    saved = {n: getattr(_cfg, n) for n in _FLAGS}
    monkeypatch.chdir(tmp_path)
    for var in ("DATA_MASKING_PASSWORD", "MASKING_PASSWORD", "UNMASK_PASSWORD"):
        monkeypatch.delenv(var, raising=False)
    yield
    for n, v in saved.items():
        setattr(_cfg, n, v)
    _cfg.DEBUG_MODE = False


def write_input(tmp_path: Path, text: str = SAMPLE, name: str = "in.txt") -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8", newline="")
    return p


def mask(*args: str) -> int:
    return mask_cli.main(list(args) + ["--no-report"])


def unmask(*args: str) -> int:
    return unmask_cli.main(list(args))


def one(tmp_path: Path, pattern: str) -> Path:
    files = sorted(tmp_path.glob(pattern))
    assert len(files) == 1, f"expected exactly one {pattern}, got {files}"
    return files[0]


# ============================================================================
# Roundtrip: txt / json
# ============================================================================

class TestRoundtrip:
    def test_txt_roundtrip_byte_exact(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "masked.txt") == 0
        masked = (tmp_path / "masked.txt").read_text(encoding="utf-8")
        assert "Петренко" not in masked and "1234567890" not in masked
        mp = one(tmp_path, "masking_map_*.json")
        assert unmask("masked.txt", "--map", str(mp), "-o", "rec.txt") == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == SAMPLE

    def test_mapping_written_private_and_next_to_output(self, tmp_path):
        inp = write_input(tmp_path)
        sub = tmp_path / "sub"
        sub.mkdir()
        assert mask("-i", str(inp), "-o", str(sub / "m.txt")) == 0
        mp = one(sub, "masking_map_*.json")  # поруч із -o, не в cwd
        assert not list(tmp_path.glob("masking_map_*"))
        if os.name != "nt":
            assert (mp.stat().st_mode & 0o777) == 0o600

    def test_json_roundtrip(self, tmp_path):
        data = {"pib": "капітан Петренко Іван Сергійович", "ipn": "1234567890",
                "items": [{"x": "сержант Коваль Олег Петрович"}]}
        inp = tmp_path / "in.json"
        inp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        assert mask("-i", str(inp), "-o", "masked.json") == 0
        masked = json.loads((tmp_path / "masked.json").read_text(encoding="utf-8"))
        assert masked["ipn"] != "1234567890"
        mp = one(tmp_path, "masking_map_*.json")
        assert unmask("masked.json", "--map", str(mp), "-o", "rec.json") == 0
        assert json.loads((tmp_path / "rec.json").read_text(encoding="utf-8")) == data


# ============================================================================
# Шифрування
# ============================================================================

class TestEncrypt:
    def test_encrypt_writes_only_enc_and_roundtrips(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "masked.txt", "--encrypt", "--password", "Pw1!") == 0
        enc = one(tmp_path, "masking_map_*.enc")
        # КРИТИЧНО: plaintext mapping поруч із .enc бути не повинно
        assert not list(tmp_path.glob("masking_map_*.json")), "plaintext mapping leaked next to .enc"
        assert b"1234567890" not in enc.read_bytes()
        assert unmask("masked.txt", "--map", str(enc), "--password", "Pw1!", "-o", "rec.txt") == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == SAMPLE

    def test_wrong_password_is_clean_error(self, tmp_path):
        inp = write_input(tmp_path)
        mask("-i", str(inp), "-o", "masked.txt", "--encrypt", "--password", "Pw1!")
        enc = one(tmp_path, "masking_map_*.enc")
        assert unmask("masked.txt", "--map", str(enc), "--password", "wrong", "-o", "rec.txt") == 1
        assert not (tmp_path / "rec.txt").exists()

    def test_password_env_both_sides(self, tmp_path, monkeypatch):
        inp = write_input(tmp_path)
        monkeypatch.setenv("MY_PW", "s3cret")
        assert mask("-i", str(inp), "-o", "masked.txt", "--encrypt", "--password-env", "MY_PW") == 0
        enc = one(tmp_path, "masking_map_*.enc")
        assert unmask("masked.txt", "--map", str(enc), "--password-env", "MY_PW", "-o", "rec.txt") == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == SAMPLE

    def test_default_env_var_shared_by_both_sides(self, tmp_path, monkeypatch):
        inp = write_input(tmp_path)
        monkeypatch.setenv("DATA_MASKING_PASSWORD", "fromenv")
        assert mask("-i", str(inp), "-o", "masked.txt", "--encrypt") == 0
        enc = one(tmp_path, "masking_map_*.enc")
        # unmask бере той самий DATA_MASKING_PASSWORD без --password
        assert unmask("masked.txt", "--map", str(enc), "-o", "rec.txt") == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == SAMPLE

    def test_unset_password_env_is_fatal_before_any_write(self, tmp_path, monkeypatch):
        inp = write_input(tmp_path)
        monkeypatch.delenv("NOPE", raising=False)
        assert mask("-i", str(inp), "-o", "masked.txt", "--encrypt", "--password-env", "NOPE") == 2
        assert not (tmp_path / "masked.txt").exists()
        assert not list(tmp_path.glob("masking_map_*"))

    def test_empty_password_rejected(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "masked.txt", "--encrypt", "--password", "") == 2
        assert not (tmp_path / "masked.txt").exists()

    def test_generated_password_goes_to_stderr(self, tmp_path, capsys):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "masked.txt", "--encrypt") == 0
        captured = capsys.readouterr()
        assert "Generated password" in captured.err
        assert "Generated password" not in captured.out
        one(tmp_path, "masking_map_*.enc")
        assert not list(tmp_path.glob("masking_map_*.json"))


# ============================================================================
# --only / --exclude
# ============================================================================

class TestSelective:
    def test_only_ipn_masks_ipn_only(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--only", "ipn") == 0
        out = (tmp_path / "m.txt").read_text(encoding="utf-8")
        assert "1234567890" not in out
        assert "Петренко Іван Сергійович" in out  # імена не чіпались
        assert "01.01.2025" in out

    def test_comma_form_from_readme(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--only", "ipn,passport") == 0
        out = (tmp_path / "m.txt").read_text(encoding="utf-8")
        assert "1234567890" not in out and "123456789" not in out
        assert "Петренко" in out

    @pytest.mark.parametrize("name", ["rank", "ranks", "звання"])
    def test_canonical_plural_and_ukrainian_aliases(self, tmp_path, name):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--only", name) == 0
        out = (tmp_path / "m.txt").read_text(encoding="utf-8")
        assert "Капітан Петренко" not in out  # звання замасковано
        assert "Петренко" in out               # прізвище — ні

    def test_unknown_type_is_fatal_and_writes_nothing(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--only", "bogus") == 2
        assert not (tmp_path / "m.txt").exists()
        assert not list(tmp_path.glob("masking_map_*"))

    def test_exclude_dates_keeps_dates(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--exclude", "dates") == 0
        out = (tmp_path / "m.txt").read_text(encoding="utf-8")
        assert "01.01.2025" in out and "15.03.2025" in out
        assert "Петренко" not in out

    def test_only_and_exclude_together_rejected(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--only", "ipn", "--exclude", "dates") == 2

    def test_list_types_shows_aliases(self, capsys):
        assert mask_cli.main(["--list-types"]) == 0
        out = capsys.readouterr().out
        assert "ranks" in out and "звання" in out and "personal" in out


# ============================================================================
# --re-mask (chain)
# ============================================================================

class TestReMask:
    def test_chain_written_and_summary_points_to_it(self, tmp_path, capsys):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--re-mask", "2") == 0
        chain = one(tmp_path, "masking_chain_*.json")
        assert not list(tmp_path.glob("masking_map_*")), "phantom masking_map for chain mode"
        out = capsys.readouterr().out
        assert chain.name in out
        assert unmask("m.txt", "--map", str(chain), "-o", "rec.txt") == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == SAMPLE

    def test_chain_encrypted(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--re-mask", "2",
                    "--encrypt", "--password", "Pw1!") == 0
        enc = one(tmp_path, "masking_chain_*.enc")
        assert not list(tmp_path.glob("masking_chain_*.json"))
        assert not list(tmp_path.glob("masking_map_*"))
        assert unmask("m.txt", "--map", str(enc), "--password", "Pw1!", "-o", "rec.txt") == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == SAMPLE


# ============================================================================
# Захист -o і коди виходу
# ============================================================================

class TestOutputSafety:
    def test_output_equal_input_refused(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", str(inp)) == 2
        assert inp.read_text(encoding="utf-8") == SAMPLE

    def test_existing_output_needs_force(self, tmp_path):
        inp = write_input(tmp_path)
        (tmp_path / "m.txt").write_text("keep", encoding="utf-8")
        assert mask("-i", str(inp), "-o", "m.txt") == 2
        assert (tmp_path / "m.txt").read_text(encoding="utf-8") == "keep"
        assert mask("-i", str(inp), "-o", "m.txt", "--force") == 0
        assert (tmp_path / "m.txt").read_text(encoding="utf-8") != "keep"

    def test_missing_input_exit_1(self, tmp_path):
        assert mask("-i", "nope.txt") == 1

    def test_unmask_missing_map_exit_1(self, tmp_path):
        write_input(tmp_path, name="masked.txt")
        assert unmask("masked.txt", "--map", "nope.json") == 1

    def test_unmask_invalid_mapping_schema_exit_1(self, tmp_path):
        write_input(tmp_path, name="masked.txt")
        (tmp_path / "bad.json").write_text("[1, 2]", encoding="utf-8")
        assert unmask("masked.txt", "--map", "bad.json", "-o", "rec.txt") == 1

    def test_init_config_does_not_clobber(self, tmp_path):
        (tmp_path / "config.yaml").write_text("mine: true\n", encoding="utf-8")
        assert mask_cli.main(["--init-config"]) == 1
        assert (tmp_path / "config.yaml").read_text(encoding="utf-8") == "mine: true\n"
        assert mask_cli.main(["--init-config", "--force"]) == 0
        assert "masking_rules" in (tmp_path / "config.yaml").read_text(encoding="utf-8")


# ============================================================================
# Конфіг / ENV (аудит: пріоритет CLI > ENV > YAML був зламаний)
# ============================================================================

class TestConfigAndEnv:
    def test_env_applies_without_config_yaml(self, tmp_path, monkeypatch):
        # Раніше без config.yaml loader не запускався → усі DATA_MASKING_* ігнорувались
        inp = write_input(tmp_path)
        monkeypatch.setenv("DATA_MASKING_DEBUG", "1")
        try:
            assert mask("-i", str(inp), "-o", "m.txt") == 0
            assert _cfg.DEBUG_MODE is True
        finally:
            _cfg.DEBUG_MODE = False

    def test_malformed_yaml_is_fatal(self, tmp_path):
        inp = write_input(tmp_path)
        (tmp_path / "config.yaml").write_text("system: [unclosed\n  bad: : :\n", encoding="utf-8")
        assert mask("-i", str(inp), "-o", "m.txt") == 1
        assert not (tmp_path / "m.txt").exists()

    def test_missing_explicit_config_is_fatal(self, tmp_path):
        inp = write_input(tmp_path)
        assert mask("-i", str(inp), "-o", "m.txt", "--config", "nope.yaml") == 1

    def test_encrypt_output_from_yaml(self, tmp_path, monkeypatch):
        # security.encrypt_output: true == --encrypt (раніше мертвий ключ)
        inp = write_input(tmp_path)
        (tmp_path / "config.yaml").write_text("security:\n  encrypt_output: true\n", encoding="utf-8")
        monkeypatch.setenv("DATA_MASKING_PASSWORD", "yamlpw")
        assert mask("-i", str(inp), "-o", "m.txt") == 0
        enc = one(tmp_path, "masking_map_*.enc")
        assert not list(tmp_path.glob("masking_map_*.json"))
        assert unmask("m.txt", "--map", str(enc), "-o", "rec.txt") == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == SAMPLE

    def test_password_env_value_not_stored_in_config(self, monkeypatch):
        from datamasking.extras.config import ConfigLoader
        monkeypatch.setenv("DATA_MASKING_PASSWORD", "EnvPw1!")
        cfg = ConfigLoader().load()
        assert cfg.security.password_env_var == "DATA_MASKING_PASSWORD"  # назва змінної, не пароль

    def test_max_input_size_from_yaml(self, tmp_path):
        inp = write_input(tmp_path)
        (tmp_path / "config.yaml").write_text("validation:\n  max_input_size_mb: 1\n", encoding="utf-8")
        saved = _cfg.MAX_INPUT_FILE_SIZE
        try:
            assert mask("-i", str(inp), "-o", "m.txt") == 0
            assert _cfg.MAX_INPUT_FILE_SIZE == 1024 * 1024
        finally:
            _cfg.MAX_INPUT_FILE_SIZE = saved

    def test_generated_template_matches_loader_schema(self, tmp_path):
        from datamasking.extras.config import ConfigLoader, PasswordGenerationConfig
        assert mask_cli.main(["--init-config"]) == 0
        cfg = ConfigLoader("config.yaml").load()
        # password_generation — секція (dataclass), а не bool
        assert isinstance(cfg.security.password_generation, PasswordGenerationConfig)
        assert "Fernet" not in (tmp_path / "config.yaml").read_text(encoding="utf-8")

    def test_local_config_py_only_from_cwd(self, tmp_path):
        # ./config.py читається; довільний модуль «config» із sys.path — ні
        from datamasking.extras.config import ConfigLoader
        (tmp_path / "config.py").write_text("CONFIG = {'system': {'hash_algorithm': 'sha256'}}\n", encoding="utf-8")
        assert ConfigLoader().load().system.hash_algorithm == "sha256"
        (tmp_path / "config.py").unlink()
        assert ConfigLoader().load().system.hash_algorithm == "blake2b"
