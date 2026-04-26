#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base helper functions for masking operations.

Extracted from data_masking.py during v2.5.0 refactoring.
"""

import hashlib
import re
from pathlib import Path
from typing import Dict

from masking import constants as _cfg


def validate_file_size(file_path: Path, max_size: int = None) -> None:
    """
    Перевіряє розмір файлу перед зчитуванням у пам'ять.

    Raises:
        ValueError: якщо файл перевищує допустимий розмір
    """
    if max_size is None:
        max_size = _cfg.MAX_INPUT_FILE_SIZE
    file_size = file_path.stat().st_size
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        raise ValueError(
            f"File {file_path.name} ({actual_mb:.1f} MB) exceeds maximum "
            f"allowed size ({max_mb:.0f} MB)"
        )


def get_next_instance(masked_value: str, instance_counters: Dict[str, int]) -> int:
    """
    Повертає наступний номер екземпляра для даного замаскованого значення.

    Instance tracking: відстежуємо випадки коли різні оригінали
    маскуються в одне значення (колізії)
    """
    instance_counters.setdefault(masked_value, 0)
    instance_counters[masked_value] += 1
    return instance_counters[masked_value]

def add_to_mapping(masking_dict: Dict, instance_counters: Dict, category: str, original: str, masked: str) -> str:
    """
    Додає маппінг оригінал->маска до словника та оновлює статистику.

    Args:
        masking_dict: Словник з усіма маппінгами
        instance_counters: Лічильники екземплярів для instance tracking
        category: Категорія даних (ipn, surname, rank, тощо)
        original: Оригінальне значення
        masked: Замасковане значення

    Returns:
        Замасковане значення (може бути взято з існуючого mapping)

    Note:
        Статистика оновлюється тільки для УНІКАЛЬНИХ оригіналів
    """
    if original not in masking_dict["mappings"][category]:
        masking_dict["mappings"][category][original] = {
            "masked_as": masked,
            "instances": []
        }
        # Статистика оновлюється тільки для унікальних оригіналів
        masking_dict["statistics"][category] = masking_dict["statistics"].get(category, 0) + 1
    else:
        masked = masking_dict["mappings"][category][original]["masked_as"]

    # Instance tracking: зберігаємо кожне входження
    instance_num = get_next_instance(masked, instance_counters)
    masking_dict["mappings"][category][original]["instances"].append(instance_num)
    return masked

def _apply_original_case(original: str, masked: str) -> str:
    """
    Застосовує регістр оригінального тексту до замаскованого.

    Підтримує:
    - UPPER CASE (весь текст великими)
    - Title Case (перша велика, решта малі)
    - lower case (весь текст малими)
    """
    if not original or not masked: return masked
    if original.isupper(): return masked.upper()
    elif len(original) > 1 and original[0].isupper() and original[1:].islower(): return masked.capitalize()
    else: return masked.lower()

def normalize_string(s: str) -> str:
    if not s: return ""
    s_str = str(s).lower()
    s_str = s_str.replace("'", "'").replace('\xa0', ' ').replace(".", " ").replace(";", " ")
    return re.sub(r'\s+', ' ', s_str).strip()

def normalize_identifier(identifier: str) -> str:
    if not identifier: return ""
    identifier_str = str(identifier).upper()
    return re.sub(r'[\s\-.]', '', identifier_str).strip()

def is_pib_anchor(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    if not word or len(word) <= 2: return False
    word_lower = word.lower()
    if word_lower in [w.lower() for w in _cfg.EXCLUDE_WORDS]: return False
    if word_lower in [r.lower() for r in _cfg.RANKS_LIST]: return False
    return word[0].isupper()

def get_deterministic_seed(original: str) -> int:
    """
    Генерує детермінований seed для маскування на основі оригінального значення.

    Використовує hashlib для створення унікального, але повторюваного seed'а.
    """
    algo = _cfg.HASH_ALGORITHM
    if algo == 'md5': hasher = hashlib.md5()
    elif algo == 'sha1': hasher = hashlib.sha1()
    elif algo == 'sha256': hasher = hashlib.sha256()
    elif algo == 'blake2b': hasher = hashlib.blake2b()
    elif algo == 'sha512': hasher = hashlib.sha512()
    else: raise ValueError(f"Unknown hash algorithm: {algo}")
    hasher.update(original.encode('utf-8'))
    return int(hasher.hexdigest(), 16) % (2**32)
