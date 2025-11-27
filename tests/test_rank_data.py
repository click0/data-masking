#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести для rank_data.py
Комплексне тестування структур даних українських військових звань

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.2.14
License: BSD 3-Clause "New" or "Revised" License
Year: 2025

"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from rank_data import (
    RANK_DECLENSIONS,
    RANK_FEMININE_MAP,
    RANK_DECLENSIONS_FEMALE,
    RANK_TO_NOMINATIVE,
    ALL_RANK_FORMS,
    ARMY_RANKS,
    NAVAL_RANKS,
    LEGAL_RANKS,
    MEDICAL_RANKS,
    RANKS_LIST,
)


class TestRankDeclensions:
    """Тести для RANK_DECLENSIONS - словника відмінків чоловічих звань"""

    def test_declensions_structure(self):
        """Тест: структура словника відмінків"""
        assert isinstance(RANK_DECLENSIONS, dict)
        assert len(RANK_DECLENSIONS) > 0

    def test_all_ranks_have_four_cases(self):
        """Тест: кожне звання має 4 відмінки"""
        required_cases = {'nominative', 'genitive', 'dative', 'instrumental'}

        for rank, cases in RANK_DECLENSIONS.items():
            assert isinstance(cases, dict), f"Звання '{rank}' має неправильний тип даних"
            assert set(cases.keys()) == required_cases, \
                f"Звання '{rank}' має неповний набір відмінків: {cases.keys()}"

    def test_soldat_declensions(self):
        """Тест: відмінки звання 'солдат'"""
        assert 'солдат' in RANK_DECLENSIONS

        soldat = RANK_DECLENSIONS['солдат']
        assert soldat['nominative'] == 'солдат'
        assert soldat['genitive'] == 'солдата'
        assert soldat['dative'] == 'солдату'
        assert soldat['instrumental'] == 'солдатом'

    def test_kapitan_declensions(self):
        """Тест: відмінки звання 'капітан'"""
        assert 'капітан' in RANK_DECLENSIONS

        kapitan = RANK_DECLENSIONS['капітан']
        assert kapitan['nominative'] == 'капітан'
        assert kapitan['genitive'] == 'капітана'
        assert kapitan['dative'] == 'капітану'
        assert kapitan['instrumental'] == 'капітаном'

    def test_compound_rank_starshyi_soldat(self):
        """Тест: складене звання 'старший солдат'"""
        assert 'старший солдат' in RANK_DECLENSIONS

        starshyi = RANK_DECLENSIONS['старший солдат']
        assert starshyi['nominative'] == 'старший солдат'
        assert starshyi['genitive'] == 'старшого солдата'
        assert starshyi['dative'] == 'старшому солдату'
        assert starshyi['instrumental'] == 'старшим солдатом'

    def test_naval_rank_matros(self):
        """Тест: морське звання 'матрос'"""
        assert 'матрос' in RANK_DECLENSIONS

        matros = RANK_DECLENSIONS['матрос']
        assert matros['nominative'] == 'матрос'
        assert matros['genitive'] == 'матроса'
        assert matros['dative'] == 'матросу'
        assert matros['instrumental'] == 'матросом'

    def test_officer_rank_mayor(self):
        """Тест: офіцерське звання 'майор'"""
        assert 'майор' in RANK_DECLENSIONS

        mayor = RANK_DECLENSIONS['майор']
        assert mayor['nominative'] == 'майор'
        assert mayor['genitive'] == 'майора'
        assert mayor['dative'] == 'майору'
        assert mayor['instrumental'] == 'майором'

    def test_general_rank(self):
        """Тест: генеральське звання"""
        assert 'генерал' in RANK_DECLENSIONS

        general = RANK_DECLENSIONS['генерал']
        assert general['nominative'] == 'генерал'
        assert general['genitive'] == 'генерала'
        assert general['dative'] == 'генералу'
        assert general['instrumental'] == 'генералом'

    def test_no_empty_declensions(self):
        """Тест: немає порожніх значень відмінків"""
        for rank, cases in RANK_DECLENSIONS.items():
            for case_name, case_form in cases.items():
                assert case_form, f"Порожня форма: {rank}.{case_name}"
                assert len(case_form) > 0, f"Порожній рядок: {rank}.{case_name}"

    def test_all_forms_lowercase(self):
        """Тест: всі форми в нижньому регістрі"""
        for rank, cases in RANK_DECLENSIONS.items():
            for case_form in cases.values():
                assert case_form == case_form.lower(), \
                    f"Форма '{case_form}' не в нижньому регістрі"


class TestRankFeminineMap:
    """Тести для RANK_FEMININE_MAP - мапи чоловічих на жіночі форми"""

    def test_feminine_map_structure(self):
        """Тест: структура мапи фемінітивів"""
        assert isinstance(RANK_FEMININE_MAP, dict)
        assert len(RANK_FEMININE_MAP) > 0

    def test_soldat_feminine(self):
        """Тест: жіноча форма 'солдат' → 'солдатка'"""
        assert RANK_FEMININE_MAP['солдат'] == 'солдатка'

    def test_serzhant_feminine(self):
        """Тест: жіноча форма 'сержант' → 'сержантка'"""
        assert RANK_FEMININE_MAP['сержант'] == 'сержантка'

    def test_kapitan_feminine(self):
        """Тест: жіноча форма 'капітан' → 'капітанка'"""
        assert RANK_FEMININE_MAP['капітан'] == 'капітанка'

    def test_mayor_feminine(self):
        """Тест: жіноча форма 'майор' → 'майорка'"""
        assert RANK_FEMININE_MAP['майор'] == 'майорка'

    def test_compound_rank_feminine(self):
        """Тест: жіноча форма складеного звання"""
        assert RANK_FEMININE_MAP['старший солдат'] == 'старша солдатка'
        assert RANK_FEMININE_MAP['молодший сержант'] == 'молодша сержантка'

    def test_all_male_ranks_exist(self):
        """Тест: всі чоловічі звання з мапи існують в RANK_DECLENSIONS"""
        for male_rank in RANK_FEMININE_MAP.keys():
            assert male_rank in RANK_DECLENSIONS, \
                f"Чоловіче звання '{male_rank}' відсутнє в RANK_DECLENSIONS"

    def test_all_female_ranks_exist(self):
        """Тест: всі жіночі звання з мапи існують в RANK_DECLENSIONS_FEMALE"""
        for female_rank in RANK_FEMININE_MAP.values():
            assert female_rank in RANK_DECLENSIONS_FEMALE, \
                f"Жіноче звання '{female_rank}' відсутнє в RANK_DECLENSIONS_FEMALE"

    def test_no_duplicate_female_forms(self):
        """Тест: немає дублікатів жіночих форм"""
        female_forms = list(RANK_FEMININE_MAP.values())
        assert len(female_forms) == len(set(female_forms)), \
            "Знайдено дублікати жіночих форм"

    def test_all_forms_lowercase(self):
        """Тест: всі форми в нижньому регістрі"""
        for male, female in RANK_FEMININE_MAP.items():
            assert male == male.lower(), f"Чоловіча форма '{male}' не в нижньому регістрі"
            assert female == female.lower(), f"Жіноча форма '{female}' не в нижньому регістрі"


class TestRankDeclensionsFemale:
    """Тести для RANK_DECLENSIONS_FEMALE - відмінків жіночих форм"""

    def test_female_declensions_structure(self):
        """Тест: структура словника жіночих відмінків"""
        assert isinstance(RANK_DECLENSIONS_FEMALE, dict)
        assert len(RANK_DECLENSIONS_FEMALE) > 0

    def test_all_female_ranks_have_four_cases(self):
        """Тест: кожне жіноче звання має 4 відмінки"""
        required_cases = {'nominative', 'genitive', 'dative', 'instrumental'}

        for rank, cases in RANK_DECLENSIONS_FEMALE.items():
            assert isinstance(cases, dict), f"Звання '{rank}' має неправильний тип"
            assert set(cases.keys()) == required_cases, \
                f"Звання '{rank}' має неповний набір відмінків"

    def test_soldatka_declensions(self):
        """Тест: відмінки жіночого звання 'солдатка'"""
        assert 'солдатка' in RANK_DECLENSIONS_FEMALE

        soldatka = RANK_DECLENSIONS_FEMALE['солдатка']
        assert soldatka['nominative'] == 'солдатка'
        assert soldatka['genitive'] == 'солдатки'
        assert soldatka['dative'] == 'солдатці'
        assert soldatka['instrumental'] == 'солдаткою'

    def test_serzhantka_declensions(self):
        """Тест: відмінки жіночого звання 'сержантка'"""
        assert 'сержантка' in RANK_DECLENSIONS_FEMALE

        serzhantka = RANK_DECLENSIONS_FEMALE['сержантка']
        assert serzhantka['nominative'] == 'сержантка'
        assert serzhantka['genitive'] == 'сержантки'
        assert serzhantka['dative'] == 'сержантці'
        assert serzhantka['instrumental'] == 'сержанткою'

    def test_kapitanka_declensions(self):
        """Тест: відмінки жіночого звання 'капітанка'"""
        assert 'капітанка' in RANK_DECLENSIONS_FEMALE

        kapitanka = RANK_DECLENSIONS_FEMALE['капітанка']
        assert kapitanka['nominative'] == 'капітанка'
        assert kapitanka['genitive'] == 'капітанки'
        assert kapitanka['dative'] == 'капітанці'
        assert kapitanka['instrumental'] == 'капітанкою'

    def test_compound_female_rank(self):
        """Тест: складене жіноче звання 'старша солдатка'"""
        assert 'старша солдатка' in RANK_DECLENSIONS_FEMALE

        starsha = RANK_DECLENSIONS_FEMALE['старша солдатка']
        assert starsha['nominative'] == 'старша солдатка'
        assert starsha['genitive'] == 'старшої солдатки'
        assert starsha['dative'] == 'старшій солдатці'
        assert starsha['instrumental'] == 'старшою солдаткою'

    def test_no_empty_declensions(self):
        """Тест: немає порожніх значень відмінків"""
        for rank, cases in RANK_DECLENSIONS_FEMALE.items():
            for case_name, case_form in cases.items():
                assert case_form, f"Порожня форма: {rank}.{case_name}"
                assert len(case_form) > 0

    def test_all_forms_lowercase(self):
        """Тест: всі форми в нижньому регістрі"""
        for rank, cases in RANK_DECLENSIONS_FEMALE.items():
            for case_form in cases.values():
                assert case_form == case_form.lower(), \
                    f"Форма '{case_form}' не в нижньому регістрі"


class TestRankToNominative:
    """Тести для RANK_TO_NOMINATIVE - зворотного індексу для пошуку"""

    def test_rank_to_nominative_structure(self):
        """Тест: структура зворотного індексу"""
        assert isinstance(RANK_TO_NOMINATIVE, dict)
        assert len(RANK_TO_NOMINATIVE) > 0

    def test_soldat_forms_in_index(self):
        """Тест: всі форми 'солдат' в індексі"""
        assert 'солдат' in RANK_TO_NOMINATIVE
        assert 'солдата' in RANK_TO_NOMINATIVE
        assert 'солдату' in RANK_TO_NOMINATIVE
        assert 'солдатом' in RANK_TO_NOMINATIVE

    def test_soldat_nominative_lookup(self):
        """Тест: пошук називного відмінка 'солдат'"""
        base, case, gender = RANK_TO_NOMINATIVE['солдат']
        assert base == 'солдат'
        assert case == 'nominative'
        assert gender == 'male'

    def test_soldat_dative_lookup(self):
        """Тест: пошук давального відмінка 'солдату'"""
        base, case, gender = RANK_TO_NOMINATIVE['солдату']
        assert base == 'солдат'
        assert case == 'dative'
        assert gender == 'male'

    def test_soldatka_nominative_lookup(self):
        """Тест: пошук жіночої форми 'солдатка'"""
        base, case, gender = RANK_TO_NOMINATIVE['солдатка']
        assert base == 'солдат'  # Базова форма - чоловіча!
        assert case == 'nominative'
        assert gender == 'female'

    def test_soldatka_dative_lookup(self):
        """Тест: пошук давального відмінка жіночої форми"""
        base, case, gender = RANK_TO_NOMINATIVE['солдатці']
        assert base == 'солдат'  # Базова форма - чоловіча!
        assert case == 'dative'
        assert gender == 'female'

    def test_compound_rank_lookup(self):
        """Тест: пошук складеного звання"""
        base, case, gender = RANK_TO_NOMINATIVE['старшого солдата']
        assert base == 'старший солдат'
        assert case == 'genitive'
        assert gender == 'male'

    def test_all_male_forms_present(self):
        """Тест: всі чоловічі форми присутні в індексі"""
        for rank, cases in RANK_DECLENSIONS.items():
            for case_form in cases.values():
                assert case_form.lower() in RANK_TO_NOMINATIVE, \
                    f"Форма '{case_form}' відсутня в RANK_TO_NOMINATIVE"

    def test_all_female_forms_present(self):
        """Тест: всі жіночі форми присутні в індексі"""
        for rank, cases in RANK_DECLENSIONS_FEMALE.items():
            for case_form in cases.values():
                assert case_form.lower() in RANK_TO_NOMINATIVE, \
                    f"Жіноча форма '{case_form}' відсутня в RANK_TO_NOMINATIVE"

    def test_tuple_structure(self):
        """Тест: структура tuple значень"""
        for case_form, value in RANK_TO_NOMINATIVE.items():
            assert isinstance(value, tuple), f"Значення для '{case_form}' не tuple"
            assert len(value) == 3, f"Tuple для '{case_form}' має {len(value)} елементів, очікується 3"

            base, case, gender = value
            assert isinstance(base, str), f"Базова форма не str: {base}"
            assert isinstance(case, str), f"Відмінок не str: {case}"
            assert gender in ('male', 'female'), f"Невірний рід: {gender}"

    def test_case_names_valid(self):
        """Тест: валідність назв відмінків"""
        valid_cases = {'nominative', 'genitive', 'dative', 'instrumental'}

        for case_form, (base, case, gender) in RANK_TO_NOMINATIVE.items():
            assert case in valid_cases, \
                f"Невалідний відмінок '{case}' для форми '{case_form}'"

    def test_lowercase_keys(self):
        """Тест: всі ключі в нижньому регістрі"""
        for key in RANK_TO_NOMINATIVE.keys():
            assert key == key.lower(), f"Ключ '{key}' не в нижньому регістрі"


class TestAllRankForms:
    """Тести для ALL_RANK_FORMS - відсортованого списку всіх форм"""

    def test_all_rank_forms_is_list(self):
        """Тест: ALL_RANK_FORMS є списком"""
        assert isinstance(ALL_RANK_FORMS, list)
        assert len(ALL_RANK_FORMS) > 0

    def test_sorted_by_length_descending(self):
        """Тест: список відсортовано за довжиною (від найдовших)"""
        for i in range(len(ALL_RANK_FORMS) - 1):
            assert len(ALL_RANK_FORMS[i]) >= len(ALL_RANK_FORMS[i + 1]), \
                f"Порушення сортування: '{ALL_RANK_FORMS[i]}' ({len(ALL_RANK_FORMS[i])}) " \
                f"коротше за '{ALL_RANK_FORMS[i + 1]}' ({len(ALL_RANK_FORMS[i + 1])})"

    def test_contains_compound_ranks_first(self):
        """Тест: складені звання йдуть першими"""
        # Складені звання довші, тому мають бути на початку
        first_ten = ALL_RANK_FORMS[:10]

        # Перевіряємо, що в топ-10 є складені звання
        has_compound = any(' ' in rank for rank in first_ten)
        assert has_compound, "У топ-10 немає жодного складеного звання"

    def test_all_forms_from_rank_to_nominative(self):
        """Тест: всі форми з RANK_TO_NOMINATIVE присутні"""
        rank_to_nom_set = set(RANK_TO_NOMINATIVE.keys())
        all_rank_forms_set = set(ALL_RANK_FORMS)

        assert rank_to_nom_set == all_rank_forms_set, \
            "ALL_RANK_FORMS не відповідає RANK_TO_NOMINATIVE"

    def test_no_duplicates(self):
        """Тест: немає дублікатів"""
        assert len(ALL_RANK_FORMS) == len(set(ALL_RANK_FORMS)), \
            "Знайдено дублікати в ALL_RANK_FORMS"

    def test_all_lowercase(self):
        """Тест: всі форми в нижньому регістрі"""
        for rank_form in ALL_RANK_FORMS:
            assert rank_form == rank_form.lower(), \
                f"Форма '{rank_form}' не в нижньому регістрі"

    def test_longest_rank_first(self):
        """Тест: найдовше звання на початку списку"""
        longest = ALL_RANK_FORMS[0]

        # Перевіряємо, що перше звання дійсно найдовше
        for rank_form in ALL_RANK_FORMS[1:]:
            assert len(longest) >= len(rank_form), \
                f"Звання '{rank_form}' довше за '{longest}'"


class TestRankLists:
    """Тести для списків звань (ARMY_RANKS, NAVAL_RANKS, etc.)"""

    def test_army_ranks_not_empty(self):
        """Тест: список армійських звань не порожній"""
        assert isinstance(ARMY_RANKS, list)
        assert len(ARMY_RANKS) > 0

    def test_naval_ranks_not_empty(self):
        """Тест: список морських звань не порожній"""
        assert isinstance(NAVAL_RANKS, list)
        assert len(NAVAL_RANKS) > 0

    def test_legal_ranks_not_empty(self):
        """Тест: список звань юстиції не порожній"""
        assert isinstance(LEGAL_RANKS, list)
        assert len(LEGAL_RANKS) > 0

    def test_medical_ranks_not_empty(self):
        """Тест: список медичних звань не порожній"""
        assert isinstance(MEDICAL_RANKS, list)
        assert len(MEDICAL_RANKS) > 0

    def test_army_ranks_content(self):
        """Тест: армійські звання містять очікувані звання"""
        assert "солдат" in ARMY_RANKS
        assert "сержант" in ARMY_RANKS
        assert "капітан" in ARMY_RANKS
        assert "майор" in ARMY_RANKS
        assert "генерал" in ARMY_RANKS

    def test_naval_ranks_content(self):
        """Тест: морські звання містять матросів та адміралів"""
        assert "матрос" in NAVAL_RANKS
        assert any("адмірал" in rank for rank in NAVAL_RANKS)

    def test_legal_ranks_have_yustytsii(self):
        """Тест: звання юстиції містять слово 'юстиції'"""
        for rank in LEGAL_RANKS:
            assert "юстиції" in rank, \
                f"Звання '{rank}' не містить 'юстиції'"

    def test_medical_ranks_have_medychnoi(self):
        """Тест: медичні звання містять 'медичної служби'"""
        for rank in MEDICAL_RANKS:
            assert "медичної служби" in rank, \
                f"Звання '{rank}' не містить 'медичної служби'"

    def test_no_duplicates_in_army_ranks(self):
        """Тест: немає дублікатів в армійських званнях"""
        assert len(ARMY_RANKS) == len(set(ARMY_RANKS))

    def test_no_duplicates_in_naval_ranks(self):
        """Тест: немає дублікатів в морських званнях"""
        assert len(NAVAL_RANKS) == len(set(NAVAL_RANKS))

    def test_all_lists_lowercase(self):
        """Тест: всі списки в нижньому регістрі"""
        for rank in ARMY_RANKS + NAVAL_RANKS + LEGAL_RANKS + MEDICAL_RANKS:
            assert rank == rank.lower(), f"Звання '{rank}' не в нижньому регістрі"


class TestRanksList:
    """Тести для RANKS_LIST - фінального списку всіх звань"""

    def test_ranks_list_structure(self):
        """Тест: структура RANKS_LIST"""
        assert isinstance(RANKS_LIST, list)
        assert len(RANKS_LIST) > 0

    def test_ranks_list_sorted_by_length(self):
        """Тест: RANKS_LIST відсортовано за довжиною"""
        for i in range(len(RANKS_LIST) - 1):
            assert len(RANKS_LIST[i]) >= len(RANKS_LIST[i + 1]), \
                f"Порушення сортування в RANKS_LIST"

    def test_ranks_list_no_duplicates(self):
        """Тест: немає дублікатів в RANKS_LIST"""
        assert len(RANKS_LIST) == len(set(RANKS_LIST)), \
            "Знайдено дублікати в RANKS_LIST"

    def test_ranks_list_contains_all_categories(self):
        """Тест: RANKS_LIST містить звання з усіх категорій"""
        # Перевіряємо наявність звань з різних категорій
        assert "солдат" in RANKS_LIST
        assert "матрос" in RANKS_LIST or "моряк" in RANKS_LIST
        assert any("юстиції" in r for r in RANKS_LIST)
        assert any("медичної служби" in r for r in RANKS_LIST)

    def test_ranks_list_contains_all_declensions(self):
        """Тест: RANKS_LIST містить всі відмінкові форми"""
        # Перевіряємо різні відмінки солдата
        assert "солдат" in RANKS_LIST
        assert "солдата" in RANKS_LIST
        assert "солдату" in RANKS_LIST
        assert "солдатом" in RANKS_LIST

    def test_ranks_list_contains_female_forms(self):
        """Тест: RANKS_LIST містить жіночі форми"""
        assert "солдатка" in RANKS_LIST
        assert "сержантка" in RANKS_LIST
        assert "капітанка" in RANKS_LIST

    def test_ranks_list_all_lowercase(self):
        """Тест: всі елементи в нижньому регістрі"""
        for rank in RANKS_LIST:
            assert rank == rank.lower(), f"Звання '{rank}' не в нижньому регістрі"

    def test_ranks_list_comprehensive(self):
        """Тест: RANKS_LIST містить більше звань ніж окремі категорії"""
        # RANKS_LIST має бути більшим за будь-яку окрему категорію
        assert len(RANKS_LIST) > len(ARMY_RANKS)
        assert len(RANKS_LIST) > len(NAVAL_RANKS)
        assert len(RANKS_LIST) > len(LEGAL_RANKS)
        assert len(RANKS_LIST) > len(MEDICAL_RANKS)


class TestDataConsistency:
    """Тести для узгодженості даних між різними структурами"""

    def test_feminine_map_consistency(self):
        """Тест: узгодженість RANK_FEMININE_MAP з іншими структурами"""
        for male_rank, female_rank in RANK_FEMININE_MAP.items():
            # Чоловіче звання має бути в RANK_DECLENSIONS
            assert male_rank in RANK_DECLENSIONS, \
                f"Чоловіче '{male_rank}' відсутнє в RANK_DECLENSIONS"

            # Жіноче звання має бути в RANK_DECLENSIONS_FEMALE
            assert female_rank in RANK_DECLENSIONS_FEMALE, \
                f"Жіноче '{female_rank}' відсутнє в RANK_DECLENSIONS_FEMALE"

    def test_rank_to_nominative_completeness(self):
        """Тест: RANK_TO_NOMINATIVE містить всі форми з обох словників"""
        # Перевіряємо чоловічі форми
        for rank, cases in RANK_DECLENSIONS.items():
            for case_form in cases.values():
                assert case_form.lower() in RANK_TO_NOMINATIVE, \
                    f"Чоловіча форма '{case_form}' відсутня в індексі"

        # Перевіряємо жіночі форми
        for rank, cases in RANK_DECLENSIONS_FEMALE.items():
            for case_form in cases.values():
                assert case_form.lower() in RANK_TO_NOMINATIVE, \
                    f"Жіноча форма '{case_form}' відсутня в індексі"

    def test_all_rank_forms_matches_index(self):
        """Тест: ALL_RANK_FORMS повністю відповідає RANK_TO_NOMINATIVE"""
        set1 = set(ALL_RANK_FORMS)
        set2 = set(RANK_TO_NOMINATIVE.keys())

        assert set1 == set2, \
            f"Розбіжність між ALL_RANK_FORMS та RANK_TO_NOMINATIVE: " \
            f"різниця = {set1.symmetric_difference(set2)}"

    def test_ranks_list_includes_all_declensions(self):
        """Тест: RANKS_LIST включає всі форми з відмінків"""
        # Всі форми з RANK_DECLENSIONS мають бути в RANKS_LIST
        for rank, cases in RANK_DECLENSIONS.items():
            for case_form in cases.values():
                assert case_form in RANKS_LIST, \
                    f"Форма '{case_form}' відсутня в RANKS_LIST"


class TestEdgeCases:
    """Тести для граничних випадків та особливих ситуацій"""

    def test_hyphenated_ranks(self):
        """Тест: звання з дефісами"""
        # Перевіряємо, що звання з дефісами правильно оброблені
        hyphenated_ranks = [r for r in RANKS_LIST if '-' in r]

        assert len(hyphenated_ranks) > 0, "Немає звань з дефісами"

        # Приклади звань з дефісами
        examples = ['штаб-сержант', 'мастер-сержант', 'контр-адмірал', 'віце-адмірал']
        for example in examples:
            if example in RANK_DECLENSIONS:
                assert example in RANKS_LIST

    def test_multi_word_ranks(self):
        """Тест: багатослівні звання"""
        multi_word = [r for r in RANKS_LIST if ' ' in r]

        assert len(multi_word) > 0, "Немає багатослівних звань"

        # Складені звання мають бути довшими і йти першими
        assert multi_word[0] in RANKS_LIST[:50], \
            "Складені звання не на початку списку"

    def test_special_service_ranks(self):
        """Тест: звання спеціальних служб"""
        # Медична служба
        medical = [r for r in RANKS_LIST if 'медичної служби' in r]
        assert len(medical) > 0, "Немає звань медичної служби"

        # Юстиція
        legal = [r for r in RANKS_LIST if 'юстиції' in r]
        assert len(legal) > 0, "Немає звань юстиції"

    def test_rank_forms_length_distribution(self):
        """Тест: розподіл довжин форм звань"""
        lengths = [len(r) for r in RANKS_LIST]

        # Мають бути як короткі, так і довгі звання
        assert min(lengths) < 10, "Немає коротких звань"
        assert max(lengths) > 20, "Немає довгих звань"

    def test_unicode_handling(self):
        """Тест: правильна обробка українських символів"""
        for rank in RANKS_LIST:
            # Перевіряємо, що звання містить кирилицю
            has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in rank)
            assert has_cyrillic or rank in ['-'], \
                f"Звання '{rank}' не містить кирилиці"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
