#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tools API module for data_masking.py v2.2.15

Provides direct masking functions for programmatic use (without CLI).

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025
"""

from typing import Dict
from data_masking import (
    mask_ipn, mask_rank, mask_surname, mask_name, mask_patronymic
)


def _ensure_category(masking_dict: Dict, category: str) -> None:
    """Ensure a category exists in the mappings dict."""
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if category not in masking_dict["mappings"]:
        masking_dict["mappings"][category] = {}
    if "statistics" not in masking_dict:
        masking_dict["statistics"] = {}
    if "instance_tracking" not in masking_dict:
        masking_dict["instance_tracking"] = {}


def mask_ipn_direct(ipn: str, masking_dict: Dict,
                    instance_counters: Dict) -> str:
    """Mask an IPN (Individual Tax Number) directly.

    Args:
        ipn: 10-digit IPN string
        masking_dict: Mapping dictionary (will be updated)
        instance_counters: Instance tracking counters

    Returns:
        Masked IPN string
    """
    _ensure_category(masking_dict, "ipn")
    return mask_ipn(ipn, masking_dict, instance_counters)


def mask_rank_direct(rank: str, masking_dict: Dict,
                     instance_counters: Dict) -> str:
    """Mask a military rank directly.

    Args:
        rank: Rank string (e.g., "старший сержант")
        masking_dict: Mapping dictionary (will be updated)
        instance_counters: Instance tracking counters

    Returns:
        Masked rank string
    """
    _ensure_category(masking_dict, "rank")
    return mask_rank(rank, masking_dict, instance_counters)


def mask_pib_force(pib: str, masking_dict: Dict,
                   instance_counters: Dict) -> str:
    """Mask a full PIB (Прізвище Ім'я По батькові) directly.

    Args:
        pib: Full name string "Surname Name Patronymic"
        masking_dict: Mapping dictionary (will be updated)
        instance_counters: Instance tracking counters

    Returns:
        Masked PIB string
    """
    parts = pib.split()
    if len(parts) != 3:
        return pib

    surname, name, patronymic = parts

    _ensure_category(masking_dict, "surname")
    _ensure_category(masking_dict, "name")
    _ensure_category(masking_dict, "patronymic")

    # Detect gender from patronymic
    patronymic_lower = patronymic.lower()
    if patronymic_lower.endswith("ович") or patronymic_lower.endswith("йович"):
        gender = "male"
    elif patronymic_lower.endswith("івна") or patronymic_lower.endswith("ївна"):
        gender = "female"
    else:
        gender = "unknown"

    masked_surname = mask_surname(surname, masking_dict, instance_counters)
    masked_name = mask_name(name, masking_dict, instance_counters,
                            gender_hint=gender, patronymic_hint=patronymic)
    masked_patronymic = mask_patronymic(patronymic, gender, masking_dict,
                                        instance_counters)

    return f"{masked_surname} {masked_name} {masked_patronymic}"
