#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Language analysis functions: gender detection, grammatical case, declension.

Extracted from data_masking.py during v2.5.0 refactoring.
"""

import random
import re
from typing import Tuple

from masking import constants as _cfg
from masking.helpers import get_deterministic_seed


def is_likely_surname_by_case(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    if not word or len(word) < 3: return False
    letters_only = re.sub(r"[-']", '', word)
    return letters_only.isupper() and len(letters_only) >= 3

def looks_like_name(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    clean_word = word.rstrip(',.!?;:')
    if len(clean_word) < 3: return False
    if '.' in clean_word: return False
    if clean_word in _cfg.EXCLUDE_WORDS or clean_word.lower() in [w.lower() for w in _cfg.EXCLUDE_WORDS]: return False
    if re.search(r'\d', clean_word): return False
    if clean_word.lower() in _cfg.RANKS_LIST: return False
    if clean_word.lower() in ['по', 'про', 'від', 'до', 'за', 'на', 'у', 'в', 'з', 'із']: return False

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
    if not patronymic: return 'unknown'
    patron_lower = patronymic.lower().strip('.,!?;')
    male_endings = ['ович', 'євич', 'ійович', 'йович', 'овича', 'євича', 'ійовича', 'йовича', 'овичу', 'євичу', 'ійовичу', 'йовичу', 'овичем', 'євичем', 'ійовичем', 'йовичем']
    female_endings = ['івна', 'ївна', 'івни', 'ївни', 'івні', 'ївні', 'івною', 'ївною']
    if any(patron_lower.endswith(e) for e in male_endings): return 'male'
    if any(patron_lower.endswith(e) for e in female_endings): return 'female'
    return 'unknown'

def detect_name_case_and_gender(name: str) -> Tuple[str, str]:
    if not name: return 'nominative', 'male'
    name_lower = name.lower().strip('.,!?;')
    if name_lower.endswith(('ом', 'ем', 'єм', 'ім', 'їм')): return 'instrumental', 'male'
    if name_lower.endswith(('у', 'ю')) and not name_lower.endswith(('ою', 'єю', 'ією')): return 'dative', 'male'
    if name_lower.endswith(('а', 'я')) and len(name) > 4:
        common_female_endings = ['ія', 'ла', 'на', 'ра', 'та', 'ка', 'га', 'ва', 'ня', 'ся', 'ша']
        if not any(name_lower.endswith(e) for e in common_female_endings): return 'genitive', 'male'
    if name_lower.endswith(('ією', 'ою', 'єю')): return 'instrumental', 'female'
    if name_lower.endswith(('і', 'ї')) and len(name) > 3: return 'dative', 'female'
    if name_lower.endswith(('ія', 'а', 'я')) and len(name) > 2: return 'nominative', 'female'
    return 'nominative', 'male'

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
    if not name: return name
    name = name.strip()
    if case == 'nominative': return name

    if gender == 'male':
        stem = name
        if name.endswith('о') or name.endswith('а'): stem = name[:-1]
        elif name.endswith('ій'): stem = name[:-2] + 'і'
        elif name.endswith('й'): stem = name[:-1]

        if case == 'genitive':
            if name.endswith('о') or name.endswith('а'): return stem + ('а' if name.endswith('о') else 'и')
            if name.endswith('ій') or name.endswith('й'): return stem + 'я'
            return stem + 'а'
        elif case == 'dative':
            if name.endswith('о'): return stem + 'у'
            if name.endswith('а'): return stem + 'і'
            if name.endswith('ій') or name.endswith('й'): return stem + 'ю'
            return stem + 'у'
        elif case == 'instrumental':
            if name.endswith('о'): return stem + 'ом'
            if name.endswith('а'): return stem + 'ою'
            if name.endswith('ій') or name.endswith('й'): return stem + 'єм'
            return stem + 'ом'

    elif gender == 'female':
        stem = name
        if name.endswith('ія'): stem = name[:-2]
        elif name.endswith(('а', 'я')): stem = name[:-1]

        if case == 'genitive' or case == 'dative':
            if name.endswith('ія'): return stem + 'ії'
            return stem + 'і'
        elif case == 'instrumental':
            if name.endswith('ія'): return stem + 'ією'
            return stem + 'ою'

    return name

def generate_easy_name(gender: str, first_letter: str, seed: int, max_attempts: int = 50) -> str:
    random.seed(seed)
    whitelist = _cfg.GOOD_UKRAINIAN_NAMES_MALE if gender == 'male' else _cfg.GOOD_UKRAINIAN_NAMES_FEMALE
    available = [n for n in whitelist if n[0].lower() == first_letter.lower()]
    if available:
        name = random.choice(available).capitalize()
        return name

    last_name = None
    for attempt in range(max_attempts):
        if gender == 'female': name = _cfg.fake_uk.first_name_female()
        else: name = _cfg.fake_uk.first_name_male()
        last_name = name
        if name[0].lower() != first_letter: continue
        if is_easy_to_decline(name, gender): return name

    if whitelist: return random.choice(whitelist).capitalize()
    return last_name if last_name else (_cfg.fake_uk.first_name_female() if gender == 'female' else _cfg.fake_uk.first_name_male())
