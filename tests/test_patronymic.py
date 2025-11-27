# -*- coding: utf-8 -*-
"""
Tests for patronymic masking

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.2.14
License: BSD 3-Clause "New" or "Revised" License
Year: 2025

"""
import pytest
from data_masking import mask_patronymic


@pytest.mark.patronymic
class TestMaskPatronymic:
    """Tests for mask_patronymic() function"""

    def test_male_patronymic_basic(self, empty_masking_dict, instance_counters):
        """Test basic male patronymic masking"""
        result = mask_patronymic("Миколайович", "male", empty_masking_dict, instance_counters)

        # Перевіряємо що результат не пустий і відрізняється від оригіналу
        assert result
        assert result != "Миколайович"
        assert result.endswith("ович") or result.endswith("ич")

        # Перевіряємо що додано в mapping
        assert "patronymic" in empty_masking_dict["mappings"]
        assert "миколайович" in empty_masking_dict["mappings"]["patronymic"]

    def test_female_patronymic_basic(self, empty_masking_dict, instance_counters):
        """Test basic female patronymic masking"""
        result = mask_patronymic("Петрівна", "female", empty_masking_dict, instance_counters)

        assert result
        assert result != "Петрівна"
        # Перевіряємо що це жіноче по-батькові (закінчується на -івна, -ївна, -овна)
        assert result.endswith("івна") or result.endswith("ївна") or result.endswith("овна")

        assert "patronymic" in empty_masking_dict["mappings"]
        assert "петрівна" in empty_masking_dict["mappings"]["patronymic"]

    def test_uppercase_patronymic(self, empty_masking_dict, instance_counters):
        """Test UPPERCASE patronymic masking"""
        result = mask_patronymic("МИКОЛАЙОВИЧ", "male", empty_masking_dict, instance_counters)

        assert result
        assert result.isupper()

    def test_capitalize_patronymic(self, empty_masking_dict, instance_counters):
        """Test Capitalized patronymic masking"""
        result = mask_patronymic("Миколайович", "male", empty_masking_dict, instance_counters)

        assert result
        assert result[0].isupper()
        assert result[1:].islower()

    def test_lowercase_patronymic(self, empty_masking_dict, instance_counters):
        """Test lowercase patronymic masking"""
        result = mask_patronymic("миколайович", "male", empty_masking_dict, instance_counters)

        assert result
        # Перевіряємо що перша літера lowercase (не capitalize і не uppercase)
        assert result[0].islower()
        assert not result.isupper()

    def test_consistency_same_patronymic(self, empty_masking_dict, instance_counters):
        """Test that same patronymic masks to same value"""
        result1 = mask_patronymic("Миколайович", "male", empty_masking_dict, instance_counters)
        result2 = mask_patronymic("Миколайович", "male", empty_masking_dict, instance_counters)

        assert result1 == result2

        # Перевіряємо instance tracking
        assert len(empty_masking_dict["mappings"]["patronymic"]["миколайович"]["instances"]) == 2

    def test_different_case_same_mapping(self, empty_masking_dict, instance_counters):
        """Test that different cases of same patronymic use same mapping"""
        result1 = mask_patronymic("Миколайович", "male", empty_masking_dict, instance_counters)
        result2 = mask_patronymic("МИКОЛАЙОВИЧ", "male", empty_masking_dict, instance_counters)
        result3 = mask_patronymic("миколайович", "male", empty_masking_dict, instance_counters)

        # Всі мають бути з одного маппінгу (lowercase key)
        assert "миколайович" in empty_masking_dict["mappings"]["patronymic"]

        # Але з різним регістром
        assert result1[0].isupper() and result1[1:].islower()
        # result2 має бути uppercase (всі великі літери)
        assert result2.isupper(), f"Expected UPPERCASE result for UPPERCASE input, got: '{result2}'"
        assert result3[0].islower()  # lowercase - перша літера мала

    def test_empty_patronymic(self, empty_masking_dict, instance_counters):
        """Test with empty patronymic"""
        result = mask_patronymic("", "male", empty_masking_dict, instance_counters)
        assert result == ""

    def test_none_patronymic(self, empty_masking_dict, instance_counters):
        """Test with None patronymic"""
        result = mask_patronymic(None, "male", empty_masking_dict, instance_counters)
        assert result is None

    @pytest.mark.parametrize("patronymic,gender,expected_ending", [
        ("Іванович", "male", "ович"),
        ("Петрович", "male", "ович"),
        ("Іванівна", "female", "івна"),
        ("Петрівна", "female", "івна"),
        ("Олександрович", "male", "ович"),
        ("Олександрівна", "female", "івна"),
    ])
    def test_various_patronymics(self, patronymic, gender, expected_ending,
                                 empty_masking_dict, instance_counters):
        """Parametrized test for various patronymics"""
        result = mask_patronymic(patronymic, gender, empty_masking_dict, instance_counters)

        assert result
        assert result != patronymic

        # Перевіряємо що закінчення відповідає гендеру
        if gender == "male":
            # Чоловіче по-батькові: -ович, -евич, -ич
            assert result.lower().endswith("ович") or result.lower().endswith("евич") or result.lower().endswith("ич")
        else:
            # Жіноче по-батькові: -івна, -ївна, -овна
            assert result.lower().endswith("івна") or result.lower().endswith("ївна") or result.lower().endswith("овна")


@pytest.mark.integration
@pytest.mark.patronymic
class TestPatronymicIntegration:
    """Integration tests for patronymic in full PIB"""

    def test_full_pib_with_patronymic(self, empty_masking_dict, instance_counters):
        """Test patronymic masking in context of full PIB"""
        from data_masking import mask_surname, mask_name, mask_patronymic

        surname = "Іванов"
        name = "Петро"
        patronymic = "Миколайович"

        masked_surname = mask_surname(surname, empty_masking_dict, instance_counters)
        masked_name = mask_name(name, empty_masking_dict, instance_counters,
                                gender_hint="male", patronymic_hint=patronymic)
        masked_patronymic = mask_patronymic(patronymic, "male", empty_masking_dict, instance_counters)

        # Всі компоненти мають бути замасковані
        assert masked_surname != surname
        assert masked_name != name
        assert masked_patronymic != patronymic

        # Перевіряємо mapping
        assert "surname" in empty_masking_dict["mappings"]
        assert "name" in empty_masking_dict["mappings"]
        assert "patronymic" in empty_masking_dict["mappings"]