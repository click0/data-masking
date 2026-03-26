#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Tests for modules/selective.py"""

import pytest

from modules.selective import (
    AVAILABLE_TYPES,
    TYPE_ALIASES,
    TYPE_GROUPS,
    SelectiveFilter,
    get_available_types,
    parse_type_list,
    apply_filter_to_globals,
)


class TestAvailableTypes:
    """Tests for available type definitions."""

    def test_available_types_not_empty(self):
        assert len(AVAILABLE_TYPES) > 0

    def test_core_types_present(self):
        for t in ("ipn", "passport", "surname", "rank", "date"):
            assert t in AVAILABLE_TYPES

    def test_get_available_types(self):
        result = get_available_types()
        assert isinstance(result, (set, list))
        assert len(result) == len(AVAILABLE_TYPES)


class TestTypeAliases:
    """Tests for type alias resolution."""

    def test_plural_aliases(self):
        assert TYPE_ALIASES["ipns"] == "ipn"
        assert TYPE_ALIASES["passports"] == "passport"
        assert TYPE_ALIASES["ranks"] == "rank"
        assert TYPE_ALIASES["dates"] == "date"

    def test_ukrainian_aliases(self):
        assert TYPE_ALIASES["іпн"] == "ipn"
        assert TYPE_ALIASES["паспорт"] == "passport"
        assert TYPE_ALIASES["звання"] == "rank"
        assert TYPE_ALIASES["дата"] == "date"

    def test_shortcut_aliases(self):
        assert TYPE_ALIASES["unit"] == "military_unit"
        assert TYPE_ALIASES["order"] == "order_number"
        assert TYPE_ALIASES["mid"] == "military_id"

    def test_all_aliases_resolve_to_available_types(self):
        for alias, canonical in TYPE_ALIASES.items():
            assert canonical in AVAILABLE_TYPES, (
                f"Alias '{alias}' resolves to '{canonical}' "
                f"which is not in AVAILABLE_TYPES"
            )


class TestTypeGroups:
    """Tests for type group definitions."""

    def test_personal_group(self):
        assert "surname" in TYPE_GROUPS["personal"]
        assert "name" in TYPE_GROUPS["personal"]
        assert "patronymic" in TYPE_GROUPS["personal"]

    def test_ids_group(self):
        assert "ipn" in TYPE_GROUPS["ids"]
        assert "passport" in TYPE_GROUPS["ids"]

    def test_all_group_matches_available(self):
        assert TYPE_GROUPS["all"] == AVAILABLE_TYPES


class TestSelectiveFilter:
    """Tests for SelectiveFilter dataclass."""

    def test_default_enables_all(self):
        sf = SelectiveFilter()
        assert sf.enabled_types == AVAILABLE_TYPES

    def test_only_filter(self):
        sf = SelectiveFilter(only_types={"ipn", "passport"})
        assert sf.is_enabled("ipn")
        assert sf.is_enabled("passport")
        assert not sf.is_enabled("rank")
        assert not sf.is_enabled("date")

    def test_exclude_filter(self):
        sf = SelectiveFilter(exclude_types={"date", "rank"})
        assert not sf.is_enabled("date")
        assert not sf.is_enabled("rank")
        assert sf.is_enabled("ipn")
        assert sf.is_enabled("surname")

    def test_both_only_and_exclude_raises(self):
        with pytest.raises(ValueError, match="Cannot use both"):
            SelectiveFilter(only_types={"ipn"}, exclude_types={"date"})

    def test_unknown_type_in_only_raises(self):
        with pytest.raises(ValueError, match="Unknown masking type"):
            SelectiveFilter(only_types={"nonexistent_type"})

    def test_unknown_type_in_exclude_raises(self):
        with pytest.raises(ValueError, match="Unknown masking type"):
            SelectiveFilter(exclude_types={"nonexistent_type"})

    def test_get_enabled_list(self):
        sf = SelectiveFilter(only_types={"ipn", "date"})
        enabled = sf.get_enabled_list()
        assert sorted(enabled) == ["date", "ipn"]

    def test_get_disabled_list(self):
        sf = SelectiveFilter(only_types={"ipn"})
        disabled = sf.get_disabled_list()
        assert "ipn" not in disabled
        assert len(disabled) == len(AVAILABLE_TYPES) - 1

    def test_to_dict(self):
        sf = SelectiveFilter(only_types={"ipn", "rank"})
        d = sf.to_dict()
        assert "enabled_types" in d
        assert "disabled_types" in d
        assert "only_types" in d

    def test_from_dict_roundtrip(self):
        sf = SelectiveFilter(only_types={"ipn", "passport"})
        d = sf.to_dict()
        sf2 = SelectiveFilter.from_dict(d)
        assert sf.enabled_types == sf2.enabled_types

    def test_exclude_roundtrip(self):
        sf = SelectiveFilter(exclude_types={"date"})
        d = sf.to_dict()
        sf2 = SelectiveFilter.from_dict(d)
        assert sf.enabled_types == sf2.enabled_types

    def test_empty_only_set(self):
        """Empty only_types is treated as no filter (falsy empty set)."""
        sf = SelectiveFilter(only_types=set())
        # Empty set is falsy, so _compute_enabled returns all types
        assert sf.enabled_types == AVAILABLE_TYPES

    def test_single_type_only(self):
        sf = SelectiveFilter(only_types={"surname"})
        assert sf.is_enabled("surname")
        assert len(sf.get_enabled_list()) == 1


class TestParseTypeList:
    """Tests for parse_type_list() function."""

    def test_comma_separated(self):
        result = parse_type_list("ipn,passport,rank")
        assert result == {"ipn", "passport", "rank"}

    def test_with_spaces(self):
        result = parse_type_list("ipn, passport, rank")
        assert result == {"ipn", "passport", "rank"}

    def test_alias_resolution(self):
        result = parse_type_list("ipns,ranks,dates")
        assert result == {"ipn", "rank", "date"}

    def test_single_type(self):
        result = parse_type_list("ipn")
        assert result == {"ipn"}

    def test_group_expansion(self):
        result = parse_type_list("personal")
        assert "surname" in result
        assert "name" in result
        assert "patronymic" in result
