# -*- coding: utf-8 -*-
"""
End-to-end integration tests for the masking/unmasking pipeline.
Tests mask_text_context_aware, mask_text_wrapper, and round-trip mask→unmask.
"""
import pytest

from data_masking import mask_text_context_aware, mask_text_wrapper
from unmask_data import unmask_text_v2


def _make_full_masking_dict():
    """Create a masking dict with all required category keys."""
    return {
        "version": "v2.0",
        "timestamp": "2025-11-19T00:00:00",
        "statistics": {},
        "mappings": {k: {} for k in [
            "ipn", "passport_id", "military_id", "surname", "name",
            "military_unit", "order_number", "order_number_with_letters",
            "br_number", "br_number_slash", "br_number_complex",
            "rank", "brigade_number", "date", "patronymic",
        ]},
        "instance_tracking": {},
    }


@pytest.mark.integration
class TestMaskTextContextAware:
    """Tests for the main entry point mask_text_context_aware()."""

    def test_masks_pib_with_rank(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        text = "капітан Іванов Петро Миколайович отримує премію"
        result = mask_text_context_aware(text, masking_dict, counters)
        # Original PIB should be replaced
        assert "Іванов" not in result or "Петро" not in result

    def test_masks_ipn(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        text = "ІПН військовослужбовця 1234567890 зареєстровано"
        result = mask_text_context_aware(text, masking_dict, counters)
        assert "1234567890" not in result

    def test_masks_date(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        text = "Наказ від 15.03.2024 року"
        result = mask_text_context_aware(text, masking_dict, counters)
        assert "15.03.2024" not in result

    def test_preserves_text_structure(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        text = "Рядок 1\nРядок 2\nРядок 3"
        result = mask_text_context_aware(text, masking_dict, counters)
        # Should preserve line count
        assert result.count("\n") == text.count("\n")

    def test_empty_text(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        result = mask_text_context_aware("", masking_dict, counters)
        assert result == ""

    def test_text_without_sensitive_data(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        text = "Звичайний текст без конфіденційних даних."
        result = mask_text_context_aware(text, masking_dict, counters)
        assert result == text

    def test_mapping_populated(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        text = "ІПН 1234567890 дата 15.03.2024"
        mask_text_context_aware(text, masking_dict, counters)
        # At least one mapping category should have entries
        has_entries = any(
            len(v) > 0 for v in masking_dict["mappings"].values()
        )
        assert has_entries


@pytest.mark.integration
class TestMaskTextWrapper:
    """Tests for mask_text_wrapper() — thin wrapper around mask_text_context_aware."""

    def test_wrapper_produces_same_result(self):
        masking_dict1 = _make_full_masking_dict()
        masking_dict2 = _make_full_masking_dict()
        counters1 = {}
        counters2 = {}
        text = "капітан Іванов Петро Миколайович 1234567890"
        r1 = mask_text_context_aware(text, masking_dict1, counters1)
        r2 = mask_text_wrapper(text, masking_dict2, counters2)
        assert r1 == r2


@pytest.mark.integration
class TestRoundTrip:
    """End-to-end: mask text then unmask and verify recovery."""

    def test_roundtrip_ipn(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        original = "ІПН військовослужбовця 1234567890 зареєстровано"
        masked = mask_text_context_aware(original, masking_dict, counters)
        assert "1234567890" not in masked

        # Unmask
        recovered, stats = unmask_text_v2(masked, masking_dict, "v2.0")
        assert "1234567890" in recovered

    def test_roundtrip_date(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        original = "Наказ від 15.03.2024 року"
        masked = mask_text_context_aware(original, masking_dict, counters)

        recovered, stats = unmask_text_v2(masked, masking_dict, "v2.0")
        assert "15.03.2024" in recovered

    def test_roundtrip_preserves_unmasked_text(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        original = "Звичайний текст залишається без змін."
        masked = mask_text_context_aware(original, masking_dict, counters)
        recovered, stats = unmask_text_v2(masked, masking_dict, "v2.0")
        assert recovered == original

    def test_roundtrip_complex_document(self):
        masking_dict = _make_full_masking_dict()
        counters = {}
        original = (
            "НАКАЗ\n"
            "від 15.03.2024\n"
            "капітан Іванов Петро Миколайович\n"
            "ІПН 1234567890\n"
        )
        masked = mask_text_context_aware(original, masking_dict, counters)
        # Verify something was actually masked
        assert masked != original

        recovered, stats = unmask_text_v2(masked, masking_dict, "v2.0")
        # Key data should be recovered
        assert "1234567890" in recovered
        assert "15.03.2024" in recovered
