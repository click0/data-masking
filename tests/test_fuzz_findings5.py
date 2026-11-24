#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Знахідки п'ятого пошуку помилок (після 3.2.0): «суп» із випадкових слів і
чисел, мутації прикладів документів, знаки впритул до ПІБ.

  - маркер переліку, нумерація чи мітка з двокрапкою впритул до слова
    («-Петренко Іван Петрович», «1)Петренко…», «ПІБ:Петренко…»): прізвище
    лишалось відкритим, а звання після маркера не маскувалось;
  - ПІБ із двох слів у лапках чи дужках, ПІБ в одинарних лапках, прізвище
    «О'Коннор», рядок капсом «ПЕТРЕНКО ІВАН ПЕТРОВИЧ:» — лишались відкритими;
  - тире, «/» чи дужка між двома особами: рядок кидався цілком або по
    батькові лишалось відкритим;
  - unmask не знаходив маску, якщо перед «№» стояла літера («наказ№14дск»),
    перед словом — цифра («22.10.2004Іванов», «1950капітану»), а звання після
    «звання:» / «посада/» бралось без першого слова;
  - фаза ініціалів маскувала частину слова («В.Савчука2», «12А. Петренко»),
    а основний розбір — маску ще раз («Олег Лисенко<таб>Коваль П.П.»);
  - слова змішаним регістром («Старший Лейтенант», «Петренко-Коваль» на
    місці по батькові) поверталися малими літерами.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking.context import (  # noqa: E402
    analyze_br_keyword, clean_line_before_parsing, looks_like_pib_line, separate_glued,
)
from datamasking.masking.helpers import ends_clause, strip_word  # noqa: E402
from datamasking.masking.language import looks_like_name  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import _apply_original_case, check_mapping_version  # noqa: E402
from datamasking.unmasking.io import validate_mapping_schema  # noqa: E402
from tests.test_initials import mask  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


def _unmask(masked, mappings):
    mapping = {"version": "3.2.1", "instance_case": "insensitive", "mappings": mappings}
    return unmask_text_v2(masked, mapping, check_mapping_version(mapping))[0]


class TestGluedMarkers:
    """Знак упритул до слова — не частина слова."""

    @pytest.mark.parametrize("text", [
        "-Петренко Іван Петрович прибув",
        "–Петренко Іван Петрович прибув",
        "—Петренко Іван Петрович прибув",
        "•Петренко Іван Петрович прибув",
        "…Петренко Іван Петрович прибув",
        "1)Петренко Іван Петрович",
        "а)Петренко Іван Петрович",
        "12.Петренко Іван прибув до частини",
        "-Петренко І.П. прибув",
        "-Петренко Іван прибув до частини",
        "ПІБ:Петренко Іван Петрович",
        "Виконавець:сержант Петренко Іван Петрович",
        "(Петренко Іван) прибув",
        "[Петренко Іван] прибув",
        "**Петренко Іван** прибув",
        "‘Петренко Іван Петрович’ прибув",
        "'Петренко І.П.' прибув",
        "’майор Петренко’ прибув",
        "_Петренко Іван Петрович_ прибув",
        "__майор Петренко__",
        "Петренко Іван Петрович- командир",
        "(майор Петренко-",
        "ПЕТРЕНКО ІВАН ПЕТРОВИЧ:",
        "Сержант вибув.Петренко Іван Петрович прибув.",
        "наказ виконано.Петренко І.П. прибув",
    ])
    def test_surname_is_masked(self, text):
        masked, _ = _rt(text)
        assert "петренко" not in masked.lower(), masked

    @pytest.mark.parametrize("text", [
        "-майор Петренко прибув",
        "•майор Петренко Іван Петрович",
        "1)майор Петренко Іван Петрович",
        "‘майор Петренко прибув",
        "_майор Петренко прибув",
        "Звання:майор Петренко Іван Петрович",
    ])
    def test_rank_after_marker_is_masked(self, text):
        masked, mapping = _rt(text)
        assert "майор" in mapping["mappings"]["rank"], mapping["mappings"]["rank"]
        assert "петренко" not in masked.lower(), masked

    @pytest.mark.parametrize("text", [
        "нагороджений відзнакою «Золота Зірка» у 2024 році",
        "товариство \"Нова Пошта\" доставило",
        "навчання „Східний Вал“ завершено",
    ])
    def test_quoted_title_is_not_a_name(self, text):
        assert _rt(text)[0] == text

    def test_heading_with_colon_is_still_a_heading(self):
        assert _rt("НАКАЗУЮ:\nВИРІШИЛИ ТАКЕ:\n")[0] == "НАКАЗУЮ:\nВИРІШИЛИ ТАКЕ:\n"
        assert not looks_like_pib_line("НАКАЗУЮ:")

    @pytest.mark.parametrize("line, expected", [
        ("звання:старший матрос", "звання: старший матрос"),
        ("посада/старший сержант", "посада/ старший сержант"),
        ("-Петренко", "- Петренко"),
        ("1)Петренко", "1) Петренко"),
        ("12.Петренко", "12. Петренко"),
        ("_Петренко Іван_", "_ Петренко Іван_"),
        ("1991старшого матроса", "1991 старшого матроса"),
        ("Васильович—___RANK_MASKED_1___", "Васильович— ___RANK_MASKED_1___"),
        ("___PIB_MASKED_2___/старшого", "___PIB_MASKED_2___/ старшого"),
        ("вибув.Петренко Іван", "вибув. Петренко Іван"),
    ])
    def test_separate_glued(self, line, expected):
        assert separate_glued(line) == expected

    @pytest.mark.parametrize("line", [
        "в/ч А1234", "п/п", "___RANK_MASKED_1___ ___PIB_MASKED_2___", "капітан 2-го рангу", "з 01.02.2024",
        "Мар'яна Петренко-Коваль", "- Петренко", "ІПН1234567890", "І.Петренко", "ст.сержант", "м.Київ",
        "т.в.о.Командира", "№957/ШТАБ Марію", "№ 7-К/Ярославу", "1/старшим",
    ])
    def test_separate_glued_keeps(self, line):
        assert separate_glued(line) == line

    def test_strip_word(self):
        assert strip_word("‘Петренко’") == "Петренко"
        assert strip_word("Петренко-") == "Петренко"
        assert strip_word("Іван_") == "Іван"
        assert strip_word("О'Коннор") == "О'Коннор"
        assert strip_word("…БР", leading_punct=True) == "БР"

    def test_ends_clause(self):
        assert ends_clause("Васильович—") and ends_clause("Євген/") and ends_clause("Іван…")
        assert not ends_clause("/Петренко/") and not ends_clause("Петренко")

    def test_name_has_only_letters(self):
        assert not looks_like_name("Василівні№") and not looks_like_name("Петренко=")
        assert looks_like_name("Петренко") and looks_like_name("Нечуй-Левицький") and looks_like_name("Дем’янчук")


class TestTwoPeopleInOneLine:
    @pytest.mark.parametrize("text, secrets", [
        ("Ярошенко Олег Васильович—підполковнику Мельнику Ігорю Петровичу", ["васильович", "мельнику"]),
        ("контр-адмірала Поліщук Євген—Євген ПОЛІЩУК", ["поліщук", "євген"]),
        ("полковника Савчук Євген/Савчук Євген Олександрович", ["савчук", "євген"]),
        ("Кравченко Мар'яни Дмитрівни/майора Мороза", ["дмитрівни", "мороза"]),
        ("Доповів [Петро БІЛИЙ].", ["петро", "білий"]),
        ("відповідальний (Олег МЕЛЬНИК); (підпис)", ["олег", "мельник"]),
        ("Сергій РУДЕНКО\tВасиль ДОРОШЕНКО", ["руденко", "василь", "дорошенко"]),
        ("С.Б. Зінченко|Світлана ЗІНЧЕНКО", ["зінченко", "світлана"]),
        ("Коваль Любові Андріївні—Роман ПИЛИП'ЮК/", ["андріївні", "роман", "пилип'юк"]),
        ("Коваль Тетяна Дмитрівна,майором Руденком Юрієм Олександровичем.", ["дмитрівна", "руденком"]),
        ("підполковнику Кравченку Ігорю Ігоровичу/Є.С. Зінченко!", ["ігоровичу", "зінченко"]),
    ])
    def test_everyone_is_masked(self, text, secrets):
        masked, _ = _rt(text)
        for secret in secrets:
            assert secret not in masked.lower(), (secret, masked)

    def test_dash_and_rank_stay_in_masked_text(self):
        # до 3.2.1 «Васильович—підполковнику» було одним словом: тире і звання
        # зникали з маскованого тексту
        masked, mapping = _rt("Ярошенко Олег Васильович—підполковнику Мельнику Ігорю Петровичу")
        assert "—" in masked and "підполковник" in mapping["mappings"]["rank"]

    def test_name_surname_pairs_keep_roles(self):
        _masked, mapping = _rt("Сергій РУДЕНКО\tВасиль ДОРОШЕНКО")
        assert set(mapping["mappings"]["surname"]) == {"РУДЕНКО", "ДОРОШЕНКО"}
        assert "patronymic" not in mapping["mappings"] or not mapping["mappings"]["patronymic"]

    def test_name_caps_surname_patronymic_is_one_person(self):
        _masked, mapping = _rt("Іван ПЕТРЕНКО Петрович прибув")
        assert "петрович" in mapping["mappings"]["patronymic"]


class TestUnmaskBoundaries:
    @pytest.mark.parametrize("text", [
        "наказ№14дск від 01.02.2024",
        "статті№114дск",
        "Наказ№5 від 01.02.2024",
        "123№БР456",
        "майором№БР844",
        "№18дск2020",
        "солдат 22.10.2004Іванов Петро Іванович",
        "доповісти 28.02.1950капітану 2-го рангу Ткаченку",
        "звання 14.04.1997старшому лейтенанту Морозу",
        "2004Ткачук Т.",
        "_Петренко І.П._ прибув",
        "_І.П. Петренко прибув",
        "Звання:старший матрос Петренко Іван Петрович",
        "посада/старший лейтенант Коваль Олег Іванович",
        "області/старшого матроса Світланою",
        "./старшому матросу Тарас",
        "1991старшого матроса Петренка Івана",
        "1СТАРШИМ МАТРОСОМ Віталій",
        "рядового1складу солдата Бондаренка Івана Петровича",
        "АДМІРАЛ2 віце-адміралом Євгену",
        "1912рядового\nсолдата Бондаренко",
        "М/старшому матросу Тарас",
        "№БР7-К/Ярославу Поліщук",
        "№БР78-К/АНДРІЇВНІ Богданівні",
        "№957/ШТАБ\tМарію",
        "Поліщуку Шевчука №907/Поліщуку",
        "майор-      Коваленко",
        "майора юстиції.Мороза;Володимиру",
    ])
    def test_round_trip(self, text):
        _rt(text)

    def test_rank_after_colon_is_whole(self):
        _masked, mapping = _rt("Звання:старший матрос Петренко Іван Петрович")
        assert list(mapping["mappings"]["rank"]) == ["старший матрос"]

    def test_mask_after_number_sign_glued_to_a_word(self):
        mappings = {"br_number": {"№14дск": {"masked_as": "№19дск", "instances": [1]}}}
        assert _unmask("наказ№19дск", mappings) == "наказ№14дск"

    def test_word_mask_next_to_digits(self):
        mappings = {"surname": {"Іванов": {"masked_as": "Івенов", "instances": [1, 2]}}}
        assert _unmask("2004Івенов і Івенов5", mappings) == "2004Іванов і Іванов5"

    def test_word_mask_inside_a_word_is_not_a_mask(self):
        mappings = {"surname": {"Іванов": {"masked_as": "Івенов", "instances": [1]}}}
        assert _unmask("хІвенов Івеновський Івенов", mappings) == "хІвенов Івеновський Іванов"

    def test_initials_mask_is_not_found_in_a_year(self):
        # «Р.» — маска ініціала; «2024р.» і «12Р.» — не вона
        mappings = {"initials": {"К.": {"masked_as": "Р.", "instances": [1]}},
                    "surname": {"Петренко": {"masked_as": "Пебоженко", "instances": [1]}}}
        assert _unmask("від 01.02.2024р. буд. 12Р. Пебоженко Р.", mappings) == "від 01.02.2024р. буд. 12Р. Петренко К."

    def test_rank_inside_compound_is_not_a_rank(self):
        mappings = {"rank": {"капітан": {"masked_as": "майор", "instances": [1]}}}
        assert _unmask("генерал-майор і майор-інструктор, -майор Коваль, майор- Мороз", mappings) == \
            "генерал-майор і майор-інструктор, -капітан Коваль, майор- Мороз"
        mappings["rank"]["капітан"]["instances"] = [1, 2]
        assert _unmask("-майор Коваль, майор- Мороз", mappings) == "-капітан Коваль, капітан- Мороз"


class TestCombinedUnmaskRegex:
    """Маски згруповано за першим символом (швидкодія); результат — як у
    одного переліку «довша маска першою»."""

    def test_longer_mask_first(self):
        mappings = {"surname": {"Іванов": {"masked_as": "Ковар", "instances": [1]},
                                "Петренко": {"masked_as": "Коваренко", "instances": [1]}}}
        assert _unmask("Коваренко і Ковар", mappings) == "Петренко і Іванов"

    def test_first_letter_in_any_case(self):
        mappings = {"surname": {"Іванов": {"masked_as": "Ковар", "instances": [1, 2, 3]}}}
        assert _unmask("КОВАР, ковар і Ковар", mappings) == "ІВАНОВ, іванов і Іванов"

    def test_initials_and_surname_with_the_same_first_letter(self):
        mappings = {"initials": {"П.": {"masked_as": "К.", "instances": [1]}},
                    "surname": {"Іванов": {"masked_as": "Ковар", "instances": [1]}}}
        assert _unmask("Ковар К. прибув у буд. 12К.", mappings) == "Іванов П. прибув у буд. 12К."

    def test_text_date_before_a_number_with_the_same_digits(self):
        mappings = {"date_text": {"28 вересня 2025": {"masked_as": "31 грудня 2025", "instances": [1, 2]}},
                    "order_number": {"12": {"masked_as": "31", "instances": [1]}}}
        assert _unmask("№ 31 від «31» грудня 2025 та 31 грудня 2025", mappings) == \
            "№ 12 від «28» вересня 2025 та 28 вересня 2025"

    def test_masks_of_every_kind_together(self):
        mappings = {"surname": {"Іванов": {"masked_as": "Ковар", "instances": [1]}},
                    "ipn": {"1234567890": {"masked_as": "1239999990", "instances": [1]}},
                    "br_number": {"№14дск": {"masked_as": "№19дск", "instances": [1]}},
                    "military_unit": {"А1234": {"masked_as": "А9377", "instances": [1]}}}
        assert _unmask("наказ№19дск: Ковар, ІПН1239999990, в/ч А9377; слово Коваром і 91239999990", mappings) == \
            "наказ№14дск: Іванов, ІПН1234567890, в/ч А1234; слово Коваром і 91239999990"

    def test_empty_mask_is_ignored(self):
        # mapping, переданий у функцію напряму (CLI такий відхиляє раніше)
        mappings = {"surname": {"Іванов": {"masked_as": "", "instances": [1]},
                                "Петренко": {"masked_as": "Ковар", "instances": [1]}}}
        assert _unmask("Ковар прибув", mappings) == "Петренко прибув"
        assert _unmask("Ковар прибув", {"surname": {"Іванов": {"masked_as": "", "instances": [1]}}}) == "Ковар прибув"

    def test_many_masks(self):
        originals = [f"Прізвище{chr(0x430 + i % 32)}{chr(0x430 + i // 32)}" for i in range(600)]
        masks = [f"Маска{chr(0x430 + i % 32)}{chr(0x430 + i // 32)}" for i in range(600)]
        mappings = {"surname": {o: {"masked_as": m, "instances": [1]} for o, m in zip(originals, masks)}}
        assert _unmask(" ".join(masks), mappings) == " ".join(originals)


class TestInitials:
    @pytest.mark.parametrize("text, kept", [
        ("буд. 12А. Петренко прибув", "12А."),
        ("№ 953-К.Миколаївни", "-К."),
        ("№452/Я.БРИГАДИ", "/Я."),
        ("2027А.Прізвище", "2027А."),
    ])
    def test_letter_glued_to_a_number_is_not_an_initial(self, text, kept):
        masked, mapping = _rt(text)
        assert kept in masked and not mapping["mappings"].get("initials"), (masked, mapping["mappings"])

    @pytest.mark.parametrize("text", [
        "П.ГРИЦЕНКОкомандир", "Т.СавчукаОлегівні", "І.ОМБр", "Б.ВікторіяЯ", "І.ЗСУГнатюка",
    ])
    def test_part_of_a_word_is_not_a_surname(self, text):
        assert _rt(text)[0] == text

    @pytest.mark.parametrize("text", ["В.Савчука2", "Ю.Бондарем9", "К.Олександрівни91", "В.ВІДПУСТКУ03",
                                      "наказ №764Сидоренко О.П."])
    def test_surname_next_to_digits(self, text):
        masked, mapping = _rt(text)
        assert mapping["mappings"]["surname"], masked

    def test_order_number_is_not_glued_to_a_surname(self):
        _masked, mapping = _rt("наказ №764Сидоренко О.П.")
        assert "Сидоренко" in mapping["mappings"]["surname"]
        assert not any("идоренко" in key or "икитенко" in key
                       for category, entries in mapping["mappings"].items() if category != "surname"
                       for key in entries)

    @pytest.mark.parametrize("text, key", [("№ 123дск", "№ 123дск"), ("№ 45ОС", "45ОС"), ("№ 12/ОКП", "№ 12/ОКП"),
                                           ("№ 7-РС", "7-РС"), ("№БР-316/7-К", "№БР-316/7-К"),
                                           ("№ 15/2/аг", "15/2/аг")])
    def test_number_suffix_still_part_of_the_number(self, text, key):
        _masked, mapping = _rt(text)
        assert any(key in entries for entries in mapping["mappings"].values()), mapping["mappings"]

    def test_br_suffix_ends_at_word_end(self):
        import re
        text = "БР208Капітану"
        result = analyze_br_keyword(text, re.match("БР", text))
        assert result["number_part"] == "208"
        assert analyze_br_keyword("БР 208к від", re.match("БР", "БР 208к від"))["number_part"] == "208к"
        _rt("БР208Капітану Петренку")
        _rt("матросом …БР 123")


class TestMaskIsNotMaskedAgain:
    @pytest.mark.parametrize("text", [
        "Олег Лисенко\tКоваль П.П.",
        "Олег  Лисенком\tПилип'юк П.",
        "Сергіївні Гончаренку Галина  А.",
        "Поліщука Галини Дмитром І.",
        "Світлану Литвин Олену М.",
    ])
    def test_round_trip(self, text):
        _masked, mapping = _rt(text)
        originals = {key.lower() for entries in mapping["mappings"].values() for key in entries}
        masks = {info["masked_as"].lower() for entries in mapping["mappings"].values() for info in entries.values()}
        assert not originals & masks, originals & masks

    def test_words_before_the_mask_are_a_name(self):
        masked, _ = _rt("Олег Лисенко\tКоваль П.П.")
        assert "лисенко" not in masked.lower() and "коваль" not in masked.lower(), masked


class TestMixedCase:
    @pytest.mark.parametrize("text", [
        "сержант О'Коннор Іван Петрович прибув",
        "Рапорт сержанта О’Коннора Івана Петровича",
        "солдат Д'Артаньян Шарль",
        "О'Коннор І.П. прибув",
        "І.П. О’Коннор прибув",
        "Д'АРТАНЬЯН Ш.П.",
    ])
    def test_apostrophe_surname(self, text):
        masked, mapping = _rt(text)
        assert "коннор" not in masked.lower() and "артаньян" not in masked.lower(), masked
        mask_ = next(iter(mapping["mappings"]["surname"].values()))["masked_as"]
        assert mask_[1] == "'" and mask_[2].isupper(), mask_

    def test_apostrophe_surname_forms_share_stem(self):
        masked, mapping = _rt("сержант О'Коннор прибув, О'Коннору видано, О'Коннора немає")
        assert "коннор" not in masked.lower(), masked
        masks = sorted(info["masked_as"] for info in mapping["mappings"]["surname"].values())
        assert len(masks) == 3 and all(m.startswith(masks[0]) for m in masks), masks

    @pytest.mark.parametrize("text", [
        "Анна Марія Петренко-Коваль прибула",
        "Марія Руденку Дорошенку-Ґудзю",
        "Лисенку Василя Дорошенко-Ґудзь",
        "ОЛЕКСАНДРА ЛИСЕНКОу",
    ])
    def test_mixed_case_word_is_restored(self, text):
        masked, _ = _rt(text)
        assert all(word[0].isupper() for word in masked.split()[:3]), masked

    @pytest.mark.parametrize("text", [
        "Старший Лейтенант Петренко Іван Петрович",
        "Старшого Сержанта Сидоренка",
        "старшому ЛЕЙТЕНАНТУ Шевченку Івану Петровичу",
        "старшому ЛЕЙТЕНАНТУ Шевченко та Старший Лейтенант Мороз, СТАРШИЙ ЛЕЙТЕНАНТ Коваль і старший лейтенант Білий",
        "Капітан Медичної Служби Петренко Іван Петрович",
    ])
    def test_rank_in_irregular_case(self, text):
        _rt(text)

    def test_exact_rank_spelling_is_in_the_mapping(self):
        _masked, mapping = _rt("Старший Лейтенант Мороз, старший лейтенант Коваль")
        entry = mapping["mappings"]["rank"]["старший лейтенант"]
        assert entry["exact"] == {"1": "Старший Лейтенант"}
        validate_mapping_schema(mapping)

    def test_regular_case_has_no_exact(self):
        _masked, mapping = _rt("Старший лейтенант Мороз, СТАРШИЙ ЛЕЙТЕНАНТ Коваль, старший лейтенант Білий")
        assert "exact" not in mapping["mappings"]["rank"]["старший лейтенант"]

    def test_mapping_without_exact_still_restores(self):
        masked, mapping = mask("Старший Лейтенант Мороз Іван Петрович")
        del mapping["mappings"]["rank"]["старший лейтенант"]["exact"]
        restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
        assert restored == "Старший лейтенант Мороз Іван Петрович"

    def test_feminine_rank_with_masculine_only_mask(self, monkeypatch):
        from datamasking.masking import constants as _cfg
        # маска без жіночої форми: рід відновлюється з «exact»
        monkeypatch.setattr(_cfg, "RANK_FEMININE_MAP", {"капітан": _cfg.RANK_FEMININE_MAP["капітан"]})
        text = "Капітанці медичної служби Коваленко Марії Іванівні, ІПН 1234567890"
        masked, mapping = mask(text)
        restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
        assert restored == text, (masked, restored)
        assert mapping["mappings"]["rank"]["капітан"]["exact"] == {"1": "Капітанці"}

    @pytest.mark.parametrize("text", [
        "ГОЛОВНОГО МАЙСТЕР-СЕРЖАНТА Петренка Олега Івановича",
        "Майор Петренко Іван Петрович, майор Коваль Олег Іванович",
    ])
    def test_rank_case_without_preserve_case(self, text, monkeypatch):
        from datamasking.masking import constants as _cfg
        monkeypatch.setattr(_cfg, "PRESERVE_CASE", False)
        _rt(text)

    @pytest.mark.parametrize("exact", [["Старший Лейтенант"], {"1": 5}, "x"])
    def test_bad_exact_is_rejected(self, exact):
        mapping = {"version": "3.2.1", "mappings": {"rank": {
            "старший лейтенант": {"masked_as": "майор", "instances": [1], "exact": exact}}}}
        with pytest.raises(ValueError, match="exact"):
            validate_mapping_schema(mapping)

    def test_unmask_case_helper(self):
        assert _apply_original_case("О'Кегус", "О'Коннор") == "О'Коннор"
        assert _apply_original_case("Кегус", "МакКейн") == "МакКейн"
        assert _apply_original_case("Яремович", "Дорошенку-Ґудзю") == "Дорошенку-Ґудзю"
        # як і раніше: регістр — з тексту, якщо в mapping він звичайний
        assert _apply_original_case("Пебоженко", "ПЕТРЕНКО") == "Петренко"
        assert _apply_original_case("ПЕБОЖЕНКО", "Петренко") == "ПЕТРЕНКО"
        assert _apply_original_case("Пебоженко", "петренко") == "Петренко"
        assert _apply_original_case("Анна-Марія", "АННА-МАРІЯ") == "Анна-Марія"

    @pytest.mark.parametrize("text", ['«сержантом  "', "звання «сержант » присвоєно", "звання « старший сержант» присвоєно"])
    def test_spaces_inside_quotes_are_kept(self, text):
        _rt(text)


class TestKnownSurnameAlone:
    """Прізвище, вже замасковане в документі, — і в іншому відмінку без звання."""

    @pytest.mark.parametrize("text, stem", [
        ("сержант Мороз прибув, Морозу видано, Мороза немає, з Морозом", "мороз"),
        ("сержант Коваль прибув, Ковалю видано, Коваля немає, з Ковалем", "ковал"),
        ("сержант Бондар прибув, Бондарю видано, Бондаря немає, з Бондарем", "бондар"),
        ("сержант Ткач прибув, Ткача немає, Ткачу видано, з Ткачем", "ткач"),
        ("сержант Хмара прибув, Хмари немає, Хмару викликали, з Хмарою", "хмар"),
        ("сержант Шамрай прибув, Шамрая немає, Шамраю видано", "шамра"),
        ("сержант Гончар прибув, Гончара немає", "гончар"),
        ("Рапорт сержанта Коваля. Коваль прибув, Ковалю видано", "ковал"),
    ])
    def test_every_form_is_masked(self, text, stem):
        masked, _ = _rt(text)
        assert stem not in masked.lower(), masked

    def test_forms_share_the_stem(self):
        _masked, mapping = _rt("сержант Мороз прибув, Морозу видано, Мороза немає, з Морозом")
        masks = sorted(info["masked_as"] for info in mapping["mappings"]["surname"].values())
        assert len(masks) == 4 and all(m.startswith(masks[0]) for m in masks), masks

    @pytest.mark.parametrize("text, kept", [
        ("сержант Мороз прибув. Морозна ніч, морози посилились", "Морозна ніч, морози"),
        ("сержант Іванов прибув. Івана та Іванну викликали", "Івана та Іванну"),
        ("сержант Білий прибув. Біло навколо", "Біло навколо"),
    ])
    def test_other_words_are_kept(self, text, kept):
        masked, _ = _rt(text)
        assert kept in masked, masked


class TestDecomposedLetters:
    """«й», «ї» як «и» / «і» + комбінувальний знак (NFD, тексти з macOS)."""

    @pytest.mark.parametrize("text", [
        "Разом з сержантом БОЙКОМ В.М.",
        "сержант БОЙКО В.М. прибув",
        "Бойком В.М.",
        "В.М. Бойко прибув",
        "Гайовий Й.Й. та Й.Й. ГАЙОВИЙ",
        "Сергій РУДЕНКО\tВасиль ГАЙОВИЙ",
        "полковник ВИШНЕВЕЦЬКИЙ Микола Юрійович.",
        "Надати відпустку полковнику БОЙКУ  ТАРАСУ ЮРІЙОВИЧУ.",
        "(Бойко Андрій) прибув",
    ])
    def test_masked_and_restored(self, text):
        import unicodedata
        text = unicodedata.normalize("NFD", text)
        masked, mapping = _rt(text)
        masked = unicodedata.normalize("NFC", masked).lower()
        for secret in ("бойк", "гайов", "вишневецьк", "юрійович", "руденко"):
            assert secret not in masked, masked
        assert not {unicodedata.normalize("NFC", k).lower() for k in mapping["mappings"]["surname"]} & {"ком", "ко"}


class TestRankWithLatinLookalike:
    """Латинська літера-двійник усередині звання (текст, склеєний з різних джерел)."""

    @pytest.mark.parametrize("text, rank", [
        ("CТАРШИЙ ЛЕЙТЕНАНТ КРАВЧЕНКО ОЛЬГА ПЕТРІВНА.", "старший лейтенант"),   # латинська C
        ("cержант Петренко Іван Петрович прибув, сержант Коваль Олег Іванович", "сержант"),
        ("kапітан медичної служби Мороз Ігор Петрович", "капітан"),
        ("стаpший сеpжант Мороз Ігор", "старший сержант"),   # латинська p
    ])
    def test_rank_is_recognised_and_restored(self, text, rank):
        masked, mapping = _rt(text)
        assert list(mapping["mappings"]["rank"]) == [rank], mapping["mappings"]["rank"]
        assert not any("тарш" in key.lower() or "ержант" in key.lower() for key in mapping["mappings"]["surname"])
        assert masked.isascii() is False and not any(ch in masked for ch in "Ccpk"), masked

    def test_spelling_is_kept_in_the_mapping(self):
        _masked, mapping = _rt("cержант Петренко Іван Петрович")
        assert mapping["mappings"]["rank"]["сержант"]["exact"] == {"1": "cержант"}


class TestSameRankTwice:
    """Те саме звання двічі поспіль (кінець рядка і початок наступного)."""

    @pytest.mark.parametrize("text", [
        "доповів старший лейтенант\nСтарший лейтенант Мороз Ігор Петрович прибув",
        "Кравченко Ольга Петрівна, 1984 р.н., старший лейтенант\nСТАРШИЙ ЛЕЙТЕНАНТ КРАВЧЕНКО ОЛЬГА ПЕТРІВНА.",
        "капітаном старший лейтенант Мороз Ігор, старший лейтенант Коваль Олег",
        "сержант Петренко та сержант Коваль, сержант Мороз Ігор Іванович",
    ])
    def test_rank_word_is_not_a_surname(self, text):
        masked, mapping = _rt(text)
        assert not any("тарш" in key.lower() for key in mapping["mappings"]["surname"]), mapping["mappings"]["surname"]
        assert set(mapping["mappings"]["rank"]) <= {"старший лейтенант", "сержант"}, mapping["mappings"]["rank"]
        assert "мороз" not in masked.lower() and "кравченко" not in masked.lower()


class TestNameMaskAndOpenWord:
    @pytest.mark.parametrize("text", [
        "Івану сержанту Гриценку Ігорю",
        "ІВАНУ сержанту Гриценку Ігорю",
        "Ігоря немає. сержанта Гриценка Івана викликали, Ігоря теж",
    ])
    def test_mask_is_not_a_word_left_in_the_document(self, text):
        masked, mapping = _rt(text)
        for info in mapping["mappings"]["name"].values():
            assert info["masked_as"].lower() not in {w.strip(".,").lower() for w in text.split()}, masked


class TestParsingLine:
    def test_clean_line_is_for_parsing_only(self):
        # у самому тексті нічого не міняється
        text = "звання:старший матрос Петренко Іван Петрович;посада/стрілець"
        masked, _ = _rt(text)
        assert masked.startswith("звання:") and masked.endswith(";посада/стрілець")

    def test_clean_line(self):
        assert clean_line_before_parsing("-Петренко Іван Петрович") == "- Петренко Іван Петрович"
        assert clean_line_before_parsing("1.Петренко Іван") == "Петренко Іван"

    def test_unlocatable_name_does_not_stop_the_line(self):
        # розбір бачить «Петренко,Іван» як слова CSV, а в рядку між ними ще й дужка
        masked, _ = _rt("Петренко,(Іван) та сержант Коваль Олег Іванович")
        assert "коваль" not in masked.lower(), masked
