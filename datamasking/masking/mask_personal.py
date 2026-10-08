#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Personal data masking functions: IPN, passport, military ID, names.

Extracted from data_masking.py during the package refactoring (v2.5.0).
"""

import random
import re
from typing import Dict, List, Optional

from datamasking.masking import constants as _cfg
from datamasking.masking.helpers import (
    add_to_mapping, get_deterministic_seed, get_next_instance,
    _apply_original_case, normalize_identifier,
)
from datamasking.masking.language import (
    detect_gender_by_patronymic, detect_name_case_and_gender,
    generate_easy_name, apply_case_to_name, same_name_forms, normalize_apostrophe,
)
from datamasking.masking import surname as _surname
from datamasking.masking.surname import synthesize_surname, known_surname_forms


_IPN_WEIGHTS = (-1, 5, 7, 9, 4, 6, 10, 5, 7)


def ipn_checksum(first9: str) -> int:
    """Контрольна цифра РНОКПП (ІПН) за першими 9 цифрами."""
    return (sum(w * int(d) for w, d in zip(_IPN_WEIGHTS, first9)) % 11) % 10


def is_valid_ipn(value: str) -> bool:
    return len(value) == 10 and value.isdigit() and ipn_checksum(value[:9]) == int(value[9])


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
        # validation.validate_ipn_checksum: валідний ІПН → валідна маска
        # (контрольна цифра перераховується); невалідний — як і раніше
        if _cfg.VALIDATE_IPN_CHECKSUM and is_valid_ipn(original):
            first9 = original[:3] + middle
            masked = first9 + str(ipn_checksum(first9))
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
        # Серія — як в оригіналі (до 3.1.8 переводилась у верхній регістр:
        # «мт-123456» → «МТ-…», і unmask повертав «МТ-123456»)
        prefix_match = re.match(r'^([A-Za-zА-Яа-яІіЇїЄєҐґ]{2})?([\s-]*)(\d{6})$', original.strip())
        if not prefix_match: return original
        prefix = prefix_match.group(1) or ""
        sep = prefix_match.group(2) if prefix else ""
        digits = prefix_match.group(3)
        seed = get_deterministic_seed(original)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(2)])
        masked_digits = digits[:2] + middle + digits[-2:]
        masked = prefix + sep + masked_digits
    return add_to_mapping(masking_dict, instance_counters, "military_id", original, masked)

def mask_surname(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує прізвище синтетичною формою без витоку оригіналу (v3.0.2).

    Відмінкове/родове закінчення оригіналу зберігається, основа —
    синтетична (див. masking/surname.py). До 3.0.2 маска була
    original[:3] + середина + original[-5:], і для прізвищ 5–8 літер
    оригінал читався в масці цілком.

    ВИКЛЮЧЕННЯ:
    - Абревіатури з ABBREVIATION_WHITELIST НЕ маскуються (ЗСУ, МОУ, СБУ тощо)
    """
    if original.lower() in _cfg.ABBREVIATION_WHITELIST: return original
    if original in masking_dict["mappings"]["surname"]:
        masked = masking_dict["mappings"]["surname"][original]["masked_as"]
    else:
        forbidden = known_surname_forms(masking_dict, except_original=original)
        hyphen_parts = original.split('-')
        if len(hyphen_parts) == 2 and all(len(p) >= 3 for p in hyphen_parts):
            # Подвійне прізвище: кожна частина — власна синтетична маска,
            # структура «Х-Y» зберігається (Петренко-Іванова → Сірченко-Юхимова)
            masked_parts: List[str] = []
            for part in hyphen_parts:
                mp = synthesize_surname(part, forbidden=forbidden | set(masked_parts))
                masked_parts.append(_apply_original_case(part, mp))
            masked = '-'.join(masked_parts)
        else:
            masked = _apply_original_case(original, synthesize_surname(original, forbidden=forbidden))
    return add_to_mapping(masking_dict, instance_counters, "surname", original, masked)

def pseudo_gender(value: str) -> str:
    """masking_rules.preserve_gender: false — рід маски не залежить від
    реального: детерміновано з хешу самого значення (≈50/50)."""
    return 'male' if get_deterministic_seed("gender\x00" + value.lower()) % 2 == 0 else 'female'


def mask_patronymic(patronymic: str, gender: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує по батькові з урахуванням роду.
    """
    if not _cfg.MASK_PATRONYMICS or not patronymic: return patronymic
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
    if not _cfg.PRESERVE_GENDER:
        gender = pseudo_gender(patronymic_lower)
    seed = get_deterministic_seed(patronymic_lower)
    random.seed(seed)
    _cfg.fake_uk.seed_instance(seed)
    # Більшість локалей faker не мають по батькові — беремо uk_UA-fallback
    provider = _cfg.fake_uk if hasattr(_cfg.fake_uk, 'middle_name_male') else _cfg.fake_uk_fallback
    if provider is not _cfg.fake_uk:
        provider.seed_instance(seed)
    fake_patronymic = normalize_apostrophe(provider.middle_name_male() if gender == 'male' else provider.middle_name_female())
    # Не те саме по батькові в іншому відмінку («Петровича» → «Петрович»)
    for attempt in range(10):
        if not same_name_forms(fake_patronymic, patronymic_lower) and not _surname.document_contains(fake_patronymic):
            break
        provider.seed_instance(seed + attempt + 1)
        fake_patronymic = normalize_apostrophe(provider.middle_name_male() if gender == 'male' else provider.middle_name_female())

    # Застосовуємо регістр
    if is_upper: fake_patronymic = fake_patronymic.upper()
    elif is_capitalize: fake_patronymic = fake_patronymic.capitalize()
    else: fake_patronymic = fake_patronymic.lower()

    return add_to_mapping(masking_dict, instance_counters, "patronymic", patronymic_lower, fake_patronymic)

def mask_name(original: str, masking_dict: Dict, instance_counters: Dict,
              gender_hint: Optional[str] = None, patronymic_hint: Optional[str] = None) -> str:
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
        if not _cfg.PRESERVE_GENDER:
            gender = pseudo_gender(original)

        # Генеруємо нове ім'я з тією ж першою літерою; оригінал (у називному)
        # виключаємо з кандидатів явно — інакше єдина кандидатка на літеру
        # (Марія, Юлія, Ірина…) поверталась як «маска»
        first_letter = original[0].lower()
        seed = get_deterministic_seed(original)
        nominative_guess = original.lower()
        doc_words = _surname.residue_vocabulary()
        new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50,
                                      exclude=nominative_guess, forbidden=doc_words)
        masked = apply_case_to_name(new_name, case, gender)

        # Страховка: маска ніколи не є тим самим ім'ям (у будь-якому відмінку)
        # і не збігається зі словом документа
        attempts = 0
        while (same_name_forms(masked, original) or same_name_forms(new_name, original)
               or masked.lower() in doc_words) and attempts < 10:
            seed = get_deterministic_seed(original + str(attempts))
            new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50,
                                          exclude=new_name.lower(), forbidden=doc_words)
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
