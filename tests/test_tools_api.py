#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.11 — datamasking.extras.tools (задокументований API) делегує в рушій:
до того мав власну застарілу реалізацію (прізвище з 8 із 9 літер оригіналу,
звання лише в називному відмінку, дати лише 2015–2035). MappingChain:
значення mapping v2 — об'єкти; save/save_mapping — атомарно, 0600.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras import tools  # noqa: E402
from datamasking.extras.re_mask import MappingChain  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.surname import split_surname  # noqa: E402
from tests.test_initials import mask  # noqa: E402


@pytest.fixture
def md():
    return tools.init_masking_dict(), tools.init_instance_counters()


class TestDelegation:
    def test_surname_has_no_original_stem(self, md):
        d, c = md
        for s in ("Сидоренко", "Петренко", "Коваленко", "Шевчук"):
            m = tools.mask_surname_direct(s, d, c)
            stem, _, _ = split_surname(s)
            assert m != s and stem not in m.lower(), (s, m)
            assert m[:2].lower() == s[:2].lower()

    def test_rank_in_oblique_case(self, md):
        d, c = md
        assert tools.mask_rank_direct("капітана", d, c) != "капітана"
        assert tools.mask_rank_direct("капітана", d, c).endswith("а")
        assert tools.mask_rank_direct("Старшому Сержанту", d, c) != "Старшому Сержанту"

    def test_date_outside_2015_2035(self, md):
        d, c = md
        masked = tools.mask_date_direct("05.03.1987", d, c)
        assert masked != "05.03.1987" and masked.endswith(("1987", "1986", "1988"))

    def test_name_patronymic_gender(self, md):
        d, c = md
        assert tools.mask_patronymic_direct("Петрівна", d, c, gender="female").endswith(("івна", "ївна"))
        assert tools.mask_name_direct("Олега", d, c) not in ("Олег", "Олега")

    def test_same_masks_as_cli_engine(self, md):
        d, c = md
        text = "капітан Сидоренко Петро Іванович, ІПН 1234567890, в/ч А1234"
        masked_text, mapping = mask(text)
        for cat in ("surname", "name", "patronymic", "ipn", "military_unit", "rank"):
            for original, info in mapping["mappings"][cat].items():
                via_api = tools.mask_value(original, cat, d, c)
                # ключі по батькові в mapping — у нижньому регістрі, регістр маски йде від входу
                assert via_api.lower() == info["masked_as"].lower(), (cat, original, via_api, info["masked_as"])

    def test_pib_force_and_dispatch(self, md):
        d, c = md
        out = tools.mask_pib_force("Коваль Тетяна Сергіївна", d, c)
        assert "Коваль" not in out and "Тетяна" not in out and "Сергіївна" not in out
        assert len(out.split()) == 3
        with pytest.raises(ValueError):
            tools.mask_value("x", "nope", d, c)

    def test_foreign_masking_dict(self, md):
        # словник без категорій рушія (initials, custom …) теж працює
        d = {"mappings": {}, "statistics": {}}
        c = {}
        assert tools.mask_ipn_direct("1234567890", d, c) != "1234567890"


class TestMappingChain:
    def test_reverse_chain_with_v2_values(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        for var in [v for v in os.environ if v.startswith("DATA_MASKING_")]:
            monkeypatch.delenv(var, raising=False)
        from datamasking.masking import cli as mask_cli
        (tmp_path / "in.txt").write_text("капітан Коваль Тетяна Сергіївна\n", encoding="utf-8")
        assert mask_cli.main(["-i", "in.txt", "-o", "out.txt", "--no-report", "--re-mask", "3", "--no-local-config"]) == 0
        chain_path = sorted(tmp_path.glob("masking_chain_*.json"))[-1]
        chain = MappingChain.load(chain_path)
        reverse = chain.get_chain_mapping(3, 0)
        assert isinstance(reverse, dict) and reverse
        assert "Коваль" in reverse.values() or any(v.startswith("Ков") for v in reverse.values())
        forward = chain.get_chain_mapping(1, 3)
        assert isinstance(forward, dict) and forward

    @pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
    def test_save_is_private(self, tmp_path):
        chain = MappingChain()
        target = tmp_path / "chain.json"
        chain.save(target)
        assert target.stat().st_mode & 0o777 == 0o600
        pytest.importorskip("cryptography")
        from datamasking.extras.security import MappingSecurityManager
        out = MappingSecurityManager().save_mapping({"version": "3", "mappings": {}}, tmp_path / "m.json", encrypt=False)
        assert Path(out).stat().st_mode & 0o777 == 0o600
