# -*- coding: utf-8 -*-
"""
Tests for helper functions

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.2.14
License: BSD 3-Clause "New" or "Revised" License
Year: 2025

"""
import pytest
from data_masking import _apply_original_case


class TestApplyOriginalCase:
    """Tests for _apply_original_case() helper function"""
    
    def test_uppercase(self):
        """Test UPPERCASE conversion"""
        result = _apply_original_case("КАПІТАН", "майор")
        assert result == "МАЙОР"
    
    def test_capitalize(self):
        """Test Capitalize conversion"""
        result = _apply_original_case("Капітан", "майор")
        assert result == "Майор"
    
    def test_lowercase(self):
        """Test lowercase conversion"""
        result = _apply_original_case("капітан", "майор")
        assert result == "майор"
    
    def test_empty_original(self):
        """Test with empty original string"""
        result = _apply_original_case("", "майор")
        assert result == "майор"
    
    def test_empty_masked(self):
        """Test with empty masked string"""
        result = _apply_original_case("КАПІТАН", "")
        assert result == ""
    
    def test_single_char_uppercase(self):
        """Test single character UPPERCASE"""
        result = _apply_original_case("А", "б")
        assert result == "Б"
    
    def test_single_char_lowercase(self):
        """Test single character lowercase"""
        result = _apply_original_case("а", "б")
        assert result == "б"
    
    def test_mixed_case_long_word(self):
        """Test with longer words"""
        result = _apply_original_case("СТАРШИЙ", "молодший")
        assert result == "МОЛОДШИЙ"
    
    def test_cyrillic_with_dash(self):
        """Test with dash in word"""
        result = _apply_original_case("Штаб-сержант", "майстер-сержант")
        assert result == "Майстер-сержант"
    
    @pytest.mark.parametrize("original,masked,expected", [
        ("ТЕСТ", "результат", "РЕЗУЛЬТАТ"),
        ("Тест", "результат", "Результат"),
        ("тест", "результат", "результат"),
        ("COLONEL", "major", "MAJOR"),
        ("Colonel", "major", "Major"),
    ])
    def test_various_cases(self, original, masked, expected):
        """Parametrized test for various cases"""
        result = _apply_original_case(original, masked)
        assert result == expected
