#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Helper functions for unmasking operations.

Extracted from unmask_data.py during v2.5.0 refactoring.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rank_data import (
    RANK_DECLENSIONS,
    RANK_FEMININE_MAP,
    RANK_DECLENSIONS_FEMALE,
    RANK_TO_NOMINATIVE,
    ALL_RANK_FORMS
)

# Maximum input file size in bytes (default: 100 MB)
MAX_INPUT_FILE_SIZE = 100 * 1024 * 1024

# Директорії для автоматичного пошуку пар файлів (output + mapping)
SEARCH_DIRECTORIES = [
    Path('.'),          # Поточна директорія
    Path('./output'),   # Підтека output
    Path('./result')    # Підтека result
]


def validate_file_size(file_path: Path, max_size: int = MAX_INPUT_FILE_SIZE) -> None:
    """
    Перевіряє розмір файлу перед зчитуванням у пам'ять.

    Raises:
        ValueError: якщо файл перевищує допустимий розмір
    """
    file_size = file_path.stat().st_size
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise ValueError(
            f"File {file_path.name} ({actual_mb:.1f} MB) exceeds maximum "
            f"allowed size ({max_mb:.0f} MB)"
        )


def get_rank_info(rank_form: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Отримує інформацію про звання за його граматичною формою.

    Returns:
        Tuple (базова_форма, відмінок, рід) або (None, None, None)
    """
    rank_lower = rank_form.lower()
    if rank_lower in RANK_TO_NOMINATIVE:
        return RANK_TO_NOMINATIVE[rank_lower]
    return None, None, None


def find_file_pairs(directories: List[Path]) -> List[Tuple[Path, Path, str]]:
    """
    Шукає пари файлів output + mapping для автоматичного unmask.

    Returns:
        Список tuple: (output_file_path, map_file_path, timestamp_string)
    """
    pairs = []

    for directory in directories:
        if not directory.exists() or not directory.is_dir():
            continue

        output_files = list(directory.glob('output_*.txt')) + list(directory.glob('output_*.json'))

        for output_file in output_files:
            match = re.match(r'output_(\d{8}_\d{6}_\d{3})', output_file.stem)
            if not match:
                continue

            timestamp_suffix = match.group(1)
            map_file = directory / f"masking_map_{timestamp_suffix}.json"

            if map_file.exists():
                pairs.append((output_file, map_file, timestamp_suffix))

    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def auto_find_latest_pair() -> Optional[Tuple[Path, Path, Path]]:
    """
    Автоматично знаходить та вибирає останню пару файлів для unmask.

    Returns:
        Tuple (output_file, map_file, recovery_file) або None
    """
    print("❗ Автоматичний режим")
    print("🔍 Шукаю пари файлів...\n")

    pairs = find_file_pairs(SEARCH_DIRECTORIES)

    if not pairs:
        print("❌ Не знайдено файлів!")
        return None

    print(f"✅ Знайдено {len(pairs)} пар")

    output_file, map_file, timestamp_suffix = pairs[0]
    print(f"\n⏰ Вибрано: {output_file.name}\n")

    extension = output_file.suffix
    recovery_file = output_file.parent / f"input_recovery_{timestamp_suffix}{extension}"

    return output_file, map_file, recovery_file


def check_mapping_version(masking_map: Dict) -> str:
    """
    Визначає версію структури mapping файлу.

    Returns:
        Версія логіки: 'v2.1', 'v2.0' або 'v1'
    """
    version = masking_map.get("version", "1.0.0")

    if version.startswith("2.") and not version.startswith("2.0"):
        return "v2.1"
    elif version.startswith("2.0"):
        return "v2.0"
    else:
        return "v1"


def find_all_occurrences(text: str, pattern: str) -> List[Tuple[int, int]]:
    """
    Знаходить всі входження шаблону в тексті (case-insensitive).
    """
    occurrences = []
    try:
        regex_pattern = r'(?<!\w)' + re.escape(pattern) + r'(?!\w)'
        for match in re.finditer(regex_pattern, text, re.IGNORECASE):
            occurrences.append((match.start(), match.end()))
    except re.error as e:
        print(f"Warning: invalid regex pattern for '{pattern}': {e}")

    return occurrences


def build_instance_map(masking_map: Dict) -> Dict[str, Dict[int, str]]:
    """
    Створює мапу для instance tracking при unmask.

    Структура: {masked_value: {instance_num: original_value}}
    """
    instance_map = {}
    mappings_data = masking_map.get("mappings", {})

    for category, mappings in mappings_data.items():
        for original, mask_info in mappings.items():
            if isinstance(mask_info, dict) and "masked_as" in mask_info:
                masked_value = mask_info["masked_as"]
                instances = mask_info.get("instances", [])

                if masked_value not in instance_map:
                    instance_map[masked_value] = {}

                for instance_num in instances:
                    instance_map[masked_value][instance_num] = original

    return instance_map


def _apply_original_case(original: str, masked: str) -> str:
    """
    Відновлює регістр літер оригіналу на маскованому значенні.
    """
    if not original or not masked:
        return masked

    if original.isupper():
        return masked.upper()
    elif len(original) > 1 and original[0].isupper() and original[1:].islower():
        return masked.capitalize()
    else:
        return masked.lower()


def is_real_mask(value: str, masking_map: Dict, all_masked_values: set = None) -> bool:
    """
    Перевіряє, чи є слово реальною маскою (а не випадковим збігом з оригіналом).
    """
    value_lower = value.lower()

    if all_masked_values is not None:
        return value_lower in all_masked_values

    mappings = masking_map.get("mappings", {})
    for category, items in mappings.items():
        for original, mask_info in items.items():
            if isinstance(mask_info, dict) and "masked_as" in mask_info:
                if mask_info["masked_as"].lower() == value_lower:
                    return True

    return False


def extract_base_rank(full_rank_text: str) -> tuple:
    """
    Виділяє базове звання та додаткові слова зі складеного звання.

    Returns:
        Tuple (базове_звання, додаткові_слова)
    """
    if not full_rank_text:
        return full_rank_text, ""

    service_type_phrases = ['медичної служби', 'юстиції']
    status_phrases = [
        'у відставці', 'в запасі', 'у запасі',
        'на пенсії', 'в резерві', 'у резерві'
    ]

    full_rank_lower = full_rank_text.lower()
    base_rank = full_rank_text
    additional_parts = []

    for phrase in service_type_phrases:
        if phrase in full_rank_lower:
            phrase_index = full_rank_lower.find(phrase)
            base_rank = full_rank_text[:phrase_index].strip()
            additional_parts.append(full_rank_text[phrase_index:phrase_index + len(phrase)])
            remaining_text = full_rank_text[phrase_index + len(phrase):].strip()
            full_rank_lower = remaining_text.lower()
            full_rank_text = remaining_text
            break

    for phrase in status_phrases:
        if phrase in full_rank_lower:
            if not additional_parts:
                phrase_index = full_rank_text.lower().find(phrase)
                base_rank = full_rank_text[:phrase_index].strip()
            phrase_start = full_rank_text.lower().find(phrase)
            additional_parts.append(full_rank_text[phrase_start:phrase_start + len(phrase)])
            break

    additional = ' '.join(additional_parts) if additional_parts else ""
    return base_rank, additional
