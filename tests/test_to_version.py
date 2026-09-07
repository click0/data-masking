#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
--to-version: часткове відновлення ланцюга --re-mask (v3.0.7).

До 3.0.7 прапорець викликав неіснуючий ChainUnmasker.convert_to_version
і падав TypeError на кожному запуску — знайдено mypy (attr-defined).
Так само ChainUnmasker._apply_reverse_pass брав значення mapping (dict)
як рядок і ніколи не міг відновити текст.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datamasking.masking import cli as mask_cli  # noqa: E402
from datamasking.unmasking import cli as unmask_cli  # noqa: E402
from datamasking.unmasking.engine import unmask_chain  # noqa: E402
from datamasking.extras.re_mask import ChainUnmasker, MappingChain, get_chain_info  # noqa: E402

SAMPLE = (
    "Капітан Петренко Іван Сергійович, ІПН 1234567890.\n"
    "Сержант Коваленко Марія Іванівна прибула 15.03.2025.\n"
)


@pytest.fixture
def chain_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "in.txt").write_bytes(SAMPLE.encode("utf-8"))
    assert mask_cli.main(["-i", "in.txt", "-o", "m.txt", "--no-report", "--re-mask", "3"]) == 0
    chain_path = next(tmp_path.glob("masking_chain_*.json"))
    masked = (tmp_path / "m.txt").read_bytes().decode("utf-8")
    import json
    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    return tmp_path, chain_path, masked, chain


class TestEngineToVersion:
    def test_zero_is_full_restore(self, chain_run):
        _, _, masked, chain = chain_run
        restored, _ = unmask_chain(masked, chain, to_version=0)
        assert restored == SAMPLE

    def test_last_pass_is_identity(self, chain_run):
        _, _, masked, chain = chain_run
        restored, _ = unmask_chain(masked, chain, to_version=3)
        assert restored == masked

    def test_intermediate_states_chain_back(self, chain_run):
        _, _, masked, chain = chain_run
        # стан після проходу 2 → далі розкручуємо лише перші 2 проходи
        after2, _ = unmask_chain(masked, chain, to_version=2)
        assert after2 != masked and after2 != SAMPLE
        sub = {"passes": chain["passes"][:2], "total_passes": 2}
        restored, _ = unmask_chain(after2, sub, to_version=0)
        assert restored == SAMPLE

    def test_out_of_range(self, chain_run):
        _, _, masked, chain = chain_run
        with pytest.raises(ValueError):
            unmask_chain(masked, chain, to_version=4)


class TestCliToVersion:
    def test_cli_partial_and_full(self, chain_run):
        tmp_path, chain_path, masked, _ = chain_run
        assert unmask_cli.main(["m.txt", "--map", str(chain_path), "--to-version", "2", "-o", "v2.txt"]) == 0
        v2 = (tmp_path / "v2.txt").read_bytes().decode("utf-8")
        assert v2 != masked and v2 != SAMPLE
        assert unmask_cli.main(["m.txt", "--map", str(chain_path), "--to-version", "0", "-o", "v0.txt"]) == 0
        assert (tmp_path / "v0.txt").read_bytes().decode("utf-8") == SAMPLE

    def test_cli_rejects_non_chain_and_out_of_range(self, chain_run):
        tmp_path, chain_path, _, _ = chain_run
        assert unmask_cli.main(["m.txt", "--map", str(chain_path), "--to-version", "9", "-o", "x.txt"]) == 1
        assert mask_cli.main(["-i", "in.txt", "-o", "s.txt", "--no-report"]) == 0
        smap = next(tmp_path.glob("masking_map_*.json"))
        assert unmask_cli.main(["s.txt", "--map", str(smap), "--to-version", "0", "-o", "y.txt"]) == 1


class TestChainUnmaskerApi:
    def test_unmask_all_and_to_version(self, chain_run):
        _, _, masked, chain = chain_run
        cu = ChainUnmasker(MappingChain.from_dict(chain))
        assert cu.unmask_all(masked) == SAMPLE
        assert cu.unmask_to_version(masked, 3) == masked
        after2 = cu.unmask_to_version(masked, 2)
        assert after2 != masked and after2 != SAMPLE

    def test_get_chain_info_accepts_dict(self, chain_run):
        _, _, _, chain = chain_run
        info = get_chain_info(chain)
        assert info and info.get("total_passes", info.get("passes")) is not None
        assert get_chain_info({"version": "3.0.7", "mappings": {}}) == {}
