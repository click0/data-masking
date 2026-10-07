#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Секція exclusions (v3.1.1): вбудовані переліки виключень винесено в
masking/exclusions.py, конфігурація їх доповнює.

Конфігурація — через ./config.py (без pyyaml).
"""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking import exclusions as _excl  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)

    def _run(text, exclusions=None, extra=()):
        for old in tmp_path.glob("masking_map_*.json"):
            old.unlink()
        cfg = tmp_path / "config.py"
        if cfg.exists():
            cfg.unlink()
        if exclusions is not None:
            (tmp_path / "config.py").write_text(f"CONFIG = {{'exclusions': {exclusions!r}}}\n",
                                                encoding="utf-8")
        (tmp_path / "in.txt").write_bytes(text.encode("utf-8"))
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--force", *extra])
        cap = capsys.readouterr()
        out = tmp_path / "out.txt"
        maps = sorted(tmp_path.glob("masking_map_*.json"))
        mapping = json.loads(maps[-1].read_text(encoding="utf-8")) if maps else None
        return rc, (out.read_text(encoding="utf-8") if out.exists() else ""), cap.out + cap.err, mapping

    return _run


def _restored(masked, mapping):
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    return restored


# ---------------------------------------------------------------------------
# Вбудовані переліки — ті самі, що були в constants.py
# ---------------------------------------------------------------------------
class TestBuiltin:
    def test_defaults_unchanged(self):
        ex = _excl.build(None)
        assert ex.abbreviations == _cfg.ABBREVIATION_WHITELIST
        assert ex.words_lower == _cfg.EXCLUDE_WORDS_LOWER
        assert ex.skip_patterns == () and ex.mask_patterns == () and ex.added == 0
        for word in ("кабінету", "міністрів", "закону", "піб"):
            assert word in ex.words_lower
        for abbr in ("зсу", "кму", "отцксп"):
            assert abbr in ex.abbreviations

    @pytest.mark.parametrize("prefix, legal", [
        ("Закону України від ", True),
        ("постанови Кабінету  Міністрів від ", True),
        ("постанови КМУ від ", True),
        ("постанови кмy від ", True),  # латинська y
        ("Указом Президента України від ", True),
        ("Конституції від ", True),
        ("наказу командира від ", False),
        ("рапорту від ", False),
    ])
    def test_legal_act_regex_same_as_before(self, prefix, legal):
        old = re.compile(r"(?:закон\w*|кодекс\w*|конституці\w*|указ\w*\s+президента|"
                         r"постанов\w*\s+(?:кабінету\s+міністрів|верховної\s+ради|км[уy]))"
                         r"[^\n.;]{0,80}?\bвід\s*$", re.IGNORECASE)
        assert bool(old.search(prefix)) is legal
        assert bool(_cfg.LEGAL_ACT_DATE_PREFIX.search(prefix)) is legal

    def test_phrase_regex(self):
        rx = re.compile(_excl.phrase_regex("Кабінет* Міністрів"), re.IGNORECASE)
        for text in ("Кабінет Міністрів", "кабінетом   міністрів", "КАБІНЕТУ МІНІСТРІВ"):
            assert rx.fullmatch(text)
        assert not rx.fullmatch("Кабінет Міністра")


# ---------------------------------------------------------------------------
# Конфігурація
# ---------------------------------------------------------------------------
class TestConfig:
    def test_abbreviations(self, run):
        text = "Доповідаю: ТРО Петренко Іван Іванович прибув.\n"
        _, out, _, _ = run(text)
        assert "ТРО" not in out
        _, out, _, _ = run(text, {"abbreviations": ["ТРО"]})
        assert "ТРО" in out and "Петренко" not in out

    def test_words(self, run):
        text = "Рада Петренко Іван Іванович\n"
        _, out, _, _ = run(text)
        assert not out.startswith("Рада ")
        _, out, _, _ = run(text, {"words": ["Рада"]})
        assert out.startswith("Рада ") and "Петренко" not in out

    def test_phrases_protect_and_keep_legal_date(self, run):
        text = "Згідно з постановою Верховної Ради від 12.03.2020 капітан Петренко Іван Іванович.\n"
        _, out, _, mapping = run(text, {"phrases": ["Верховн* Рад*"]})
        assert "постановою Верховної Ради від 12.03.2020" in out
        assert "Петренко" not in out
        assert _restored(out, mapping) == text

    def test_legal_acts(self, run):
        text = "Розпорядженням Президента від 05.05.2021 солдат Коваль Олег Петрович.\n"
        _, out, _, _ = run(text)
        assert "05.05.2021" not in out
        _, out, _, mapping = run(text, {"legal_acts": ["розпорядженн* президента"]})
        # назва акта не маскується як ПІБ, дата після «… від» не зсувається
        assert out.startswith("Розпорядженням Президента від 05.05.2021 ")
        assert "Коваль" not in out
        assert _restored(out, mapping) == text

    def test_always_mask_roundtrip(self, run):
        text = "Петренко Іван Іванович, позивний Грім, прибув.\n"
        _, out, _, _ = run(text)
        assert "Грім" in out
        rc, out, _, mapping = run(text, {"always_mask": ["Грім"]})
        assert rc == 0 and "Грім" not in out and "позивний " in out
        assert _restored(out, mapping) == text

    def test_remove_builtin(self, run):
        text = "Згідно із Законом України від 06.12.1991 капітан Петренко Іван Іванович.\n"
        _, out, _, _ = run(text)
        assert "від 06.12.1991" in out
        _, out, _, _ = run(text, {"remove": ["закон*"]})
        assert "від 06.12.1991" not in out

    @pytest.mark.parametrize("bad", [
        {"words": "Рада"},
        {"words": [""]},
        {"words": ["Верховна Рада"]},
        {"abbreviations": ["ТР*"]},
        {"phrases": ["Ка*бінет"]},
        {"phrases": [1]},
        {"always_mask": ["Я"]},
    ])
    def test_invalid_values_are_config_errors(self, run, bad):
        rc, out, msg, _ = run("капітан Петренко Іван Іванович\n", bad)
        assert rc == 1 and out == ""
        assert "exclusions." in msg

    def test_list_exclusions(self, run, tmp_path):
        rc, out, msg, _ = run("x\n", {"phrases": ["Верховн* Рад*"], "always_mask": ["Грім"]},
                              extra=["--list-exclusions"])
        assert rc == 0 and out == ""
        assert "Верховн* Рад*" in msg and "Грім" in msg and "зсу" in msg
        assert not list(tmp_path.glob("masking_map_*"))
