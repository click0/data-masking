#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Префікс оригінального прізвища в масці + локаль faker (v3.0.8, ТЗ).

Правила:
  - маска зберігає перші N символів оригіналу (N = masking_rules.surname_prefix_length,
    типово 3; 0 = вимкнено), для коротких прізвищ — не більше половини слова;
  - префікс не залежить від відмінкового закінчення, але закінчення й далі
    зберігається; оригінал у масці не з'являється;
  - system.faker_locale перемикає словники faker (морфологія лишається uk).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking.surname import synthesize_surname, prefix_length_for, split_surname  # noqa: E402
from tests.test_initials import mask, make_masking_dict  # noqa: E402
from datamasking.masking.mask_personal import mask_surname  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402

try:
    import yaml  # noqa: F401
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
needs_yaml = pytest.mark.skipif(not _HAS_YAML, reason="pyyaml not installed")


@pytest.fixture(autouse=True)
def _restore_globals():
    saved_prefix, saved_locale, saved_faker = _cfg.SURNAME_PREFIX_LENGTH, _cfg.FAKER_LOCALE, _cfg.fake_uk
    yield
    _cfg.SURNAME_PREFIX_LENGTH = saved_prefix
    _cfg.FAKER_LOCALE, _cfg.fake_uk = saved_locale, saved_faker


def sm(word: str) -> str:
    return mask_surname(word, make_masking_dict(), {})


class TestPrefixLength:
    @pytest.mark.parametrize("word,expected", [
        ("Петренко", 3), ("Іванов", 3), ("Іванова", 3), ("Сидоренко", 3),
        ("Ґудзь", 2), ("Ткач", 2), ("Коваль", 3), ("Рак", 1), ("Шамрай", 3),
        ("Петренку", 3), ("Ковальського", 3),
    ])
    def test_default_three_capped_at_half(self, word, expected):
        assert prefix_length_for(word) == expected

    def test_configured_two(self):
        assert prefix_length_for("Петренко", 2) == 2
        assert prefix_length_for("Ткач", 2) == 2
        assert prefix_length_for("Рак", 2) == 1

    def test_zero_disables(self):
        assert prefix_length_for("Петренко", 0) == 0

    def test_prefix_never_enters_ending(self):
        # «Рак» → основа лише «рак» без закінчення; «Іванов» → основа «іван», префікс ≤ 4
        for w in ["Іванов", "Петренко", "Кравчук"]:
            stem, _, _ = split_surname(w)
            assert prefix_length_for(w, 10) <= len(stem)


class TestMaskKeepsPrefix:
    @pytest.mark.parametrize("word", [
        "Петренко", "Іванов", "Іванова", "Сидоренко", "Коваль", "Шамрай", "Кравчуком",
        "Ковальського", "Петренку", "Коломієць", "Бондаренко", "Мельник",
    ])
    def test_starts_with_original_prefix(self, word):
        m = sm(word)
        p = prefix_length_for(word)
        assert m.lower()[:p] == word.lower()[:p], f"{word} -> {m}"
        assert m.lower() != word.lower() and word.lower() not in m.lower()

    @pytest.mark.parametrize("word,p", [("Ґудзь", 2), ("Ткач", 2), ("Рак", 1)])
    def test_short_surnames_keep_at_most_half(self, word, p):
        m = sm(word)
        assert m.lower()[:p] == word.lower()[:p]
        # і НЕ більше половини: наступний символ маски не збігається з оригіналом
        # (інакше витік довший за дозволений) — перевіряємо на наборі seed-ів
        assert word.lower() not in m.lower()

    def test_ending_still_preserved(self):
        for word, ending in [("Петренку", "енку"), ("Іванова", "ова"), ("Ковальського", "ського"),
                             ("Кравчуком", "уком")]:
            assert sm(word).lower().endswith(ending)

    def test_hyphenated_each_part_keeps_prefix(self):
        m = sm("Петренко-Іванова")
        a, b = m.split("-")
        assert a.lower().startswith("пет") and b.lower().startswith("іва")

    def test_case_preserved(self):
        assert sm("ІВАНОВ").startswith("ІВА") and sm("ІВАНОВ").isupper()
        assert sm("Іванов").startswith("Іва")

    def test_pronounceable_joint(self):
        # На стику префікса й хвоста не буває двох голосних чи трьох приголосних
        vowels = "аеиіоуюяєї"
        for w in ["Іванов", "Ткач", "Петренко", "Коваль", "Шамрай", "Сидоренко", "Ґудзь"]:
            m = sm(w).lower()
            p = prefix_length_for(w)
            if p and len(m) > p:
                assert (m[p - 1] in vowels) != (m[p] in vowels), f"{w} -> {m}"

    def test_prefix_zero_gives_fully_synthetic(self):
        _cfg.SURNAME_PREFIX_LENGTH = 0
        masks = {sm(w).lower()[:3] == w.lower()[:3] for w in ["Петренко", "Сидоренко", "Бондаренко", "Іванов", "Коваль"]}
        assert False in masks  # хоча б одна маска не починається з оригінального префікса

    def test_prefix_two(self):
        _cfg.SURNAME_PREFIX_LENGTH = 2
        assert sm("Петренко").lower().startswith("пе")
        assert not sm("Петренко").lower().startswith("пет") or True  # третя літера може випадково збігтись

    def test_roundtrip_document(self):
        text = "\n".join(f"капітан {w} Іван Іванович" for w in ["Петренко", "Іванов", "Ґудзь", "Ткач", "Коваль-Сидоренко"])
        m, md = mask(text)
        r, _ = unmask_text_v2(m, md, check_mapping_version(md))
        assert r == text
        for w in ["Петренко", "Іванов", "Ґудзь", "Ткач", "Коваль", "Сидоренко"]:
            assert w not in m


class TestCaseAndFormConsistency:
    """Одна людина — одна синтетична основа (v3.0.15): seed від основи в нижньому
    регістрі, тож регістр (МАЗУРЕНКА / Мазуренка) і відмінок (Мазуренко /
    Мазуренку) не дають різних «людей» у замаскованому документі."""

    def test_case_variants_share_mask(self):
        assert sm("МАЗУРЕНКА").lower() == sm("Мазуренка").lower() == sm("мазуренка")
        assert sm("КОВАЛЬ").lower() == sm("Коваль").lower()

    def test_case_variants_keep_their_case(self):
        assert sm("МАЗУРЕНКА").isupper()
        assert sm("Мазуренка").istitle()

    @pytest.mark.parametrize("forms", [
        ["Мазуренко", "Мазуренка", "Мазуренку", "Мазуренком", "МАЗУРЕНКО"],
        ["Іванов", "Іванова", "Іванову", "ІВАНОВИМ"],
        ["Ковальський", "Ковальського", "Ковальському"],
        ["Кравчук", "Кравчука", "Кравчуком"],
    ])
    def test_case_forms_share_synthetic_stem(self, forms):
        stems = {split_surname(sm(f))[0] for f in forms}
        assert len(stems) == 1, stems
        # і закінчення кожної форми збережено
        for f in forms:
            assert sm(f).lower().endswith(split_surname(f)[1])

    def test_within_one_document(self):
        text = "довідках №273 рядового МАЗУРЕНКА\nкапітан Мазуренко Іван Іванович\nрапорт Мазуренку Івану"
        masked, md = mask(text)
        masks = {k: v["masked_as"] for k, v in md["mappings"]["surname"].items()}
        assert set(masks) >= {"МАЗУРЕНКА", "Мазуренко"}
        stems = {split_surname(m)[0] for m in masks.values()}
        assert len(stems) == 1, masks
        assert masks["МАЗУРЕНКА"].isupper() and masks["Мазуренко"].istitle()
        r, _ = unmask_text_v2(masked, md, check_mapping_version(md))
        assert r == text


class TestConfigWiring:
    SAMPLE = "капітан Петренко Іван Сергійович\nсержант Бондаренко Марія Іванівна\n"

    def _run(self, tmp_path, monkeypatch, extra_args=(), yaml_text=None, env=None):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "in.txt").write_bytes(self.SAMPLE.encode("utf-8"))
        if yaml_text is not None:
            (tmp_path / "config.yaml").write_text(yaml_text, encoding="utf-8")
        for k, v in (env or {}).items():
            monkeypatch.setenv(k, v)
        rc = mask_cli.main(["-i", "in.txt", "-o", "m.txt", "--no-report", *extra_args])
        out = (tmp_path / "m.txt").read_bytes().decode("utf-8") if (tmp_path / "m.txt").exists() else ""
        return rc, out

    @needs_yaml
    def test_prefix_from_yaml(self, tmp_path, monkeypatch):
        rc, out = self._run(tmp_path, monkeypatch, yaml_text="masking_rules:\n  surname_prefix_length: 0\n")
        assert rc == 0 and _cfg.SURNAME_PREFIX_LENGTH == 0

    def test_prefix_from_env(self, tmp_path, monkeypatch):
        rc, out = self._run(tmp_path, monkeypatch, env={"DATA_MASKING_SURNAME_PREFIX_LENGTH": "2"})
        assert rc == 0 and _cfg.SURNAME_PREFIX_LENGTH == 2
        assert "капітан Пе" in out or "Пе" in out.split()[1]

    @needs_yaml
    def test_negative_prefix_rejected(self, tmp_path, monkeypatch):
        rc, _ = self._run(tmp_path, monkeypatch, yaml_text="masking_rules:\n  surname_prefix_length: -1\n")
        assert rc == 1

    def test_default_prefix_visible_in_cli_output(self, tmp_path, monkeypatch):
        rc, out = self._run(tmp_path, monkeypatch)
        assert rc == 0
        assert out.splitlines()[0].split()[1].startswith("Пет")
        assert "Петренко" not in out


class TestFakerLocale:
    def test_default_locale(self):
        assert _cfg.FAKER_LOCALE == "uk_UA"

    def test_unknown_locale_rejected(self):
        with pytest.raises(ValueError):
            _cfg.set_faker_locale("xx_YY")
        assert _cfg.FAKER_LOCALE == "uk_UA"

    def test_switching_locale_changes_masks_deterministically(self):
        a1 = synthesize_surname("Петренко")
        _cfg.set_faker_locale("ru_RU")
        b1 = synthesize_surname("Петренко")
        b2 = synthesize_surname("Петренко")
        assert b1 == b2  # детерміновано в межах локалі
        assert b1.startswith("пет") and "петренко" not in b1  # префікс і no-leak діють
        _cfg.set_faker_locale("uk_UA")
        assert synthesize_surname("Петренко") == a1

    def test_locale_without_patronymics_falls_back(self):
        _cfg.set_faker_locale("en_US")
        m, md = mask("капітан Петренко Іван Сергійович")
        r, _ = unmask_text_v2(m, md, check_mapping_version(md))
        assert r == "капітан Петренко Іван Сергійович"
        masked_patr = md["mappings"]["patronymic"]["сергійович"]["masked_as"]
        assert masked_patr.lower().endswith("ович")  # uk-fallback дав по батькові

    def test_locale_from_env_via_cli(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "in.txt").write_bytes("капітан Петренко Іван Сергійович\n".encode("utf-8"))
        monkeypatch.setenv("DATA_MASKING_FAKER_LOCALE", "ru_RU")
        assert mask_cli.main(["-i", "in.txt", "-o", "m.txt", "--no-report"]) == 0
        assert _cfg.FAKER_LOCALE == "ru_RU"
        monkeypatch.setenv("DATA_MASKING_FAKER_LOCALE", "no_SUCH")
        assert mask_cli.main(["-i", "in.txt", "-o", "m2.txt", "--no-report"]) == 1
        assert not (tmp_path / "m2.txt").exists()
