#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Маска прізвища не має розкривати оригінал (v3.0.2).

Регресія аудиту 3.0.0: original[:3] + середина + original[-5:] лишав
ціле прізвище видимим у масці для 5–8-літерних прізвищ
(Ґудзь → Ґудузіґудзь, Коваль → Ковавриліоваль).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_initials import mask, make_masking_dict  # noqa: E402
from datamasking.masking.mask_personal import mask_surname  # noqa: E402
from datamasking.masking.surname import split_surname, synthesize_surname  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402

LEAKY_BEFORE = ["Ґудзь", "Коваль", "Сидоренко", "Петров", "Шевченко", "Бондаренко",
                "Ткач", "Іванов", "Петренко", "Мороз", "Кравчук", "Білий"]

SURNAMES = LEAKY_BEFORE + [
    "Ковальчук", "Мельник", "Олійник", "Лисенко", "Гончар", "Ткаченко", "Кравченко",
    "Савченко", "Бойко", "Поліщук", "Марченко", "Руденко", "Захарченко", "Левченко",
    "Хоменко", "Пономаренко", "Дем'янчук", "Задорожний", "Коломієць", "Гаврилюк",
]


def surname_mask(word: str) -> str:
    md = make_masking_dict()
    return mask_surname(word, md, {})


class TestNoLeak:
    @pytest.mark.parametrize("word", SURNAMES)
    def test_original_not_inside_mask(self, word):
        m = surname_mask(word)
        assert m.lower() != word.lower()
        assert word.lower() not in m.lower(), f"{word} leaked in {m}"
        assert m.lower() not in word.lower()

    @pytest.mark.parametrize("word", SURNAMES)
    def test_stem_not_inside_mask(self, word):
        stem, _, _ = split_surname(word)
        m = surname_mask(word)
        assert stem not in m.lower(), f"stem '{stem}' of {word} visible in {m}"

    @pytest.mark.parametrize("word", LEAKY_BEFORE)
    def test_previously_leaky_cases(self, word):
        # Саме ці слова показували оригінал у 3.0.0/3.0.1
        m = surname_mask(word)
        assert word.lower() not in m.lower()


class TestGrammarPreserved:
    @pytest.mark.parametrize("form,ending", [
        ("Петренко", "енко"), ("Петренка", "енка"), ("Петренку", "енку"), ("Петренком", "енком"),
        ("Іванов", "ов"), ("Іванова", "ова"), ("Іванову", "ову"), ("Івановим", "овим"),
        ("Іванової", "ової"), ("Івановій", "овій"),
        ("Ковальський", "ський"), ("Ковальського", "ського"), ("Ковальська", "ська"),
        ("Кравчук", "ук"), ("Кравчука", "ука"), ("Кравчуку", "уку"), ("Кравчуком", "уком"),
        ("Коломієць", "єць"), ("Коломійця", "я"), ("Кравець", "ець"),
        ("Сорока", "а"), ("Сороки", "и"), ("Білий", "ий"), ("Білого", "ого"),
    ])
    def test_case_and_gender_ending_kept(self, form, ending):
        m = surname_mask(form)
        assert m.lower().endswith(ending), f"{form} -> {m}: ending {ending!r} lost"

    def test_same_family_preferred_for_enko(self):
        # -енко → -енко: найпоширеніша родина, faker її має вдосталь
        for w in ["Петренко", "Сидоренко", "Шевченко", "Ткаченко"]:
            assert surname_mask(w).lower().endswith("енко")

    def test_feminine_form_stays_feminine(self):
        m, md = mask("сержант Іванова Марія Петрівна")
        masked_surname = md["mappings"]["surname"]["Іванова"]["masked_as"]
        assert masked_surname.endswith("ова")
        assert masked_surname in m and "Іванов" not in m

    def test_dative_in_sentence(self):
        m, md = mask("капітану Петренку Івану Сергійовичу оголошено подяку")
        masked_surname = md["mappings"]["surname"]["Петренку"]["masked_as"]
        assert masked_surname.endswith("енку")
        assert "Петренк" not in m

    def test_no_soft_sign_before_consonant_ending(self):
        # «Заєцьуком», «Журавельий» — основа з ь перед приголосним закінченням
        for w in ["Кравчуком", "Задорожний", "Ковальського", "Іванов", "Петренко"]:
            m = surname_mask(w).lower()
            _, ending, _ = split_surname(w)
            stem = m[: -len(ending)] if ending else m
            assert stem[-1] not in "ьй'", f"{w} -> {m}"

    def test_bare_surname_gets_whole_synthetic_surname(self):
        # Не обрізана основа («Девд»), а ціле правдоподібне прізвище
        for w in ["Ткач", "Ґудзь", "Шамрай", "Коваль"]:
            m = surname_mask(w).lower()
            assert len(m) >= 4 and m[-1] not in "'", f"{w} -> {m}"


class TestDeterminismAndCase:
    def test_deterministic(self):
        assert surname_mask("Коваленко") == surname_mask("Коваленко")
        assert synthesize_surname("коваленко") == synthesize_surname("коваленко")

    def test_different_originals_different_masks(self):
        md = make_masking_dict()
        masks = [mask_surname(w, md, {}) for w in SURNAMES]
        assert len(set(m.lower() for m in masks)) == len(SURNAMES)

    def test_mask_never_equals_another_word_of_document(self):
        # Маска одного прізвища не має збігатися з іншим прізвищем (чи будь-яким
        # словом) того ж документа — інакше unmask замінить і чужі входження.
        # Рушій реєструє словник документа ДО маскування, тому це працює навіть
        # для прізвищ, що зустрічаються пізніше за текстом.
        text = "\n".join(f"капітан {w} Іван Іванович" for w in SURNAMES)
        _, md = mask(text)
        vocab = {w.lower() for w in text.replace("\n", " ").split()}
        for original, info in md["mappings"]["surname"].items():
            assert info["masked_as"].lower() not in vocab, f"{original} -> {info['masked_as']}"

    def test_vocabulary_is_cleared_between_documents(self):
        # Детермінізм: один і той самий вхід → та сама маска незалежно від того,
        # що маскувалось раніше
        a, _ = mask("капітан Коваль Іван Іванович")
        mask("\n".join(f"капітан {w} Іван Іванович" for w in SURNAMES))
        b, _ = mask("капітан Коваль Іван Іванович")
        assert a == b

    def test_case_preserved(self):
        assert surname_mask("ІВАНОВ").isupper()
        cap = surname_mask("Іванов")
        assert cap[0].isupper() and cap[1:].islower()
        assert surname_mask("іванов").islower()

    def test_whitelist_untouched(self):
        assert surname_mask("ЗСУ") == "ЗСУ"

    def test_short_and_bare_surnames(self):
        for w in ["Рак", "Ткач", "Ґудзь", "Шамрай", "Коваль"]:
            m = surname_mask(w)
            assert m.lower() != w.lower() and w.lower() not in m.lower()
            assert len(m) >= 3


class TestRoundtrip:
    @pytest.mark.parametrize("text", [
        "капітан Ґудзь Євген Петрович прибув",
        "сержант Коваль Олег Петрович та капітан Коваленко Ігор Іванович",
        "Наказ підполковнику Сидоренку Олексію Івановичу та майору Петрову Івану Івановичу.",
        "ЛЕЙТЕНАНТ ІВАНОВ ПЕТРО МИКОЛАЙОВИЧ",
        "Іванов П.А. підписав.",
    ])
    def test_roundtrip(self, text):
        m, md = mask(text)
        r, _ = unmask_text_v2(m, md, check_mapping_version(md))
        assert r == text

    def test_no_surname_visible_in_masked_document(self):
        lines = [f"капітан {w} Іван Іванович" for w in SURNAMES]
        text = "\n".join(lines)
        m, md = mask(text)
        for w in SURNAMES:
            assert w not in m, f"{w} visible in masked document"
        r, _ = unmask_text_v2(m, md, check_mapping_version(md))
        assert r == text
