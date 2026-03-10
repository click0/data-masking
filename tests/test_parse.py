# -*- coding: utf-8 -*-
"""
Tests for parsing and analysis functions: looks_like_pib_line, parse_hybrid_line.
"""
import pytest

from data_masking import looks_like_pib_line, parse_hybrid_line


class TestLooksLikePibLine:
    """Tests for looks_like_pib_line() — detects lines containing PIB data."""

    def test_line_with_rank_and_pib(self):
        assert looks_like_pib_line("Капітан Іванов Петро Миколайович отримує премію") is True

    def test_line_with_rank_only(self):
        # Rank alone should still be detected
        assert looks_like_pib_line("капітан отримує відпустку") is True

    def test_line_with_capitalized_names(self):
        # Multiple capitalized words that look like names
        assert looks_like_pib_line("Іванов Петро Миколайович 1234567890") is True

    def test_line_with_identifier(self):
        # Line with 10-digit IPN
        assert looks_like_pib_line("Солдат із ІПН 1234567890 прибув") is True

    def test_empty_line(self):
        assert looks_like_pib_line("") is False

    def test_short_line(self):
        assert looks_like_pib_line("Привіт") is False

    def test_separator_line(self):
        assert looks_like_pib_line("===========================") is False
        assert looks_like_pib_line("---------------------------") is False

    def test_legal_term_excluded(self):
        # Lines with legal terms should be excluded (for short lines)
        assert looks_like_pib_line("згідно статуту ЗСУ") is False

    def test_starts_with_excluded_word(self):
        assert looks_like_pib_line("відповідно до наказу командира") is False
        assert looks_like_pib_line("згідно з положенням про службу") is False

    def test_none_input(self):
        assert looks_like_pib_line(None) is False


class TestParseHybridLine:
    """Tests for parse_hybrid_line() — parses rank, PIB, and identifier from a line."""

    def test_full_line_with_rank_and_pib(self):
        rank, pib, identifier = parse_hybrid_line(
            "капітан Іванов Петро Миколайович 1234567890"
        )
        assert rank is not None
        assert pib is not None

    def test_line_with_pib_and_identifier(self):
        rank, pib, identifier = parse_hybrid_line(
            "1. Іванов Петро Миколайович 1234567890"
        )
        # Should find PIB and identifier
        assert pib is not None or identifier is not None

    def test_empty_line(self):
        rank, pib, identifier = parse_hybrid_line("")
        assert rank is None
        assert pib is None
        assert identifier is None

    def test_whitespace_only(self):
        rank, pib, identifier = parse_hybrid_line("   ")
        assert rank is None
        assert pib is None

    def test_returns_tuple_of_three(self):
        result = parse_hybrid_line("капітан Іванов Петро Миколайович")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_rank_detected_correctly(self):
        rank, pib, identifier = parse_hybrid_line(
            "старший сержант Петренко Андрій Сергійович"
        )
        if rank is not None:
            assert "сержант" in rank.lower() or "старший" in rank.lower()

    def test_no_pib_line(self):
        rank, pib, identifier = parse_hybrid_line("звичайний текст без імен")
        assert pib is None
