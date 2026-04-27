#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main masking engine: context-aware text masking and JSON processing.

Extracted from data_masking.py during v2.5.0 refactoring.
"""

import random
import re
from typing import Any, Dict

from masking import constants as _cfg
from masking.context import (
    analyze_number_sign_context, analyze_br_keyword,
    looks_like_pib_line, parse_hybrid_line,
)
from masking.helpers import get_deterministic_seed, add_to_mapping
from masking.language import (
    is_likely_surname_by_case, detect_gender_by_patronymic,
)
from masking.mask_personal import (
    mask_ipn, mask_passport_id, mask_military_id,
    mask_surname, mask_name, mask_patronymic,
)
from masking.mask_military import (
    mask_military_unit, mask_order_number, mask_order_number_with_letters,
    mask_br_number, mask_br_number_slash, mask_br_number_complex,
    mask_brigade_number, mask_date, _mask_date_text,
    mask_rank_preserve_case, is_valid_date,
)

_UA_UPPER = "АБВГДЕЖЗІКЛМНОПРСТУФХЦЮЯ"

_SURNAME_RE = r'[А-ЯІЇЄҐ][а-яіїєґ\'ʼ\-]{2,}'
_SURNAME_UPPER_RE = r'[А-ЯІЇЄҐ]{3,}'
_NAME_RE = r'(?:' + _SURNAME_RE + r'|' + _SURNAME_UPPER_RE + r')'

# Прізвище + 2 ініціали: Іванов П.А. / Іванов П. А. / ІВАНОВ П.А.
_RE_NAME_INI2 = re.compile(
    r'(' + _NAME_RE + r')\s+([А-ЯІЇЄҐ])\.\s?([А-ЯІЇЄҐ])\.'
)
# 2 ініціали + Прізвище: П.А. Іванов / П. А. Іванов
_RE_INI2_NAME = re.compile(
    r'(?<![а-яіїєґА-ЯІЇЄҐa-zA-Z])'
    r'([А-ЯІЇЄҐ])\.\s?([А-ЯІЇЄҐ])\.\s?(' + _NAME_RE + r')'
)
# Прізвище + 1 ініціал: Іванов П.
_RE_NAME_INI1 = re.compile(
    r'(' + _NAME_RE + r')\s+([А-ЯІЇЄҐ])\.(?![а-яіїєґА-ЯІЇЄҐa-zA-Z])'
)
# 1 ініціал + Прізвище: П. Іванов
_RE_INI1_NAME = re.compile(
    r'(?<![а-яіїєґА-ЯІЇЄҐa-zA-Z])'
    r'([А-ЯІЇЄҐ])\.\s?(' + _NAME_RE + r')'
)


def _is_surname_candidate(word: str) -> bool:
    """Перевіряє чи слово схоже на прізвище (Title Case або UPPER, >= 3 літер)."""
    if not word or len(word) < 3:
        return False
    clean = word.rstrip(',.!?;:')
    if len(clean) < 3:
        return False
    if clean.lower() in _cfg.ABBREVIATION_WHITELIST:
        return False
    if clean.lower() in [w.lower() for w in _cfg.EXCLUDE_WORDS]:
        return False
    if clean.lower() in _cfg.RANKS_LIST:
        return False
    if clean.isupper() and len(clean) >= 3:
        return True
    if clean[0].isupper() and clean[1:].islower():
        return True
    return False


def _mask_initial(letter: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """Маскує одну літеру ініціала: П -> В (детерміновано)."""
    seed = get_deterministic_seed(letter.lower() + "_initial")
    random.seed(seed)
    candidates = [c for c in _UA_UPPER if c != letter.upper()]
    return random.choice(candidates)


def _mask_initials_pib(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Знаходить ПІБ з ініціалами та маскує їх.

    Шукає ініціали (П.А., К.П., Т. А.), перевіряє сусіда — чи це прізвище.
    Збирає заміни, застосовує з кінця тексту щоб не збити позиції.
    """
    if not _cfg.MASK_NAMES:
        return text

    replacements = []  # (start, end, new_text)

    def _do(regex, handler):
        for m in regex.finditer(text):
            r = handler(m)
            if r:
                replacements.append(r)

    # Прізвище + 2 ініціали: Іванов К.П. / Іванов К. П.
    def _name_ini2(m):
        surname, i1, i2 = m.group(1), m.group(2), m.group(3)
        if not _is_surname_candidate(surname):
            return None
        ms = mask_surname(surname, masking_dict, instance_counters)
        mi1 = _mask_initial(i1, masking_dict, instance_counters)
        mi2 = _mask_initial(i2, masking_dict, instance_counters)
        has_space = f"{i1}. {i2}." in m.group(0)
        ini = f"{mi1}. {mi2}." if has_space else f"{mi1}.{mi2}."
        return (m.start(), m.end(), f"{ms} {ini}")

    # 2 ініціали + Прізвище: К.П. Іванов / К. П. Іванов
    def _ini2_name(m):
        i1, i2, surname = m.group(1), m.group(2), m.group(3)
        if not _is_surname_candidate(surname):
            return None
        ms = mask_surname(surname, masking_dict, instance_counters)
        mi1 = _mask_initial(i1, masking_dict, instance_counters)
        mi2 = _mask_initial(i2, masking_dict, instance_counters)
        has_space = f"{i1}. {i2}." in m.group(0)
        ini = f"{mi1}. {mi2}." if has_space else f"{mi1}.{mi2}."
        return (m.start(), m.end(), f"{ini} {ms}")

    # Прізвище + 1 ініціал: Іванов П.
    def _name_ini1(m):
        surname, i1 = m.group(1), m.group(2)
        if not _is_surname_candidate(surname):
            return None
        ms = mask_surname(surname, masking_dict, instance_counters)
        mi1 = _mask_initial(i1, masking_dict, instance_counters)
        return (m.start(), m.end(), f"{ms} {mi1}.")

    # 1 ініціал + Прізвище: П. Іванов
    def _ini1_name(m):
        i1, surname = m.group(1), m.group(2)
        if not _is_surname_candidate(surname):
            return None
        ms = mask_surname(surname, masking_dict, instance_counters)
        mi1 = _mask_initial(i1, masking_dict, instance_counters)
        return (m.start(), m.end(), f"{mi1}. {ms}")

    _do(_RE_NAME_INI2, _name_ini2)
    _do(_RE_INI2_NAME, _ini2_name)
    _do(_RE_NAME_INI1, _name_ini1)
    _do(_RE_INI1_NAME, _ini1_name)

    # Довші патерни мають пріоритет; видаляємо перекриття
    replacements.sort(key=lambda x: (x[1] - x[0]), reverse=True)
    kept = []
    for r in replacements:
        if not any(r[0] < k[1] and r[1] > k[0] for k in kept):
            kept.append(r)

    # Заміни з кінця тексту
    kept.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_text in kept:
        text = text[:start] + new_text + text[end:]

    return text


def normalize_broken_ranks(text: str) -> str:
    """
    Нормалізує розірвані звання у тексті (Bug Fix #15).

    Звання може бути розірване переносом рядка в документах:
    - "старшого\nсержанта" -> "старшого сержанта"
    """
    # Беремо тільки складені звання (ті, що містять пробіл)
    multi_word_ranks = [r for r in _cfg.ALL_RANK_FORMS if ' ' in r]

    if not multi_word_ranks:
        return text

    # Створюємо великий паттерн, замінюючи пробіли на \s+ (будь-який пробільний символ, включно з \n)
    patterns = [re.escape(r).replace(r'\ ', r'\s+') for r in multi_word_ranks]
    full_pattern = r'(?i)\b(' + '|'.join(patterns) + r')\b'

    def replace_match(match):
        # Замінюємо всі пробільні символи (включаючи \n) на один звичайний пробіл
        return re.sub(r'\s+', ' ', match.group(0))

    return re.sub(full_pattern, replace_match, text)


def mask_text_context_aware(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Головна функція маскування тексту з контекстним аналізом.

    Це центральна функція всього процесу маскування. Вона координує роботу
    всіх інших функцій та забезпечує правильний порядок обробки даних.
    """
    # === ШАГ 0: Нормалізація розірваних звань
    text = normalize_broken_ranks(text)

    # === ШАГ 0.5: ПІБ з ініціалами (Іванов П.А., П. Іванов тощо)
    # Запускаємо ДО основного парсера, щоб ініціали не плутали looks_like_pib_line
    text = _mask_initials_pib(text, masking_dict, instance_counters)

    items_to_mask = []
    items_to_skip = []

    if not _cfg.MASK_DATES:
        for match in re.finditer(_cfg.UKRAINIAN_DATE_PATTERN, text):
            items_to_skip.append({'start': match.start(), 'end': match.end(), 'text': match.group(0), 'reason': 'full_date', 'type': 'date'})

    legal_patterns = [
        r'(стате[йї]|стать[іеюя])\s+(\d+(?:\s*,\s*\d+)*)',
        r'(пункт[уаиіеє])\s+(\d+(?:\s*,\s*\d+)*)',
        r'(частин[аиюіеє])\s+(\d+(?:\s*,\s*\d+)*)',
        r'(розділ[уаіеє])\s+(\d+(?:\s*,\s*\d+)*)',
    ]
    for pattern in legal_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            term, numbers_text = match.group(1), match.group(2)
            base_pos = match.start(2)
            for num_match in re.finditer(r'\d+', numbers_text):
                items_to_skip.append({'start': base_pos + num_match.start(), 'end': base_pos + num_match.end(), 'text': num_match.group(0), 'reason': 'legal', 'type': 'legal_number', 'context': term})

    if _cfg.MASK_ORDERS or _cfg.MASK_BR_NUMBERS:
        for match in re.finditer(r'№', text):
            result = analyze_number_sign_context(text, match)
            if result: items_to_mask.append(result)

    if _cfg.MASK_BR_NUMBERS:
        for match in re.finditer(r'\bБР\b', text, re.IGNORECASE):
            result = analyze_br_keyword(text, match)
            if result:
                skip = any(result['start'] < item['end'] and result['end'] > item['start'] for item in items_to_skip)
                skip = skip or any(result['start'] < item['end'] and result['end'] > item['start'] for item in items_to_mask)
                if not skip: items_to_mask.append(result)

    for item_type, flag, pattern in [
        ('ipn', _cfg.MASK_IPN, r'\b\d{10}\b'),
        ('passport_id', _cfg.MASK_PASSPORT, r'\b\d{9}\b'),
        ('military_id', _cfg.MASK_MILITARY_ID, r'\b[A-ZА-Я]{2}[\s-]?\d{6}\b'),
        ('military_unit', _cfg.MASK_UNITS, r'\b[А-ЯA-Z]\d{4}\b')
    ]:
        if flag:
            for match in re.finditer(pattern, text, re.IGNORECASE if item_type == 'military_id' else 0):
                skip = any(match.start() >= item['start'] and match.end() <= item['end'] for item in items_to_skip)
                skip = skip or any(match.start() < item['end'] and match.end() > item['start'] for item in items_to_mask)
                if not skip: items_to_mask.append({'type': item_type, 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})

    if _cfg.MASK_BRIGADES:
        for match in _cfg.COMPILED_PATTERNS["brigade_number"].finditer(text):
            skip = any(match.start() >= item['start'] and match.end() <= item['end'] for item in items_to_skip)
            skip = skip or any(match.start() < item['end'] and match.end() > item['start'] for item in items_to_mask)
            if not skip: items_to_mask.append({'type': 'brigade_number', 'full_text': match.group(0), 'number_part': match.group(1), 'start': match.start(), 'end': match.end()})

    if _cfg.MASK_DATES:
        for match in _cfg.COMPILED_PATTERNS["date"].finditer(text):
            if is_valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3))):
                skip = any(match.start() >= item['start'] and match.end() <= item['end'] for item in items_to_skip)
                skip = skip or any(match.start() < item['end'] and match.end() > item['start'] for item in items_to_mask)
                if not skip: items_to_mask.append({'type': 'date', 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})

        # Text dates: "06" жовтня 2025 року
        if "date_text" not in masking_dict["mappings"]:
            masking_dict["mappings"]["date_text"] = {}
        for match in _cfg.DATE_TEXT_PATTERN.finditer(text):
            skip = any(match.start() >= item['start'] and match.end() <= item['end'] for item in items_to_skip)
            skip = skip or any(match.start() < item['end'] and match.end() > item['start'] for item in items_to_mask)
            if not skip:
                items_to_mask.append({'type': 'date_text', 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})

    items_to_mask.sort(key=lambda x: x['start'], reverse=True)

    for item in items_to_mask:
        masked = ""
        if text[item['start']:item['end']] != item['full_text']: continue
        if item['type'] == 'ipn': masked = mask_ipn(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'passport_id': masked = mask_passport_id(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'military_id': masked = mask_military_id(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'military_unit': masked = mask_military_unit(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'brigade_number':
            masked = mask_brigade_number(item['full_text'], masking_dict, instance_counters)
            text = text[:item['start']] + masked + text[item['end']:]
            continue
        elif item['type'] == 'date':
            masked = mask_date(item['full_text'], masking_dict, instance_counters)
            text = text[:item['start']] + masked + text[item['end']:]
            continue
        elif item['type'] == 'date_text':
            masked = _mask_date_text(item['full_text'], masking_dict, instance_counters)
            text = text[:item['start']] + masked + text[item['end']:]
            continue
        elif item['type'] == 'order_simple':
            masked = mask_order_number(item['number_part'], masking_dict, instance_counters)
            new_full = item['full_text'].replace(item['number_part'], masked, 1)
            text = text[:item['start']] + new_full + text[item['end']:]
            continue
        elif item['type'] == 'order_with_letters':
            masked = mask_order_number_with_letters(item['number_part'], masking_dict, instance_counters)
            new_full = item['full_text'].replace(item['number_part'], masked, 1)
            text = text[:item['start']] + new_full + text[item['end']:]
            continue
        elif item['type'] in ['br_complex', 'br_with_slashes', 'br_with_suffix', 'br_standalone']:
            masked = mask_br_number(item['full_text'], masking_dict, instance_counters)
            text = text[:item['start']] + masked + text[item['end']:]
            continue

        if masked: text = text[:item['start']] + masked + text[item['end']:]

    lines = text.split('\n')
    masked_lines = []
    for line in lines:
        if not looks_like_pib_line(line):
            masked_lines.append(line)
            continue

        iteration = 0
        current_line_for_parsing = line
        final_line = line

        while iteration < 10:
            rank, pib, identifier = parse_hybrid_line(current_line_for_parsing)
            if not pib: break
            if rank and not pib:
                current_line_for_parsing = current_line_for_parsing.replace(rank, "___SKIP_RANK___", 1)
                iteration += 1
                continue

            if rank and _cfg.MASK_RANKS:
                masked_rank_val = mask_rank_preserve_case(rank, masking_dict, instance_counters)
                final_line = final_line.replace(rank, masked_rank_val, 1)
                current_line_for_parsing = current_line_for_parsing.replace(rank, "___RANK_MASKED___", 1)

            if pib and _cfg.MASK_NAMES:
                parts = pib.split()
                if len(parts) >= 2:
                    if is_likely_surname_by_case(parts[1]):
                        name, surname = parts[0], parts[1]
                        patronymic = parts[2] if len(parts) >= 3 else ""
                        masked_surname = mask_surname(surname, masking_dict, instance_counters)
                        masked_name = mask_name(name, masking_dict, instance_counters, gender_hint=detect_gender_by_patronymic(patronymic) if patronymic else None, patronymic_hint=patronymic)
                        masked_pib_str = f"{masked_name} {masked_surname}"
                    else:
                        surname, name = parts[0], parts[1]
                        patronymic = parts[2] if len(parts) >= 3 else ""
                        masked_surname = mask_surname(surname, masking_dict, instance_counters)
                        masked_name = mask_name(name, masking_dict, instance_counters, gender_hint=detect_gender_by_patronymic(patronymic) if patronymic else None, patronymic_hint=patronymic)
                        masked_pib_str = f"{masked_surname} {masked_name}"

                    if patronymic:
                        gender = detect_gender_by_patronymic(patronymic) if patronymic else 'male'
                        masked_patronymic = mask_patronymic(patronymic, gender, masking_dict, instance_counters)
                        masked_pib_str += f" {masked_patronymic}"

                    final_line = final_line.replace(pib, masked_pib_str, 1)
                    current_line_for_parsing = current_line_for_parsing.replace(pib, "___PIB_MASKED___", 1)
            iteration += 1
        masked_lines.append(final_line)

    return '\n'.join(masked_lines)

def mask_json_recursive(data: Any, masking_dict: Dict, instance_counters: Dict) -> Any:
    if isinstance(data, dict): return {key: mask_json_recursive(value, masking_dict, instance_counters) for key, value in data.items()}
    elif isinstance(data, list): return [mask_json_recursive(item, masking_dict, instance_counters) for item in data]
    elif isinstance(data, str): return mask_text_wrapper(data, masking_dict, instance_counters)
    else: return data

def mask_text_wrapper(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    return mask_text_context_aware(text, masking_dict, instance_counters)
