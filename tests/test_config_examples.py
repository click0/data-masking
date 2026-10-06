#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сценарні набори конфігурацій відповідають коду (v3.0.21, уточнено 3.0.23).

До 3.0.21 config_example.yaml/.py лишались шаблоном v2.6.0: 57 їхніх ключів
програма мовчки ігнорувала (strict_mode, backup_enabled, router_rules,
scrypt_n …), а опис шифрування (AES-128-CBC/Fernet) був неправдою. Тепер
кожен приклад перевіряється за EFFECTIVE_KEYS — переліком ключів, які
програма справді читає, — а сценарні набори (share / strict / pii) —
маскуванням справжнього тексту.
"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras.config import EFFECTIVE_KEYS, ConfigLoader  # noqa: E402
from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False
needs_yaml = pytest.mark.skipif(not _HAS_YAML, reason="pyyaml not installed")

try:
    import cryptography  # noqa: F401
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

EXAMPLES = ROOT / "docs" / "config-examples"
SCENARIOS = ["share", "strict", "pii"]

_MASK_GLOBALS = ["MASK_NAMES", "MASK_IPN", "MASK_PASSPORT", "MASK_MILITARY_ID", "MASK_RANKS",
                 "MASK_BRIGADES", "MASK_UNITS", "MASK_ORDERS", "MASK_BR_NUMBERS", "MASK_DATES",
                 "SURNAME_PREFIX_LENGTH", "DEBUG_MODE", "PRESERVE_CASE", "HASH_ALGORITHM"]


@pytest.fixture(autouse=True)
def _restore_engine_globals():
    saved = {g: getattr(_cfg, g) for g in _MASK_GLOBALS}
    yield
    for g, v in saved.items():
        setattr(_cfg, g, v)


def _unknown_keys(data: dict) -> list:
    bad = []
    for section, values in data.items():
        if section not in EFFECTIVE_KEYS:
            bad.append(section)
            continue
        bad += [f"{section}.{k}" for k in values if k not in EFFECTIVE_KEYS[section]]
    return bad


@needs_yaml
class TestScenarioSetsUseOnlyEffectiveKeys:
    # Сценарні набори містять лише ключі, що діють. Повний приклад
    # (config_example.yaml/.py) навмисно перелічує ВСІ опції, зокрема ще не
    # реалізовані — для нього це не перевіряється.
    @pytest.mark.parametrize("path", [EXAMPLES / f"{s}.yaml" for s in SCENARIOS], ids=lambda p: p.name)
    def test_yaml_examples(self, path):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert _unknown_keys(data) == []

    def test_full_example_still_loads(self):
        from datamasking.extras.config import Config
        data = yaml.safe_load((ROOT / "config_example.yaml").read_text(encoding="utf-8"))
        Config.from_dict(data)  # не падає на опціях, яких немає в схемі


# ---------------------------------------------------------------------------
# Сценарні набори дають обіцяний результат на справжньому тексті
# ---------------------------------------------------------------------------
SAMPLE = (
    "Наказ №125 від 12.03.2024 щодо БР 75/25/3400/Р\n"
    "старший сержант Коваль Петро Іванович, ІПН 1234567890, в/ч А1234\n"
    "72 окремої механізованої бригади\n"
)


def _mask_with(tmp_path, monkeypatch, scenario):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_MASKING_PASSWORD", "test-pass-123")
    for var in ("DATA_MASKING_ENCRYPT_OUTPUT", "DATA_MASKING_SURNAME_PREFIX_LENGTH"):
        monkeypatch.delenv(var, raising=False)
    (tmp_path / "in.txt").write_bytes(SAMPLE.encode("utf-8"))
    rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report",
                        "--config", str(EXAMPLES / f"{scenario}.yaml")])
    out = (tmp_path / "out.txt").read_bytes().decode("utf-8") if (tmp_path / "out.txt").exists() else ""
    return rc, out, sorted(p.name for p in tmp_path.glob("masking_map_*"))


@needs_yaml
@pytest.mark.skipif(not _HAS_CRYPTO, reason="scenarios encrypt the mapping; cryptography not installed")
class TestScenarios:
    def test_share_keeps_dates_and_document_numbers(self, tmp_path, monkeypatch):
        rc, out, maps = _mask_with(tmp_path, monkeypatch, "share")
        assert rc == 0
        for kept in ["12.03.2024", "№125", "75/25/3400/Р"]:
            assert kept in out, kept
        for masked in ["Коваль", "1234567890", "А1234", "старший сержант"]:
            assert masked not in out, masked
        assert maps and all(m.endswith(".enc") for m in maps)

    def test_strict_masks_everything_fully_synthetic(self, tmp_path, monkeypatch):
        rc, out, maps = _mask_with(tmp_path, monkeypatch, "strict")
        assert rc == 0
        for masked in ["12.03.2024", "№125", "75/25/3400/Р", "Коваль", "1234567890", "А1234"]:
            assert masked not in out, masked
        assert _cfg.SURNAME_PREFIX_LENGTH == 0
        assert maps and all(m.endswith(".enc") for m in maps)

    def test_pii_masks_only_people_and_ids(self, tmp_path, monkeypatch):
        rc, out, maps = _mask_with(tmp_path, monkeypatch, "pii")
        assert rc == 0
        for kept in ["12.03.2024", "№125", "75/25/3400/Р", "А1234", "старший сержант", "72 окремої"]:
            assert kept in out, kept
        for masked in ["Коваль", "1234567890"]:
            assert masked not in out, masked
        assert maps and all(m.endswith(".enc") for m in maps)


def test_examples_readme_lists_every_scenario():
    text = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    for s in SCENARIOS:
        assert f"{s}.yaml" in text
    assert os.path.exists(EXAMPLES / "README.md")


# ---------------------------------------------------------------------------
# Варіант 3 (v3.0.26): нереалізовані опції лишаються в прикладах з позначкою
# і не дають попереджень; позначки ↔ PLANNED_KEYS збігаються точно
# ---------------------------------------------------------------------------
import re as _re  # noqa: E402

from datamasking.extras.config import PLANNED_KEYS, ignored_config_keys  # noqa: E402


def _tagged_yaml_paths(text: str, tag: str) -> set:
    paths, stack = set(), []
    for line in text.split("\n"):
        m = _re.match(r"^(\s*)([A-Za-z_]+):(.*)$", line)
        if m and not line.lstrip().startswith("#"):
            stack = stack[: len(m.group(1)) // 2] + [m.group(2)]
            if tag in line:
                paths.add(".".join(stack))
    return paths


def test_planned_and_effective_do_not_overlap():
    effective = {f"{s}.{k}" for s, ks in EFFECTIVE_KEYS.items() for k in ks}
    assert not (PLANNED_KEYS & effective)


@needs_yaml
class TestPlannedOptionsInExamples:
    def test_full_example_loads_without_warning(self):
        data = yaml.safe_load((ROOT / "config_example.yaml").read_text(encoding="utf-8"))
        assert ignored_config_keys(data) == []

    def test_example_tags_match_planned_keys(self):
        text = (ROOT / "config_example.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        from datamasking.extras.config import _unknown_leaf_keys
        not_effective = set(_unknown_leaf_keys(data))
        assert _tagged_yaml_paths(text, "[не реалізовано]") == not_effective
        assert not_effective <= PLANNED_KEYS

    def test_template_tags_match_and_no_warning(self, tmp_path):
        out = tmp_path / "c.yaml"
        ConfigLoader.generate_default_config(str(out))
        text = out.read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        from datamasking.extras.config import _unknown_leaf_keys
        assert _tagged_yaml_paths(text, "[not implemented yet]") == set(_unknown_leaf_keys(data))
        assert ignored_config_keys(data) == []

    def test_python_example_tags(self):
        # Поле dataclass-у (або ключ словника password_generation) позначене
        # [не реалізовано] тоді й лише тоді, коли його шлях — у PLANNED_KEYS
        sections = {"SystemConfig": "system", "SecurityConfig": "security",
                    "MaskingRulesConfig": "masking_rules", "ValidationConfig": "validation",
                    "RouterRulesConfig": "router_rules", "LoggingConfig": "logging"}
        sec = indict = None
        tagged, planned = set(), set()
        for line in (ROOT / "config_example.py").read_text(encoding="utf-8").split("\n"):
            m = _re.match(r"^class (\w+)", line)
            if m:
                sec, indict = sections.get(m.group(1)), None
            fm = _re.match(r"^    (\w+): [^=]+=(.*)$", line)
            dm = _re.match(r'^        "(\w+)": ', line)
            path = None
            if fm and sec:
                path = f"{sec}.{fm.group(1)}"
                indict = path if "{" in fm.group(2) and "}" not in fm.group(2) else None
            elif dm and indict:
                path = f"{indict}.{dm.group(1)}"
            if path:
                if "[не реалізовано]" in line:
                    tagged.add(path)
                if path in PLANNED_KEYS:
                    planned.add(path)
        assert tagged == planned and tagged


def test_todo_lists_every_planned_key():
    text = (ROOT / "docs" / "TODO-config-options.md").read_text(encoding="utf-8")
    missing = sorted(k for k in PLANNED_KEYS if f"`{k}`" not in text)
    assert missing == []
