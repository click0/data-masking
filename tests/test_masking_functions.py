# -*- coding: utf-8 -*-
"""
Unit tests for untested masking functions in data_masking.py

Tests cover: mask_ipn, mask_passport_id, mask_military_id, mask_military_unit,
mask_order_number, mask_br_number, mask_brigade_number, mask_date,
normalize_broken_ranks, detect_gender_by_patronymic
"""
import pytest
import re

from data_masking import (
    mask_ipn,
    mask_passport_id,
    mask_military_id,
    mask_military_unit,
    mask_order_number,
    mask_br_number,
    mask_brigade_number,
    mask_date,
    normalize_broken_ranks,
    detect_gender_by_patronymic,
)


@pytest.fixture
def full_masking_dict():
    """Masking dict with all required category keys."""
    return {
        "version": "v2.0",
        "timestamp": "2025-11-19T00:00:00",
        "mappings": {
            "rank": {},
            "surname": {},
            "name": {},
            "patronymic": {},
            "unit": {},
            "ipn": {},
            "passport_id": {},
            "military_id": {},
            "military_unit": {},
            "order_number": {},
            "br_number": {},
            "brigade_number": {},
            "document_number": {},
            "date": {},
        },
        "statistics": {},
    }


@pytest.fixture
def counters():
    """Fresh instance counters."""
    return {}


# ============================================================================
# mask_ipn
# ============================================================================

class TestMaskIpn:
    """Tests for mask_ipn() — 10-digit Ukrainian tax ID masking."""

    def test_basic_masking(self, full_masking_dict, counters):
        result = mask_ipn("1234567890", full_masking_dict, counters)
        assert result != "1234567890"
        assert len(result) == 10
        assert result.isdigit()

    def test_preserves_first3_and_last(self, full_masking_dict, counters):
        original = "1234567890"
        result = mask_ipn(original, full_masking_dict, counters)
        assert result[:3] == "123"
        assert result[-1] == "0"

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_ipn("1234567890", full_masking_dict, counters)
        r2 = mask_ipn("1234567890", full_masking_dict, counters)
        assert r1 == r2

    def test_invalid_length_returns_original(self, full_masking_dict, counters):
        assert mask_ipn("12345", full_masking_dict, counters) == "12345"

    def test_non_digit_returns_original(self, full_masking_dict, counters):
        assert mask_ipn("12345abcde", full_masking_dict, counters) == "12345abcde"

    def test_mapping_added(self, full_masking_dict, counters):
        mask_ipn("1234567890", full_masking_dict, counters)
        assert "1234567890" in full_masking_dict["mappings"]["ipn"]
        entry = full_masking_dict["mappings"]["ipn"]["1234567890"]
        assert "masked_as" in entry
        assert "instances" in entry

    def test_instance_tracking(self, full_masking_dict, counters):
        mask_ipn("1234567890", full_masking_dict, counters)
        mask_ipn("1234567890", full_masking_dict, counters)
        instances = full_masking_dict["mappings"]["ipn"]["1234567890"]["instances"]
        assert len(instances) == 2


# ============================================================================
# mask_passport_id
# ============================================================================

class TestMaskPassportId:
    """Tests for mask_passport_id() — 9-digit passport ID masking."""

    def test_basic_masking(self, full_masking_dict, counters):
        result = mask_passport_id("123456789", full_masking_dict, counters)
        assert result != "123456789"
        assert len(result) == 9
        assert result.isdigit()

    def test_preserves_first3_and_last(self, full_masking_dict, counters):
        result = mask_passport_id("123456789", full_masking_dict, counters)
        assert result[:3] == "123"
        assert result[-1] == "9"

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_passport_id("123456789", full_masking_dict, counters)
        r2 = mask_passport_id("123456789", full_masking_dict, counters)
        assert r1 == r2

    def test_invalid_length_returns_original(self, full_masking_dict, counters):
        assert mask_passport_id("12345", full_masking_dict, counters) == "12345"

    def test_non_digit_returns_original(self, full_masking_dict, counters):
        assert mask_passport_id("12345abcd", full_masking_dict, counters) == "12345abcd"

    def test_mapping_added(self, full_masking_dict, counters):
        mask_passport_id("123456789", full_masking_dict, counters)
        assert "123456789" in full_masking_dict["mappings"]["passport_id"]


# ============================================================================
# mask_military_id
# ============================================================================

class TestMaskMilitaryId:
    """Tests for mask_military_id() — military ID masking in various formats."""

    def test_six_digits(self, full_masking_dict, counters):
        result = mask_military_id("123456", full_masking_dict, counters)
        assert len(result) == 6
        assert result.isdigit()
        # Preserves first 2 and last 2 digits
        assert result[:2] == "12"
        assert result[-2:] == "56"

    def test_prefix_with_space(self, full_masking_dict, counters):
        result = mask_military_id("АБ 123456", full_masking_dict, counters)
        assert result.startswith("АБ ")
        digits = result.split(" ")[1]
        assert len(digits) == 6
        assert digits[:2] == "12"
        assert digits[-2:] == "56"

    def test_prefix_with_dash(self, full_masking_dict, counters):
        result = mask_military_id("АБ-123456", full_masking_dict, counters)
        assert "АБ-" in result
        digits = result.split("-")[1]
        assert len(digits) == 6

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_military_id("123456", full_masking_dict, counters)
        r2 = mask_military_id("123456", full_masking_dict, counters)
        assert r1 == r2

    def test_invalid_returns_original(self, full_masking_dict, counters):
        assert mask_military_id("abc", full_masking_dict, counters) == "abc"

    def test_mapping_added(self, full_masking_dict, counters):
        mask_military_id("123456", full_masking_dict, counters)
        assert "123456" in full_masking_dict["mappings"]["military_id"]


# ============================================================================
# mask_military_unit
# ============================================================================

class TestMaskMilitaryUnit:
    """Tests for mask_military_unit() — military unit designation masking."""

    def test_basic_masking(self, full_masking_dict, counters):
        result = mask_military_unit("А1234", full_masking_dict, counters)
        assert result != "А1234"
        assert result[0] == "А"
        assert len(result) == 5

    def test_preserves_letter(self, full_masking_dict, counters):
        result = mask_military_unit("В9876", full_masking_dict, counters)
        assert result[0] == "В"
        assert result[1:].isdigit()

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_military_unit("А1234", full_masking_dict, counters)
        r2 = mask_military_unit("А1234", full_masking_dict, counters)
        assert r1 == r2

    def test_invalid_returns_original(self, full_masking_dict, counters):
        assert mask_military_unit("12345", full_masking_dict, counters) == "12345"
        assert mask_military_unit("АБ1234", full_masking_dict, counters) == "АБ1234"

    def test_mapping_added(self, full_masking_dict, counters):
        mask_military_unit("А1234", full_masking_dict, counters)
        assert "А1234" in full_masking_dict["mappings"]["military_unit"]


# ============================================================================
# mask_order_number
# ============================================================================

class TestMaskOrderNumber:
    """Tests for mask_order_number() — order number masking."""

    def test_basic_with_space(self, full_masking_dict, counters):
        result = mask_order_number("№ 123", full_masking_dict, counters)
        assert result.startswith("№ ")
        assert result != "№ 123"

    def test_preserves_structure_with_slash(self, full_masking_dict, counters):
        result = mask_order_number("№456/2024", full_masking_dict, counters)
        assert result.startswith("№")
        assert "/" in result

    def test_only_digits_change(self, full_masking_dict, counters):
        result = mask_order_number("№ 123", full_masking_dict, counters)
        # Non-digit characters preserved
        assert result[0] == "№"
        assert result[1] == " "

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_order_number("№ 123", full_masking_dict, counters)
        r2 = mask_order_number("№ 123", full_masking_dict, counters)
        assert r1 == r2

    def test_mapping_added(self, full_masking_dict, counters):
        mask_order_number("№ 123", full_masking_dict, counters)
        assert "№ 123" in full_masking_dict["mappings"]["order_number"]


# ============================================================================
# mask_br_number
# ============================================================================

class TestMaskBrNumber:
    """Tests for mask_br_number() — BR number masking with prefix/suffix handling."""

    def test_with_prefix_and_suffix(self, full_masking_dict, counters):
        result = mask_br_number("№123дск", full_masking_dict, counters)
        assert result.startswith("№")
        assert result.endswith("дск")
        assert result != "№123дск"

    def test_with_slash(self, full_masking_dict, counters):
        result = mask_br_number("№456/789п", full_masking_dict, counters)
        assert result.startswith("№")
        assert "/" in result
        assert result.endswith("п")

    def test_simple_number(self, full_masking_dict, counters):
        result = mask_br_number("№1234", full_masking_dict, counters)
        assert result.startswith("№")
        # Digits should be replaced
        assert re.match(r'^№\d+', result)

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_br_number("№123дск", full_masking_dict, counters)
        r2 = mask_br_number("№123дск", full_masking_dict, counters)
        assert r1 == r2

    def test_mapping_added(self, full_masking_dict, counters):
        mask_br_number("№123дск", full_masking_dict, counters)
        assert "№123дск" in full_masking_dict["mappings"]["br_number"]


# ============================================================================
# mask_brigade_number
# ============================================================================

class TestMaskBrigadeNumber:
    """Tests for mask_brigade_number() — brigade number masking."""

    def test_basic_masking(self, full_masking_dict, counters):
        result = mask_brigade_number("14 механізована бригада", full_masking_dict, counters)
        assert "механізована бригада" in result
        # Number should change
        num = result.split(" ")[0]
        assert num.isdigit()

    def test_preserves_name(self, full_masking_dict, counters):
        result = mask_brigade_number("92 окрема бригада", full_masking_dict, counters)
        assert "окрема бригада" in result

    def test_number_in_range(self, full_masking_dict, counters):
        result = mask_brigade_number("14 механізована бригада", full_masking_dict, counters)
        num = int(result.split(" ")[0])
        assert 1 <= num <= 160

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_brigade_number("14 механізована бригада", full_masking_dict, counters)
        r2 = mask_brigade_number("14 механізована бригада", full_masking_dict, counters)
        assert r1 == r2

    def test_invalid_returns_original(self, full_masking_dict, counters):
        assert mask_brigade_number("no-number-here", full_masking_dict, counters) == "no-number-here"

    def test_mapping_added(self, full_masking_dict, counters):
        mask_brigade_number("14 механізована бригада", full_masking_dict, counters)
        assert "14 механізована бригада" in full_masking_dict["mappings"]["brigade_number"]


# ============================================================================
# mask_date
# ============================================================================

class TestMaskDate:
    """Tests for mask_date() — date masking with ±30 day shift."""

    def test_basic_masking(self, full_masking_dict, counters):
        result = mask_date("15.03.2024", full_masking_dict, counters)
        assert result != "15.03.2024"
        assert re.match(r'^\d{2}\.\d{2}\.\d{4}$', result)

    def test_format_preserved(self, full_masking_dict, counters):
        result = mask_date("01.01.2020", full_masking_dict, counters)
        parts = result.split(".")
        assert len(parts) == 3
        assert len(parts[0]) == 2
        assert len(parts[1]) == 2
        assert len(parts[2]) == 4

    def test_year_in_range(self, full_masking_dict, counters):
        result = mask_date("15.06.2024", full_masking_dict, counters)
        year = int(result.split(".")[2])
        assert 2015 <= year <= 2035

    def test_deterministic(self, full_masking_dict, counters):
        r1 = mask_date("15.03.2024", full_masking_dict, counters)
        r2 = mask_date("15.03.2024", full_masking_dict, counters)
        assert r1 == r2

    def test_invalid_date_returns_original(self, full_masking_dict, counters):
        # Feb 31 is invalid
        assert mask_date("31.02.2024", full_masking_dict, counters) == "31.02.2024"

    def test_out_of_range_year_returns_original(self, full_masking_dict, counters):
        assert mask_date("15.03.1990", full_masking_dict, counters) == "15.03.1990"
        assert mask_date("15.03.2050", full_masking_dict, counters) == "15.03.2050"

    def test_non_date_returns_original(self, full_masking_dict, counters):
        assert mask_date("not-a-date", full_masking_dict, counters) == "not-a-date"

    def test_mapping_added(self, full_masking_dict, counters):
        mask_date("15.03.2024", full_masking_dict, counters)
        assert "15.03.2024" in full_masking_dict["mappings"]["date"]


# ============================================================================
# normalize_broken_ranks
# ============================================================================

class TestNormalizeBrokenRanks:
    """Tests for normalize_broken_ranks() — fixing line-broken ranks."""

    def test_broken_two_word_rank(self):
        # Multi-word rank split by newline should be joined
        text = "старшого\nсержанта"
        result = normalize_broken_ranks(text)
        assert "\n" not in result or "старшого сержанта" in result

    def test_single_word_unchanged(self):
        text = "капітан отримує відпустку"
        result = normalize_broken_ranks(text)
        assert result == text

    def test_no_ranks_unchanged(self):
        text = "звичайний текст без звань"
        result = normalize_broken_ranks(text)
        assert result == text

    def test_empty_string(self):
        assert normalize_broken_ranks("") == ""

    def test_preserves_other_newlines(self):
        text = "перший рядок\nдругий рядок"
        result = normalize_broken_ranks(text)
        # Should preserve newlines that are NOT between rank parts
        assert "\n" in result


# ============================================================================
# detect_gender_by_patronymic
# ============================================================================

class TestDetectGender:
    """Tests for detect_gender_by_patronymic() — gender detection from patronymic."""

    @pytest.mark.parametrize("patronymic", [
        "Миколайович",
        "Петрович",
        "Іванович",
        "Олександрович",
        "Сергійович",
    ])
    def test_male_patronymics(self, patronymic):
        assert detect_gender_by_patronymic(patronymic) == "male"

    @pytest.mark.parametrize("patronymic", [
        "Миколаївна",
        "Петрівна",
        "Іванівна",
        "Олександрівна",
        "Сергіївна",
    ])
    def test_female_patronymics(self, patronymic):
        assert detect_gender_by_patronymic(patronymic) == "female"

    def test_empty_returns_unknown(self):
        assert detect_gender_by_patronymic("") == "unknown"

    def test_none_returns_unknown(self):
        assert detect_gender_by_patronymic(None) == "unknown"

    def test_unrecognized_returns_unknown(self):
        assert detect_gender_by_patronymic("Тест") == "unknown"

    @pytest.mark.parametrize("patronymic", [
        "Миколайовича",  # genitive male
        "Петровичу",     # dative male
        "Іванівни",      # genitive female
        "Петрівною",     # instrumental female
    ])
    def test_declined_forms(self, patronymic):
        result = detect_gender_by_patronymic(patronymic)
        assert result in ("male", "female")

    def test_with_trailing_punctuation(self):
        assert detect_gender_by_patronymic("Миколайович.") == "male"
        assert detect_gender_by_patronymic("Іванівна,") == "female"
