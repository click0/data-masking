#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сумісність із РЕАЛЬНИМИ mapping-файлами попередніх версій.

tests/fixtures/legacy_mappings/<version>/ згенеровано справжнім кодом
відповідного git-тега (data_masking.py → unmask_data.py на input_example.txt):
    input.txt        — вхід
    output.txt       — замаскований вихід тієї версії
    masking_map.json — mapping тієї версії
    recovered.txt    — що відновив unmask ТІЄЇ Ж версії

Контракт: поточний unmask на старому output+mapping має дати рівно те,
що давала стара версія (recovered.txt). Раніше сумісність доводилась лише
синтетичними словниками в тестах — реального файла 2.x у репо не було.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamasking.unmasking.engine import unmask_text_v2, unmask_text_v1  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from datamasking.unmasking.io import validate_mapping_schema  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "legacy_mappings"
VERSIONS = sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()) if FIXTURES.exists() else []


def _load(version: str):
    d = FIXTURES / version
    return (
        d / "input.txt",
        (d / "output.txt").read_bytes().decode("utf-8"),
        json.loads((d / "masking_map.json").read_text(encoding="utf-8")),
        (d / "recovered.txt").read_bytes().decode("utf-8"),
    )


def _restore(output: str, mapping: dict) -> str:
    logic = check_mapping_version(mapping)
    if logic.startswith("v2"):
        restored, _ = unmask_text_v2(output, mapping, logic)
    else:
        restored, _ = unmask_text_v1(output, mapping)
    return restored


@pytest.mark.parametrize("version", VERSIONS)
class TestLegacyMappings:
    def test_fixture_is_real(self, version):
        _, _, mapping, _ = _load(version)
        assert mapping["version"] == version.lstrip("v")
        assert mapping["mappings"]  # не порожній

    def test_schema_and_logic_detection(self, version):
        _, _, mapping, _ = _load(version)
        validate_mapping_schema(mapping)
        assert check_mapping_version(mapping) == "v2.1"  # усі 2.3+ — v2.1-логіка

    def test_engine_restores_original_input(self, version):
        """Поточний unmask на старому output+mapping повертає оригінал.

        Порівняння без урахування регістру: єдина відома розбіжність —
        префікс «БР 123/…» відновлюється як «бр 123/…» (давній баг
        збереження регістру, є окремий xfail нижче).
        """
        inp, output, mapping, _ = _load(version)
        restored = _restore(output, mapping)
        assert restored.casefold() == inp.read_bytes().decode("utf-8").casefold()

    def test_no_regression_vs_old_unmask(self, version):
        """Не гірше, ніж unmask тієї самої версії.

        v2.3.0 виключено свідомо: її ВЛАСНИЙ unmask не відновлював 24 рядки
        (passport_id/br_number лишались масками), поточний код відновлює
        їх правильно — тобто різниця є покращенням, а не регресією.
        """
        if version == "v2.3.0":
            pytest.skip("v2.3.0's own unmask was defective; current output is strictly better")
        _, output, mapping, recovered = _load(version)
        assert _restore(output, mapping) == recovered

    def test_cli_restores_legacy_files(self, version, tmp_path, monkeypatch):
        d = FIXTURES / version
        monkeypatch.chdir(tmp_path)
        rc = unmask_cli.main([str(d / "output.txt"), "--map", str(d / "masking_map.json"),
                              "-o", str(tmp_path / "rec.txt")])
        assert rc == 0
        got = (tmp_path / "rec.txt").read_bytes().decode("utf-8")
        assert got.casefold() == (d / "input.txt").read_bytes().decode("utf-8").casefold()

    @pytest.mark.xfail(strict=True, reason="BR prefix case lost on restore: 'БР 123/…' -> 'бр 123/…' (long-standing)")
    def test_engine_restores_input_byte_exact(self, version):
        inp, output, mapping, _ = _load(version)
        assert _restore(output, mapping) == inp.read_bytes().decode("utf-8")

    def test_no_original_value_left_in_output(self, version):
        _, output, mapping, _ = _load(version)
        # Кожен оригінал з mapping (крім коротких дат/чисел) відсутній у виході
        for category in ("surname", "ipn", "passport_id"):
            for original in mapping["mappings"].get(category, {}):
                assert original not in output, f"{category} '{original}' leaked in {version}"


def test_fixtures_present():
    assert VERSIONS, "tests/fixtures/legacy_mappings/ is empty"
