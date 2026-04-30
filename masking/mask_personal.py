#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Personal data masking functions: IPN, passport, military ID, names.

Extracted from data_masking.py during v2.5.0 refactoring.
"""

import random
import re
from typing import Dict

from masking import constants as _cfg
from masking.helpers import (
    add_to_mapping, get_deterministic_seed, get_next_instance,
    _apply_original_case, normalize_identifier,
)
from masking.language import (
    detect_gender_by_patronymic, detect_name_case_and_gender,
    generate_easy_name, apply_case_to_name,
)


def mask_ipn(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує ІПН (Індивідуальний податковий номер).

    Формат: 10 цифр
    Логіка: Зберігає перші 3 та останню цифру, змінює середні 6 цифр
    """
    if original in masking_dict["mappings"]["ipn"]:
        masked = masking_dict["mappings"]["ipn"][original]["masked_as"]
    else:
        if len(original) != 10 or not original.isdigit(): return original
        seed = get_deterministic_seed(original)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        masked = original[:3] + middle + original[-1]
    return add_to_mapping(masking_dict, instance_counters, "ipn", original, masked)

def mask_passport_id(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує ID паспорту.

    Формат: 9 цифр
    Логіка: Зберігає перші 3 та останню цифру, змінює середні 5 цифр
    """
    if original in masking_dict["mappings"]["passport_id"]:
        masked = masking_dict["mappings"]["passport_id"][original]["masked_as"]
    else:
        if len(original) != 9 or not original.isdigit(): return original
        seed = get_deterministic_seed(original)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(5)])
        masked = original[:3] + middle + original[-1]
    return add_to_mapping(masking_dict, instance_counters, "passport_id", original, masked)

def mask_military_id(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує військовий ID.

    Формати:
    - ######  (6 цифр)
    - AA ######  (2 великі літери + пробіл + 6 цифр)
    - AA-######  (2 великі літери + дефіс + 6 цифр)
    """
    if original in masking_dict["mappings"]["military_id"]:
        masked = masking_dict["mappings"]["military_id"][original]["masked_as"]
    else:
        normalized = normalize_identifier(original)
        prefix_match = re.match(r'^([A-ZА-Я]{2})?(\d{6})$', normalized)
        if not prefix_match: return original
        prefix = prefix_match.group(1) or ""
        digits = prefix_match.group(2)
        seed = get_deterministic_seed(original)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(2)])
        masked_digits = digits[:2] + middle + digits[-2:]
        if " " in original: masked = f"{prefix} {masked_digits}" if prefix else masked_digits
        elif "-" in original: masked = f"{prefix}-{masked_digits}" if prefix else masked_digits
        else: masked = prefix + masked_digits
    return add_to_mapping(masking_dict, instance_counters, "military_id", original, masked)

def mask_surname(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує прізвище.

    ЛОГІКА МАСКУВАННЯ:
    - Для коротких прізвищ (<5 символів): генерує нове через faker
    - Для довгих прізвищ (>=5 символів): зберігає початок (3) та кінець (5), змінює середину

    ВИКЛЮЧЕННЯ:
    - Абревіатури з ABBREVIATION_WHITELIST НЕ маскуються (ЗСУ, МОУ, СБУ тощо)
    """
    if original.lower() in _cfg.ABBREVIATION_WHITELIST: return original
    if original in masking_dict["mappings"]["surname"]:
        masked = masking_dict["mappings"]["surname"][original]["masked_as"]
    else:
        is_upper = original.isupper()
        is_capitalize = original[0].isupper() and original[1:].islower()
        seed = get_deterministic_seed(original)
        random.seed(seed)
        _cfg.fake_uk.seed_instance(seed)
        fake_surname = _cfg.fake_uk.last_name()

        # Для коротких прізвищ генеруємо нове повністю
        if len(original) < 5:
            target_length = random.randint(max(3, len(original) - 1), min(6, len(original) + 2))
            masked = fake_surname[:target_length] if len(fake_surname) > target_length else fake_surname
        else:
            # Для довгих зберігаємо початок та кінець
            # NOTE: для прізвищ 5-7 символів prefix(3)+suffix(5) перекриваються,
            # результат довший за оригінал — це відоме обмеження алгоритму
            middle_len = min(random.randint(2, 7), len(fake_surname)-2)
            middle = fake_surname[1:1+middle_len] if len(fake_surname) > 4 else fake_surname[1:-1]
            masked = original[:3] + middle + original[-5:]

        # Застосовуємо регістр
        if is_upper: masked = masked.upper()
        elif is_capitalize: masked = masked.capitalize()
    return add_to_mapping(masking_dict, instance_counters, "surname", original, masked)

def mask_patronymic(patronymic: str, gender: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує по батькові з урахуванням роду.
    """
    if not _cfg.MASK_NAMES or not patronymic: return patronymic
    is_upper = patronymic.isupper()
    is_capitalize = patronymic[0].isupper() and patronymic[1:].islower() if len(patronymic) > 1 else False
    patronymic_lower = patronymic.lower()

    if "patronymic" not in masking_dict["mappings"]: masking_dict["mappings"]["patronymic"] = {}
    if patronymic_lower in masking_dict["mappings"]["patronymic"]:
        masked = masking_dict["mappings"]["patronymic"][patronymic_lower]["masked_as"]
        masked_with_case = _apply_original_case(patronymic, masked)
        instance_num = get_next_instance(masked, instance_counters)
        masking_dict["mappings"]["patronymic"][patronymic_lower]["instances"].append(instance_num)
        return masked_with_case

    # Генеруємо нове по батькові відповідного роду
    seed = get_deterministic_seed(patronymic_lower)
    random.seed(seed)
    _cfg.fake_uk.seed_instance(seed)
    fake_patronymic = _cfg.fake_uk.middle_name_male() if gender == 'male' else _cfg.fake_uk.middle_name_female()

    # Застосовуємо регістр
    if is_upper: fake_patronymic = fake_patronymic.upper()
    elif is_capitalize: fake_patronymic = fake_patronymic.capitalize()
    else: fake_patronymic = fake_patronymic.lower()

    return add_to_mapping(masking_dict, instance_counters, "patronymic", patronymic_lower, fake_patronymic)

def mask_name(original: str, masking_dict: Dict, instance_counters: Dict, gender_hint: str = None, patronymic_hint: str = None) -> str:
    """
    Маскує ім'я з автоматичним визначенням роду та відмінка.
    """
    # БАГ #17 FIX: Зберігаємо оригінальний регістр перед обробкою
    is_upper = original.isupper()
    is_capitalize = original[0].isupper() and (len(original) == 1 or original[1:].islower())
    is_lower = original.islower()

    if original in masking_dict["mappings"]["name"]:
        # Ім'я вже маскувалось раніше - беремо існуючу маску
        masked = masking_dict["mappings"]["name"][original]["masked_as"]
    else:
        # Перше маскування - генеруємо нову маску
        if not original: return original

        # Визначаємо відмінок та рід
        case, gender_from_name = detect_name_case_and_gender(original)

        # Пріоритет визначення роду: gender_hint -> patronymic_hint -> gender_from_name
        if gender_hint: gender = gender_hint
        elif patronymic_hint:
            gender = detect_gender_by_patronymic(patronymic_hint)
            if gender == 'unknown': gender = gender_from_name
        else: gender = gender_from_name
        if gender == 'unknown': gender = 'male'

        # Генеруємо нове ім'я з тією ж першою літерою
        first_letter = original[0].lower()
        seed = get_deterministic_seed(original)
        new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50)
        masked = apply_case_to_name(new_name, case, gender)

        # Уникаємо випадків коли ім'я мапиться саме на себе
        attempts = 0
        while masked.lower() == original.lower() and attempts < 10:
            seed = get_deterministic_seed(original + str(attempts))
            new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50)
            masked = apply_case_to_name(new_name, case, gender)
            attempts += 1

    # БАГ #17 FIX: Застосовуємо регістр до masked ПЕРЕД add_to_mapping
    if is_upper:
        masked = masked.upper()
    elif is_capitalize:
        masked = masked.capitalize()
    elif is_lower:
        masked = masked.lower()

    return add_to_mapping(masking_dict, instance_counters, "name", original, masked)
