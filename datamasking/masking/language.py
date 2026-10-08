#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Language analysis functions: gender detection, grammatical case, declension.

Extracted from data_masking.py during the package refactoring (v2.5.0).
"""

import random
import re
from typing import Optional, Tuple, Set

from datamasking.masking import constants as _cfg
from datamasking.masking.declension import (
    VOCATIVE, analyze_name, analyze_patronymic, decline_name,
)
from datamasking.masking.helpers import get_deterministic_seed


def is_likely_surname_by_case(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    word = word.strip(_cfg.QUOTE_CHARS)
    if not word or len(word) < 3: return False
    letters_only = re.sub(r"[-']", '', word)
    return letters_only.isupper() and len(letters_only) >= 3

def looks_like_name(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    clean_word = word.strip(_cfg.QUOTE_CHARS).rstrip(',.!?;:')
    # validation.min_name_length / max_name_length (за замовчуванням 3 / без меж)
    if len(clean_word) < _cfg.NAME_MIN_LENGTH: return False
    if _cfg.NAME_MAX_LENGTH and len(clean_word) > _cfg.NAME_MAX_LENGTH: return False
    if '.' in clean_word: return False
    # Дієслова 1-2 особи множини (Повідомляємо, Просимо, Надаєте) —
    # ніколи не імена/прізвища
    if clean_word.lower().endswith(('ємо', 'имо', 'емо', 'єте', 'ите', 'ете')):
        return False
    if clean_word.lower() in _cfg.EXCLUDE_WORDS_LOWER: return False
    # Абревіатури (ЗСУ, ТВО, ТРО …) — не частина ПІБ: інакше «ТРО Петренко
    # Іван Іванович» розбиралось як прізвище «ТРО» + ім'я «Петренко» + по
    # батькові «Іван», і справжнє по батькові лишалось відкритим (v3.1.6)
    if clean_word.lower() in _cfg.ABBREVIATION_WHITELIST: return False
    if re.search(r'\d', clean_word): return False
    if clean_word.lower() in _cfg.RANKS_LIST_LOWER: return False
    if clean_word.lower() in ['по', 'про', 'від', 'до', 'за', 'на', 'у', 'в', 'з', 'із']: return False

    # Подвійні прізвища: Петренко-Іванова, Нечуй-Левицький — ОБИДВІ частини
    # мають виглядати як імена (раніше велика літера після дефіса ламала
    # перевірку, а «Петренко-наказу» проходило як одне слово з великої)
    if '-' in clean_word:
        parts = clean_word.split('-')
        if len(parts) == 2 and all(len(p) >= 3 for p in parts):
            return all(looks_like_name(p) for p in parts)
        return False

    if clean_word[0].isupper() and clean_word[1:].islower(): return True
    if clean_word.isupper(): return True

    declension_endings = ['ом', 'ем', 'єм', 'ім', 'ою', 'єю', 'ою', 'у', 'ю', 'а', 'я', 'і', 'ї']
    for ending in declension_endings:
        if len(clean_word) > len(ending) + 2:
            stem = clean_word[:-len(ending)]
            suffix = clean_word[-len(ending):]
            if stem.isupper() and suffix.islower() and suffix == ending:
                return True
    return False

def detect_gender_by_patronymic(patronymic: str) -> str:
    """Рід за по батькові в будь-якому відмінку: -ович/-євич/-ич (Ілліч,
    Кузьмич) — чоловічий, -івна/-ївна — жіночий; з 3.1.12 і знахідний
    («Сергіївну»). Кличний («Петрівно») не вважається по батькові —
    так само закінчуються звичайні слова («Рівно»)."""
    if not patronymic: return 'unknown'
    form = analyze_patronymic(patronymic)
    if form.case == VOCATIVE: return 'unknown'
    return form.gender

def detect_name_case_and_gender(name: str, gender_hint: Optional[str] = None) -> Tuple[str, str]:
    """Відмінок і рід форми імені (див. declension.analyze_name). До 3.1.12 —
    евристика лише за закінченням: «Петра» вважалось жіночим ім'ям у
    називному."""
    if not name: return 'nominative', 'male'
    form = analyze_name(name, gender_hint)
    return form.case, form.gender

def is_easy_to_decline(name: str, gender: str) -> bool:
    if not name: return False
    name_lower = name.lower()
    if name_lower in _cfg.PROBLEMATIC_NAMES: return False
    if re.search(r'([аеєиіїоуюя])\1', name_lower): return False
    if len(name) < 4 or len(name) > 9: return False

    if gender == 'male':
        if name_lower.endswith(('о', 'а', 'й', 'ій', 'р', 'н', 'л', 'к', 'м', 'в', 'т')):
            if name_lower in ['ілля', 'савва', 'лука', 'кузьма', 'фома']: return False
            return True
        return False
    elif gender == 'female':
        if name_lower.endswith(('а', 'я', 'ія')): return True
        return False
    return False

def apply_case_to_name(name: str, case: str, gender: str) -> str:
    """Називний відмінок імені → форма у відмінку *case* (declension.decline_name)."""
    if not name: return name
    return decline_name(name, case, gender)

def normalize_apostrophe(name: str) -> str:
    """Апостроф у масках — ASCII «'»: faker дає «ʼ» (U+02BC), якого немає в
    cp1251, і запис виходу в цьому кодуванні падав (v3.1.8)."""
    return name.replace("ʼ", "'").replace("’", "'")


def same_name_forms(candidate: str, original: str) -> bool:
    """Чи може *candidate* бути тим самим ім'ям, що й *original*, в іншому
    відмінку: «Олег» / «Олега», «Петро» / «Петра», «Юрій» / «Юрія»,
    «Марія» / «Марії». Спільний початок ≥ 3 літер і різниця — лише
    закінчення (≤ 1 літери від коротшого слова). До 3.1.6 порівнювалась
    лише точна форма, і «Олега» маскувалось як «Олег» — справжнє ім'я
    (7 із 15 поширених імен у родовому відмінку)."""
    a, b = (candidate or "").lower(), (original or "").lower()
    if not a or not b:
        return False
    if a == b:
        return True
    common = 0
    for x, y in zip(a, b):
        if x != y:
            break
        common += 1
    return common >= 3 and common >= min(len(a), len(b)) - 1


def generate_easy_name(gender: str, first_letter: str, seed: int, max_attempts: int = 50,
                       exclude: Optional[str] = None, forbidden: Optional[Set[str]] = None) -> str:
    """Синтетичне ім'я на ту саму літеру, що легко відмінюється.

    *exclude* — оригінал (нижній регістр), який НЕ можна повернути: до 3.0.3
    імена, для яких у білому списку була єдина кандидатка на цю літеру
    (Марія, Юлія, Катерина, Тетяна, Ірина), мапились самі на себе.
    Якщо на цю літеру немає інших кандидатів — беремо будь-яку іншу літеру:
    маска важливіша за збіг першої літери.
    """
    random.seed(seed)
    _cfg.fake_uk.seed_instance(seed)
    whitelist = _cfg.GOOD_UKRAINIAN_NAMES_MALE if gender == 'male' else _cfg.GOOD_UKRAINIAN_NAMES_FEMALE
    exclude = (exclude or "").lower()
    # *forbidden* — слова документа (нижній регістр): маска не має збігатися
    # з ім'ям, яке вже стоїть у тексті (v3.1.9)
    forbidden = forbidden or set()
    available = [n for n in whitelist if n[0].lower() == first_letter.lower()
                 and not same_name_forms(n, exclude) and n.lower() not in forbidden]
    if available:
        name = random.choice(available).capitalize()
        return name

    last_name = None
    for attempt in range(max_attempts):
        if gender == 'female': name = _cfg.fake_uk.first_name_female()
        else: name = _cfg.fake_uk.first_name_male()
        name = normalize_apostrophe(name)
        last_name = name
        if name[0].lower() != first_letter: continue
        if same_name_forms(name, exclude) or name.lower() in forbidden: continue
        if is_easy_to_decline(name, gender): return name

    fallback = [n for n in whitelist if not same_name_forms(n, exclude) and n.lower() not in forbidden]
    if fallback: return random.choice(fallback).capitalize()
    return last_name if last_name else normalize_apostrophe(
        _cfg.fake_uk.first_name_female() if gender == 'female' else _cfg.fake_uk.first_name_male())
