#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки аудиту API (datamasking.extras, shim-и, старі формати mapping) і
узгодженості масок прізвищ (після 3.1.21).

  - mapping v2.0 без instances нічого не відновлював; у mapping v2.0 не
    відновлювались звання; mapping без ключа version читався як v1;
  - v1 (str.replace) замінював відновлене ще раз і частини слів;
  - shim data_masking: MASK_NAMES = False лишав прізвища й по батькові
    маскованими; apply_filter_to_globals(…, data_masking.__dict__) нічого не
    робив;
  - tools: рід імені й по батькові за замовчуванням — чоловічий;
    mask_value("", "name") падав;
  - generate_password(ensure_variety=True) інколи пропускав клас символів;
    довжина 0 давала порожній пароль;
  - MappingChain.get_chain_mapping уперед — зсув на прохід; ChainUnmasker
    не бачив проходів без поля "pass"; from_dict змінював словник викликача;
  - --only , вмикав усі типи;
  - відмінки одного прізвища на приголосний діставали різні синтетичні
    основи (Коваль → Ковар, Коваля → Кобіля);
  - маска прізвища з «ʼ» (U+02BC) не зберігалась у документі cp1251.
"""
import os
import string
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.extras import tools  # noqa: E402
from datamasking.extras.password_generator import generate_password  # noqa: E402
from datamasking.extras.re_mask import ChainUnmasker, MappingChain  # noqa: E402
from datamasking.extras.selective import apply_filter_to_globals, create_filter  # noqa: E402
from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.engine import mask_text_context_aware  # noqa: E402
from datamasking.masking.mask_personal import mask_surname  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v1, unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import make_masking_dict, mask  # noqa: E402


class TestLegacyMappings:
    def test_v20_without_instances(self):
        m = {"version": "2.0.1", "mappings": {"surname": {"Іванов": {"masked_as": "Петренко", "gender": "M"}}}}
        restored, stats = unmask_text_v2("Петренко і Петренко", m, check_mapping_version(m))
        assert restored == "Іванов і Іванов" and stats["restored_count"] == 2

    def test_v20_ranks(self):
        m = {"version": "2.0.1", "mappings": {
            "rank": {"капітан": {"masked_as": "майор", "instances": [1, 2]}},
            "surname": {"Іванов": {"masked_as": "Петренко", "instances": [1]}},
            "name": {"Петро": {"masked_as": "Андрій", "instances": [1]}}}}
        restored, _ = unmask_text_v2("Майор Петренко Андрій і майор", m, check_mapping_version(m))
        assert restored == "Капітан Іванов Петро і капітан"

    def test_no_version_is_detected_by_structure(self):
        m = {"mappings": {"surname": {"Іванов": {"masked_as": "Петренко", "instances": [1]}}}}
        assert check_mapping_version(m) == "v2.1"
        assert check_mapping_version({"mappings": {"surname": {"Іванов": "Петренко"}}}) == "v1"

    def test_v1_single_pass_whole_words(self):
        m = {"mappings": {"surname": {"Сидоренко": "Коваленко", "Петренко": "Сидоренко"},
                          "name": {"Олег": "Петро"}}}
        restored, stats = unmask_text_v1("Сидоренко Петро Петрович і Коваленко", m)
        assert restored == "Петренко Олег Петрович і Сидоренко"
        assert stats["restored_count"] == 3


class TestShim:
    @pytest.fixture
    def dm(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            import data_masking
        return data_masking

    def test_mask_names_false_covers_surnames(self, dm):
        dm.MASK_NAMES = False
        assert dm.MASK_SURNAMES is False and dm.MASK_PATRONYMICS is False
        assert "Петренко Іван Петрович" in mask("сержант Петренко Іван Петрович")[0]

    def test_mask_dates_false_covers_text_dates(self, dm):
        dm.MASK_DATES = False
        assert mask("«28» вересня 2025 року")[0] == "«28» вересня 2025 року"

    def test_filter_on_shim_dict(self, dm):
        apply_filter_to_globals(create_filter(only="ipn"), dm.__dict__)
        assert _cfg.MASK_NAMES is False and _cfg.MASK_IPN is True
        assert "MASK_NAMES" not in dm.__dict__ and dm.MASK_NAMES is False


class TestTools:
    @pytest.mark.parametrize("value, kind, first", [
        ("Марія", "name", "М"), ("Наталія", "name", "Н"),
    ])
    def test_female_name_by_default(self, value, kind, first):
        out = tools.mask_value(value, kind, make_masking_dict(), {})
        assert out[0] == first and out[-1] in "аяь"

    def test_female_patronymic_by_default(self):
        assert tools.mask_value("Іванівна", "patronymic", make_masking_dict(), {}).endswith("івна")

    def test_explicit_gender_still_works(self):
        assert tools.mask_value("Іванович", "patronymic", make_masking_dict(), {}, gender="male").endswith("вич")

    def test_empty_name(self):
        assert tools.mask_value("", "name", make_masking_dict(), {}) == ""


class TestPassword:
    def test_variety_guaranteed(self):
        for _ in range(3000):
            p = generate_password(length=4)
            assert any(c in string.ascii_uppercase for c in p)
            assert any(c in string.ascii_lowercase for c in p)
            assert any(c in string.digits for c in p)

    @pytest.mark.parametrize("length", [0, -3, True, 2.5])
    def test_bad_length(self, length):
        with pytest.raises(ValueError):
            generate_password(length=length)


class TestChains:
    @pytest.fixture
    def passes(self):
        text = "сержант Петренко Іван Петрович, ІПН 1234567890"
        states, out = [text], []
        cur = text
        for _ in range(3):
            d, c = make_masking_dict(), {}
            cur = mask_text_context_aware(cur, d, c)
            d["instance_tracking"] = c
            out.append(d)
            states.append(cur)
        return out, states

    def test_unmasker_without_pass_field(self, passes):
        data, states = passes
        raw = {"passes": data}
        chain = MappingChain.from_dict(raw)
        assert ChainUnmasker(chain).unmask_all(states[-1]) == states[0]
        assert ChainUnmasker(chain).unmask_to_version(states[-1], 1) == states[1]
        chain.add_pass(make_masking_dict())
        assert len(raw["passes"]) == 3

    def test_passes_setter(self, passes):
        data, states = passes
        chain = MappingChain()
        chain.passes = data
        assert chain.current_pass == 3
        assert ChainUnmasker(chain).unmask_all(states[-1]) == states[0]

    def test_forward_is_inverse_of_reverse(self, passes):
        data, _ = passes
        chain = MappingChain()
        for d in data:
            chain.add_pass(d)
        forward, reverse = chain.get_chain_mapping(1, 2), chain.get_chain_mapping(2, 1)
        assert forward and all(reverse.get(v) == k for k, v in forward.items())


class TestSelectiveEmpty:
    @pytest.mark.parametrize("only, exclude", [(",", None), (" , ", None), (None, ",")])
    def test_empty_list_is_an_error(self, only, exclude):
        with pytest.raises(ValueError, match="no masking type"):
            create_filter(only=only, exclude=exclude)


class TestSurnameStems:
    @pytest.mark.parametrize("forms", [
        ("Коваль", "Коваля", "Ковалю", "Ковалем"),
        ("Коваля", "Коваль", "Ковалем"),
        ("Ткач", "Ткача", "Ткачу", "Ткачем"),
        ("Бондар", "Бондаря", "Бондарю", "Бондарем"),
        ("Мороз", "Мороза", "Морозу", "Морозом"),
        ("Ґудзь", "Ґудзя", "Ґудзем"),
        ("Литвин", "Литвина", "Литвину", "Литвином", "Литвинові"),
        ("Кузьмін", "Кузьміна", "Кузьміну", "Кузьміним"),
    ])
    def test_one_stem_per_document(self, forms):
        d = make_masking_dict()
        masks = [mask_surname(f, d, {}).lower() for f in forms]
        assert len(os.path.commonprefix(masks)) >= 4, masks

    def test_document(self):
        text = ("солдат Коваль Олег Петрович\nРапорт солдата Коваля Олега Петровича\n"
                "солдату Ковалю О.П.\nз солдатом Ковалем Олегом Петровичем\n")
        masked, mapping = mask(text)
        masks = [info["masked_as"].lower() for info in mapping["mappings"]["surname"].values()]
        assert len(os.path.commonprefix(masks)) >= 4, masks
        restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
        assert restored == text

    @pytest.mark.parametrize("surname", ["Кузьміним", "Мар'яненко", "Кузьмінський"])
    def test_ascii_apostrophe(self, surname):
        out = mask_surname(surname, make_masking_dict(), {})
        assert "ʼ" not in out and "’" not in out
        out.encode("cp1251")
