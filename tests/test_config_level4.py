#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Опції конфігурації рівня 4 (v3.0.30) — див. docs/TODO-config-options.md.

Це не перемикачі, а незмінна поведінка програми: ключі приймаються лише
зі значенням true; false — помилка конфігурації з поясненням.

  - masking_rules.consistent_mapping / instance_tracking / context_aware;
  - validation.validate_rank_dictionary;
  - remask.save_chain / auto_numbering.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras.config import (  # noqa: E402
    ALWAYS_ON_KEYS, EFFECTIVE_KEYS, PLANNED_KEYS, Config, ignored_config_keys,
)
from datamasking.masking import cli as mask_cli  # noqa: E402

TEXT = "капітан Петренко Іван Іванович, ІПН 1234567890\n"

KEYS = sorted(ALWAYS_ON_KEYS)


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
        monkeypatch.delenv(var, raising=False)

    def _run(config=None, extra=()):
        if config is not None:
            (tmp_path / "config.py").write_text(f"CONFIG = {config!r}\n", encoding="utf-8")
        (tmp_path / "in.txt").write_bytes(TEXT.encode("utf-8"))
        rc = mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", *extra])
        cap = capsys.readouterr()
        path = tmp_path / "out.txt"
        return rc, (path.read_bytes().decode("utf-8") if path.exists() else ""), cap.out, cap.err

    return _run


def _config(dotted, value):
    section, key = dotted.split(".")
    return {section: {key: value}}


def test_all_options_implemented():
    assert PLANNED_KEYS == frozenset()
    effective = {f"{s}.{k}" for s, ks in EFFECTIVE_KEYS.items() for k in ks}
    assert set(KEYS) <= effective
    assert len(KEYS) == 6


@pytest.mark.parametrize("dotted", KEYS)
def test_schema_default_is_true(dotted):
    section, key = dotted.split(".")
    assert getattr(getattr(Config(), section), key) is True


@pytest.mark.parametrize("dotted", KEYS)
def test_true_is_accepted_silently(dotted):
    assert ignored_config_keys(_config(dotted, True)) == []


@pytest.mark.parametrize("dotted", KEYS)
def test_true_masks_normally(run, dotted):
    rc, out, _, err = run(_config(dotted, True))
    assert rc == 0, err
    assert out and "Петренко" not in out


@pytest.mark.parametrize("dotted", KEYS)
@pytest.mark.parametrize("value", [False, "no", 0])
def test_other_values_are_config_errors(run, dotted, value):
    rc, out, stdout, err = run(_config(dotted, value))
    assert rc == 1 and out == ""
    msg = stdout + err
    assert dotted in msg and "only true is supported" in msg
    # Пояснення, чому вимкнути не можна
    assert ALWAYS_ON_KEYS[dotted] in msg


def test_hint_points_to_real_switch(run):
    _, _, stdout, err = run(_config("masking_rules.context_aware", False))
    assert "enable_names" in stdout + err
    _, _, stdout, err = run(_config("validation.validate_rank_dictionary", False))
    assert "enable_ranks" in stdout + err


def test_error_before_any_file_written(run, tmp_path):
    run(_config("remask.save_chain", False), extra=["--re-mask", "2"])
    names = {p.name for p in tmp_path.iterdir()}
    assert names <= {"config.py", "in.txt", "__pycache__"}
