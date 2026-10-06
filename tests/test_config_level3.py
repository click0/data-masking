#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Опції конфігурації рівня 3 (v3.0.29) — див. docs/TODO-config-options.md.

  - security.key_derivation / scrypt_* / salt_length — формат .enc 2;
  - masking_rules.custom_patterns + router_rules.default_action;
  - router_rules.processing_order / priority_overrides;
  - masking_rules.preserve_gender.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking import custom as _custom  # noqa: E402
from datamasking.masking.mask_personal import pseudo_gender  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402

try:
    from datamasking.extras.security import MappingSecurityManager
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False
needs_crypto = pytest.mark.skipif(not _HAS_CRYPTO, reason="cryptography not installed")

TEXT = "капітан Петренко Іван Іванович, ІПН 1234567890, ТЕЛ-1234\n"


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
        return rc, (path.read_bytes().decode("utf-8") if path.exists() else ""), cap.out, cap.err

    return _run


def _roundtrip(text):
    masked, md = mask(text)
    restored, _ = unmask_text_v2(masked, md, check_mapping_version(md))
    return masked, md, restored


# ---------------------------------------------------------------------------
# 27. scrypt і формат .enc 2
# ---------------------------------------------------------------------------
@needs_crypto
class TestKeyDerivation:
    def _encrypt(self, run, tmp_path, monkeypatch, security):
        monkeypatch.setenv("DATA_MASKING_PASSWORD", "pass-123")
        rc, *_ = run({"security": security}, extra=["--encrypt"])
        assert rc == 0
        return next(tmp_path.glob("masking_map_*.enc"))

    def test_default_is_legacy_format(self, run, tmp_path, monkeypatch):
        enc = self._encrypt(run, tmp_path, monkeypatch, {})
        assert not enc.read_bytes().startswith(b"DMENC2")

    @pytest.mark.parametrize("security", [
        {"key_derivation": "scrypt"},
        {"key_derivation": "scrypt", "scrypt_n": 32768, "scrypt_r": 8, "scrypt_p": 2, "salt_length": 32},
        {"key_derivation": "pbkdf2", "salt_length": 24},
    ])
    def test_v2_roundtrip_through_cli(self, run, tmp_path, monkeypatch, security):
        enc = self._encrypt(run, tmp_path, monkeypatch, security)
        raw = enc.read_bytes()
        assert raw.startswith(b"DMENC2")
        header = json.loads(raw[8:8 + int.from_bytes(raw[6:8], "big")])
        assert header["kdf"] == security["key_derivation"]
        (tmp_path / "config.py").unlink()  # unmask: формат розпізнається сам
        assert unmask_cli.main(["out.txt", "--map", enc.name, "--output", "rec.txt"]) == 0
        assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == TEXT

    def test_wrong_password_and_tampered_header(self, tmp_path):
        p = tmp_path / "m.enc"
        MappingSecurityManager().encrypt_mapping({"a": 1}, "pw", p, kdf={"kdf": "scrypt", "p": 2})
        with pytest.raises(ValueError):
            MappingSecurityManager().decrypt_mapping(p, "other")
        raw = bytearray(p.read_bytes())
        i = raw.index(b'"p": 2')
        raw[i + 5] = ord("1")
        p.write_bytes(bytes(raw))
        with pytest.raises(ValueError):
            MappingSecurityManager().decrypt_mapping(p, "pw")

    @pytest.mark.parametrize("security", [
        {"key_derivation": "argon2"},
        {"key_derivation": "scrypt", "scrypt_n": 1000},
        {"key_derivation": "scrypt", "scrypt_n": 1 << 21},
        {"key_derivation": "scrypt", "scrypt_n": 1 << 20, "scrypt_r": 16},
        {"salt_length": 8},
    ])
    def test_bad_params_are_config_errors(self, run, security):
        rc, out, stdout, _ = run({"security": security})
        assert rc == 1 and out == ""


# ---------------------------------------------------------------------------
# 26. Власні шаблони
# ---------------------------------------------------------------------------
class TestCustomPatterns:
    def test_mask_whole_match_and_group(self):
        _cfg.CUSTOM_PATTERNS = _custom.compile_patterns([
            r"\bТЕЛ-\d{4}\b",
            {"pattern": r"посвідчення\s+(\d{6})", "name": "id_card"},
        ])
        text = "ТЕЛ-1234 і посвідчення 123456; ще раз ТЕЛ-1234"
        masked, md, restored = _roundtrip(text)
        assert restored == text
        assert "ТЕЛ-1234" not in masked and "123456" not in masked and "посвідчення " in masked
        m = md["mappings"]["custom"]["ТЕЛ-1234"]["masked_as"]
        assert len(m) == 8 and m[3] == "-" and m[4:].isdigit() and m[:3].isupper()
        assert md["mappings"]["custom"]["ТЕЛ-1234"]["instances"] == [1, 2]

    def test_skip_protects_from_all_masking(self):
        _cfg.CUSTOM_PATTERNS = _custom.compile_patterns([
            {"pattern": r"№\s*\d+-[IVXLC]+", "action": "skip"},
            {"pattern": r"Петренко Іван Іванович", "action": "skip"},
        ])
        text = "Закону від 06.12.1991 № 1932-XII; капітан Петренко Іван Іванович"
        masked, _, restored = _roundtrip(text)
        assert "№ 1932-XII" in masked and "Петренко Іван Іванович" in masked
        assert restored == text

    def test_warn_counts(self):
        _custom.WARN_COUNTS.clear()
        _cfg.CUSTOM_PATTERNS = _custom.compile_patterns([{"pattern": r"\d{3}-\d{3}", "name": "tel",
                                                          "action": "warn"}])
        masked, *_ = _roundtrip("тел 123-456 і 789-012")
        assert "123-456" in masked and _custom.WARN_COUNTS == {"tel": 2}

    def test_default_action(self):
        cps = _custom.compile_patterns([r"\d{3}", {"pattern": r"x\d", "action": "mask"}], "skip")
        assert [c.action for c in cps] == ["skip", "mask"]

    def test_mask_never_equals_document_text(self):
        _cfg.CUSTOM_PATTERNS = _custom.compile_patterns([r"\bК-\d\b"])
        text = " ".join(f"К-{d}" for d in range(10))  # усі можливі маски вже в тексті
        masked, md, restored = _roundtrip(text)
        assert restored == text

    @pytest.mark.parametrize("raw", [
        "not a list",
        [123],
        [{"pattern": "("}],
        [{"pattern": "a*"}],                       # збіг із порожнім текстом
        [{"pattern": "x", "action": "delete"}],
        [{"pattern": "x", "colour": "red"}],
        [{"pattern": "x" * 1001}],
    ])
    def test_invalid(self, raw):
        with pytest.raises(ValueError):
            _custom.compile_patterns(raw)

    def test_invalid_default_action(self):
        with pytest.raises(ValueError):
            _custom.compile_patterns([], "explode")

    def test_cli(self, run):
        cfg = {"masking_rules": {"custom_patterns": [r"\bТЕЛ-\d{4}\b",
                                                     {"pattern": "Петренко", "action": "warn", "name": "p"}]}}
        rc, out, _, err = run(cfg)
        assert rc == 0 and "ТЕЛ-1234" not in out and "Петренко" in out
        assert "custom pattern 'p': 1 match(es) left unmasked" in err
        rc, out, stdout, _ = run({"masking_rules": {"custom_patterns": ["("]}}, out="o2.txt")
        assert rc == 1 and out == ""


# ---------------------------------------------------------------------------
# 29. Порядок обробки і пріоритети
# ---------------------------------------------------------------------------
class TestProcessingOrder:
    KNOWN = _cfg.DEFAULT_PROCESSING_ORDER

    def test_default_unchanged(self):
        assert _custom.build_processing_order(None, None, self.KNOWN) == self.KNOWN

    def test_partial_list_and_rank_pib_ignored(self):
        order = _custom.build_processing_order(["date", "rank", "ipn", "pib"], {}, self.KNOWN)
        assert order[:2] == ("date", "ipn") and set(order) == set(self.KNOWN)

    def test_priority_overrides(self):
        order = _custom.build_processing_order(None, {"date_text": -1, "custom": 100}, self.KNOWN)
        assert order[0] == "date_text" and order[-1] == "custom"

    @pytest.mark.parametrize("order,over", [(["nope"], {}), ("ipn", {}), (None, {"nope": 1}),
                                            (None, {"ipn": "high"}), (None, [1])])
    def test_invalid(self, order, over):
        with pytest.raises(ValueError):
            _custom.build_processing_order(order, over, self.KNOWN)

    def test_order_decides_overlaps(self):
        _cfg.CUSTOM_PATTERNS = _custom.compile_patterns([r"\b\d{10}\b"])
        _, md, _ = _roundtrip("код 1234567890")
        assert "1234567890" in md["mappings"].get("custom", {})          # custom — першим
        _cfg.PROCESSING_ORDER = _custom.build_processing_order(["ipn"], {}, self.KNOWN)
        _, md, _ = _roundtrip("код 1234567890")
        assert "1234567890" in md["mappings"]["ipn"] and not md["mappings"].get("custom")

    def test_full_example_config_changes_nothing(self, run):
        rc, plain, *_ = run({})
        rc2, with_example, _, err = run(None, extra=["--config", str(ROOT / "config_example.yaml")], out="o2.txt") \
            if _yaml() else (0, plain, "", "")
        assert rc == 0 and rc2 == 0 and plain == with_example and "Warning" not in err


def _yaml() -> bool:
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# 28. Маски без ознаки статі
# ---------------------------------------------------------------------------
class TestPreserveGender:
    NAMES = ["Іван", "Петро", "Олег", "Андрій", "Василь", "Тарас",
             "Марія", "Олена", "Ірина", "Наталія", "Оксана", "Юлія"]

    def test_pseudo_gender_is_balanced_and_deterministic(self):
        genders = [pseudo_gender(n) for n in self.NAMES]
        assert 3 <= genders.count("female") <= 9
        assert genders == [pseudo_gender(n) for n in self.NAMES]

    def test_masks_not_tied_to_real_gender(self):
        _cfg.PRESERVE_GENDER = False
        text = "\n".join(f"капітан Петренко {n} Іванович" for n in self.NAMES)
        masked, md, restored = _roundtrip(text)
        assert restored == text
        from datamasking.masking.language import detect_name_case_and_gender
        flipped = sum(1 for n in self.NAMES
                      if detect_name_case_and_gender(md["mappings"]["name"][n]["masked_as"])[1]
                      != detect_name_case_and_gender(n)[1])
        assert flipped > 0
        for n in self.NAMES:
            assert md["mappings"]["name"][n]["masked_as"].lower() != n.lower()

    def test_default_keeps_gender(self, run):
        rc, out, _, err = run({"masking_rules": {"preserve_gender": False}})
        assert rc == 0 and "preserve_gender is false" in err
