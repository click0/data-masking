#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Selective Masking Module v2.4.0

Provides --only / --exclude support: mask only selected data types.
Supports type aliases (plural forms, Ukrainian names), type groups,
and integration with MASK_* globals in data_masking.py.

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025-2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

__version__ = "2.4.0"

# ============================================================================
# AVAILABLE TYPES
# ============================================================================

AVAILABLE_TYPES: Set[str] = {
    "ipn",
    "passport",
    "military_id",
    "surname",
    "name",
    "patronymic",
    "rank",
    "military_unit",
    "order_number",
    "br_number",
    "brigade",
    "date",
}

# ============================================================================
# TYPE ALIASES — plural forms, Ukrainian names, shortcuts
# ============================================================================

TYPE_ALIASES: Dict[str, str] = {
    # Plural forms
    "ipns": "ipn",
    "passports": "passport",
    "military_ids": "military_id",
    "surnames": "surname",
    "names": "name",
    "patronymics": "patronymic",
    "ranks": "rank",
    "military_units": "military_unit",
    "order_numbers": "order_number",
    "br_numbers": "br_number",
    "brigades": "brigade",
    "dates": "date",
    # Ukrainian forms
    "іпн": "ipn",
    "паспорт": "passport",
    "паспорти": "passport",
    "військовий_квиток": "military_id",
    "прізвище": "surname",
    "прізвища": "surname",
    "імя": "name",
    "імена": "name",
    "по_батькові": "patronymic",
    "звання": "rank",
    "військова_частина": "military_unit",
    "частина": "military_unit",
    "частини": "military_unit",
    "номер_наказу": "order_number",
    "накази": "order_number",
    "бр_номер": "br_number",
    "бригада": "brigade",
    "бригади": "brigade",
    "дата": "date",
    "дати": "date",
    # Shortcuts
    "unit": "military_unit",
    "units": "military_unit",
    "order": "order_number",
    "orders": "order_number",
    "mid": "military_id",
    "pat": "patronymic",
    "brn": "br_number",
    "brig": "brigade",
    "brigade_number": "brigade",
}

# ============================================================================
# TYPE GROUPS
# ============================================================================
TYPE_GROUPS: Dict[str, Set[str]] = {
    "personal": {"surname", "name", "patronymic"},
    "ids": {"ipn", "passport", "military_id"},
    "military": {"rank", "military_unit", "brigade"},
    "documents": {"order_number", "br_number"},
    "all": set(AVAILABLE_TYPES),
}

# ============================================================================
# MAPPING: type name -> MASK_* global variable name
# ============================================================================
_TYPE_TO_GLOBAL: Dict[str, str] = {
    "ipn": "MASK_IPN",
    "passport": "MASK_PASSPORT",
    "military_id": "MASK_MILITARY_ID",
    "surname": "MASK_NAMES",
    "name": "MASK_NAMES",
    "patronymic": "MASK_NAMES",
    "rank": "MASK_RANKS",
    "military_unit": "MASK_UNITS",
    "order_number": "MASK_ORDERS",
    "br_number": "MASK_BR_NUMBERS",
    "brigade": "MASK_BRIGADES",
    "date": "MASK_DATES",
}


# ============================================================================
# SELECTIVE FILTER DATACLASS
# ============================================================================
@dataclass
class SelectiveFilter:
    """Filter that determines which masking types are enabled.

    Provide either ``only_types`` (whitelist) or ``exclude_types``
    (blacklist), but not both.  If neither is given every type is enabled.
    """
    only_types: Optional[Set[str]] = field(default=None)
    exclude_types: Optional[Set[str]] = field(default=None)
    enabled_types: Set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        self._validate()
        self.enabled_types = self._compute_enabled()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _validate(self) -> None:
        """Validate filter configuration.

        Raises:
            ValueError: If both only_types and exclude_types are set,
                        or if any type name is unknown.
        """
        if self.only_types and self.exclude_types:
            raise ValueError(
                "Cannot use both --only and --exclude at the same time."
            )
        for label, types in (
            ("only", self.only_types),
            ("exclude", self.exclude_types),
        ):
            if types is None:
                continue
            unknown = types - AVAILABLE_TYPES
            if unknown:
                raise ValueError(
                    f"Unknown masking type(s) in --{label}: "
                    f"{sorted(unknown)}. "
                    f"Available: {sorted(AVAILABLE_TYPES)}"
                )

    def _compute_enabled(self) -> Set[str]:
        """Return the effective set of enabled types."""
        if self.only_types:
            return set(self.only_types)
        if self.exclude_types:
            return AVAILABLE_TYPES - self.exclude_types
        return set(AVAILABLE_TYPES)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_enabled(self, type_name: str) -> bool:
        """Check whether a given masking type is currently enabled.

        Args:
            type_name: Canonical type name.

        Returns:
            ``True`` when the type should be masked.
        """
        return type_name in self.enabled_types

    def get_enabled_list(self) -> List[str]:
        """Return a sorted list of enabled type names."""
        return sorted(self.enabled_types)

    def get_disabled_list(self) -> List[str]:
        """Return a sorted list of disabled type names."""
        return sorted(AVAILABLE_TYPES - self.enabled_types)

    def to_dict(self) -> Dict:
        """Serialize filter state to a plain dictionary."""
        data: Dict = {
            "version": __version__,
            "enabled_types": sorted(self.enabled_types),
            "disabled_types": self.get_disabled_list(),
        }
        if self.only_types:
            data["only_types"] = sorted(self.only_types)
        if self.exclude_types:
            data["exclude_types"] = sorted(self.exclude_types)
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> "SelectiveFilter":
        """Restore a :class:`SelectiveFilter` from a dictionary.

        Args:
            data: Dictionary previously produced by :meth:`to_dict`.

        Returns:
            A new :class:`SelectiveFilter` instance.
        """
        only = set(data["only_types"]) if "only_types" in data else None
        exclude = set(data["exclude_types"]) if "exclude_types" in data else None
        return cls(only_types=only, exclude_types=exclude)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def normalize_type(name: str) -> str:
    """Resolve a type alias to its canonical name.

    Args:
        name: Raw type name (may be an alias, plural, or Ukrainian form).

    Returns:
        The canonical type name.

    Raises:
        ValueError: If the name cannot be resolved.
    """
    lower = name.strip().lower()
    if lower in AVAILABLE_TYPES:
        return lower
    if lower in TYPE_ALIASES:
        return TYPE_ALIASES[lower]
    # Check groups
    if lower in TYPE_GROUPS:
        raise ValueError(
            f"'{name}' is a type group, not a single type. "
            f"Group members: {sorted(TYPE_GROUPS[lower])}"
        )
    raise ValueError(
        f"Unknown masking type: '{name}'. "
        f"Available: {sorted(AVAILABLE_TYPES)}. "
        f"Groups: {sorted(TYPE_GROUPS.keys())}"
    )


def parse_type_list(type_string: str) -> Set[str]:
    """Parse a comma-separated (or space-separated) type string.

    Group names are expanded automatically.

    Args:
        type_string: e.g. ``"ipn,passport,names"`` or ``"personal military"``

    Returns:
        Set of canonical type names.
    """
    if not type_string or not type_string.strip():
        return set()

    result: Set[str] = set()
    # Support both comma and space separation
    raw_items = type_string.replace(",", " ").split()

    for item in raw_items:
        lower = item.strip().lower()
        if not lower:
            continue
        # Expand groups
        if lower in TYPE_GROUPS:
            result.update(TYPE_GROUPS[lower])
        else:
            result.add(normalize_type(lower))

    return result


def create_filter(
    only: Optional[str] = None,
    exclude: Optional[str] = None,
) -> SelectiveFilter:
    """High-level factory: parse string arguments and build a filter.

    Args:
        only: Comma/space-separated list of types to include.
        exclude: Comma/space-separated list of types to exclude.

    Returns:
        Configured :class:`SelectiveFilter`.
    """
    only_set = parse_type_list(only) if only else None
    exclude_set = parse_type_list(exclude) if exclude else None
    return SelectiveFilter(only_types=only_set, exclude_types=exclude_set)


def apply_filter_to_globals(
    selective_filter: SelectiveFilter,
    globals_dict: Dict,
) -> None:
    """Apply the selective filter to MASK_* global variables.

    Sets each ``MASK_*`` flag in *globals_dict* to ``True`` or ``False``
    depending on whether its associated type(s) are enabled.

    Args:
        selective_filter: The filter to apply.
        globals_dict: The module globals dict (e.g. ``data_masking.__dict__``
                      or the result of ``globals()``).
    """
    # Collect which MASK_* keys should be True
    enabled_globals: Set[str] = set()
    for type_name in selective_filter.enabled_types:
        global_name = _TYPE_TO_GLOBAL.get(type_name)
        if global_name:
            enabled_globals.add(global_name)

    # Apply: set every known MASK_* global
    all_mask_globals: Set[str] = set(_TYPE_TO_GLOBAL.values())
    for gname in all_mask_globals:
        globals_dict[gname] = gname in enabled_globals


# ============================================================================
# HELP / INFO
# ============================================================================
def get_types_help() -> str:
    """Return a formatted help string describing all available types and groups.

    Returns:
        Multi-line string suitable for printing to the console.
    """
    lines: List[str] = []
    lines.append("Available masking types:")
    lines.append("")
    for t in sorted(AVAILABLE_TYPES):
        global_name = _TYPE_TO_GLOBAL.get(t, "—")
        lines.append(f"  {t:<20s} -> {global_name}")
    lines.append("")
    lines.append("Type groups (can be used with --only / --exclude):")
    lines.append("")
    for group_name in sorted(TYPE_GROUPS):
        members = ", ".join(sorted(TYPE_GROUPS[group_name]))
        lines.append(f"  {group_name:<20s} = {members}")
    lines.append("")
    lines.append("Aliases (plural / Ukrainian forms are accepted):")
    lines.append("")
    alias_by_target: Dict[str, List[str]] = {}
    for alias, target in sorted(TYPE_ALIASES.items()):
        alias_by_target.setdefault(target, []).append(alias)
    for target in sorted(alias_by_target):
        aliases = ", ".join(sorted(alias_by_target[target]))
        lines.append(f"  {target:<20s} <- {aliases}")
    return "\n".join(lines)


def get_available_types() -> Set[str]:
    """Return a copy of the set of all available masking types."""
    return set(AVAILABLE_TYPES)


def get_type_groups() -> Dict[str, Set[str]]:
    """Return a copy of the type groups dictionary."""
    return {k: set(v) for k, v in TYPE_GROUPS.items()}
