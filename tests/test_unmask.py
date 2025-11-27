#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тести для unmask_data.py

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
from unmask_data import (
    _apply_original_case,
    extract_base_rank,
    is_real_mask,
    get_rank_info,
    find_all_occurrences,
    build_instance_map,
)


class TestGetRankInfo:
    """Тести для get_rank_info() - розпізнавання звань"""

    def test_dative_male(self):
        """Тест: давальний відмінок чоловічого роду"""
        base, case, gender = get_rank_info("солдату")
        assert base == "солдат"
        assert case == "dative"
        assert gender == "male"

    def test_dative_female(self):
        """Тест: давальний відмінок жіночого роду"""
        base, case, gender = get_rank_info("сержантці")
        assert base == "сержант"
        assert case == "dative"
        assert gender == "female"

    def test_compound_rank_genitive(self):
        """Тест: складене звання в родовому відмінку"""
        base, case, gender = get_rank_info("капітана медичної служби")
        assert base == "капітан медичної служби"
        assert case == "genitive"
        assert gender == "male"

    def test_unknown_rank(self):
        """Тест: невідоме звання"""
        base, case, gender = get_rank_info("неіснуюче_звання")
        assert base is None
        assert case is None
        assert gender is None

    def test_nominative_male(self):
        """Тест: називний відмінок чоловічого роду"""
        base, case, gender = get_rank_info("капітан")
        assert base == "капітан"
        assert case == "nominative"
        assert gender == "male"

    def test_nominative_female(self):
        """Тест: називний відмінок жіночого роду"""
        base, case, gender = get_rank_info("капітанка")
        assert base == "капітан"
        assert case == "nominative"
        assert gender == "female"


class TestFindAllOccurrences:
    """Тести для find_all_occurrences() - пошук входжень у тексті"""

    def test_single_word(self):
        """Тест: одне входження цілого слова"""
        text = "Солдат виконав наказ. Солдату присвоєно звання."
        occurrences = find_all_occurrences(text, "солдат")
        # Має знайти тільки "Солдат", а не "Солдату" (це інша форма)
        assert len(occurrences) == 1
        assert occurrences[0] == (0, 6)

    def test_multiple_occurrences(self):
        """Тест: кілька входжень одного слова"""
        text = "Капітан наказав. Капітан перевірив. Капітан затвердив."
        occurrences = find_all_occurrences(text, "капітан")
        assert len(occurrences) == 3

    def test_case_insensitive(self):
        """Тест: регістронезалежний пошук"""
        text = "МАЙОР прибув. Майор доповів. майор пішов."
        occurrences = find_all_occurrences(text, "майор")
        assert len(occurrences) == 3

    def test_no_partial_matches(self):
        """Тест: не знаходить часткові збіги"""
        text = "Солдат і солдатка служили"
        occurrences = find_all_occurrences(text, "солдат")
        # Має знайти тільки "Солдат", а не "солдатка"
        assert len(occurrences) == 1

    def test_empty_text(self):
        """Тест: порожній текст"""
        occurrences = find_all_occurrences("", "капітан")
        assert occurrences == []

    def test_word_boundaries(self):
        """Тест: перевірка меж слова"""
        text = "Сержант говорив про підсержанта"
        occurrences = find_all_occurrences(text, "сержант")
        # Має знайти тільки "Сержант", а не "підсержанта"
        assert len(occurrences) == 1


class TestBuildInstanceMap:
    """Тести для build_instance_map() - створення мапи instance tracking"""

    def test_simple_mapping(self):
        """Тест: проста мапа з одним входженням"""
        masking_map = {
            "mappings": {
                "surname": {
                    "петренко": {
                        "masked_as": "Іваненко",
                        "instances": [1]
                    }
                }
            }
        }

        instance_map = build_instance_map(masking_map)

        assert "Іваненко" in instance_map
        assert instance_map["Іваненко"][1] == "петренко"

    def test_collision_mapping(self):
        """Тест: мапа з колізіями (різні оригінали → одна маска)"""
        masking_map = {
            "mappings": {
                "surname": {
                    "петренко": {
                        "masked_as": "Іваненко",
                        "instances": [1]
                    },
                    "сидоренко": {
                        "masked_as": "Іваненко",
                        "instances": [2, 3]
                    }
                }
            }
        }

        instance_map = build_instance_map(masking_map)

        assert instance_map["Іваненко"][1] == "петренко"
        assert instance_map["Іваненко"][2] == "сидоренко"
        assert instance_map["Іваненко"][3] == "сидоренко"

    def test_multiple_categories(self):
        """Тест: мапа з кількома категоріями"""
        masking_map = {
            "mappings": {
                "surname": {
                    "петренко": {
                        "masked_as": "Іваненко",
                        "instances": [1]
                    }
                },
                "name": {
                    "андрій": {
                        "masked_as": "Петро",
                        "instances": [1]
                    }
                }
            }
        }

        instance_map = build_instance_map(masking_map)

        assert "Іваненко" in instance_map
        assert "Петро" in instance_map

    def test_empty_mapping(self):
        """Тест: порожня мапа"""
        masking_map = {"mappings": {}}
        instance_map = build_instance_map(masking_map)
        assert instance_map == {}

    def test_no_instances(self):
        """Тест: маска без instances"""
        masking_map = {
            "mappings": {
                "surname": {
                    "петренко": {
                        "masked_as": "Іваненко"
                        # instances відсутній
                    }
                }
            }
        }

        instance_map = build_instance_map(masking_map)
        assert "Іваненко" in instance_map
        assert instance_map["Іваненко"] == {}


class TestApplyOriginalCaseUnmask:
    """Тести для _apply_original_case() в unmask_data"""

    def test_uppercase(self):
        """Тест: UPPER регістр"""
        result = _apply_original_case("КАПІТАН", "майор")
        assert result == "МАЙОР"

    def test_capitalize(self):
        """Тест: Capitalize регістр"""
        result = _apply_original_case("Капітан", "майор")
        assert result == "Майор"

    def test_lowercase(self):
        """Тест: lower регістр"""
        result = _apply_original_case("капітан", "майор")
        assert result == "майор"

    def test_empty_strings(self):
        """Тест: порожні рядки"""
        assert _apply_original_case("", "майор") == "майор"
        assert _apply_original_case("КАПІТАН", "") == ""

    def test_mixed_case(self):
        """Тест: мішаний регістр (fallback до lower)"""
        result = _apply_original_case("КаПіТаН", "майор")
        # Має повернути lower, бо не UPPER і не Title Case
        assert result == "майор"

    def test_cyrillic_uppercase(self):
        """Тест: кирилиця у верхньому регістрі"""
        result = _apply_original_case("СОЛДАТ", "капітан")
        assert result == "КАПІТАН"


class TestExtractBaseRank:
    """Тести для extract_base_rank()"""

    def test_simple_rank(self):
        """Тест: просте звання без додаткових слів"""
        base, extras = extract_base_rank("майор")
        assert base == "майор"
        assert extras == ""

    def test_rank_with_retirement(self):
        """Тест: звання у відставці"""
        base, extras = extract_base_rank("майор у відставці")
        assert base == "майор"
        assert "у відставці" in extras

    def test_rank_with_reserve(self):
        """Тест: звання в запасі"""
        base, extras = extract_base_rank("капітан в запасі")
        assert base == "капітан"
        assert "в запасі" in extras

    def test_rank_medical(self):
        """Тест: звання медичної служби"""
        base, extras = extract_base_rank("майор медичної служби")
        assert base == "майор"
        assert "медичної служби" in extras

    def test_rank_justice(self):
        """Тест: звання юстиції"""
        base, extras = extract_base_rank("капітан юстиції")
        assert base == "капітан"
        assert "юстиції" in extras

    def test_complex_rank(self):
        """Тест: складне звання з кількома додатковими словами"""
        base, extras = extract_base_rank("капітан медичної служби у відставці")
        assert base == "капітан"
        assert "медичної служби" in extras
        assert "у відставці" in extras

    def test_compound_rank(self):
        """Тест: складене звання (штаб-сержант)"""
        base, extras = extract_base_rank("штаб-сержант")
        assert base == "штаб-сержант"
        assert extras == ""

    def test_rank_dative_with_reserve(self):
        """Тест: звання у давальному відмінку з запасом"""
        base, extras = extract_base_rank("молодшому сержанту в запасі")
        assert base == "молодшому сержанту"
        assert "в запасі" in extras

    def test_rank_with_pension(self):
        """Тест: звання на пенсії"""
        base, extras = extract_base_rank("полковник на пенсії")
        assert base == "полковник"
        assert "на пенсії" in extras

    def test_empty_rank(self):
        """Тест: порожній рядок"""
        base, extras = extract_base_rank("")
        assert base == ""
        assert extras == ""


class TestIsRealMask:
    """Тести для is_real_mask() - O(1) оптимізація v2.2.1"""

    def test_real_mask_found(self):
        """Тест: справжня маска знайдена"""
        masking_map = {
            "mappings": {
                "rank": {
                    "майор": {
                        "masked_as": "капітан",
                        "gender": "male",
                        "instances": [1]
                    }
                }
            }
        }

        # Створюємо lookup set
        all_masked_values = {"капітан"}

        result = is_real_mask("капітан", masking_map, all_masked_values)
        assert result is True

    def test_not_mask_original(self):
        """Тест: це оригінальне значення, не маска"""
        masking_map = {
            "mappings": {
                "rank": {
                    "майор": {
                        "masked_as": "капітан",
                        "gender": "male",
                        "instances": [1]
                    }
                }
            }
        }

        all_masked_values = {"капітан"}

        # "майор" - це оригінал, не маска
        result = is_real_mask("майор", masking_map, all_masked_values)
        assert result is False

    def test_empty_mapping(self):
        """Тест: порожній mapping"""
        masking_map = {
            "mappings": {
                "rank": {}
            }
        }

        all_masked_values = set()

        result = is_real_mask("будь-що", masking_map, all_masked_values)
        assert result is False

    def test_case_insensitive(self):
        """Тест: перевірка незалежно від регістру"""
        masking_map = {
            "mappings": {
                "rank": {
                    "майор": {
                        "masked_as": "капітан",
                        "gender": "male",
                        "instances": [1]
                    }
                }
            }
        }

        all_masked_values = {"капітан"}

        # Перевіряємо різні регістри
        assert is_real_mask("КАПІТАН", masking_map, all_masked_values) is True
        assert is_real_mask("Капітан", masking_map, all_masked_values) is True
        assert is_real_mask("капітан", masking_map, all_masked_values) is True

    def test_without_lookup_set(self):
        """Тест: перевірка без lookup set (повільний шлях)"""
        masking_map = {
            "mappings": {
                "rank": {
                    "майор": {
                        "masked_as": "капітан",
                        "gender": "male",
                        "instances": [1]
                    }
                }
            }
        }

        # Не передаємо all_masked_values
        result = is_real_mask("капітан", masking_map)
        assert result is True

    def test_multiple_categories(self):
        """Тест: маска в різних категоріях"""
        masking_map = {
            "mappings": {
                "rank": {
                    "майор": {
                        "masked_as": "капітан",
                        "instances": [1]
                    }
                },
                "surname": {
                    "петренко": {
                        "masked_as": "Іваненко",
                        "instances": [1]
                    }
                }
            }
        }

        all_masked_values = {"капітан", "іваненко"}

        assert is_real_mask("капітан", masking_map, all_masked_values) is True
        assert is_real_mask("Іваненко", masking_map, all_masked_values) is True
        assert is_real_mask("петренко", masking_map, all_masked_values) is False


class TestUnmaskIntegration:
    """Інтеграційні тести для unmask процесу"""

    def test_unmask_preserves_case(self):
        """Тест: unmask зберігає оригінальний регістр"""
        # Якщо в тексті було "КАПІТАН", unmask має повернути "МАЙОР"
        original_case = "КАПІТАН"
        unmasked_value = "майор"

        result = _apply_original_case(original_case, unmasked_value)
        assert result == "МАЙОР"

    def test_extract_and_reconstruct(self):
        """Тест: extraction та reconstruction звання"""
        full_rank = "капітан медичної служби у відставці"
        base, extras = extract_base_rank(full_rank)

        # Reconstruct
        reconstructed = base
        if extras:
            reconstructed += " " + extras

        assert reconstructed == full_rank

    def test_complex_rank_extraction(self):
        """Тест: витягування складного звання"""
        full_rank = "майор юстиції в запасі"
        base, extras = extract_base_rank(full_rank)

        assert base == "майор"
        assert "юстиції" in extras
        assert "в запасі" in extras

    def test_instance_tracking_scenario(self):
        """Тест: сценарій з instance tracking"""
        masking_map = {
            "mappings": {
                "surname": {
                    "петренко": {
                        "masked_as": "Коваленко",
                        "instances": [1, 3]
                    },
                    "сидоренко": {
                        "masked_as": "Коваленко",
                        "instances": [2]
                    }
                }
            }
        }

        instance_map = build_instance_map(masking_map)

        # Перше та третє входження "Коваленко" мають розмаскуватися в "петренко"
        assert instance_map["Коваленко"][1] == "петренко"
        assert instance_map["Коваленко"][3] == "петренко"
        # Друге входження має розмаскуватися в "сидоренко"
        assert instance_map["Коваленко"][2] == "сидоренко"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
