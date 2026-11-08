#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки фазера (після 3.1.20): розмаскування не повертало оригінал або
частина ПІБ лишалась відкритою.

  - звання «… медичної служби» з маскою «генерал-майор» не розмасковувалось
    («майор медичної служби» знаходилось усередині «генерал-майор …»);
  - флотські звання маскувались армійськими («капітан 1-го рангу» → «майор»);
  - нерозривний пробіл чи таб усередині звання губився, коли маска мала
    іншу кількість слів;
  - перенос рядка всередині звання не відновлювався, а всередині ПІБ —
    частина ПІБ на іншому рядку лишалась відкритою;
  - ПІБ перед званням, після якого йдуть ще слова, не маскувалось зовсім;
  - заголовок капсом перед ПІБ, прізвище-прикметник у родовому, кличний
    «Любове», подвійне прізвище капсом і апостроф у прізвищі капсом
    з ініціалами, по батькові перед ініціалами;
  - відкрите звання «… медичної служби» ставало маскою іншого звання;
  - номер бригади, розірваний переносом, губив решту назви;
  - маски в одному рядку записувались не в порядку тексту.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.context import parse_hybrid_line  # noqa: E402
from datamasking.masking.declension import VOCATIVE, analyze_name, analyze_patronymic  # noqa: E402
from datamasking.masking.engine import (  # noqa: E402
    _pib_crosses_break, _spaced_rank_bases, normalize_broken_ranks,
)
from datamasking.masking.mask_military import get_rank_category_and_match  # noqa: E402
from datamasking.masking.surname import split_surname  # noqa: E402
from datamasking.rank_data import NAVAL_RANKS  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


def _absent(masked, *words):
    for w in words:
        assert w not in masked, (w, masked)


class TestServiceRankUnmask:
    @pytest.mark.parametrize("text", [
        "полковник медичної служби Петренко Іван Іванович",
        "Рапорт полковника медичної служби Петренка Івана Івановича",
        "Надати відпустку полковнику медичної служби Петренку Івану Івановичу",
        "з полковником медичної служби Петренком Іваном Івановичем",
        "генерал-майора медичної служби Петренка Івана Івановича",
        "полковнику медичної служби у відставці Петренку Івану Івановичу",
    ])
    def test_roundtrip(self, text):
        masked, _ = _rt(text)
        _absent(masked, "Петренк", "Іван")

    def test_mask_is_hyphenated_rank(self):
        masked, mapping = _rt("полковник медичної служби Петренко Іван Іванович")
        assert mapping["mappings"]["rank"]["полковник"]["masked_as"] == "генерал-майор"
        assert masked.startswith("генерал-майор медичної служби ")


class TestNavalRanks:
    @pytest.mark.parametrize("rank, category, match", [
        ("капітан 1-го рангу", "naval", "капітан 1-го рангу"),
        ("капітан-лейтенант", "naval", "капітан-лейтенант"),
        ("капітан", "army", "капітан"),
        ("сержант", "army", "сержант"),
        ("старший матрос", "naval", "старший матрос"),
    ])
    def test_category(self, rank, category, match):
        assert get_rank_category_and_match(rank) == (category, match)

    @pytest.mark.parametrize("text", [
        "капітан 1-го рангу Лисенко Богдан Романович",
        "капітану 3-го рангу Петру Васильовичу Сидорову оголосити подяку",
        "капітан-лейтенант Лисенко Богдан Романович",
    ])
    def test_mask_is_naval(self, text):
        masked, mapping = _rt(text)
        masks = [v["masked_as"] for v in mapping["mappings"]["rank"].values()]
        assert masks and all(m in NAVAL_RANKS for m in masks), masks


class TestSpacedRanks:
    @pytest.mark.parametrize("text", [
        "капітан\xa01-го рангу Лисенко Богдан Романович",
        "старший\xa0майстер-сержант Коваль Галина Іванівна",
        "старшому\xa0моряку Вікторії Ігорівні Ковальській",
        "старшій\xa0сержантці Коваль Галині Іванівні",
        "сержант\xa0медичної\xa0служби Коваль Олег Іванович",
        "старшому сержанту\xa0медичної служби Коваль Олегу Івановичу",
        "полковнику медичної служби у\xa0відставці Петренку Івану Івановичу",
        "капітан\tюстиції Коваль Олег Іванович",
        "головний  сержант Коваль Олег Іванович\nголовний сержант Петренко Іван Іванович",
    ])
    def test_roundtrip_keeps_separators(self, text):
        masked, _ = _rt(text)
        assert ("\xa0" in masked) == ("\xa0" in text) and ("\t" in masked) == ("\t" in text)

    def test_bases(self):
        assert _spaced_rank_bases("старший\xa0сержант Коваль") == frozenset({"старший сержант"})
        assert _spaced_rank_bases("сержант\xa0медичної служби Коваль") == frozenset({"сержант"})
        assert _spaced_rank_bases("старший сержант Коваль\nсолдат Петренко") == frozenset()
        assert _cfg.SPACED_RANK_BASES == frozenset()


class TestLineBreaks:
    @pytest.mark.parametrize("text", [
        "Призначити старшого\nсержанта Петренка Івана Івановича на посаду.",
        "Призначити старшого сержанта\nПетренка Івана Івановича на посаду.",
        "Призначити старшого сержанта Петренка\nІвана Івановича на посаду.",
        "Призначити старшого сержанта Петренка Івана\nІвановича на посаду.",
        "Призначити Петренка\nІвана Івановича на посаду.",
        "Призначити Петренка\r\nІвана Івановича на посаду.\r\n",
        "полковнику Олегу Петровичу\nПетренку оголосити подяку",
        "Шановний Віталію\nРомановичу! полковник медичної служби у відставці",
        "капітан медичної\nслужби в запасі Коваль Олег Петрович",
    ])
    def test_masked_and_restored(self, text):
        masked, _ = _rt(text)
        _absent(masked, "Петренк", "Іван", "Олег", "Петрович", "Віталі", "Романович", "Коваль")
        assert masked.count("\n") == text.count("\n")

    @pytest.mark.parametrize("prev, nxt", [
        ("1. солдат Петренко Іван Іванович", "2. солдат Коваль Олег Петрович"),
        ("солдат Петренко Іван Іванович", "Коваль Олег Петрович"),
        ("Командир військової частини", "полковник Петренко Іван Іванович"),
        ("НАКАЗУЮ:", "Петренко Іван Іванович"),
        ("Шановний Олегу Петровичу!", "Петренко повідомив про виконання."),
        ("перший рядок", "другий рядок"),
    ])
    def test_complete_lines_not_joined(self, prev, nxt):
        assert not _pib_crosses_break(prev, nxt)

    def test_public_normalizer_unchanged(self):
        assert normalize_broken_ranks("старшого\nсержанта") == "старшого сержанта"

    def test_list_lines_keep_structure(self):
        text = "1. солдат Петренко Іван Іванович\n2. солдат Коваль Олег Петрович"
        masked, _ = _rt(text)
        assert masked.startswith("1. ") and "\n2. " in masked


class TestPibBeforeRank:
    @pytest.mark.parametrize("text, kept", [
        ("Петренко Іван Іванович доповів капітану про виконання.", " доповів капітану про виконання."),
        ("Олег Петрович доповів капітану про виконання.", " доповів капітану про виконання."),
        ("Петренко Іван Іванович, 1990 р.н., солдат за контрактом", ", 1990 р.н., солдат за контрактом"),
        ("Коваль Тетяна Сергіївна, рядовий склад роти, прибула.", ", рядовий склад роти, прибула."),
        ("Шановний Олегу Петровичу! Прошу надати відпустку полковнику медичної служби",
         "! Прошу надати відпустку полковнику медичної служби"),
    ])
    def test_masked(self, text, kept):
        masked, _ = _rt(text)
        assert masked.endswith(kept), masked
        _absent(masked, "Петренко", "Іван", "Олег", "Петрович", "Коваль", "Тетяна")

    def test_rank_pib_and_pib_before_it(self):
        text = "Петренко Іван Іванович доповів капітану Коваленку Олегу Петровичу про виконання."
        masked, mapping = _rt(text)
        _absent(masked, "Петренко", "Коваленк", "Іван", "Олег")
        assert set(mapping["mappings"]["rank"]) == {"капітан"}

    def test_rank_words_are_not_anchors(self):
        assert parse_hybrid_line("Капітан Петренко Іван Іванович доповів")[:2] == (
            "Капітан", "Петренко Іван Іванович")
        assert mask("Командир роти капітан доповів про виконання")[0] == "Командир роти капітан доповів про виконання"


class TestHeadingsAndAdjectives:
    @pytest.mark.parametrize("text, surname", [
        ("ВИТЯГ З НАКАЗУ Коваль Сергій Васильович доповів", "Коваль"),
        ("ВИТЯГ З НАКАЗУ Білий Василь Васильович доповів", "Білий"),
        ("ВИТЯГ З НАКАЗУ БІЛИЙ Тарас Васильович доповів", "БІЛИЙ"),
        ("Рапорт Білого Ярослава Миколайовича про відпустку.", "Білого"),
    ])
    def test_surname_masked(self, text, surname):
        masked, mapping = _rt(text)
        assert surname in mapping["mappings"]["surname"], mapping["mappings"]["surname"]
        _absent(masked, surname, "Васильович", "Миколайович")
        assert masked.split()[0] == text.split()[0]

    def test_position_title_still_untouched(self):
        text = "на посаду МАСКУВАЛЬНИКОМ ІМІТАЦІЙНОГО ВІДДІЛЕННЯ ІНЖЕНЕРНО-МАСКУВАЛЬНОГО ВЗВОДУ"
        assert mask(text)[0] == text

    def test_feminine_adjective_genitive_shares_stem(self):
        assert split_surname("Білої") == ("біл", "ої", "а")
        masked, mapping = _rt("Біла Людмила Юріївна вибула.\nРапорт Білої Людмили Юріївни.\n"
                              "Надати Білій Людмилі Юріївні.\nз Білою Людмилою Юріївною")
        masks = {v["masked_as"] for k, v in mapping["mappings"]["surname"].items()}
        stems = {split_surname(m)[0] for m in masks}
        assert len(stems) == 1, masks


class TestVocativeLyubov:
    def test_analyze(self):
        assert analyze_name("Любове")[:3] == ("любов", VOCATIVE, "female")
        assert analyze_name("Любове", "female").known

    def test_address(self):
        masked, mapping = _rt("Шановна Любове Андріївно!")
        assert masked.startswith("Шановна ") and not mapping["mappings"]["surname"]
        pat = masked.split()[2].rstrip("!")
        assert analyze_patronymic(pat)[1:] == (VOCATIVE, "female"), masked


class TestInitials:
    @pytest.mark.parametrize("text, words", [
        ("ПЕТРЕНКО-КОВАЛЬ І.М. прибув", ("ПЕТРЕНКО", "КОВАЛЬ")),
        ("О.П. ПЕТРЕНКО-КОВАЛЬ підпис", ("ПЕТРЕНКО", "КОВАЛЬ")),
        ("І.М. ДОРОШЕНКО-ҐУДЗЬ прибув", ("ДОРОШЕНКО", "ҐУДЗЬ")),
        ("ПИЛИП'ЮК О.І. прибув", ("ПИЛИП", "'ЮК")),
        ("О.І. ПИЛИП'ЮК прибув", ("ПИЛИП", "'ЮК")),
        ("ознайомлений. Л.І.\nКоваль паспорт", ("Коваль",)),
        ("підпис Петренко\nО.П. дата", ("Петренко",)),
        ("О.І.\nПИЛИП'ЮК Дата народження 01.01.1990", ("ПИЛИП",)),
    ])
    def test_surname_masked(self, text, words):
        masked, _ = _rt(text)
        _absent(masked, *words)

    @pytest.mark.parametrize("text", [
        "Видати квиток капітан-лейтенанта Мороз Ольги Богданівни Л.А. Мороз",
        "Видати квиток сержанта Хмари Юрія Юрійовича О.Ю. ХМАРІ паспорт",
    ])
    def test_patronymic_before_initials(self, text):
        masked, mapping = _rt(text)
        assert "Богданівни" not in mapping["mappings"]["surname"]
        assert "Юрійовича" not in mapping["mappings"]["surname"]

    @pytest.mark.parametrize("text", ["Додаток А.\nПетренко прибув", "М.П.\nКомандир частини"])
    def test_not_initials(self, text):
        assert mask(text)[0] == text

    def test_patronymic_shaped_surname_still_masked(self):
        masked, _ = _rt("наказ Петрович О.П.")
        assert "Петрович" not in masked


class TestOpenServiceRankNotAMask:
    def test_open_rank_with_service(self):
        text = "Командир роти капітан медичної служби\nпідполковник Петренко Іван Іванович"
        masked, mapping = _rt(text)
        assert masked.startswith("Командир роти капітан медичної служби\n")
        assert mapping["mappings"]["rank"]["підполковник"]["masked_as"] != "капітан"


class TestBrigadeAcrossLines:
    @pytest.mark.parametrize("nl", ["\n", "\r\n"])
    def test_rest_of_name_kept(self, nl):
        text = f"у складі 60 окремої{nl}механізованої бригади прибув"
        masked, _ = _rt(text)
        assert masked.endswith(f" окремої{nl}механізованої бригади прибув") and "60" not in masked


class TestInstanceOrderInLine:
    @pytest.mark.parametrize("text", [
        "Шановний Іване Дмитровичу! Надати відпустку генералу Зінченку Івану Дмитровичу з 01 по 10 число.",
        "Шановна Тетяно Петрівно! Видати сержанту Коваль Тетяни Петрівни квиток та Коваль Тетяні Петрівні",
    ])
    def test_roundtrip(self, text):
        _rt(text)


class TestRankPibAdjacency:
    """Звання й ПІБ — пара упритул, а не перше входження ПІБ у рядку. До
    виправлення перевірка переносу рядка на «М.О. Ткачук Адмірал\\nТкачук
    М.О.» дублювала фрагмент на кожній ітерації і зависала."""

    def test_no_hang(self):
        text = ("вих. № 633/60-дск від\n06.04.2029 №БР-289/52-К\nпаспорт 460628459, ІПН\n"
                "3643164026 Командир військової\nчастини Згідно\xa0із Законом\nУкраїни від 08.03.2019 №\n"
                "5855-IX М.О. Ткачук Адмірал\nТкачук М.О. — ознайомлений\nЗгідно із Законом України від\n"
                "21.03.2026 № 970-IX Про\nпризначення на посаду та\nприсвоєння військових звань")
        masked, _ = _rt(text)
        assert "Ткачук" not in masked
        # результат не важливий — лише що виклик завершується
        _pib_crosses_break("5855-IX М.О. Ткачук Адмірал", "Ткачук М.О. — ознайомлений")

    def test_rank_goes_with_adjacent_surname(self):
        masked, mapping = _rt("Ткачук доповів, а солдат Ткачук Іван Іванович прибув")
        assert "Ткачук" not in masked and set(mapping["mappings"]["rank"]) == {"солдат"}
        assert set(mapping["mappings"]["name"]) == {"Іван"}


class TestChainedInitials:
    """«Ю.А. Зінченко Н.І. Савчук»: кандидати перекриваються; береться набір
    із найбільшою кількістю ПІБ (раніше — найдовший перший: «Зінченко Н.І.»,
    і «Ю.А.» та «Савчук» лишались відкритими)."""

    @pytest.mark.parametrize("text", [
        "Ю.А. Зінченко Н.І. Савчук підписали",
        "Ю.А. ЗІНЧЕНКО Н.І. САВЧУК підписали",
        "на поточний період. Ю.А. ЗІНЧЕНКО Н.І.\nСАВЧУК майстер-сержантом Ткачук О.І. —\nпідпис",
    ])
    def test_all_masked(self, text):
        masked, mapping = _rt(text)
        _absent(masked, "Ю.А.", "Зінченко", "ЗІНЧЕНКО", "Савчук", "САВЧУК", "Н.І.")
        assert len(mapping["mappings"]["surname"]) >= 2

    @pytest.mark.parametrize("text, kept", [
        ("Кім О.П. Петренко", "Кім "),          # один збіг — як раніше, довший
        ("Петренко\nО.П. Коваль", "Петренко\n"),  # у межах рядка — перед переносом
    ])
    def test_single_overlap_unchanged(self, text, kept):
        masked, _ = _rt(text)
        assert masked.startswith(kept), masked
