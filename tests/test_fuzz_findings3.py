#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки третього прогону фазера (після 3.1.21): таблиці й CSV, латинські
літери-двійники, подвійні імена, великі документи.

  - CSV з Excel («Петренко Іван Петрович;сержант;1234567890»): клітинка
    після «;» без пробілу була одним словом, і по батькові лишалось відкритим;
  - подвійне ім'я «Анна-Марія» розмасковувалось як «Анна-марія»;
  - номери входжень маски рахувались за її регістром у першій появі, а в
    тексті маска стоїть у регістрі кожного входження: коли два оригінали
    мали маски, що різнились лише регістром («ГОРДІЇВНИ» / «Гордіївни»),
    одне входження не розмасковувалось. Подвійне прізвище в рядку капсом
    розмасковувалось капсом і в звичайному рядку;
  - у великому наказі, де відкрито згадано багато звань, маска звання
    збігалася з відкритим званням, і unmask підміняв його;
  - «…капітаном» у кінці рядка і «СТАРШИЙ ЛЕЙТЕНАНТ …» на наступному:
    «СТАРШИЙ» маскувалось як прізвище;
  - латинська «o» в імені («Ярoслав»): маскою ставало справжнє ім'я
    («Ярослав»), а прізвище в непрямому відмінку лишалось відкритим;
  - звання «… запасу» / «… резерву» і давальний на «-ові» («майорові»)
    лишались відкритими.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.declension import fold_homoglyphs  # noqa: E402
from datamasking.masking.mask_military import mask_rank  # noqa: E402
from datamasking.rank_data import RANK_DATIVE_OVI, RANK_TO_NOMINATIVE  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import _apply_original_case, check_mapping_version  # noqa: E402
from tests.test_initials import make_masking_dict, mask  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, stats = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping, stats


def _absent(masked, *words):
    for w in words:
        assert w not in masked, (w, masked)


class TestCsv:
    @pytest.mark.parametrize("text", [
        "ПІБ;Звання;ІПН\nПетренко Іван Петрович;сержант;1234567890",
        "Петренко;Іван;Петрович;сержант;1234567890",
        "сержант;Петренко;Іван;Петрович;1234567890",
        "1;Петренко Іван Петрович;12.05.1990;сержант",
        "Петренко Іван Петрович,сержант,1234567890",
    ])
    def test_masked_and_separators_kept(self, text):
        masked, _, _ = _rt(text)
        _absent(masked, "Петренк", "Іван", "Петрович", "1234567890")
        assert masked.count(";") == text.count(";") and masked.count(",") == text.count(",")

    def test_prose_semicolon_still_ends_name(self):
        masked, mapping, _ = _rt("Петренко Іван; Коваль Олег Петрович")
        assert "; " in masked
        assert not any(";" in k for cat in mapping["mappings"].values() for k in cat)


class TestHyphenatedNameCase:
    @pytest.mark.parametrize("text", [
        "Анна-Марія Петрівна Коваль прибула.",
        "солдат Коваль Анна-Марія Петрівна",
        "АННА-МАРІЯ ПЕТРІВНА КОВАЛЬ прибула; Анна-Марія Петрівна Коваль",
    ])
    def test_roundtrip(self, text):
        _rt(text)

    def test_rank_keeps_lower_second_part(self):
        assert _apply_original_case("Полковник", "генерал-майор") == "Генерал-майор"
        assert _apply_original_case("Алла", "Анна-Марія") == "Анна-Марія"
        assert _apply_original_case("Алла", "АННА-МАРІЯ") == "Анна-Марія"

    def test_double_surname_case_from_text(self):
        assert _apply_original_case("Доличенко-Ґубко", "ДОРОШЕНКО-ҐУДЗЬ") == "Дорошенко-Ґудзь"
        assert _apply_original_case("ДОЛИЧЕНКО-ҐУБКО", "Дорошенко-Ґудзь") == "ДОРОШЕНКО-ҐУДЗЬ"


class TestInstanceCase:
    MAPPING = {
        "version": "3.1.22",
        "mappings": {"patronymic": {
            "петрівни": {"masked_as": "ГОРДІЇВНИ", "instances": [1, 3]},
            "богданівни": {"masked_as": "Гордіївни", "instances": [2]},
        }},
    }

    def test_new_mapping_counts_case_insensitively(self):
        mapping = dict(self.MAPPING, instance_case="insensitive")
        restored, stats = unmask_text_v2("ГОРДІЇВНИ, Гордіївни, Гордіївни", mapping, "v2.1")
        assert restored == "ПЕТРІВНИ, Богданівни, Петрівни"
        assert stats["skipped_count"] == 0

    def test_legacy_mapping_counts_by_exact_case(self):
        legacy = {"version": "2.6.5", "mappings": {"name": {
            "Петро": {"masked_as": "Павло", "instances": [1, 2]},
            "ПЕТРО": {"masked_as": "ПАВЛО", "instances": [1]},
        }}}
        restored, _ = unmask_text_v2("Павло ПАВЛО Павло", legacy, check_mapping_version(legacy))
        assert restored == "Петро ПЕТРО Петро"

    def test_masking_marks_mapping(self):
        _, mapping, _ = _rt("сержант Петренко Іван Петрович")
        assert mapping["instance_case"] == "insensitive"

    @pytest.mark.parametrize("text", [
        "ШЕВЧУК;ОКСАНИ;ПЕТРІВНИ;МОЛОДШОГО СЕРЖАНТА;2160850962\n"
        "24. майора Мороз Любові Богданівни\n"
        "Рапорт молодшого сержанта Шевчук Оксани Петрівни.\n",
        "Дорошенку-Ґудзю П.Р. — ознайомлений\n"
        "сержант ДОРОШЕНКО-ҐУДЗЬ ПЕТРО РОМАНОВИЧ\n"
        "Рапорт сержанта Дорошенка-Ґудзя Петра Романовича.\n",
    ])
    def test_documents(self, text):
        _rt(text)


class TestRankMaskWhenNeighboursAreOpen:
    def test_nearest_free_rank_beyond_shift(self):
        hierarchy = [r.lower() for r in _cfg.ARMY_RANKS]
        idx = hierarchy.index("майор")
        _cfg.AVOID_RANK_MASKS = frozenset(hierarchy[idx - 2:idx + 3]) - {"майор"}
        masked = mask_rank("майор", make_masking_dict(), {})
        assert masked.lower() not in _cfg.AVOID_RANK_MASKS and masked.lower() != "майор"

    def test_no_free_rank_keeps_rank(self):
        _cfg.AVOID_RANK_MASKS = frozenset(r.lower() for r in _cfg.ARMY_RANKS) - {"майор"}
        assert mask_rank("майор", make_masking_dict(), {}) == "майор"

    def test_document_with_many_open_ranks(self):
        open_ranks = ["капітану", "майору", "лейтенанту", "старшому лейтенанту", "підполковнику",
                      "полковнику", "молодшому лейтенанту", "прапорщику", "старшому прапорщику"]
        lines = [f"Петренко Іван Петрович доповів {r} роти про виконання." for r in open_ranks]
        lines += ["капітан Коваленко Олег Олегович прибув.", "майор Мельник Тарас Петрович прибув."]
        _rt("\n".join(lines))


class TestRankAfterRank:
    @pytest.mark.parametrize("text, kept", [
        ("Ковальським Романом Ігоровичем, 1994 р.н., капітаном\n"
         "СТАРШИЙ ЛЕЙТЕНАНТ ПИЛИП'ЮК ТАРАС ОЛЕГОВИЧ.", "ПИЛИП"),
        ("капітаном старшим лейтенантом Петренком", "Петренк"),
        ("капітан старший лейтенант Петренко Іван Іванович", "Петренк"),
    ])
    def test_second_rank_is_not_a_surname(self, text, kept):
        masked, mapping, _ = _rt(text)
        _absent(masked, kept)
        assert not any("старш" in k.lower() for k in mapping["mappings"].get("surname", {}))

    def test_rank_word_surname_still_masked(self):
        masked, _, _ = _rt("капітан Майор Іван Іванович")
        _absent(masked, "Майор", "Іван")


class TestHomoglyphs:
    def test_fold(self):
        assert fold_homoglyphs("Ярoслав") == "ярослав"
        assert fold_homoglyphs("John") == "john"

    @pytest.mark.parametrize("text, secrets", [
        ("Литвин Ярoслав Петрович прибув", ("Литвин", "Ярослав", "Ярoслав")),
        ("сержант Литвин Ярoслав Петрович", ("Литвин", "Ярослав", "Ярoслав")),
        ("Литвином Ярославoм Петровичем, 1980 р.н., капітан-лейтенантом", ("Литвином", "Ярослав")),
        ("Рапорт Литвина Ярославa Петровича", ("Литвина", "Ярослав")),
        ("Шановна Мaріє Іванівно!", ("Марі", "Мaрі")),
    ])
    def test_masked(self, text, secrets):
        masked, _, _ = _rt(text)
        _absent(masked, *secrets)


class TestRankForms:
    @pytest.mark.parametrize("text, rank", [
        ("майор запасу Петренко Іван Петрович", "майор "),
        ("майора запасу Петренка Івана Петровича", "майора "),
        ("старший лейтенант резерву ПЕТРЕНКО Іван Петрович", "старший лейтенант"),
        ("капітан медичної служби запасу Петренко Іван Петрович", "капітан "),
    ])
    def test_reserve(self, text, rank):
        masked, _, _ = _rt(text)
        assert not masked.startswith(rank) and (" запасу " in masked or " резерву " in masked)

    @pytest.mark.parametrize("text, rank", [
        ("Надати відпустку майорові Петренку Івану Петровичу", "майорові"),
        ("оголосити подяку солдатові Коваленку Олегу Олеговичу", "подяку солдатові"),
        ("старшому лейтенантові Петренку Івану Петровичу та старшому лейтенанту "
         "Коваленку Олегу Олеговичу", "лейтенантові"),
        ("Капітанові 1-го рангу Мельнику Тарасу Петровичу", "Капітанові"),
        ("МАЙОРОВІ ПЕТРЕНКУ ІВАНУ ПЕТРОВИЧУ", "МАЙОРОВІ"),
        ("рядовий Петренко Іван Петрович; рядовому Коваленку Олегу Олеговичу; "
         "солдатові Мельнику Тарасу Петровичу", "; солдатові"),
    ])
    def test_dative_ovi(self, text, rank):
        masked, _, _ = _rt(text)
        _absent(masked, rank)
        assert "ові " in masked or "ОВІ " in masked

    def test_ovi_forms(self):
        assert RANK_DATIVE_OVI["майор"] == "майорові"
        assert RANK_DATIVE_OVI["старший лейтенант"] == "старшому лейтенантові"
        assert "рядовий" not in RANK_DATIVE_OVI
        assert RANK_TO_NOMINATIVE["генерал-майорові"] == ("генерал-майор", "dative_ovi", "male")
