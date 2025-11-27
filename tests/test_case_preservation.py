# -*- coding: utf-8 -*-
"""
Tests for case preservation

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.2.14
License: BSD 3-Clause "New" or "Revised" License
Year: 2025

"""
import pytest
from data_masking import mask_rank


@pytest.mark.unit
class TestCasePreservation:
    """Tests for case preservation in masking"""

    def test_rank_uppercase(self, empty_masking_dict, instance_counters):
        """Test rank with UPPERCASE preservation"""
        result = mask_rank("КАПІТАН", empty_masking_dict, instance_counters)

        assert result
        assert result.isupper(), f"Expected uppercase, got: '{result}'"
        assert result != "КАПІТАН"

    def test_rank_capitalize(self, empty_masking_dict, instance_counters):
        """Test rank with Capitalize preservation"""
        result = mask_rank("Капітан", empty_masking_dict, instance_counters)

        assert result
        assert result[0].isupper(), f"Expected Title Case, got: '{result}'"
        if len(result) > 1:
            assert result[1:].islower()
        assert result != "Капітан"

    def test_rank_lowercase(self, empty_masking_dict, instance_counters):
        """Test rank with lowercase preservation"""
        result = mask_rank("капітан", empty_masking_dict, instance_counters)

        assert result
        assert result.islower(), f"Expected lowercase, got: '{result}'"
        assert result != "капітан"

    def test_same_rank_different_cases(self, empty_masking_dict, instance_counters):
        """Test that same rank with different cases maps to same masked value"""
        result1 = mask_rank("КАПІТАН", empty_masking_dict, instance_counters)
        result2 = mask_rank("Капітан", empty_masking_dict, instance_counters)
        result3 = mask_rank("капітан", empty_masking_dict, instance_counters)

        # Всі мають маскуватися до одного базового значення (lowercase key)
        assert "капітан" in empty_masking_dict["mappings"]["rank"]

        # Але з різним регістром
        assert result1.isupper(), f"result1 should be uppercase: '{result1}'"

        # result2 має бути Title Case
        assert result2[0].isupper(), f"Expected Title Case for result2, got: '{result2}'"

        assert result3.islower(), f"result3 should be lowercase: '{result3}'"

        # Базове значення має бути однакове
        base_masked = empty_masking_dict["mappings"]["rank"]["капітан"]["masked_as"]
        assert result1.lower() == base_masked.lower()
        assert result2.lower() == base_masked.lower()
        assert result3.lower() == base_masked.lower()

    def test_compound_rank_case(self, empty_masking_dict, instance_counters):
        """Test compound rank with case preservation
        """
        result = mask_rank("Старший Лейтенант", empty_masking_dict, instance_counters)

        assert result
        # Для складних слів використовується title()
        # Кожне слово має починатися з великої літери
        words = result.split()
        for word in words:
            if word:  # Пропускаємо порожні рядки
                assert word[0].isupper(), f"Word '{word}' in compound rank should start with uppercase"


@pytest.mark.integration
class TestCasePreservationIntegration:
    """Integration tests for case preservation across functions"""

    def test_surname_case_preservation(self, empty_masking_dict, instance_counters):
        """Test surname case preservation"""
        from data_masking import mask_surname

        result_upper = mask_surname("ІВАНОВ", empty_masking_dict, instance_counters)
        result_cap = mask_surname("Іванов", empty_masking_dict, instance_counters)
        result_lower = mask_surname("іванов", empty_masking_dict, instance_counters)

        assert result_upper.isupper(), f"Expected uppercase, got: '{result_upper}'"
        assert result_cap[0].isupper(), f"Expected first letter uppercase in: '{result_cap}'"
        if len(result_cap) > 1:
            assert result_cap[1:].islower(), f"Expected lowercase after first letter in: '{result_cap}'"
        assert result_lower.islower(), f"Expected lowercase, got: '{result_lower}'"

    def test_name_case_preservation(self, empty_masking_dict, instance_counters):
        """Test name case preservation
        """
        from data_masking import mask_name

        result_upper = mask_name("ПЕТРО", empty_masking_dict, instance_counters)
        result_cap = mask_name("Петро", empty_masking_dict, instance_counters)
        result_lower = mask_name("петро", empty_masking_dict, instance_counters)

        assert result_upper.isupper(), f"Expected uppercase, got: '{result_upper}'"
        assert result_cap[0].isupper(), f"Expected first letter uppercase in: '{result_cap}'"
        if len(result_cap) > 1:
            assert result_cap[1:].islower(), f"Expected lowercase after first letter in: '{result_cap}'"

        assert result_lower.islower(), f"Expected lowercase, got: '{result_lower}'"


# === ДІАГНОСТИЧНИЙ ТЕСТ ===

@pytest.mark.unit
def test_case_preservation_diagnostic(empty_masking_dict, instance_counters):
    """Діагностичний тест для виявлення проблеми зберігання регістру

    Цей тест показує як саме функція обробляє різні регістри
    """
    print("\n" + "="*70)
    print("ДІАГНОСТИКА ЗБЕРІГАННЯ РЕГІСТРУ")
    print("="*70)

    test_cases = [
        ("КАПІТАН", "uppercase"),
        ("Капітан", "title"),
        ("капітан", "lowercase"),
    ]

    for input_val, case_type in test_cases:
        result = mask_rank(input_val, empty_masking_dict, instance_counters)

        print(f"\nInput:  '{input_val}' ({case_type})")
        print(f"Output: '{result}'")
        print(f"  - isupper(): {result.isupper()}")
        print(f"  - istitle(): {result.istitle()}")
        print(f"  - islower(): {result.islower()}")

        # Перевірка чи зберігся регістр
        if case_type == "uppercase":
            status = "✅" if result.isupper() else "❌"
        elif case_type == "title":
            status = "✅" if result.istitle() or result[0].isupper() else "❌"
        else:  # lowercase
            status = "✅" if result.islower() else "❌"

        print(f"  Status: {status}")

    print("="*70)
