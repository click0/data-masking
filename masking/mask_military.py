#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Military data masking: ranks, units, orders, BR numbers, dates.

Extracted from data_masking.py during v2.4.0 refactoring.
"""

import random
import re
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from masking import constants as _cfg
from masking.helpers import add_to_mapping, get_deterministic_seed, _apply_original_case
from masking.context import extract_base_rank


def mask_military_unit(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує військову частину.

    Формат: A#### (одна велика літера + 4 цифри)
    Логіка: Зберігає літеру, змінює всі 4 цифри
    """
    if original in masking_dict["mappings"]["military_unit"]:
        masked = masking_dict["mappings"]["military_unit"][original]["masked_as"]
    else:
        match = re.match(r'^([А-ЯA-Z])(\d{4})$', original)
        if not match: return original
        letter = match.group(1)
        seed = get_deterministic_seed(original)
        random.seed(seed)
        digits = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        masked = letter + digits
    return add_to_mapping(masking_dict, instance_counters, "military_unit", original, masked)

def mask_order_number(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує номер наказу.

    Логіка: Замінює всі цифри, зберігає формат (№, пробіли, слеші)
    """
    if original in masking_dict["mappings"]["order_number"]:
        masked = masking_dict["mappings"]["order_number"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = re.sub(r'\d', lambda _: str(random.randint(0, 9)), original)
    return add_to_mapping(masking_dict, instance_counters, "order_number", original, masked)

def mask_order_number_with_letters(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["order_number_with_letters"]:
        masked = masking_dict["mappings"]["order_number_with_letters"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = re.sub(r'\d', lambda _: str(random.randint(0, 9)), original)
    return add_to_mapping(masking_dict, instance_counters, "order_number_with_letters", original, masked)

def mask_br_number(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує БР номер.

    Логіка: Замінює всі цифри, зберігає структуру (префікси, суфікси, слеші)
    """
    if original in masking_dict["mappings"]["br_number"]:
        masked = masking_dict["mappings"]["br_number"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)

        # Витягуємо суфікс (дск, п, к)
        suffix_match = re.search(r'(дск|п|к)$', original)
        suffix = suffix_match.group(1) if suffix_match else ""

        # Витягуємо префікс (№)
        prefix = ""
        number_part = original
        if original.startswith("№"):
            match = re.match(r'(№\s*)', original)
            if match:
                prefix = match.group(1)
                number_part = original[len(prefix):]
        if suffix: number_part = number_part[:-len(suffix)]

        # Обробляємо частини розділені слешами
        parts = re.split(r'(/)', number_part)
        masked_parts = []
        for part in parts:
            if part == '/': masked_parts.append(part)
            elif part and re.match(r'^\d', part):
                digit_match = re.match(r'(\d+)(.*)', part)
                if digit_match:
                    digits = digit_match.group(1)
                    rest = digit_match.group(2)
                    masked_digits = ''.join([str(random.randint(0, 9)) for _ in range(len(digits))])
                    masked_parts.append(masked_digits + rest)
                else: masked_parts.append(part)
            else: masked_parts.append(part)
        masked = prefix + ''.join(masked_parts) + suffix
    return add_to_mapping(masking_dict, instance_counters, "br_number", original, masked)

def mask_br_number_slash(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["br_number_slash"]:
        masked = masking_dict["mappings"]["br_number_slash"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        suffix_match = re.search(r'(дск|п|к)$', original)
        suffix = suffix_match.group(1) if suffix_match else ""
        prefix = ""
        number_part = original
        if original.startswith("№"):
            match = re.match(r'(№\s*)', original)
            if match:
                prefix = match.group(1)
                number_part = original[len(prefix):]
        if suffix: number_part = number_part[:-len(suffix)]

        parts = number_part.split('/')
        masked_parts = []
        for part in parts:
            if part.strip().isdigit():
                masked_parts.append(''.join([str(random.randint(0, 9)) for _ in range(len(part.strip()))]))
            else:
                masked_parts.append(part)
        masked = prefix + '/'.join(masked_parts) + suffix
    return add_to_mapping(masking_dict, instance_counters, "br_number_slash", original, masked)

def mask_br_number_complex(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["br_number_complex"]:
        masked = masking_dict["mappings"]["br_number_complex"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = re.sub(r'\d', lambda _: str(random.randint(0, 9)), original)
    return add_to_mapping(masking_dict, instance_counters, "br_number_complex", original, masked)

def mask_brigade_number(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["brigade_number"]:
        masked = masking_dict["mappings"]["brigade_number"][original]["masked_as"]
    else:
        match = re.match(r'(\d+)\s+(.+)', original)
        if not match: return original
        brigade_name = match.group(2)
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = f"{random.randint(1, 160)} {brigade_name}"
    return add_to_mapping(masking_dict, instance_counters, "brigade_number", original, masked)

def is_valid_date(day: int, month: int, year: int) -> bool:
    if year < 2015 or year > 2035: return False
    try:
        datetime(year, month, day)
        return True
    except ValueError: return False

def mask_date(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує дату у форматі DD.MM.YYYY.

    Логіка: Зміщує дату на +-30 днів, обмежує роки 2015-2035.
    """
    if original in masking_dict["mappings"]["date"]:
        masked = masking_dict["mappings"]["date"][original]["masked_as"]
    else:
        try:
            match = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', original)
            if not match: return original

            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if not is_valid_date(day, month, year): return original

            # Створюємо об'єкт дати та зміщуємо на +-30 днів
            date_obj = datetime(year, month, day)
            seed = get_deterministic_seed(original)
            random.seed(seed)
            new_date = date_obj + timedelta(days=random.randint(-30, 30))

            # Обмежуємо діапазон років 2015-2035
            if new_date.year < 2015:
                new_date = datetime(2015, 1, 1) + timedelta(days=random.randint(0, 365))
            elif new_date.year > 2035:
                new_date = datetime(2035, 12, 31) - timedelta(days=random.randint(0, 365))

            masked = new_date.strftime("%d.%m.%Y")
        except (ValueError, OverflowError, TypeError, AttributeError) as e:
            if _cfg.DEBUG_MODE:
                print(f"Warning: error parsing date '{original}': {e}")
            return original

    return add_to_mapping(masking_dict, instance_counters, "date", original, masked)


def mask_date_text(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує текстову дату у форматі: "06" жовтня 2025 року.
    """
    match = _cfg.DATE_TEXT_PATTERN.search(original)
    if not match:
        return original

    day, month_name, year = match.group(1), match.group(2), match.group(3)
    original_key = f"{day} {month_name} {year}"

    category = "date_text"

    # Перевіряємо чи вже маскували цю дату
    if category not in masking_dict["mappings"]:
        masking_dict["mappings"][category] = {}

    existing = masking_dict["mappings"].get(category, {})
    if original_key.lower() in existing:
        masked_val = existing[original_key.lower()]
        if isinstance(masked_val, dict):
            masked_val = masked_val.get("masked_as", original)
        parts = masked_val.split()
        if len(parts) >= 3:
            result = original.replace(day, parts[0], 1).replace(
                month_name, parts[1], 1).replace(year, parts[2], 1)
            return result
        return original

    # Генеруємо детермінований seed
    seed = get_deterministic_seed(original_key)
    random.seed(seed)

    # Зміщуємо день на +-5 (в межах 1-28)
    day_shift = random.choice([-5, -3, -2, 2, 3, 5])
    new_day = str(max(1, min(28, int(day) + day_shift))).zfill(len(day))

    # Замінюємо місяць на випадковий інший
    available_months = [m for m in _cfg._MONTHS_UA_LIST if m != month_name.lower()]
    new_month = random.choice(available_months)

    # Зміщуємо рік на +-1
    year_shift = random.choice([-1, 0, 1])
    new_year = str(int(year) + year_shift)

    # Формуємо замаскований текст
    masked_text = original.replace(day, new_day, 1).replace(
        month_name, new_month, 1).replace(year, new_year, 1)
    masked_key = f"{new_day} {new_month} {new_year}"

    # Зберігаємо у mappings
    mappings = masking_dict["mappings"].setdefault(category, {})
    key = original_key.lower()
    if key not in mappings:
        mappings[key] = {"masked_as": masked_key, "instances": [1]}
        instance_counters[masked_key] = instance_counters.get(masked_key, 0) + 1
    masking_dict["statistics"][category] = masking_dict["statistics"].get(category, 0) + 1

    return masked_text


def _mask_date_text(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """Mask a text date like '"06" жовтня 2025 року'."""
    match = _cfg.DATE_TEXT_PATTERN.search(original)
    if not match:
        return original

    day, month, year = match.group(1), match.group(2), match.group(3)
    original_key = f"{day} {month} {year}"

    category = "date_text"
    existing = masking_dict["mappings"].get(category, {})
    if original_key.lower() in existing:
        masked_val = existing[original_key.lower()]
        if isinstance(masked_val, dict):
            masked_val = masked_val.get("masked_as", original)
        return original.replace(day, masked_val.split()[0]).replace(
            month, masked_val.split()[1] if len(masked_val.split()) > 1 else month).replace(
            year, masked_val.split()[2] if len(masked_val.split()) > 2 else year)

    # Shift day by +-5, month randomly, year +-1
    new_day = str(max(1, min(28, int(day) + random.choice([-5, -3, -2, 2, 3, 5])))).zfill(len(day))
    new_month = random.choice([m for m in _cfg._MONTHS_UA_LIST if m != month.lower()])
    new_year = str(int(year) + random.choice([-1, 0, 1]))

    masked_text = original.replace(day, new_day, 1).replace(month, new_month, 1).replace(year, new_year, 1)
    masked_key = f"{new_day} {new_month} {new_year}"

    # Store in mappings directly
    mappings = masking_dict["mappings"].setdefault(category, {})
    key = original_key.lower()
    if key not in mappings:
        mappings[key] = {"masked_as": masked_key, "instances": [1]}
        instance_counters[masked_key] = instance_counters.get(masked_key, 0) + 1
    masking_dict["statistics"][category] = masking_dict["statistics"].get(category, 0) + 1
    return masked_text


# ============================================================================
# RANK MASKING
# ============================================================================

def get_rank_category_and_match(text: str) -> Tuple[Optional[str], Optional[str]]:
    text_lower = text.lower()
    for category, pattern in _cfg.RANK_PATTERNS.items():
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match: return category, match.group(0)
    return None, None

def get_rank_info(rank_form: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    rank_lower = rank_form.lower()
    if rank_lower in _cfg.RANK_TO_NOMINATIVE:
        return _cfg.RANK_TO_NOMINATIVE[rank_lower]
    return None, None, None

def get_rank_in_case(nominative_rank: str, target_case: str) -> str:
    if nominative_rank not in _cfg.RANK_DECLENSIONS: return nominative_rank
    return _cfg.RANK_DECLENSIONS[nominative_rank].get(target_case, nominative_rank)

def mask_rank(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує звання (базова версія).

    Логіка:
    1. Визначає категорію звання (army, naval, legal, medical)
    2. Знаходить позицію у відповідній ієрархії
    3. Генерує нове звання зі зсувом +-1-2 позиції
    4. Зберігає граматичний відмінок
    """
    original_key = original.lower()
    detected_base, detected_case, detected_gender = get_rank_info(original_key)

    # Use nominative (base) form as the lookup/storage key for consistent mapping
    lookup_key = detected_base.lower() if detected_base else original_key
    search_key = detected_base.lower() if detected_base else original_key

    # Instance tracking: перевіряємо чи це звання вже не є маскою іншого
    if lookup_key in masking_dict["mappings"]["rank"]:
        is_someone_else_mask = False
        for other_original, other_data in masking_dict["mappings"]["rank"].items():
            if isinstance(other_data, dict) and "masked_as" in other_data:
                if other_data["masked_as"].lower() == lookup_key and other_original != lookup_key:
                    is_someone_else_mask = True
                    break
        if not is_someone_else_mask:
            masked = masking_dict["mappings"]["rank"][lookup_key]["masked_as"]
            final_masked = add_to_mapping(masking_dict, instance_counters, "rank", lookup_key, masked)
            # Apply grammatical case if the original was not nominative
            if detected_case and detected_case != "nominative":
                final_masked = get_rank_in_case(final_masked, detected_case)
            if _cfg.PRESERVE_CASE: return _apply_original_case(original, final_masked)
            return final_masked

    # Визначаємо категорію та ієрархію звань
    category_name, matched = get_rank_category_and_match(search_key)
    if not matched: return original

    if category_name == "army": hierarchy = _cfg.ARMY_RANKS
    elif category_name == "naval": hierarchy = _cfg.NAVAL_RANKS
    elif category_name == "legal": hierarchy = _cfg.LEGAL_RANKS
    elif category_name == "medical": hierarchy = _cfg.MEDICAL_RANKS
    else: return original

    try: idx = [r.lower() for r in hierarchy].index(matched.lower())
    except ValueError: return original

    # Генеруємо нове звання зі зсувом позиції
    seed = get_deterministic_seed(search_key)
    random.seed(seed)
    shift = random.choice(_cfg.RANK_SHIFT_OPTIONS)
    new_idx = max(0, min(len(hierarchy) - 1, idx + shift))
    masked = hierarchy[new_idx]

    # Уникаємо випадків коли звання мапиться саме на себе
    attempts = 0
    while masked.lower() == search_key and attempts < 10:
        shift = random.choice(_cfg.RANK_SHIFT_OPTIONS)
        new_idx = max(0, min(len(hierarchy) - 1, idx + shift))
        masked = hierarchy[new_idx]
        attempts += 1

    # Store mapping by base form (nominative) for consistency
    final_masked = add_to_mapping(masking_dict, instance_counters, "rank", lookup_key, masked)

    # Застосовуємо граматичний відмінок якщо потрібно
    if detected_case and detected_case != "nominative":
        final_masked = get_rank_in_case(final_masked, detected_case)
    # БАГ #16 & #18 FIX: Застосовуємо регістр ПІСЛЯ add_to_mapping
    if _cfg.PRESERVE_CASE:
        # Спеціальна обробка для складених звань (з дефісом або пробілом)
        if '-' in original and original.istitle():
            return final_masked.title()

        # БАГ #18 FIX: Перевірка для багатослівних звань у Title Case
        words = original.split()
        if len(words) > 1:
            all_title = all(word and word[0].isupper() for word in words if word)
            if all_title:
                return final_masked.title()

        # Інакше використовуємо стандартну логіку збереження регістру
        return _apply_original_case(original, final_masked)
    return final_masked

def mask_rank_preserve_case(original_text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує звання зі збереженням регістру та граматичного відмінка (Bug Fix #16-18).
    """
    base_rank_text, additional_words = extract_base_rank(original_text)
    base_male_form, detected_case, gender = get_rank_info(base_rank_text)

    if not base_male_form:
        masked_result = mask_rank(base_rank_text, masking_dict, instance_counters)
        return f"{masked_result} {additional_words}" if additional_words else masked_result

    masked_base_male = mask_rank(base_male_form, masking_dict, instance_counters)
    final_rank = None

    if gender == 'female':
        if masked_base_male.lower() in _cfg.RANK_FEMININE_MAP:
            masked_base_female = _cfg.RANK_FEMININE_MAP[masked_base_male.lower()]
            if masked_base_female in _cfg.RANK_DECLENSIONS_FEMALE and detected_case:
                final_rank = _cfg.RANK_DECLENSIONS_FEMALE[masked_base_female].get(detected_case, masked_base_female)
            else: final_rank = masked_base_female
        else:
            if masked_base_male.lower() in _cfg.RANK_DECLENSIONS and detected_case:
                final_rank = _cfg.RANK_DECLENSIONS[masked_base_male.lower()].get(detected_case, masked_base_male)
            else: final_rank = masked_base_male
    else:
        if masked_base_male.lower() in _cfg.RANK_DECLENSIONS and detected_case:
            final_rank = _cfg.RANK_DECLENSIONS[masked_base_male.lower()].get(detected_case, masked_base_male)
        else: final_rank = masked_base_male

    if _cfg.PRESERVE_CASE and final_rank:
        final_rank = _apply_original_case(base_rank_text, final_rank)
    result = final_rank if final_rank else masked_base_male
    return f"{result} {additional_words}" if additional_words else result
