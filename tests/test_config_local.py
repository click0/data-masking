#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
config_local.yaml (v3.1.1): приватні перекриття поверх config.yaml.

Пошук: тека користувача (XDG_CONFIG_HOME / APPDATA — у тестах тимчасова,
див. conftest.isolate_user_config_dir), потім поруч із config.yaml; явний
--config-local замінює автопошук. Значення не-null перекривають спільні.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras.config import (  # noqa: E402
    ConfigLoader, merge_config_dicts, user_config_dir,
)
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402

try:
    import yaml  # noqa: F401
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
needs_yaml = pytest.mark.skipif(not _HAS_YAML, reason="pyyaml not installed")


def _write(path: Path, text: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.chmod(path, mode)
    return path


class TestMerge:
    def test_semantics(self):
        base = {"system": {"debug_mode": True, "encoding": "utf-8"},
                "exclusions": {"words": ["A1", "B2"]}, "logging": {"level": "INFO"}}
        local = {"system": {"debug_mode": None, "encoding": "cp1251"},
                 "exclusions": {"words": ["C3"]}, "logging": {"level": None},
                 "remask": {"max_passes": 3}}
        merged = merge_config_dicts(base, local)
        assert merged["system"] == {"debug_mode": True, "encoding": "cp1251"}  # null не перекриває
        assert merged["exclusions"]["words"] == ["C3"]                         # список замінюється
        assert merged["logging"]["level"] == "INFO"
        assert merged["remask"] == {"max_passes": 3}
        assert base["system"]["encoding"] == "utf-8"                           # вхід не змінено

    def test_empty_list_and_false_override(self):
        merged = merge_config_dicts({"a": {"x": [1], "y": True}}, {"a": {"x": [], "y": False}})
        assert merged == {"a": {"x": [], "y": False}}

    def test_section_replaced_by_scalar_and_back(self):
        assert merge_config_dicts({"s": {"k": 1}}, {"s": False}) == {"s": False}
        assert merge_config_dicts({"s": False}, {"s": {"k": 1}}) == {"s": {"k": 1}}

    def test_user_config_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert user_config_dir() == tmp_path / "data-masking"


@needs_yaml
class TestLoader:
    def test_local_next_to_config_overrides(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config.yaml",
               "system:\n  hash_algorithm: sha256\n  debug_mode: true\n"
               "exclusions:\n  words: [Шаблон]\n")
        _write(tmp_path / "config_local.yaml",
               "system:\n  hash_algorithm: sha512\n  debug_mode: null\n"
               "exclusions:\n  words: [Приватне]\n")
        loader = ConfigLoader()
        cfg = loader.load()
        assert cfg.system.hash_algorithm == "sha512"
        assert cfg.system.debug_mode is True
        assert cfg.exclusions.words == ["Приватне"]
        assert loader.local_loaded == ["config_local.yaml"]
        assert loader.notices == []

    def test_local_without_shared_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config_local.yaml", "masking_rules:\n  surname_prefix_length: 0\n")
        cfg = ConfigLoader().load()
        assert cfg.masking_rules.surname_prefix_length == 0

    def test_local_on_top_of_config_py(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.py").write_text(
            "CONFIG = {'system': {'hash_algorithm': 'sha256', 'debug_mode': True}}\n", encoding="utf-8")
        _write(tmp_path / "config_local.yaml", "system:\n  hash_algorithm: md5\n")
        cfg = ConfigLoader().load()
        assert (cfg.system.hash_algorithm, cfg.system.debug_mode) == ("md5", True)

    def test_user_dir_then_project(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        user = user_config_dir() / "config_local.yaml"
        _write(user, "system:\n  hash_algorithm: sha256\n  debug_mode: true\n")
        loader = ConfigLoader()
        cfg = loader.load()
        assert (cfg.system.hash_algorithm, cfg.system.debug_mode) == ("sha256", True)
        assert loader.local_loaded == [str(user)]
        # Файл поруч із config.yaml важить більше за теку користувача
        _write(tmp_path / "config_local.yaml", "system:\n  hash_algorithm: sha512\n")
        loader = ConfigLoader()
        cfg = loader.load()
        assert (cfg.system.hash_algorithm, cfg.system.debug_mode) == ("sha512", True)
        assert loader.local_loaded == [str(user), "config_local.yaml"]

    def test_next_to_explicit_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        shared = _write(tmp_path / "team" / "config.yaml", "system:\n  hash_algorithm: sha256\n")
        _write(tmp_path / "team" / "config_local.yaml", "system:\n  hash_algorithm: sha512\n")
        _write(tmp_path / "config_local.yaml", "system:\n  hash_algorithm: md5\n")  # не той
        cfg = ConfigLoader(str(shared)).load()
        assert cfg.system.hash_algorithm == "sha512"

    def test_explicit_and_disabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config_local.yaml", "system:\n  hash_algorithm: sha512\n")
        other = _write(tmp_path / "private.yaml", "system:\n  hash_algorithm: md5\n")
        assert ConfigLoader(local_path=str(other)).load().system.hash_algorithm == "md5"
        assert ConfigLoader(use_local=False).load().system.hash_algorithm == "blake2b"
        with pytest.raises(ValueError, match="Local config file not found"):
            ConfigLoader(local_path="missing.yaml").load()

    def test_unknown_keys_reported_per_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config.yaml", "system:\n  typo_shared: 1\n")
        _write(tmp_path / "config_local.yaml", "system:\n  typo_local: 1\n")
        loader = ConfigLoader()
        loader.load()
        assert loader.ignored_by_source == [("config.yaml", ["system.typo_shared"]),
                                            ("config_local.yaml", ["system.typo_local"])]

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
    def test_permission_notice(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config_local.yaml", "system:\n  debug_mode: false\n", mode=0o644)
        loader = ConfigLoader()
        loader.load()
        assert len(loader.notices) == 1 and "chmod 600" in loader.notices[0]

    def test_malformed_local_is_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config_local.yaml", "system: [unclosed\n")
        with pytest.raises(ValueError, match="Malformed YAML"):
            ConfigLoader().load()


@needs_yaml
class TestCli:
    TEXT = "Доповідаю: ТРО Петренко Іван Іванович прибув.\n"

    def _mask(self, tmp_path, capsys, *extra):
        (tmp_path / "in.txt").write_text(self.TEXT, encoding="utf-8")
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--force", *extra])
        cap = capsys.readouterr()
        out = tmp_path / "out.txt"
        return rc, out.read_text(encoding="utf-8") if out.exists() else "", cap.out, cap.err

    def test_mask_uses_local_exclusions(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config_local.yaml", "exclusions:\n  abbreviations: [ТРО]\n")
        rc, out, stdout, _ = self._mask(tmp_path, capsys)
        assert rc == 0 and "ТРО" in out and "Петренко" not in out
        assert "Loaded local config from config_local.yaml" in stdout
        rc, out, stdout, _ = self._mask(tmp_path, capsys, "--no-local-config")
        assert rc == 0 and "ТРО" not in out and "Loaded local config" not in stdout

    def test_mask_missing_explicit_local(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        rc, out, stdout, _ = self._mask(tmp_path, capsys, "--config-local", "nope.yaml")
        assert rc == 1 and out == "" and "nope.yaml" in stdout

    def test_strict_mode_covers_local_file(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        _write(tmp_path / "config.yaml", "system:\n  strict_mode: true\n")
        _write(tmp_path / "config_local.yaml", "system:\n  typo_local: 1\n")
        rc, out, stdout, _ = self._mask(tmp_path, capsys)
        assert rc == 1 and out == ""
        assert "config_local.yaml" in stdout and "system.typo_local" in stdout

    def test_unmask_reads_local(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        rc, out, _, _ = self._mask(tmp_path, capsys)
        assert rc == 0
        mapping = sorted(tmp_path.glob("masking_map_*.json"))[-1]
        _write(tmp_path / "config_local.yaml", "system:\n  typo_local: 1\n")
        rc = unmask_cli.main(["out.txt", "--map", str(mapping), "--output", "back.txt"])
        err = capsys.readouterr().err
        assert rc == 0
        assert (tmp_path / "back.txt").read_text(encoding="utf-8") == self.TEXT
        assert "config_local.yaml" in err and "system.typo_local" in err
