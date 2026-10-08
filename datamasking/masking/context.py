#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Context analysis and line parsing functions.

Extracted from data_masking.py during the package refactoring (v2.5.0).
"""

import re
from typing import Dict, List, Optional, Set, Tuple

from datamasking.masking import constants as _cfg
from datamasking.masking.helpers import normalize_string, normalize_identifier, is_pib_anchor
from datamasking.masking.language import looks_like_name, detect_gender_by_patronymic

# Роздільники слів усередині рядка: будь-які пробільні символи (пробіл, таб,
# NBSP) і «|» таблиць. До 3.1.7 ПІБ із табуляцією або подвійним пробілом
# між словами не маскувався взагалі: parse_hybrid_line стискав пробіли, а
# рушій шукав зібраний ПІБ дослівно в рядку (і не знаходив).
WORD_SEPARATOR_RE = re.compile(r"[\s|]+")

# Канцелярські слова, після яких кандидат на ПІБ — не ПІБ («Наказ
# Міністерства…»). Збіг — лише цілим словом: до 3.1.7 порівнювався підрядок,
# і прізвище «Наказний» або «Законова» відкидало весь рядок
_BAD_WORD_RE = re.compile(
    r"\b(?:наказ(?:у|ом|и|ів|ах)?|статут(?:у|ом|и)?|вимог(?:а|и|у|ам|ами)?|порушенн(?:я|ю|ям|і)|"
    r"служб(?:а|и|у|ою|і)|закон(?:у|ом|и|ів|ах)?|указ(?:у|ом|и|ів)?|кодекс(?:у|ом|и)?|положенн(?:я|ю|ям|і))\b",
    re.IGNORECASE)


def _strip_word(word: str) -> str:
    return word.strip(_cfg.QUOTE_CHARS).strip(',.!?;:')


def has_full_pib(words: List[str]) -> bool:
    """Сильна ознака ПІБ: три слова поспіль схожі на імена, третє — по
    батькові (-ович/-івна … у будь-якому відмінку). Такий рядок маскується
    незалежно від евристик-фільтрів (капс, «Згідно…», «статуту», довжина):
    до 3.1.7 вони відкидали весь рядок разом із ПІБ."""
    clean = [_strip_word(w) for w in words]
    for i in range(len(clean) - 2):
        a, b, c = clean[i], clean[i + 1], clean[i + 2]
        if (a and b and c and a[0].isupper() and b[0].isupper() and c[0].isupper()
                and detect_gender_by_patronymic(c) != 'unknown'
                and looks_like_name(a) and looks_like_name(b) and looks_like_name(c)):
            return True
    return False


def analyze_number_sign_context(text: str, match: re.Match) -> Optional[Dict]:
    """Аналізує контекст після символу №"""
    pos = match.end()
    after_text = text[pos:pos+100]

    # 1. №БР...
    if re.match(r'\s*БР', after_text, re.IGNORECASE):
        br_match = re.match(r'\s*БР[-\s]?(\d+(?:[/-]\d+)*(?:[/-][А-Яа-яA-Za-z]+)*)', after_text, re.IGNORECASE)
        if br_match:
            full_text = text[match.start():match.end() + len(br_match.group(0))]
            return {
                'type': 'br_complex',
                'full_text': full_text,
                'number_part': br_match.group(1),
                'start': match.start(),
                'end': match.end() + len(br_match.group(0))
            }

    # 2. № 123...
    number_match = re.match(r'\s*(\d+(?:[/-]\d+)*(?:[/-][А-Яа-яA-Za-z]+|[А-Яа-яA-Za-z]+)?)', after_text)
    if not number_match:
        return None

    number_text = number_match.group(1)
    full_text = text[match.start():match.end() + len(number_match.group(0))]

    # 3. № 123дск
    if re.search(r'(дск|п|к)$', number_text, re.IGNORECASE):
        if number_text.count('/') >= 2:
            return {'type': 'br_with_slashes', 'full_text': full_text, 'number_part': number_text, 'start': match.start(), 'end': match.end() + len(number_match.group(0))}
        else:
            return {'type': 'br_with_suffix', 'full_text': full_text, 'number_part': number_text, 'start': match.start(), 'end': match.end() + len(number_match.group(0))}

    # 4. № 123/ОКП
    if re.search(r'[А-Яа-яA-Za-z]', number_text):
        return {'type': 'order_with_letters', 'full_text': full_text, 'number_part': number_text, 'start': match.start(), 'end': match.end() + len(number_match.group(0))}

    # 5. № 123
    return {'type': 'order_simple', 'full_text': full_text, 'number_part': number_text, 'start': match.start(), 'end': match.end() + len(number_match.group(0))}

def analyze_br_keyword(text: str, match: re.Match) -> Optional[Dict]:
    """Аналізує контекст після слова БР"""
    pos = match.end()
    after_text = text[pos:pos+100]
    br_match = re.match(r'[-\s]?(\d+(?:[/-]\d+)*(?:дск|п|к)?)', after_text, re.IGNORECASE)
    if br_match:
        return {
            'type': 'br_standalone',
            'full_text': match.group(0) + br_match.group(0),
            'number_part': br_match.group(1),
            'start': match.start(),
            'end': match.end() + len(br_match.group(0))
        }
    return None

def clean_line_before_parsing(line: str) -> str:
    # «|» таблиць — як пробіл (рушій потім знаходить слова ПІБ у рядку з
    # оригінальними роздільниками, див. engine.locate_words)
    line = line.replace('|', ' ')
    # Видаляємо нумерацію пунктів на початку рядка: "20.1.2.1.", "1.", "1.2.", "3.2." тощо
    line = re.sub(r'^\s*(?:\d+\.)+\s*', '', line)
    line = re.sub(r'\d{1,2}[.!]\d{1,2}\.\d{4}', '', line)
    line = re.sub(r'\s+року\s+', ' ', line, flags=re.IGNORECASE)
    line = re.sub(r'\s+', ' ', line)
    return line.strip()

def extract_identifier_from_line(line: str) -> Optional[str]:
    words = line.strip().split()
    if not words: return None
    last_word = words[-1]
    if re.match(r'^[A-Za-zА-Яа-яІіЇїЄєΐё]*\d+[\w\-]*$', last_word):
        return normalize_identifier(last_word)
    return None

def extract_base_rank(full_rank_text: str) -> Tuple[str, str]:
    if not full_rank_text: return full_rank_text, ""
    service_type_phrases = ['медичної служби', 'юстиції']
    status_phrases = ['у відставці', 'в запасі', 'у запасі', 'на пенсії', 'в резерві', 'у резерві']
    full_rank_lower = full_rank_text.lower()
    base_rank = full_rank_text
    additional_parts = []

    for phrase in service_type_phrases:
        if phrase in full_rank_lower:
            phrase_index = full_rank_lower.find(phrase)
            base_rank = full_rank_text[:phrase_index].strip()
            additional_parts.append(full_rank_text[phrase_index:phrase_index + len(phrase)])
            remaining_text = full_rank_text[phrase_index + len(phrase):].strip()
            full_rank_lower = remaining_text.lower()
            full_rank_text = remaining_text
            break

    for phrase in status_phrases:
        if phrase in full_rank_lower:
            if not additional_parts:
                phrase_index = full_rank_text.lower().find(phrase)
                base_rank = full_rank_text[:phrase_index].strip()
            additional_parts.append(full_rank_text[full_rank_text.lower().find(phrase):full_rank_text.lower().find(phrase) + len(phrase)])
            break

    additional = ' '.join(additional_parts) if additional_parts else ""
    return base_rank, additional

def looks_like_pib_line(line: str) -> bool:
    if not line or len(line.strip()) < 6: return False
    line_clean = WORD_SEPARATOR_RE.sub(' ', line).strip()
    line_lower = line_clean.lower()

    if line_clean.startswith('===') or line_clean.startswith('---') or re.match(r'^[А-ЯҐЄІЇA-Z\s]+:\s*$', line_clean): return False

    normalized = normalize_string(line_clean)
    has_rank = any(rank in normalized for rank in _cfg.RANKS_LIST)
    words = line_clean.split()

    # Повний ПІБ (…Прізвище Ім'я По-батькові…) — маскуємо завжди: і в рядку
    # капсом («КОВАЛЬ ТЕТЯНА СЕРГІЇВНА» — підпис), і після «Згідно з рапортом»,
    # і поруч зі «статуту». До 3.1.7 такі рядки лишались відкритими
    if has_full_pib(words): return True

    if not has_rank:
        # Рядок капсом без звання і без ПІБ — заголовок («НАКАЗ КОМАНДИРА…»)
        if line_clean.isupper() and len(words) >= 3:
            if not re.search(r'\b\d{10}\b|\b\d{9}\b|[А-ЯA-Z]{2}\s*-?\s*\d{6}\b', line_clean): return False

    # Звання — сильний контекст: «Відповідно до рапорту старшого сержанта
    # Мазуренка…», «Згідно з наказом №12 лейтенант Петренко…» — типові
    # зачини військових документів, і раніше такі рядки пропускались
    # ЦІЛКОМ (ПІБ лишався відкритим). Канцелярські звороти на місці ПІБ
    # («Наказ Міністерства…») відсікає parse_hybrid_line (bad_words)
    if has_rank: return True

    exclude_starts = ['відповідно', 'згідно', 'на підставі']
    for start in exclude_starts:
        if line_lower.startswith(start): return False

    if len(line_clean) < 100:
        legal_terms = ['статуту', 'кодексу', 'закону', 'указу']
        for term in legal_terms:
            if term in line_lower: return False

    capitalize_sequence = 0
    max_sequence = 0
    for word in words:
        clean_word = word.strip(',.!?;:')
        if (clean_word and len(clean_word) > 2 and clean_word[0].isupper() and looks_like_name(clean_word)):
            capitalize_sequence += 1
            max_sequence = max(max_sequence, capitalize_sequence)
        else:
            capitalize_sequence = 0

    if max_sequence >= 2: return True
    if re.search(r'\b\d{10}\b|\b\d{9}\b|[А-ЯA-Z]{2}\s*-?\s*\d{6}\b', line_clean): return True
    return False

def parse_hybrid_line(line: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    line = line.strip()
    if not line: return None, None, None
    line = clean_line_before_parsing(line)
    identifier = extract_identifier_from_line(line)
    if identifier:
        words = line.split()
        line = ' '.join(words[:-1])
    parts = line.strip().split()
    if not parts: return None, None, identifier
    if parts and parts[0].isdigit(): parts = parts[1:]
    if not parts: return None, None, identifier

    # Нормалізуємо ПОСЛІВНО і пам'ятаємо, якому слову з parts належить кожен
    # символ. Раніше позиція звання рахувалась за словами normalize_string(line),
    # а та розбиває «Г.Г.», «т.ч.» на кілька слів: після таких слів індекс
    # зсувався відносно parts, і за звання бралось сусіднє слово («сержанта
    # Мазуренка», «Коваля»), а ПІБ — не той. Так само зсув давав номер на
    # початку рядка (відкинутий із parts, але не з нормалізованого рядка).
    chunks: List[str] = []
    char_tok: List[int] = []     # символ normalized_line → індекс у parts (-1 — роздільник)
    tok_start: Set[int] = set()  # позиції, з яких починається слово parts
    for i, part in enumerate(parts):
        norm = normalize_string(part)
        if not norm:
            continue
        if chunks:
            char_tok.append(-1)
        tok_start.add(len(char_tok))
        char_tok.extend([i] * len(norm))
        chunks.append(norm)
    normalized_line = ' '.join(chunks)

    pib_start_index = -1
    found_rank = None
    found_rank_original_case = None
    rank_position = -1
    rank_matches = []

    for rank_form in _cfg.ALL_RANK_FORMS:
        rank_pattern = rank_form + ' '
        rank_index = normalized_line.find(rank_pattern)
        # Звання — лише цілими словами: «майора» всередині «генерал-майора»
        # чи «солдата» всередині «Солдатенка» — не звання
        while rank_index != -1:
            end = rank_index + len(rank_form)
            if rank_index in tok_start and char_tok[end] == -1:
                break
            rank_index = normalized_line.find(rank_pattern, rank_index + 1)
        if rank_index == -1:
            continue

        first_tok = char_tok[rank_index]
        last_tok = char_tok[rank_index + len(rank_form) - 1]
        words_after = normalized_line[rank_index + len(rank_pattern):].split()
        additional_words = 0

        if len(words_after) >= 2:
            two_words = ' '.join(words_after[:2])
            if two_words == 'медичної служби':
                additional_words += 2
                words_after = words_after[2:]
        if words_after and words_after[0] == 'юстиції':
            additional_words += 1
            words_after = words_after[1:]
        if words_after and words_after[0] in ['у', 'в', 'на']:
            if len(words_after) > 1 and words_after[1] in ['відставці', 'запасі', 'пенсії', 'резерві']:
                additional_words += 2

        rank_matches.append((rank_index, rank_form, first_tok, last_tok - first_tok + 1 + additional_words))

    if rank_matches:
        rank_matches.sort(key=lambda x: x[0])
        rank_index, found_rank, rank_position, rank_word_count = rank_matches[0]
        pib_start_index = rank_position + rank_word_count
        rank_words = [w.strip(_cfg.QUOTE_CHARS) for w in
                      parts[rank_position:rank_position + rank_word_count]]
        found_rank_original_case = ' '.join(rank_words) if rank_words else found_rank

    # Кандидати на початок ПІБ: після звання (пріоритет), далі — кожен
    # якір у рядку. Раніше брався лише ПЕРШИЙ якір; якщо за ним не було
    # ≥2 слів імені (наприклад, «Сірченко Е.Г.» — уже замаскована фаза
    # ініціалів), увесь рядок кидався і справжній ПІБ далі лишався відкритим.
    starts = []
    if pib_start_index != -1:
        starts.append((pib_start_index, True))
    for i, part in enumerate(parts):
        if i > pib_start_index and is_pib_anchor(part):
            starts.append((i, False))
    if not starts: return None, None, identifier

    if found_rank:
        rank = found_rank_original_case if found_rank_original_case else found_rank
    else:
        rank = ""

    if rank and len(rank) > 60: return None, None, identifier
    if rank:
        rank_without_number = re.sub(r'^\d+\.\s*', '', rank)
        if re.search(r'\d{2,}', rank_without_number): return None, None, identifier

    pib = None
    strong_only = False
    for start, after_rank in starts:
        pib_words = _extract_pib_words(parts, start, after_rank)
        if not pib_words:
            continue
        candidate = " ".join(pib_words)
        if _BAD_WORD_RE.search(candidate):
            # Канцелярський зворот («Наказ Міністерства Оборони…») — не ПІБ.
            # Далі в рядку приймаємо лише сильних кандидатів (після звання
            # або з по батькові), щоб «Міністерства Оборони» не стало ПІБ,
            # а «… капітан Петренко Іван Іванович» у тому ж рядку — маскувалось
            strong_only = True
            continue
        if strong_only and not after_rank and not (
                len(pib_words) == 3 and detect_gender_by_patronymic(pib_words[2]) != 'unknown'):
            continue
        # Одне слово приймаємо ЛИШЕ одразу після звання («рядовий Іванов прибув»,
        # «рядовий Кіт»): звання — сильний контекст, що далі стоїть прізвище
        if len(pib_words) >= 2 or (after_rank and len(pib_words[0]) >= 3):
            pib = candidate
            break

    if rank and not pib and not identifier: return None, None, None

    return rank, pib, identifier


def _rank_word_as_surname(word: str, next_word: Optional[str]) -> bool:
    """«капітан Майор Іван Іванович»: слово-звання з великої літери одразу
    після справжнього звання і перед іменем — це прізвище (Майор, Сотник,
    Полковник — реальні українські прізвища)."""
    clean = word.strip(_cfg.QUOTE_CHARS).rstrip(',.!?;:')
    if len(clean) < 3 or clean.lower() not in _cfg.RANKS_LIST_LOWER:
        return False
    if not (clean[0].isupper() and clean[1:].islower()):
        return False
    if not next_word:
        return False
    return looks_like_name(next_word)


def _extract_pib_words(parts, start: int, after_rank: bool):
    pib_words = []
    for idx, word in enumerate(parts[start:start + 3]):
        clean = word.strip(_cfg.QUOTE_CHARS).rstrip(',.!?;:')
        if looks_like_name(word):
            pib_words.append(clean)
        elif idx == 0 and after_rank and _rank_word_as_surname(
                word, parts[start + 1] if start + 1 < len(parts) else None):
            pib_words.append(clean)
        else:
            break
        # Розділовий знак після слова завершує ПІБ: «Сергійович, ІПН …» —
        # інакше наступне слово з великої приклеювалось, і зібраний рядок
        # не існував у тексті (заміна не спрацьовувала)
        if word.rstrip(_cfg.QUOTE_CHARS)[-1:] in ',.;:!?':
            break
    return pib_words
