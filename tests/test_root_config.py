#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config.yaml у корені репозиторію (v3.1.3): спільна конфігурація з усіма
ключами й повними переліками виключень (dictionaries); config_local.yaml —
приватні перекриття (шаблон config_local.example.yaml).
"""
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras.config import ConfigLoader, ignored_config_keys  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import exclusions as _excl  # noqa: E402

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
needs_yaml = pytest.mark.skipif(not _HAS_YAML, reason="pyyaml not installed")

CONFIG = ROOT / "config.yaml"
LOCAL_TEMPLATE = ROOT / "config_local.example.yaml"


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_files_exist():
    assert CONFIG.is_file() and LOCAL_TEMPLATE.is_file()


@needs_yaml
class TestContent:
    def test_loads_without_ignored_keys(self):
        assert ignored_config_keys(_load(CONFIG)) == []
        assert ignored_config_keys(_load(LOCAL_TEMPLATE)) == []

    def test_same_data_as_full_example(self):
        assert _load(CONFIG) == _load(ROOT / "config_example.yaml")

    def test_dictionaries_match_builtin_copy(self):
        # Запасна копія в коді (без PyYAML / з іншим конфігом) = config.yaml.
        # Змінили перелік у config.yaml — оновіть masking/exclusions.py.
        d = _load(CONFIG)["dictionaries"]
        assert tuple(d["abbreviations"]) == _excl.BUILTIN_ABBREVIATIONS
        assert tuple(d["non_name_words"]) == _excl.BUILTIN_WORDS
        assert tuple(d["legal_acts"]) == _excl.BUILTIN_LEGAL_ACTS

    def test_init_config_template_has_dictionaries(self, tmp_path):
        out = tmp_path / "c.yaml"
        ConfigLoader.generate_default_config(str(out))
        d = _load(out)["dictionaries"]
        assert tuple(d["non_name_words"]) == _excl.BUILTIN_WORDS
        assert ignored_config_keys(_load(out)) == []

    def test_every_key_the_program_reads(self):
        # «усі ключі»: кожен ключ із EFFECTIVE_KEYS, крім старих псевдонімів
        from datamasking.extras.config import EFFECTIVE_KEYS
        aliases = {"security.password_length", "security.password_generation",
                   "password_generation.enabled", "password_generation.env_var",
                   "password_generation.length", "password_generation.use_special_chars"}
        data = _load(CONFIG)

        def has(path):
            cur = data
            for part in path.split("."):
                if not isinstance(cur, dict) or part not in cur:
                    return False
                cur = cur[part]
            return True
        missing = sorted(f"{s}.{k}" for s, ks in EFFECTIVE_KEYS.items() for k in ks
                         if f"{s}.{k}" not in aliases and not has(f"{s}.{k}"))
        assert missing == []

    def test_kabinet_ministriv_listed(self):
        words = {w.lower() for w in _load(CONFIG)["dictionaries"]["non_name_words"]}
        assert {"кабінет", "кабінету", "кабінетом", "міністрів"} <= words

    def test_gitignore(self):
        if not (ROOT / ".gitignore").is_file():
            pytest.skip("no .gitignore (sdist)")
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert "config_local.yaml" in lines
        assert "config.yaml" not in lines


@needs_yaml
class TestMasking:
    TEXT = ("Згідно з постановою Кабінету Міністрів України від 12.03.2020 та Закону "
            "України від 06.12.1991 капітан Петренко Іван Іванович, ЗСУ, прибув.\n")

    def _mask(self, tmp_path, capsys, *extra):
        (tmp_path / "in.txt").write_text(self.TEXT, encoding="utf-8")
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--force", *extra])
        stdout = capsys.readouterr().out
        assert rc == 0, stdout
        return (tmp_path / "out.txt").read_text(encoding="utf-8"), stdout

    def test_same_masks_as_without_config(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
            monkeypatch.delenv(var, raising=False)
        plain, stdout = self._mask(tmp_path, capsys)
        assert "Loaded config" not in stdout
        shutil.copy(CONFIG, tmp_path / "config.yaml")
        with_config, stdout = self._mask(tmp_path, capsys)
        assert "Loaded config from config.yaml" in stdout
        assert with_config == plain
        assert "Кабінету Міністрів України від 12.03.2020" in with_config
        assert "ЗСУ" in with_config and "Петренко" not in with_config

    def test_local_template_changes_nothing(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        shutil.copy(CONFIG, tmp_path / "config.yaml")
        plain, _ = self._mask(tmp_path, capsys)
        shutil.copy(LOCAL_TEMPLATE, tmp_path / "config_local.yaml")
        os.chmod(tmp_path / "config_local.yaml", 0o600)
        local, stdout = self._mask(tmp_path, capsys)
        assert "Loaded local config from config_local.yaml" in stdout
        assert local == plain

    def test_edited_dictionary_takes_effect(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        data = _load(CONFIG)
        data["dictionaries"]["legal_acts"] = [a for a in data["dictionaries"]["legal_acts"]
                                              if a != "закон*"]
        (tmp_path / "config.yaml").write_text(yaml.safe_dump(data, allow_unicode=True),
                                              encoding="utf-8")
        out, _ = self._mask(tmp_path, capsys)
        assert "Закону України від 06.12.1991" not in out  # дату закону тепер зсунуто


class TestDictionaries:
    def test_missing_keys_use_builtin(self):
        assert _excl.build(None, {}).words_lower == _excl.build(None).words_lower
        assert _excl.build(None, {"abbreviations": None}).abbreviations == \
            frozenset(_excl.BUILTIN_ABBREVIATIONS)

    def test_replace_and_extend(self):
        ex = _excl.build({"abbreviations": ["ОК"]}, {"abbreviations": ["ТРО"]})
        assert ex.abbreviations == {"тро", "ок"}
        assert _excl.build(None, {"non_name_words": []}).words_lower == frozenset()

    @pytest.mark.parametrize("bad", [
        {"non_name_words": "Рада"},
        {"non_name_words": ["Кабінет Міністрів"]},
        {"abbreviations": [""]},
        {"legal_acts": ["за*кон"]},
    ])
    def test_invalid(self, bad):
        with pytest.raises(ValueError, match="dictionaries"):
            _excl.build(None, bad)
