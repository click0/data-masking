#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Helper functions for unmasking operations.

Extracted from unmask_data.py during the package refactoring (v2.5.0).
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from datamasking.rank_data import (
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
            # mapping або ланцюг, відкритий або шифрований (v3.1.10)
            for name in (f"masking_map_{timestamp_suffix}.json", f"masking_map_{timestamp_suffix}.enc",
                         f"masking_chain_{timestamp_suffix}.json", f"masking_chain_{timestamp_suffix}.enc"):
                map_file = directory / name
                if map_file.exists():
                    pairs.append((output_file, map_file, timestamp_suffix))
                    break

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
    # Без ключа version — за структурою (до 3.1.22 тут підставлялось «1.0.0»,
    # і mapping 2.x/3.x без version ішов у v1 і нічого не відновлював)
    version = masking_map.get("version")

    match = re.match(r"v?(\d+)\.(\d+)", str(version)) if version is not None else None
    if not match:
        # Невідома/відсутня версія — визначаємо за структурою: записи-об'єкти
        # з masked_as — це v2.1 (до 3.1.10 такий mapping ішов у v1 і нічого
        # не відновлював, мовчки)
        for entries in masking_map.get("mappings", {}).values():
            if isinstance(entries, dict) and any(isinstance(v, dict) and "masked_as" in v for v in entries.values()):
                return "v2.1"
        return "v1"
    major, minor = int(match.group(1)), int(match.group(2))

    if major >= 3:
        # Формат mapping не змінювався з 2.1 — новіші версії читаємо
        # тією ж логікою (інакше mapping 3.x падав би у v1)
        return "v2.1"
    if major == 2:
        return "v2.0" if minor == 0 else "v2.1"
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


# Номер «будь-якого входження» для записів без instances (див. build_instance_map)
ANY_INSTANCE = 0


def instance_original(instances: Dict[int, str], number: int) -> Optional[str]:
    """Оригінал для входження *number* маски (або для будь-якого — ANY_INSTANCE)."""
    value = instances.get(number)
    return value if value is not None else instances.get(ANY_INSTANCE)


def build_instance_map(masking_map: Dict) -> Dict[str, Dict[int, str]]:
    """
    Створює мапу для instance tracking при unmask.

    Структура: {masked_value: {instance_num: original_value}}. Запис без
    ключа instances (mapping v2.0) — номер ANY_INSTANCE: оригінал для
    будь-якого входження цієї маски (до 3.1.22 такий запис не відновлювався).
    """
    instance_map: Dict[str, Dict[int, str]] = {}
    mappings_data = masking_map.get("mappings", {})

    for category, mappings in mappings_data.items():
        for original, mask_info in mappings.items():
            if isinstance(mask_info, dict) and "masked_as" in mask_info:
                masked_value = mask_info["masked_as"]
                instances = mask_info.get("instances", [ANY_INSTANCE])

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
        # Подвійне ім'я («Анна-Марія», «АННА-МАРІЯ»): кожна частина з великої,
        # якщо так записано в mapping — до 3.1.22 capitalize() давав
        # «Анна-марія». «генерал-майор» лишається «Генерал-майор»
        parts = masked.split("-")
        if len(parts) > 1 and all(p[:1].isupper() for p in parts):
            return "-".join(p.capitalize() for p in parts)
        return masked.capitalize()
    elif original.islower():
        return masked.lower()
    # Подвійне слово (маска «Доличенко-Ґубко»): регістр — по частинах, з
    # тексту. До 3.1.22 бралося як у mapping, і запис-двійник з іншим
    # регістром («ДОРОШЕНКО-ҐУДЗЬ» з рядка капсом) повертався капсом
    o_parts, m_parts = original.split("-"), masked.split("-")
    if len(o_parts) > 1 and len(o_parts) == len(m_parts) and all(o_parts) and all(m_parts):
        return "-".join(_apply_original_case(o, m) for o, m in zip(o_parts, m_parts))
    # Змішаний регістр (McDonald) — лишаємо як у mapping; раніше все, що не
    # UPPER/Title, силоміць переводилось у нижній
    return masked


def is_real_mask(value: str, masking_map: Dict, all_masked_values: Optional[set] = None) -> bool:
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
        'на пенсії', 'в резерві', 'у резерві',
        'запасу', 'резерву',
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
