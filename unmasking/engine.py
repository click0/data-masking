#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Core unmasking logic: text and JSON restoration.

Extracted from unmask_data.py during v2.5.1 refactoring.
"""

import re
from typing import Any, Dict, List, Tuple

from rank_data import (
    RANK_DECLENSIONS,
    RANK_FEMININE_MAP,
    RANK_DECLENSIONS_FEMALE,
    RANK_TO_NOMINATIVE,
    ALL_RANK_FORMS
)

from unmasking.helpers import (
    get_rank_info, check_mapping_version,
    find_all_occurrences, build_instance_map,
    _apply_original_case, is_real_mask, extract_base_rank,
)


def unmask_ranks_gender_aware(masked_text: str, masking_map: Dict) -> Tuple[str, Dict]:
    """
    Відновлення звань з урахуванням гендеру та граматичних відмінків.
    """
    restored_text = masked_text
    stats = {"restored_count": 0, "skipped_count": 0}

    mappings = masking_map.get("mappings", {})
    temp_map_for_ranks = {"mappings": {"rank": mappings.get("rank", {})}}
    rank_instance_map = build_instance_map(temp_map_for_ranks)

    all_masked_ranks = set()
    for original, mask_info in mappings.get("rank", {}).items():
        if isinstance(mask_info, dict) and "masked_as" in mask_info:
            all_masked_ranks.add(mask_info["masked_as"].lower())

    # КРОК 1: ПОШУК ВСІХ ЗВАНЬ У ТЕКСТІ
    all_found_ranks = []
    for rank_form in ALL_RANK_FORMS:
        pattern = r'\b' + re.escape(rank_form) + r'\b'
        for match in re.finditer(pattern, restored_text, re.IGNORECASE):
            all_found_ranks.append({
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0)
            })

    # Fallback: звання-маски, які відсутні у словнику
    for masked_rank in all_masked_ranks:
        pattern = r'\b' + re.escape(masked_rank) + r'\b'
        for match in re.finditer(pattern, restored_text, re.IGNORECASE):
            overlaps = any(
                match.start() < found["end"] and match.end() > found["start"]
                for found in all_found_ranks
            )
            if not overlaps:
                all_found_ranks.append({
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "simple": True
                })

    all_found_ranks.sort(key=lambda x: x['start'])

    # КРОК 2: ОБРОБКА КОЖНОГО ЗНАЙДЕНОГО ЗВАННЯ
    replacements_to_do = []
    instance_counters = {}

    for found in all_found_ranks:
        # ЛОГІКА A: ПРОСТА ЗАМІНА
        if found.get("simple", False):
            full_rank_text = found["text"]
            base_rank, additional_words = extract_base_rank(full_rank_text)
            masked_rank_lower = base_rank.lower()

            instance_counters.setdefault(masked_rank_lower, 0)
            instance_counters[masked_rank_lower] += 1
            instance_num = instance_counters[masked_rank_lower]

            if masked_rank_lower in rank_instance_map and instance_num in rank_instance_map[masked_rank_lower]:
                original_rank = rank_instance_map[masked_rank_lower][instance_num]

                if not is_real_mask(masked_rank_lower, masking_map, all_masked_ranks):
                    stats["skipped_count"] += 1
                    continue

                original_rank = _apply_original_case(base_rank, original_rank)
                restored_full_rank = f"{original_rank} {additional_words}" if additional_words else original_rank

                replacements_to_do.append((found["start"], found["end"], restored_full_rank))
                stats["restored_count"] += 1
            else:
                stats["skipped_count"] += 1
            continue

        # ЛОГІКА B: РОЗУМНА ЗАМІНА (з відновленням відмінку та роду)
        full_rank_text = found["text"]
        base_rank_text, additional_words = extract_base_rank(full_rank_text)

        base_masked_form, case, gender = get_rank_info(base_rank_text)

        if not base_masked_form:
            continue

        instance_counters.setdefault(base_masked_form, 0)
        instance_counters[base_masked_form] += 1
        instance_num = instance_counters[base_masked_form]

        if base_masked_form in rank_instance_map and instance_num in rank_instance_map[base_masked_form]:
            original_base_form = rank_instance_map[base_masked_form][instance_num]

            if not is_real_mask(base_masked_form, masking_map, all_masked_ranks):
                stats["skipped_count"] += 1
                continue

            reconstructed_form = original_base_form

            if gender == 'female':
                if original_base_form in RANK_FEMININE_MAP:
                    base_female = RANK_FEMININE_MAP[original_base_form]
                    if base_female in RANK_DECLENSIONS_FEMALE:
                        reconstructed_form = RANK_DECLENSIONS_FEMALE[base_female].get(case, base_female)

            else:
                if original_base_form in RANK_DECLENSIONS:
                    reconstructed_form = RANK_DECLENSIONS[original_base_form].get(case, original_base_form)

            reconstructed_form = _apply_original_case(base_rank_text, reconstructed_form)
            restored_full_rank = f"{reconstructed_form} {additional_words}" if additional_words else reconstructed_form

            replacements_to_do.append((found["start"], found["end"], restored_full_rank))
            stats["restored_count"] += 1
        else:
            stats["skipped_count"] += 1

    # КРОК 3: ВИКОНАННЯ ЗАМІН (з кінця до початку)
    replacements_to_do.sort(key=lambda x: x[0], reverse=True)
    for start, end, original in replacements_to_do:
        restored_text = restored_text[:start] + original + restored_text[end:]

    return restored_text, stats


def unmask_other_data(masked_text: str, masking_map: Dict) -> Tuple[str, Dict]:
    """
    Відновлення інших типів даних (окрім звань).
    """
    restored_text = masked_text

    mappings_copy = masking_map.get("mappings", {}).copy()
    if "rank" in mappings_copy:
        del mappings_copy["rank"]

    instance_map = build_instance_map({"mappings": mappings_copy})

    stats = {"restored_count": 0, "skipped_count": 0}
    replacements_to_do = []

    for masked_value, instance_to_original in instance_map.items():
        occurrences = find_all_occurrences(restored_text, masked_value)

        for instance_num, (start_pos, end_pos) in enumerate(occurrences, 1):
            if instance_num in instance_to_original:
                original_value = instance_to_original[instance_num]
                replacements_to_do.append((start_pos, end_pos, original_value, masked_value))
                stats["restored_count"] += 1
            else:
                stats["skipped_count"] += 1

    replacements_to_do.sort(key=lambda x: x[0], reverse=True)
    for start_pos, end_pos, original_value, masked_value in replacements_to_do:
        if restored_text[start_pos:end_pos].lower() == masked_value.lower():
            masked_segment = restored_text[start_pos:end_pos]
            original_value = _apply_original_case(masked_segment, original_value)
            restored_text = restored_text[:start_pos] + original_value + restored_text[end_pos:]

    return restored_text, stats


def unmask_text_v2(masked_text: str, masking_map: Dict, map_version: str) -> Tuple[str, Dict]:
    """
    Основна функція unmask для версій 2.x маппінгів.
    """
    if "re_mask_passes" in masking_map:
        passes = masking_map["re_mask_passes"]
        total_stats = {"restored_count": 0, "skipped_count": 0}
        text = masked_text
        for pass_map in reversed(passes):
            pass_version = check_mapping_version(pass_map)
            text, stats = unmask_text_v2(text, pass_map, pass_version)
            total_stats["restored_count"] += stats.get("restored_count", 0)
            total_stats["skipped_count"] += stats.get("skipped_count", 0)
        return text, total_stats

    if map_version == "v2.1":
        text_after_ranks, rank_stats = unmask_ranks_gender_aware(masked_text, masking_map)
        final_text, other_stats = unmask_other_data(text_after_ranks, masking_map)
        return final_text, {
            "restored_count": rank_stats["restored_count"] + other_stats["restored_count"],
            "skipped_count": rank_stats["skipped_count"] + other_stats["skipped_count"]
        }
    else:
        return unmask_other_data(masked_text, masking_map)


def unmask_text_v1(masked_text: str, masking_map: Dict) -> Tuple[str, Dict]:
    """
    Unmask для старих версій 1.x (проста заміна рядків).
    """
    restored_text = masked_text
    stats = {"restored_count": 0, "skipped_count": 0}
    all_replacements = []

    for category, cat_mappings in masking_map.get("mappings", {}).items():
        for original, masked in cat_mappings.items():
            if isinstance(masked, str):
                all_replacements.append((masked, original))

    all_replacements.sort(key=lambda x: len(x[0]), reverse=True)

    for masked, original in all_replacements:
        if masked in restored_text:
            stats["restored_count"] += restored_text.count(masked)
            restored_text = restored_text.replace(masked, original)

    return restored_text, stats


def unmask_json_recursive(masked_data: Any, masking_map: Dict, map_version: str) -> Any:
    """
    Рекурсивний unmask для JSON структур.
    """
    if isinstance(masked_data, dict):
        return {k: unmask_json_recursive(v, masking_map, map_version) for k, v in masked_data.items()}
    elif isinstance(masked_data, list):
        return [unmask_json_recursive(item, masking_map, map_version) for item in masked_data]
    elif isinstance(masked_data, str):
        if map_version.startswith("v2"):
            restored, _ = unmask_text_v2(masked_data, masking_map, map_version)
        else:
            restored, _ = unmask_text_v1(masked_data, masking_map)
        return restored
    else:
        return masked_data


# ============================================================================
# CHAIN UNMASK
# ============================================================================

def unmask_chain(masked_text: str, chain_data: Dict) -> Tuple[str, Dict]:
    """
    Unmask a multi-pass (re-mask chain) masked text by reversing passes.
    """
    passes = chain_data.get("passes", [])
    if not passes:
        return masked_text, {"restored_count": 0, "skipped_count": 0}

    total_stats = {"restored_count": 0, "skipped_count": 0}
    text = masked_text

    for pass_data in reversed(passes):
        pass_version = check_mapping_version(pass_data)
        text, stats = unmask_text_v2(text, pass_data, pass_version)
        total_stats["restored_count"] += stats.get("restored_count", 0)
        total_stats["skipped_count"] += stats.get("skipped_count", 0)

    return text, total_stats


def unmask_json_chain(masked_data: Any, chain_data: Dict) -> Any:
    """
    Unmask JSON data masked with multiple passes (chain).
    """
    passes = chain_data.get("passes", [])
    if not passes:
        return masked_data

    data = masked_data
    for pass_data in reversed(passes):
        pass_version = check_mapping_version(pass_data)
        data = unmask_json_recursive(data, pass_data, pass_version)

    return data


def is_chain_mapping(masking_map: Dict) -> bool:
    """Check if a mapping dict is a chain (multi-pass) mapping."""
    return "passes" in masking_map and isinstance(masking_map["passes"], list)
