#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main masking engine: context-aware text masking and JSON processing.

Extracted from data_masking.py during the package refactoring (v2.5.0).
"""

import random
import re
from typing import Any, Dict

from datamasking.masking import constants as _cfg
from datamasking.masking.context import (
    analyze_number_sign_context, analyze_br_keyword,
    looks_like_pib_line, parse_hybrid_line,
)
from datamasking.masking.helpers import get_deterministic_seed, add_to_mapping
from datamasking.masking.language import (
    is_likely_surname_by_case, detect_gender_by_patronymic,
)
from datamasking.masking.mask_personal import (
    mask_ipn, mask_passport_id, mask_military_id,
    mask_surname, mask_name, mask_patronymic,
)
from datamasking.masking.mask_military import (
    mask_military_unit, mask_order_number, mask_order_number_with_letters,
    mask_br_number, mask_br_number_slash, mask_br_number_complex,
    mask_brigade_number, mask_date, _mask_date_text,
    mask_rank_preserve_case, is_valid_date,
)

_UA_UPPER = "АБВГҐДЕЖЗІЙКЛМНОПРСТУФХЦЧШЩЮЯЄІЇҐ"

_SURNAME_RE = r'[А-ЯІЇЄҐ][а-яіїєґ\'ʼ\-]{2,}'
_SURNAME_UPPER_RE = r'[А-ЯІЇЄҐ]{3,}'
_NAME_RE = r'(?:' + _SURNAME_RE + r'|' + _SURNAME_UPPER_RE + r')'

# Пробіл у межах рядка (НЕ \s — щоб ініціали не склеювались
# з наступним рядком через \n)
_SP = r'[  ]'

# Прізвище + 2 ініціали: Іванов П.А. / Іванов П. А. / ІВАНОВ П.А.
_RE_NAME_INI2 = re.compile(
    r'(' + _NAME_RE + r')' + _SP + r'+([А-ЯІЇЄҐ])\.' + _SP + r'?([А-ЯІЇЄҐ])\.'
)
# 2 ініціали + Прізвище: П.А. Іванов / П. А. Іванов
_RE_INI2_NAME = re.compile(
    r'(?<![а-яіїєґА-ЯІЇЄҐa-zA-Z])'
    r'([А-ЯІЇЄҐ])\.' + _SP + r'?([А-ЯІЇЄҐ])\.' + _SP + r'?(' + _NAME_RE + r')'
)
# Прізвище + 1 ініціал: Іванов П.
_RE_NAME_INI1 = re.compile(
    r'(' + _NAME_RE + r')' + _SP + r'+([А-ЯІЇЄҐ])\.(?![а-яіїєґА-ЯІЇЄҐa-zA-Z])'
)
# 1 ініціал + Прізвище: П. Іванов
_RE_INI1_NAME = re.compile(
    r'(?<![а-яіїєґА-ЯІЇЄҐa-zA-Z])'
    r'([А-ЯІЇЄҐ])\.' + _SP + r'?(' + _NAME_RE + r')'
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
    if clean.lower() in _cfg.EXCLUDE_WORDS_LOWER:
        return False
    if clean.lower() in _cfg.RANKS_LIST_LOWER:
        return False
    if clean.isupper() and len(clean) >= 3:
        return True
    if clean[0].isupper() and clean[1:].islower():
        return True
    return False


def _mask_initial(letter: str, context: str = "") -> str:
    """Маскує одну літеру ініціала: П -> В (детерміновано, з контекстом прізвища)."""
    seed = get_deterministic_seed(letter.lower() + "_initial_" + context.lower())
    random.seed(seed)
    candidates = [c for c in _UA_UPPER if c != letter.upper()]
    return random.choice(candidates)


# Службові скорочення з крапкою. Якщо такий токен стоїть безпосередньо
# перед "ініціалом + прізвищем" (П. Іванов), то перша літера — це
# буквений підпункт ("п. В. Петренко" = пункт В), а не ім'я.
_NON_INITIAL_LEFT = frozenset({
    'п', 'пп', 'ч', 'чч', 'ст', 'стст', 'абз', 'гл', 'розд', 'р', 'рр',
    'арт', 'н', 'прим', 'дод', 'табл', 'мал', 'рис',
})


def _left_token(text: str, pos: int) -> str:
    """Останнє слово (без розділових) безпосередньо ліворуч від pos."""
    left = text[:pos].rstrip()
    if not left:
        return ""
    tok = left.split()[-1]
    return tok.rstrip('.').lower()


def _mask_initials_pib(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Знаходить ПІБ з ініціалами та маскує їх.

    Шукає ініціали (П.А., К.П., Т. А.), перевіряє сусіда — чи це прізвище.
    Фаза 1 збирає кандидатів без побічних ефектів, фаза 2 (після зняття
    перекриттів, у порядку документа) пише mapping — інакше instance
    tracking розійдеться з порядком входжень і unmask поверне не те.
    """
    if not _cfg.MASK_NAMES:
        return text

    # Фаза 1: збір кандидатів (start, end, surname, [ініціали], has_space, ini_first)
    candidates = []

    for m in _RE_NAME_INI2.finditer(text):
        surname, i1, i2 = m.group(1), m.group(2), m.group(3)
        if _is_surname_candidate(surname):
            has_space = f"{i1}. {i2}." in m.group(0)
            candidates.append((m.start(), m.end(), surname, [i1, i2], has_space, False))

    for m in _RE_INI2_NAME.finditer(text):
        i1, i2, surname = m.group(1), m.group(2), m.group(3)
        if _is_surname_candidate(surname) and _left_token(text, m.start()) not in _NON_INITIAL_LEFT:
            has_space = f"{i1}. {i2}." in m.group(0)
            candidates.append((m.start(), m.end(), surname, [i1, i2], has_space, True))

    for m in _RE_NAME_INI1.finditer(text):
        surname, i1 = m.group(1), m.group(2)
        if _is_surname_candidate(surname):
            candidates.append((m.start(), m.end(), surname, [i1], False, False))

    for m in _RE_INI1_NAME.finditer(text):
        i1, surname = m.group(1), m.group(2)
        if _is_surname_candidate(surname) and _left_token(text, m.start()) not in _NON_INITIAL_LEFT:
            candidates.append((m.start(), m.end(), surname, [i1], False, True))

    # Довші патерни мають пріоритет; знімаємо перекриття
    candidates.sort(key=lambda x: (x[1] - x[0]), reverse=True)
    kept = []
    for c in candidates:
        if not any(c[0] < k[1] and c[1] > k[0] for k in kept):
            kept.append(c)

    # Фаза 2: у порядку документа маскуємо, записуємо mapping
    # і збираємо результат сегментами (O(n))
    masking_dict["mappings"].setdefault("initials", {})
    kept.sort(key=lambda x: x[0])
    segments = []
    prev_end = 0
    for start, end, surname, initials, has_space, ini_first in kept:
        ms = mask_surname(surname, masking_dict, instance_counters)
        sep = '. ' if has_space else '.'
        orig_ini = sep.join(initials) + '.'
        masked_letters = [_mask_initial(i, surname) for i in initials]
        masked_ini = sep.join(masked_letters) + '.'
        # Зберігаємо у mapping — інакше unmask не зможе відновити ініціали
        masked_ini = add_to_mapping(masking_dict, instance_counters,
                                    "initials", orig_ini, masked_ini)
        new_text = f"{masked_ini} {ms}" if ini_first else f"{ms} {masked_ini}"
        segments.append(text[prev_end:start])
        segments.append(new_text)
        prev_end = end

    if segments:
        segments.append(text[prev_end:])
        text = ''.join(segments)

    return text


_BROKEN_RANKS_RE = None

def _get_broken_ranks_re():
    global _BROKEN_RANKS_RE
    if _BROKEN_RANKS_RE is None:
        multi_word_ranks = [r for r in _cfg.ALL_RANK_FORMS if ' ' in r]
        if multi_word_ranks:
            patterns = [re.escape(r).replace(r'\ ', r'\s+') for r in multi_word_ranks]
            _BROKEN_RANKS_RE = re.compile(r'(?i)\b(' + '|'.join(patterns) + r')\b')
    return _BROKEN_RANKS_RE

def normalize_broken_ranks(text: str) -> str:
    """
    Нормалізує розірвані звання у тексті (Bug Fix #15).

    Звання може бути розірване переносом рядка в документах:
    - "старшого\nсержанта" -> "старшого сержанта"
    """
    pattern = _get_broken_ranks_re()
    if pattern is None:
        return text

    def replace_match(match):
        return re.sub(r'\s+', ' ', match.group(0))

    return pattern.sub(replace_match, text)


# Лапки (відкриваючі/закриваючі будь-якого стилю) для пошуку значень у лапках
_QUOTED_RE = re.compile(r'([«"„“\'])([^«»"„“”\']{1,60})([»"”“\'])')


def _mask_quoted_ranks(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує звання, взяте в лапки як самостійне значення: «молодший сержант».

    Основний парсер маскує звання лише в парі з ПІБ. Але у форматах-логах
    звання йде як окреме значення в лапках без ПІБ. Тут маскуємо ТІЛЬКИ якщо
    весь вміст лапок — рівно відома форма звання (ALL_RANK_FORMS), щоб не
    зачепити довільний текст. Лапки лишаються на місці; unmask відновлює
    звання зі словника rank як звичайно.
    """
    if not _cfg.MASK_RANKS:
        return text

    # Вже використані маски звань — щоб не маскувати результат повторно
    already = {
        info["masked_as"].lower()
        for info in masking_dict["mappings"].get("rank", {}).values()
        if isinstance(info, dict) and "masked_as" in info
    }

    segments = []
    prev_end = 0
    for m in _QUOTED_RE.finditer(text):
        inner = m.group(2).strip()
        low = inner.lower()
        if low not in _cfg.ALL_RANK_FORMS_LOWER or low in already:
            continue
        masked = mask_rank_preserve_case(inner, masking_dict, instance_counters)
        if masked == inner:
            continue
        already.add(masked.lower())
        segments.append(text[prev_end:m.start()])
        segments.append(m.group(1) + masked + m.group(3))
        prev_end = m.end()

    if segments:
        segments.append(text[prev_end:])
        text = ''.join(segments)
    return text


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

    # Обхід у порядку документа: instance tracking збігається з порядком
    # входжень (потрібно для unmask), а заміни збираються сегментами —
    # O(n) замість квадратичного text[:i] + ... + text[j:] на кожен елемент
    items_to_mask.sort(key=lambda x: x['start'])

    segments = []
    prev_end = 0
    for item in items_to_mask:
        if item['start'] < prev_end: continue  # перекриття — пропускаємо
        if text[item['start']:item['end']] != item['full_text']: continue

        replacement = None
        if item['type'] == 'ipn': replacement = mask_ipn(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'passport_id': replacement = mask_passport_id(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'military_id': replacement = mask_military_id(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'military_unit': replacement = mask_military_unit(item['number_part'], masking_dict, instance_counters)
        elif item['type'] == 'brigade_number':
            replacement = mask_brigade_number(item['full_text'], masking_dict, instance_counters)
        elif item['type'] == 'date':
            replacement = mask_date(item['full_text'], masking_dict, instance_counters)
        elif item['type'] == 'date_text':
            replacement = _mask_date_text(item['full_text'], masking_dict, instance_counters)
        elif item['type'] == 'order_simple':
            masked = mask_order_number(item['number_part'], masking_dict, instance_counters)
            replacement = item['full_text'].replace(item['number_part'], masked, 1)
        elif item['type'] == 'order_with_letters':
            masked = mask_order_number_with_letters(item['number_part'], masking_dict, instance_counters)
            replacement = item['full_text'].replace(item['number_part'], masked, 1)
        elif item['type'] in ['br_complex', 'br_with_slashes', 'br_with_suffix', 'br_standalone']:
            replacement = mask_br_number(item['full_text'], masking_dict, instance_counters)

        if replacement is None or replacement == "":
            continue
        segments.append(text[prev_end:item['start']])
        segments.append(replacement)
        prev_end = item['end']

    if segments:
        segments.append(text[prev_end:])
        text = ''.join(segments)

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
                    # Не маскуємо повторно те, що вже є маскою (наприклад,
                    # прізвище, замасковане фазою ініціалів) — вкладену маску
                    # unmask не зможе розкрутити за один прохід
                    already_masked = {
                        info["masked_as"].lower()
                        for cat in ("surname", "name")
                        for info in masking_dict["mappings"].get(cat, {}).values()
                        if isinstance(info, dict) and "masked_as" in info
                    }
                    if any(p.lower() in already_masked for p in parts[:2]):
                        current_line_for_parsing = current_line_for_parsing.replace(pib, "___PIB_MASKED___", 1)
                        iteration += 1
                        continue
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

    text = '\n'.join(masked_lines)

    # Звання-значення в лапках без ПІБ («молодший сержант») — після
    # основного циклу, з пропуском уже замаскованих форм
    text = _mask_quoted_ranks(text, masking_dict, instance_counters)

    return text

def mask_json_recursive(data: Any, masking_dict: Dict, instance_counters: Dict) -> Any:
    if isinstance(data, dict): return {key: mask_json_recursive(value, masking_dict, instance_counters) for key, value in data.items()}
    elif isinstance(data, list): return [mask_json_recursive(item, masking_dict, instance_counters) for item in data]
    elif isinstance(data, str): return mask_text_wrapper(data, masking_dict, instance_counters)
    else: return data

def mask_text_wrapper(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    return mask_text_context_aware(text, masking_dict, instance_counters)
