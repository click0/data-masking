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
from datamasking.masking.declension import (
    NOMINATIVE, VOCATIVE, analyze_name, analyze_patronymic, decline_name, decline_patronymic,
)
from datamasking.masking.language import (
    generate_easy_name, same_name_forms, normalize_apostrophe,
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
    Маскує по батькові з урахуванням роду і відмінка.

    З 3.1.12 маска стоїть у відмінку оригіналу («Петровича» → «Івановича»,
    «Сергіївною» → «Борисівною»), а всі відмінки одного по батькові дають
    одну маску (seed — від називного відмінка; для називного — як раніше).
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

    form = analyze_patronymic(patronymic_lower)
    if form.gender == 'unknown':
        lemma, case = patronymic_lower, NOMINATIVE
    else:
        lemma, case = form.nominative, form.case
        if gender not in ('male', 'female'):
            gender = form.gender

    # Генеруємо нове по батькові відповідного роду
    if not _cfg.PRESERVE_GENDER:
        gender = pseudo_gender(lemma)
    seed = get_deterministic_seed(lemma)
    random.seed(seed)
    _cfg.fake_uk.seed_instance(seed)
    # Більшість локалей faker не мають по батькові — беремо uk_UA-fallback
    provider = _cfg.fake_uk if hasattr(_cfg.fake_uk, 'middle_name_male') else _cfg.fake_uk_fallback
    if provider is not _cfg.fake_uk:
        provider.seed_instance(seed)

    def _generate() -> str:
        return normalize_apostrophe(provider.middle_name_male() if gender == 'male' else provider.middle_name_female())

    fake_nominative = _generate()
    fake_patronymic = decline_patronymic(fake_nominative, case)
    # Не те саме по батькові в іншому відмінку («Петровича» → «Петрович»)
    # і не слово, що лишається в документі відкритим
    for attempt in range(10):
        if (not same_name_forms(fake_nominative, lemma) and not same_name_forms(fake_patronymic, patronymic_lower)
                and not _surname.document_contains(fake_patronymic)):
            break
        provider.seed_instance(seed + attempt + 1)
        fake_nominative = _generate()
        fake_patronymic = decline_patronymic(fake_nominative, case)

    # Застосовуємо регістр
    if is_upper: fake_patronymic = fake_patronymic.upper()
    elif is_capitalize: fake_patronymic = fake_patronymic.capitalize()
    else: fake_patronymic = fake_patronymic.lower()

    return add_to_mapping(masking_dict, instance_counters, "patronymic", patronymic_lower, fake_patronymic)

def mask_name(original: str, masking_dict: Dict, instance_counters: Dict,
              gender_hint: Optional[str] = None, patronymic_hint: Optional[str] = None,
              case_hint: Optional[str] = None) -> str:
    """
    Маскує ім'я з автоматичним визначенням роду та відмінка.

    *patronymic_hint* дає рід і відмінок; *case_hint* — відмінок від звання
    («рядового Петренка Богуслава» → родовий від Богуслав), коли по батькові
    немає (v3.1.12). Маска стоїть у відмінку оригіналу, а всі відмінки одного
    імені дають одну маску.
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

        # Рід і відмінок: по батькові (якщо є) знімає неоднозначність форми
        # («Петра Івановича» — чоловічий родовий, «Наталі Петрівни» — родовий)
        if patronymic_hint:
            pat_form = analyze_patronymic(patronymic_hint)
            if pat_form.gender != 'unknown' and pat_form.case != VOCATIVE:
                case_hint = pat_form.case
                if gender_hint not in ('male', 'female'):
                    gender_hint = pat_form.gender
        form = analyze_name(original, gender_hint if gender_hint in ('male', 'female') else None, case_hint)
        case, gender = form.case, form.gender
        if not _cfg.PRESERVE_GENDER:
            gender = pseudo_gender(form.nominative)

        # Генеруємо нове ім'я (у називному) з тією ж першою літерою; оригінал
        # виключаємо з кандидатів явно — інакше єдина кандидатка на літеру
        # (Марія, Юлія, Ірина…) поверталась як «маска». Seed — від називного
        # відмінка оригіналу (в регістрі оригіналу), тож усі відмінки одного
        # імені дають одну маску: «Петро/Петра/Петром» → «Павло/Павла/Павлом»
        # (v3.1.12; для називного відмінка — як у попередніх версіях)
        first_letter = original[0].lower()
        lemma = _apply_original_case(original, form.nominative)
        seed = get_deterministic_seed(lemma)
        doc_words = _surname.residue_vocabulary()
        new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50,
                                      exclude=form.nominative, forbidden=doc_words)
        masked = decline_name(new_name, case, gender)

        # Страховка: маска ніколи не є тим самим ім'ям (у будь-якому відмінку)
        # і не збігається зі словом документа
        attempts = 0
        while (same_name_forms(masked, original) or same_name_forms(new_name, original)
               or same_name_forms(new_name, form.nominative)
               or masked.lower() in doc_words) and attempts < 10:
            seed = get_deterministic_seed(lemma + str(attempts))
            new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50,
                                          exclude=new_name.lower(), forbidden=doc_words)
            masked = decline_name(new_name, case, gender)
            attempts += 1

    # БАГ #17 FIX: Застосовуємо регістр до masked ПЕРЕД add_to_mapping
    if is_upper:
        masked = masked.upper()
    elif is_capitalize:
        masked = masked.capitalize()
    elif is_lower:
        masked = masked.lower()

    return add_to_mapping(masking_dict, instance_counters, "name", original, masked)
