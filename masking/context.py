#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Context analysis and line parsing functions.

Extracted from data_masking.py during v2.5.1 refactoring.
"""

import re
from typing import Dict, Optional, Tuple

from masking import constants as _cfg
from masking.helpers import normalize_string, normalize_identifier, is_pib_anchor
from masking.language import looks_like_name


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
    if not line or len(line.strip()) < 10: return False
    line_clean = line.strip()
    line_lower = line_clean.lower()

    if line_clean.startswith('===') or line_clean.startswith('---') or re.match(r'^[А-ЯҐЄІЇA-Z\s]+:\s*$', line_clean): return False

    normalized = normalize_string(line_clean)
    has_rank = any(rank in normalized for rank in _cfg.RANKS_LIST)

    if not has_rank:
        if line_clean.isupper() and len(line_clean.split()) >= 3:
            if not re.search(r'\b\d{10}\b|\b\d{9}\b|[А-ЯA-Z]{2}\s*-?\s*\d{6}\b', line_clean): return False

    exclude_starts = ['відповідно', 'згідно', 'на підставі']
    for start in exclude_starts:
        if line_lower.startswith(start): return False

    if len(line_clean) < 100:
        legal_terms = ['статуту', 'кодексу', 'закону', 'указу']
        for term in legal_terms:
            if term in line_lower: return False

    if has_rank: return True

    words = line_clean.split()
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

    normalized_line = normalize_string(line)
    pib_start_index = -1
    found_rank = None
    found_rank_original_case = None
    rank_position = -1
    rank_matches = []

    for rank_form in _cfg.ALL_RANK_FORMS:
        rank_pattern = rank_form + ' '
        rank_index = normalized_line.find(rank_pattern)
        if rank_index != -1:
            words_before_rank = normalized_line[:rank_index].split()
            rank_word_count = len(rank_form.split())
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

            rank_matches.append((rank_index, rank_form, len(words_before_rank), rank_word_count + additional_words))

    if rank_matches:
        rank_matches.sort(key=lambda x: x[0])
        rank_index, found_rank, rank_position, rank_word_count = rank_matches[0]
        pib_start_index = rank_position + rank_word_count
        rank_words = line.split()[rank_position:rank_position + rank_word_count]
        found_rank_original_case = ' '.join(rank_words) if rank_words else found_rank

    if pib_start_index == -1:
        for i, part in enumerate(parts):
            if is_pib_anchor(part):
                pib_start_index = i
                break

    if pib_start_index == -1: return None, None, identifier

    if found_rank:
        rank = found_rank_original_case if found_rank_original_case else found_rank
    else:
        rank = " ".join(parts[rank_position:pib_start_index]) if 0 <= rank_position < pib_start_index else ""

    pib_words = []
    for word in parts[pib_start_index:pib_start_index + 3]:
        if looks_like_name(word):
            pib_words.append(word.rstrip(',.!?;:'))
        else:
            break
    pib = " ".join(pib_words) if pib_words else None

    if rank and len(rank) > 60: return None, None, identifier
    if rank:
        rank_without_number = re.sub(r'^\d+\.\s*', '', rank)
        if re.search(r'\d{2,}', rank_without_number): return None, None, identifier
    if pib and len(pib.split()) < 2: return None, None, identifier
    if pib:
        pib_lower = pib.lower()
        bad_words = ['статут', 'наказ', 'вимог', 'порушення', 'служби', 'закон', 'указ', 'кодекс', 'положення']
        for bad_word in bad_words:
            if bad_word in pib_lower: return None, None, identifier
    if rank and not pib and not identifier: return None, None, None

    return rank, pib, identifier
