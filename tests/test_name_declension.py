#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3.1.12 — маски імен і по батькові у відмінку оригіналу; всі відмінки одного
імені дають одну маску. До того «Петра» вважалось жіночим ім'ям у називному
(маска «Павло»), по батькові маскувалось лише в називному, а «Петро» й
«Петра» діставали різні маски.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from datamasking.masking import constants as _cfg  # noqa: E402
from datamasking.masking.declension import (  # noqa: E402
    ACCUSATIVE, DATIVE, DATIVE_OVI, GENITIVE, INSTRUMENTAL, NOMINATIVE, VOCATIVE,
    analyze_name, analyze_patronymic, decline_name, decline_patronymic, known_names,
)
from datamasking.masking.language import (  # noqa: E402
    detect_gender_by_patronymic, detect_name_case_and_gender, same_name_forms,
)
from datamasking.masking.mask_personal import mask_name, mask_patronymic  # noqa: E402
from datamasking.unmasking.engine import unmask_text_v2  # noqa: E402
from datamasking.unmasking.helpers import check_mapping_version  # noqa: E402
from tests.test_initials import mask  # noqa: E402


def _rt(text):
    masked, mapping = mask(text)
    restored, _ = unmask_text_v2(masked, mapping, check_mapping_version(mapping))
    assert restored == text, (masked, restored)
    return masked, mapping


class TestAnalyzeName:
    @pytest.mark.parametrize("form,hint,nominative,case,gender", [
        ("Петро", None, "петро", NOMINATIVE, "male"),
        ("Петра", "male", "петро", GENITIVE, "male"),
        ("Петра", None, "петро", GENITIVE, "male"),
        ("Петру", None, "петро", DATIVE, "male"),
        ("Петрові", None, "петро", DATIVE_OVI, "male"),
        ("Петром", None, "петро", INSTRUMENTAL, "male"),
        ("Петре", None, "петро", VOCATIVE, "male"),
        ("Олега", None, "олег", GENITIVE, "male"),
        ("Олеже", None, "олег", VOCATIVE, "male"),
        ("Андрія", None, "андрій", GENITIVE, "male"),
        ("Андрієм", None, "андрій", INSTRUMENTAL, "male"),
        ("Василя", None, "василь", GENITIVE, "male"),
        ("Ігоря", None, "ігор", GENITIVE, "male"),
        ("Ігорем", None, "ігор", INSTRUMENTAL, "male"),
        ("Миколи", None, "микола", GENITIVE, "male"),
        ("Миколою", None, "микола", INSTRUMENTAL, "male"),
        ("Іллі", "male", "ілля", DATIVE, "male"),
        ("Тетяна", None, "тетяна", NOMINATIVE, "female"),
        ("Тетяни", None, "тетяна", GENITIVE, "female"),
        ("Тетяні", None, "тетяна", DATIVE, "female"),
        ("Тетяну", None, "тетяна", ACCUSATIVE, "female"),
        ("Тетяною", None, "тетяна", INSTRUMENTAL, "female"),
        ("Марії", None, "марія", GENITIVE, "female"),
        ("Марією", None, "марія", INSTRUMENTAL, "female"),
        ("Ользі", None, "ольга", DATIVE, "female"),
        ("Вероніці", "female", "вероніка", DATIVE, "female"),
        ("Наталі", "female", "наталя", DATIVE, "female"),
        ("Любові", None, "любов", DATIVE, "female"),
        ("Любов'ю", None, "любов", INSTRUMENTAL, "female"),
        # Валентина / Богуслава: жіноче ім'я, якщо рід не підказано інакше
        ("Валентина", None, "валентина", NOMINATIVE, "female"),
        ("Валентина", "male", "валентин", GENITIVE, "male"),
        ("Богуслава", None, "богуслава", NOMINATIVE, "female"),
    ])
    def test_forms(self, form, hint, nominative, case, gender):
        got = analyze_name(form, hint)
        assert (got.nominative, got.case, got.gender) == (nominative, case, gender), got

    def test_case_hint_resolves_ambiguity(self):
        # -і: родовий чи давальний — вирішує по батькові / звання
        assert analyze_name("Наталі", "female", GENITIVE).case == GENITIVE
        assert analyze_name("Наталі", "female", DATIVE).case == DATIVE
        assert analyze_name("Марії", "female", DATIVE).case == DATIVE
        # відмінок звання обирає прочитання: Богуслава — родовий від Богуслав
        got = analyze_name("Богуслава", None, GENITIVE)
        assert (got.nominative, got.case, got.gender) == ("богуслав", GENITIVE, "male")
        # але кличний не стає давальним через «Івановичу», -ові лишається
        assert analyze_name("Петре", "male", DATIVE).case == VOCATIVE
        assert analyze_name("Петрові", "male", DATIVE).case == DATIVE_OVI
        # знахідний жіночий не стає родовим через звання «сержанта»
        assert analyze_name("Тетяну", "female", GENITIVE).case == ACCUSATIVE

    def test_unknown_name_falls_back_to_endings(self):
        got = analyze_name("Зюзюка", None)
        assert got.case == NOMINATIVE and got.gender == "female" and not got.known
        got = analyze_name("Зюзюком", None)
        assert got.case == INSTRUMENTAL and got.gender == "male" and got.nominative == "зюзюк"
        got = analyze_name("Зюзюка", "male")
        assert got.case == GENITIVE and got.nominative == "зюзюк"

    def test_detect_name_case_and_gender_wrapper(self):
        assert detect_name_case_and_gender("Петра") == (GENITIVE, "male")
        assert detect_name_case_and_gender("Тетяни") == (GENITIVE, "female")
        assert detect_name_case_and_gender("Валентина", "male") == (GENITIVE, "male")

    def test_known_names_include_builtin_and_faker(self):
        assert {"петро", "микола", "ілля", "ігор"} <= known_names("male")
        assert {"тетяна", "наталя", "любов", "марія"} <= known_names("female")
        assert "в'ячеслав" in known_names("male")  # апостроф нормалізовано


class TestDeclineName:
    @pytest.mark.parametrize("name,gender,forms", [
        ("Павло", "male", ["Павла", "Павлу", "Павлові", "Павла", "Павлом", "Павле"]),
        ("Олег", "male", ["Олега", "Олегу", "Олегові", "Олега", "Олегом", "Олеже"]),
        ("Андрій", "male", ["Андрія", "Андрію", "Андрієві", "Андрія", "Андрієм", "Андрію"]),
        ("Василь", "male", ["Василя", "Василю", "Василеві", "Василя", "Василем", "Василю"]),
        ("Ігор", "male", ["Ігоря", "Ігорю", "Ігореві", "Ігоря", "Ігорем", "Ігорю"]),
        ("Микола", "male", ["Миколи", "Миколі", "Миколі", "Миколу", "Миколою", "Миколо"]),
        ("Ілля", "male", ["Іллі", "Іллі", "Іллі", "Іллю", "Іллею", "Ілле"]),
        ("Марк", "male", ["Марка", "Марку", "Маркові", "Марка", "Марком", "Марку"]),
        ("Тетяна", "female", ["Тетяни", "Тетяні", "Тетяні", "Тетяну", "Тетяною", "Тетяно"]),
        ("Ольга", "female", ["Ольги", "Ользі", "Ользі", "Ольгу", "Ольгою", "Ольго"]),
        ("Марія", "female", ["Марії", "Марії", "Марії", "Марію", "Марією", "Маріє"]),
        ("Наталя", "female", ["Наталі", "Наталі", "Наталі", "Наталю", "Наталею", "Наталю"]),
        ("Наташа", "female", ["Наташі", "Наташі", "Наташі", "Наташу", "Наташею", "Наташо"]),
        ("Любов", "female", ["Любові", "Любові", "Любові", "Любов", "Любов'ю", "Любове"]),
    ])
    def test_paradigm(self, name, gender, forms):
        cases = [GENITIVE, DATIVE, DATIVE_OVI, ACCUSATIVE, INSTRUMENTAL, VOCATIVE]
        assert [decline_name(name, c, gender) for c in cases] == forms
        assert decline_name(name, NOMINATIVE, gender) == name

    def test_analyze_then_decline_is_identity(self):
        for form, hint in [("Петра", "male"), ("Тетяною", "female"), ("Андрієві", "male"),
                           ("Миколі", "male"), ("Ользі", "female"), ("Марії", "female"),
                           ("Любові", "female"), ("Олеже", "male")]:
            got = analyze_name(form, hint)
            assert decline_name(got.nominative, got.case, got.gender) == form.lower(), (form, got)


class TestPatronymics:
    @pytest.mark.parametrize("form,nominative,case,gender", [
        ("Іванович", "іванович", NOMINATIVE, "male"),
        ("Івановича", "іванович", GENITIVE, "male"),
        ("Івановичу", "іванович", DATIVE, "male"),
        ("Івановичем", "іванович", INSTRUMENTAL, "male"),
        ("Ілліча", "ілліч", GENITIVE, "male"),
        ("Сергіївна", "сергіївна", NOMINATIVE, "female"),
        ("Сергіївни", "сергіївна", GENITIVE, "female"),
        ("Сергіївні", "сергіївна", DATIVE, "female"),
        ("Сергіївну", "сергіївна", ACCUSATIVE, "female"),
        ("Сергіївною", "сергіївна", INSTRUMENTAL, "female"),
        ("Петрівно", "петрівна", VOCATIVE, "female"),
    ])
    def test_analyze(self, form, nominative, case, gender):
        got = analyze_patronymic(form)
        assert (got.nominative, got.case, got.gender) == (nominative, case, gender)
        assert decline_patronymic(nominative.capitalize(), case) == form

    def test_gender_detection(self):
        assert detect_gender_by_patronymic("Сергіївну") == "female"
        assert detect_gender_by_patronymic("Івановичем") == "male"
        # кличний не вважається по батькові — так закінчуються звичайні слова
        assert detect_gender_by_patronymic("Петрівно") == "unknown"
        assert detect_gender_by_patronymic("Рівно") == "unknown"
        assert detect_gender_by_patronymic("Згідно") == "unknown"

    def test_mask_patronymic_declined_and_consistent(self, empty_masking_dict, instance_counters):
        nom = mask_patronymic("Петрович", "male", empty_masking_dict, instance_counters)
        gen = mask_patronymic("Петровича", "male", empty_masking_dict, instance_counters)
        dat = mask_patronymic("Петровичу", "male", empty_masking_dict, instance_counters)
        ins = mask_patronymic("Петровичем", "male", empty_masking_dict, instance_counters)
        assert nom.endswith("ич") and (gen, dat, ins) == (nom + "а", nom + "у", nom + "ем")
        assert not same_name_forms(nom, "Петрович")
        fnom = mask_patronymic("Сергіївна", "female", empty_masking_dict, instance_counters)
        fgen = mask_patronymic("Сергіївни", "female", empty_masking_dict, instance_counters)
        fins = mask_patronymic("Сергіївною", "female", empty_masking_dict, instance_counters)
        assert fnom.endswith("на") and (fgen, fins) == (fnom[:-1] + "и", fnom[:-1] + "ою")
        # ключі mapping — форми в нижньому регістрі, як і раніше
        assert {"петрович", "петровича", "сергіївни"} <= set(empty_masking_dict["mappings"]["patronymic"])

    def test_gender_param_falls_back_to_form(self, empty_masking_dict, instance_counters):
        # рід, якого не передали, береться з форми по батькові
        masked = mask_patronymic("Сергіївни", "unknown", empty_masking_dict, instance_counters)
        assert masked.endswith("и") and masked[:-1].endswith("вн")


class TestMaskName:
    def test_all_cases_share_one_mask(self, empty_masking_dict, instance_counters):
        nom = mask_name("Петро", empty_masking_dict, instance_counters, gender_hint="male")
        forms = {c: mask_name(f, empty_masking_dict, instance_counters, gender_hint="male")
                 for f, c in [("Петра", GENITIVE), ("Петру", DATIVE), ("Петром", INSTRUMENTAL),
                              ("Петрові", DATIVE_OVI), ("Петре", VOCATIVE)]}
        for case, masked in forms.items():
            assert masked == decline_name(nom, case, "male"), (case, nom, masked)
        assert nom[0].isupper() and nom != "Петро"

    def test_female_paradigm_and_gender(self, empty_masking_dict, instance_counters):
        nom = mask_name("Тетяна", empty_masking_dict, instance_counters, patronymic_hint="Сергіївна")
        gen = mask_name("Тетяни", empty_masking_dict, instance_counters, patronymic_hint="Сергіївни")
        dat = mask_name("Тетяні", empty_masking_dict, instance_counters, patronymic_hint="Сергіївні")
        acc = mask_name("Тетяну", empty_masking_dict, instance_counters, patronymic_hint="Сергіївну")
        ins = mask_name("Тетяною", empty_masking_dict, instance_counters, patronymic_hint="Сергіївною")
        assert nom.lower() in known_names("female")
        assert (gen, dat, acc, ins) == tuple(decline_name(nom, c, "female")
                                             for c in (GENITIVE, DATIVE, ACCUSATIVE, INSTRUMENTAL))

    def test_genitive_male_with_patronymic_is_male_genitive(self, empty_masking_dict, instance_counters):
        masked = mask_name("Петра", empty_masking_dict, instance_counters, patronymic_hint="Івановича")
        assert masked.endswith("а") and masked != "Петра"
        got = analyze_name(masked, "male")
        assert got.case == GENITIVE and got.known and got.nominative in known_names("male")

    def test_upper_case_keeps_paradigm(self, empty_masking_dict, instance_counters):
        nom = mask_name("ПЕТРО", empty_masking_dict, instance_counters, gender_hint="male")
        gen = mask_name("ПЕТРА", empty_masking_dict, instance_counters, gender_hint="male")
        assert nom.isupper() and gen.isupper()
        assert gen == decline_name(nom, GENITIVE, "male").upper()

    def test_never_same_name_in_any_case(self, empty_masking_dict, instance_counters):
        for form, pat in [("Олега", "Петровича"), ("Олексія", "Петровича"), ("Марії", "Петрівни"),
                          ("Миколи", "Петровича"), ("Іллі", "Петровича"), ("Ользі", "Петрівні")]:
            masked = mask_name(form, empty_masking_dict, instance_counters, patronymic_hint=pat)
            assert not same_name_forms(masked, form), (form, masked)

    def test_pseudo_gender_still_declines(self, empty_masking_dict, instance_counters):
        saved = _cfg.PRESERVE_GENDER
        _cfg.PRESERVE_GENDER = False
        try:
            masks = {f: mask_name(f, empty_masking_dict, instance_counters, patronymic_hint=p)
                     for f, p in [("Петра", "Івановича"), ("Тетяни", "Петрівни"), ("Олегу", "Петровичу")]}
        finally:
            _cfg.PRESERVE_GENDER = saved
        for form, masked in masks.items():
            assert masked != form and masked[0].isupper()
            # форма маски — не називний: родовий/давальний імені будь-якого роду
            assert masked.lower() not in known_names("male") | known_names("female"), (form, masked)


class TestEngineIntegration:
    def test_full_paradigm_in_text(self):
        text = ("капітан Петренко Петро Іванович\nкапітана Петренка Петра Івановича\n"
                "капітану Петренку Петру Івановичу\nкапітаном Петренком Петром Івановичем")
        masked, mapping = _rt(text)
        lines = [ln.split() for ln in masked.split("\n")]
        names = [ln[-2] for ln in lines]
        pats = [ln[-1] for ln in lines]
        nom_name, nom_pat = names[0], pats[0]
        assert names[1:] == [decline_name(nom_name, c, "male") for c in (GENITIVE, DATIVE, INSTRUMENTAL)]
        assert pats[1:] == [nom_pat + e for e in ("а", "у", "ем")]
        assert "Петр" not in masked and "Іванович" not in masked

    def test_female_paradigm_in_text(self):
        text = ("сержант Коваль Тетяна Сергіївна\nсержанта Коваль Тетяни Сергіївни\n"
                "сержанту Коваль Тетяні Сергіївні\nсержантом Коваль Тетяною Сергіївною\n"
                "призначити Коваль Тетяну Сергіївну")
        masked, mapping = _rt(text)
        lines = [ln.split() for ln in masked.split("\n")]
        names = [ln[-2] for ln in lines]
        pats = [ln[-1] for ln in lines]
        assert names[1:] == [decline_name(names[0], c, "female")
                             for c in (GENITIVE, DATIVE, INSTRUMENTAL, ACCUSATIVE)]
        assert pats[1:] == [pats[0][:-1] + e for e in ("и", "і", "ою", "у")]
        assert "Тетян" not in masked and "Сергіївн" not in masked

    @pytest.mark.parametrize("text,ending", [
        ("лейтенанта Іванова Миколи Ігоровича", "а"),
        ("рядового Сидоренка Олега Васильовича", "а"),
        ("рядового Сидоренка Ігоря Ілліча", "а"),
        ("рядовому Сидоренку Миколі Петровичу", "у"),
        ("рядової Сидоренко Марії Іллівни", "и"),
        ("рядової Сидоренко Ольги Петрівни", "и"),
        ("рядовій Сидоренко Наталі Петрівні", "і"),
        ("рядової Сидоренко Любові Петрівни", "и"),
    ])
    def test_patronymic_mask_in_original_case(self, text, ending):
        masked, _ = _rt(text)
        assert masked.split()[-1].endswith(ending), masked
        assert masked.split()[-1] != text.split()[-1]

    def test_rank_case_hint_without_patronymic(self):
        masked, mapping = _rt("рядового Петренка Богуслава")
        name_mask = mapping["mappings"]["name"]["Богуслава"]["masked_as"]
        got = analyze_name(name_mask, "male")
        assert got.case == GENITIVE and got.known, name_mask
        # знахідний жіночий після «сержанта» лишається знахідним
        masked, mapping = _rt("призначити сержанта Коваль Тетяну")
        assert analyze_name(mapping["mappings"]["name"]["Тетяну"]["masked_as"], "female").case == ACCUSATIVE

    def test_feminine_rank_marks_woman(self):
        masked, mapping = _rt("сержантки Коваль Наталі")
        name_mask = mapping["mappings"]["name"]["Наталі"]["masked_as"]
        got = analyze_name(name_mask, "female")
        assert got.gender == "female" and got.known and got.case in (GENITIVE, DATIVE), name_mask

    def test_nominative_examples_unchanged(self):
        # маски називного відмінка — як у 3.1.11 (README)
        masked, _ = _rt("Іванов Петро Іванович і Петров Олег Петрович. Потім Іванов пішов, а Петров лишився.")
        assert masked == "Івенов Павло Леонідович і Пергов Омелян Степанович. Потім Івенов пішов, а Пергов лишився."

    def test_accusative_patronymic_is_strong_pib_signal(self):
        masked, _ = _rt("Згідно з рапортом Коваль Тетяну Сергіївну зараховано")
        assert "Тетяну" not in masked and "Сергіївну" not in masked
