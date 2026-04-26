#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main masking engine: context-aware text masking and JSON processing.

Extracted from data_masking.py during v2.4.0 refactoring.
"""

import re
from typing import Any, Dict

from masking import constants as _cfg
from masking.context import (
    analyze_number_sign_context, analyze_br_keyword,
    looks_like_pib_line, parse_hybrid_line,
)
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
