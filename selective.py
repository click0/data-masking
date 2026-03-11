#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Selective masking module for data_masking.py v2.2.15

Provides --only / --exclude support: mask only selected data types.

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025
"""

from typing import Set, Optional

# All available masking types
AVAILABLE_TYPES: Set[str] = {
    "rank",
    "name",
    "surname",
    "patronymic",
    "ipn",
    "passport",
    "military_id",
    "date",
    "military_unit",
    "order_number",
    "br_number",
    "brigade_number",
}


def get_available_types() -> Set[str]:
    """Return the set of all available masking types."""
    return AVAILABLE_TYPES.copy()


def validate_types(types: Set[str]) -> Set[str]:
    """Validate that all requested types are available.

    Args:
        types: Set of type names to validate

    Returns:
        Set of valid types

    Raises:
        ValueError: If any type is not available
    """
    invalid = types - AVAILABLE_TYPES
    if invalid:
        raise ValueError(
            f"Unknown masking types: {invalid}. "
            f"Available: {sorted(AVAILABLE_TYPES)}"
        )
    return types


def apply_only_filter(only_types: Optional[Set[str]] = None,
                      exclude_types: Optional[Set[str]] = None) -> Set[str]:
    """Compute the effective set of types to mask.

    Args:
        only_types: If set, mask ONLY these types
        exclude_types: If set, mask everything EXCEPT these types

    Returns:
        Set of types that should be masked
    """
    if only_types and exclude_types:
        raise ValueError("Cannot use both --only and --exclude")

    if only_types:
        return validate_types(only_types)
    elif exclude_types:
        validate_types(exclude_types)
        return AVAILABLE_TYPES - exclude_types
    else:
        return AVAILABLE_TYPES.copy()
