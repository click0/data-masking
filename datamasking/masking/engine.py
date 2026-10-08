#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main masking engine: context-aware text masking and JSON processing.

Extracted from data_masking.py during the package refactoring (v2.5.0).
"""

import json
import random
import re
from typing import Any, Dict, List, Optional, Pattern, Tuple

from datamasking.masking import constants as _cfg
from datamasking.masking import surname as _surname
from datamasking.masking import custom as _custom
from datamasking.masking.context import (
    analyze_number_sign_context, analyze_br_keyword,
    looks_like_pib_line, parse_hybrid_line, WORD_SEPARATOR_RE,
)
from datamasking.masking.helpers import get_deterministic_seed, add_to_mapping
from datamasking.masking.language import (
    is_likely_surname_by_case, detect_gender_by_patronymic, looks_like_name,
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

# Прізвище у Title Case, зокрема подвійне з великої після дефіса
# (Петренко-Іванова, Нечуй-Левицький)
_SURNAME_RE = r'[А-ЯІЇЄҐ][а-яіїєґ\'ʼ’]{2,}(?:-[А-ЯІЇЄҐ]?[а-яіїєґ\'ʼ’]{2,})?'
_SURNAME_UPPER_RE = r'[А-ЯІЇЄҐ]{3,}'
_NAME_RE = r'(?:' + _SURNAME_RE + r'|' + _SURNAME_UPPER_RE + r')'

# Пробіл у межах рядка (НЕ \s — щоб ініціали не склеювались
# з наступним рядком через \n)
_SP = r'[  ]'

# Прізвище + 2 ініціали: Іванов П.А. / Іванов П. А. / ІВАНОВ П.А. / Іванов П.А (без
# останньої крапки — лише якщо далі не літера)
_RE_NAME_INI2 = re.compile(
    r'(' + _NAME_RE + r')' + _SP + r'+([А-ЯІЇЄҐ])\.' + _SP + r'?([А-ЯІЇЄҐ])(?:\.|(?![а-яіїєґА-ЯІЇЄҐa-zA-Z\'ʼ’]))'
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
    """Перевіряє чи слово схоже на прізвище (Title Case або UPPER, >= 3 літер;
    подвійне — кожна частина окремо: Нечуй-Левицький)."""
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
    parts = [p for p in clean.split('-') if p]
    if not parts:
        return False
    for part in parts:
        letters = part.replace("'", "").replace("ʼ", "").replace("’", "")
        if not letters:
            return False
        if letters.isupper() and len(letters) >= 2:
            continue
        if letters[0].isupper() and letters[1:].islower():
            continue
        return False
    return True


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
    """Останнє слово (без розділових) безпосередньо ліворуч від pos.
    «р.»/«рр.» одразу після числа («2024 р.») — рік, не підпункт: повертає ""."""
    left = text[:pos].rstrip()
    if not left:
        return ""
    words = left.split()
    tok = words[-1].rstrip('.').lower()
    if tok in ('р', 'рр') and len(words) >= 2 and re.search(r'\d$', words[-2]):
        return ""
    return tok


def _mask_initials_pib(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Знаходить ПІБ з ініціалами та маскує їх.

    Шукає ініціали (П.А., К.П., Т. А.), перевіряє сусіда — чи це прізвище.
    Фаза 1 збирає кандидатів без побічних ефектів, фаза 2 (після зняття
    перекриттів, у порядку документа) пише mapping — інакше instance
    tracking розійдеться з порядком входжень і unmask поверне не те.
    """
    mask_surnames = _cfg.MASK_SURNAMES
    mask_initials = _cfg.MASK_NAMES or _cfg.MASK_PATRONYMICS
    if not (mask_surnames or mask_initials):
        return text

    # Фаза 1: збір кандидатів (start, end, surname, [ініціали], has_space, ini_first)
    candidates = []

    for m in _RE_NAME_INI2.finditer(text):
        surname, i1, i2 = m.group(1), m.group(2), m.group(3)
        if _is_surname_candidate(surname):
            has_space = f"{i1}. {i2}" in m.group(0)
            # «Петренко О.П» без останньої крапки — маска теж без неї
            candidates.append((m.start(), m.end(), surname, [i1, i2], has_space, False,
                               m.group(0).endswith('.')))

    for m in _RE_INI2_NAME.finditer(text):
        i1, i2, surname = m.group(1), m.group(2), m.group(3)
        if _is_surname_candidate(surname) and _left_token(text, m.start()) not in _NON_INITIAL_LEFT:
            has_space = f"{i1}. {i2}." in m.group(0)
            candidates.append((m.start(), m.end(), surname, [i1, i2], has_space, True, True))

    for m in _RE_NAME_INI1.finditer(text):
        surname, i1 = m.group(1), m.group(2)
        if _is_surname_candidate(surname):
            candidates.append((m.start(), m.end(), surname, [i1], False, False, True))

    for m in _RE_INI1_NAME.finditer(text):
        i1, surname = m.group(1), m.group(2)
        if _is_surname_candidate(surname) and _left_token(text, m.start()) not in _NON_INITIAL_LEFT:
            candidates.append((m.start(), m.end(), surname, [i1], False, True, True))

    # Довші патерни мають пріоритет; знімаємо перекриття
    candidates.sort(key=lambda x: (x[1] - x[0]), reverse=True)
    kept: List[Tuple[int, int, str, List[str], bool, bool, bool]] = []
    for c in candidates:
        if not any(c[0] < k[1] and c[1] > k[0] for k in kept):
            kept.append(c)

    # Фаза 2: у порядку документа маскуємо, записуємо mapping
    # і збираємо результат сегментами (O(n))
    masking_dict["mappings"].setdefault("initials", {})
    kept.sort(key=lambda x: x[0])
    segments = []
    prev_end = 0
    for start, end, surname, initials, has_space, ini_first, final_dot in kept:
        ms = mask_surname(surname, masking_dict, instance_counters) if mask_surnames else surname
        sep = '. ' if has_space else '.'
        tail = '.' if final_dot else ''
        orig_ini = sep.join(initials) + tail
        if mask_initials:
            masked_letters = [_mask_initial(i, surname) for i in initials]
            masked_ini = sep.join(masked_letters) + tail
            # Зберігаємо у mapping — інакше unmask не зможе відновити ініціали
            masked_ini = add_to_mapping(masking_dict, instance_counters,
                                        "initials", orig_ini, masked_ini)
        else:
            masked_ini = orig_ini
        new_text = f"{masked_ini} {ms}" if ini_first else f"{ms} {masked_ini}"
        segments.append(text[prev_end:start])
        segments.append(new_text)
        prev_end = end

    if segments:
        segments.append(text[prev_end:])
        text = ''.join(segments)

    return text


_BROKEN_RANKS_RE: Optional[Pattern[str]] = None

def _get_broken_ranks_re() -> Optional[Pattern[str]]:
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
        # Лише розрив переносом рядка; таб чи подвійний пробіл між словами
        # звання лишаються (до 3.1.7 стискались безповоротно — unmask не
        # відновлював оригінальні роздільники)
        return re.sub(r'\s*\n\s*', ' ', match.group(0))

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


_ORDER_CONTEXT = re.compile(
    r"(?:наказ|розпорядженн|розпорядж|директив)\w*(?:[^.;\n№]|(?<=\d)\.(?=\d)){0,80}$", re.IGNORECASE)


def _number_sign_enabled(text: str, start: int, item_type: str) -> bool:
    """Чи маскувати «№ …» цього типу: БР — MASK_BR_NUMBERS; після слова
    «наказ…/розпорядження…/директива…» у тому ж реченні — MASK_ORDERS;
    інші (довідка, рапорт, протокол …) — MASK_DOCUMENT_NUMBERS."""
    if item_type.startswith('br_'):
        return _cfg.MASK_BR_NUMBERS
    if _ORDER_CONTEXT.search(text[max(0, start - 120):start]):
        return _cfg.MASK_ORDERS
    return _cfg.MASK_DOCUMENT_NUMBERS


def mask_text_context_aware(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Головна функція маскування тексту з контекстним аналізом.

    Це центральна функція всього процесу маскування. Вона координує роботу
    всіх інших функцій та забезпечує правильний порядок обробки даних.
    """
    # Словник документа для синтетичних масок прізвищ (див. surname.py):
    # маска не має збігатися з жодним словом тексту
    _surname.enter_document(text)
    try:
        return _mask_text_context_aware_impl(text, masking_dict, instance_counters)
    finally:
        _surname.exit_document()


def _protect_custom(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """custom_patterns з action skip/warn: збіги замінюються токенами з
    латинських літер (їх не чіпає жоден тип маскування), а наприкінці
    повертаються. warn — ще й рахує збіги для попередження в CLI."""
    kept: List[Tuple[str, str]] = []
    if not _cfg.CUSTOM_PATTERNS:
        return text, kept
    spans: List[Tuple[int, int, str]] = []
    for cp in _cfg.CUSTOM_PATTERNS:
        if cp.action == "mask":
            continue
        for s, e in _custom.iter_matches(cp, text):
            if not any(s < pe and e > ps for ps, pe, _ in spans):
                spans.append((s, e, cp.name))
                if cp.action == "warn":
                    _custom.WARN_COUNTS[cp.name] = _custom.WARN_COUNTS.get(cp.name, 0) + 1
    if not spans:
        return text, kept
    spans.sort()
    out, prev = [], 0
    for i, (s, e, _name) in enumerate(spans):
        token = "___KEEP" + _letters(i) + "___"
        kept.append((token, text[s:e]))
        out.append(text[prev:s])
        out.append(token)
        prev = e
    out.append(text[prev:])
    return "".join(out), kept


def _letters(n: int) -> str:
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def _mask_text_context_aware_impl(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    text, kept = _protect_custom(text)
    text = _mask_text_core(text, masking_dict, instance_counters, kept)
    for token, original in kept:
        text = text.replace(token, original, 1)
    return text


def locate_words(line: str, phrase: str) -> Optional[Tuple[int, int, List[str]]]:
    """Знаходить слова *phrase* (розділені пробілом) у *line*, де між ними
    може стояти будь-який роздільник: кілька пробілів, таб, NBSP, «|»
    таблиць. Повертає (start, end, роздільники між словами) або None.
    До 3.1.7 ПІБ шукався дослівно, і «Коваль\tТетяна\tСергіївна» не маскувався."""
    words = phrase.split()
    if not words:
        return None
    pattern = r"(?<![\w'’ʼ-])" + r"([\s|]+)".join(re.escape(w) for w in words) + r"(?![\w'’ʼ-])"
    m = re.search(pattern, line)
    if not m:
        # Слово могло бути приклеєне до лапок/розділового знака — як раніше, дослівно
        idx = line.find(phrase)
        if idx < 0:
            return None
        return idx, idx + len(phrase), [" "] * (len(words) - 1)
    return m.start(), m.end(), list(m.groups())


def join_with_separators(words: List[str], separators: List[str]) -> str:
    """Склеює слова оригінальними роздільниками (їх на 1 менше, ніж слів;
    якщо кількість слів змінилась — одинарні пробіли)."""
    if len(separators) != len(words) - 1:
        return " ".join(words)
    out = [words[0]]
    for sep, w in zip(separators, words[1:]):
        out.append(sep)
        out.append(w)
    return "".join(out)


def _mask_known_surnames_standalone(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """Прізвище, яке вже замасковано в документі, маскується і там, де воно
    стоїть само («…Івенов Павло Данилович звільнений. Іванов отримав
    виплату.») — до 3.1.7 другий «Іванов» лишався відкритим поруч із
    маскою. Інші відмінки того ж прізвища (Іванова, Іванову) розпізнаються
    за основою і дістають ту саму синтетичну основу."""
    if not _cfg.MASK_SURNAMES:
        return text
    mappings = masking_dict.get("mappings", {})
    surnames = mappings.get("surname", {})
    if not surnames:
        return text
    # Відоме прізвище — пара (основа, родове закінчення): «Іванов»/«Іванова»/
    # «Іванову» → (іван, ов). Лише основи недостатньо: ім'я «Івана» має ту
    # саму основу «іван», і його маска перемаскувалась би як прізвище
    known_pairs = set()
    for original in surnames:
        stem, _ending, family = _surname.split_surname(original)
        if len(stem) >= 3:
            known_pairs.add((stem.lower(), family.lower()))
    if not known_pairs:
        return text
    # Жодну вже вставлену маску (будь-якої категорії) не чіпаємо
    masks_lower = {
        info["masked_as"].lower()
        for category in mappings.values() if isinstance(category, dict)
        for info in category.values() if isinstance(info, dict) and info.get("masked_as")
    }

    def _replace(m: "re.Match[str]") -> str:
        word: str = m.group(0)
        low = word.lower()
        if low in masks_lower or low in _cfg.EXCLUDE_WORDS_LOWER or low in _cfg.ABBREVIATION_WHITELIST \
                or low in _cfg.RANKS_LIST_LOWER or not looks_like_name(word):
            return word
        stem, _ending, family = _surname.split_surname(word)
        if len(stem) < 3 or (stem.lower(), family.lower()) not in known_pairs:
            return word
        return mask_surname(word, masking_dict, instance_counters)

    return re.sub(r"(?<![\w'’ʼ-])[А-ЯІЇЄҐ][А-ЯІЇЄҐа-яіїєґ'’ʼ-]{2,}(?![\w'’ʼ-])", _replace, text)


def _mask_text_core(text: str, masking_dict: Dict, instance_counters: Dict,
                    kept: Optional[List[Tuple[str, str]]] = None) -> str:
    # BOM на початку файлу інакше «приклеюється» до першого слова, і перше
    # прізвище лишається відкритим
    bom = text.startswith("\ufeff")
    if bom:
        text = text[1:]
    text = _mask_text_core_impl(text, masking_dict, instance_counters, kept)
    return ("\ufeff" + text) if bom else text


def _mask_text_core_impl(text: str, masking_dict: Dict, instance_counters: Dict,
                         kept: Optional[List[Tuple[str, str]]] = None) -> str:
    # === ШАГ 0: Нормалізація розірваних звань
    if _cfg.RANK_LINE_BREAK_FIX:
        text = normalize_broken_ranks(text)

    # === ШАГ 0.5: ПІБ з ініціалами (Іванов П.А., П. Іванов тощо)
    # Запускаємо ДО основного парсера, щоб ініціали не плутали looks_like_pib_line
    if _cfg.ALLOW_ABBREVIATED_PATRONYMIC:
        text = _mask_initials_pib(text, masking_dict, instance_counters)

    items_to_mask = []
    items_to_skip = []

    # Перевірка перекриттів через покриття позицій (bytearray) замість
    # any(...) по всіх зібраних елементах — O(довжина спану) замість O(елементів);
    # на великих файлах old-варіант давав ~60% часу маскування
    covered_mask = bytearray(len(text) + 1)
    covered_skip = bytearray(len(text) + 1)

    def _overlaps_mask(s: int, e: int) -> bool:
        return 1 in covered_mask[s:e]

    def _inside_skip(s: int, e: int) -> bool:
        # елемент цілком усередині пропущеного спану
        return e > s and covered_skip[s:e].count(1) == e - s

    def _overlaps_skip(s: int, e: int) -> bool:
        return 1 in covered_skip[s:e]

    def _add_mask(item) -> None:
        items_to_mask.append(item)
        covered_mask[item['start']:item['end']] = b'\x01' * (item['end'] - item['start'])

    def _add_skip(item) -> None:
        items_to_skip.append(item)
        covered_skip[item['start']:item['end']] = b'\x01' * (item['end'] - item['start'])

    if not _cfg.MASK_DATES:
        for match in re.finditer(_cfg.UKRAINIAN_DATE_PATTERN, text):
            _add_skip({'start': match.start(), 'end': match.end(), 'text': match.group(0), 'reason': 'full_date', 'type': 'date'})

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
                _add_skip({'start': base_pos + num_match.start(), 'end': base_pos + num_match.end(), 'text': num_match.group(0), 'reason': 'legal', 'type': 'legal_number', 'context': term})

    def _phase_custom() -> None:
        for cp in _cfg.CUSTOM_PATTERNS:
            if cp.action != "mask":
                continue
            for s, e in _custom.iter_matches(cp, text):
                if not (_overlaps_skip(s, e) or _overlaps_mask(s, e)):
                    _add_mask({'type': 'custom', 'full_text': text[s:e], 'number_part': text[s:e],
                               'start': s, 'end': e})

    def _phase_order_number() -> None:
        if not (_cfg.MASK_ORDERS or _cfg.MASK_BR_NUMBERS or _cfg.MASK_DOCUMENT_NUMBERS):
            return
        for match in re.finditer(r'№', text):
            result = analyze_number_sign_context(text, match)
            # Кожен тип — за своїм прапорцем (до 3.0.28 тип не перевірявся:
            # з увімкненими БР маскувались і номери наказів, і навпаки)
            if result and _number_sign_enabled(text, match.start(), result['type']) \
                    and not _overlaps_mask(result['start'], result['end']):
                _add_mask(result)

    def _phase_br_number() -> None:
        if not _cfg.MASK_BR_NUMBERS:
            return
        for match in re.finditer(r'\bБР\b', text, re.IGNORECASE):
            result = analyze_br_keyword(text, match)
            if result:
                skip = _overlaps_skip(result['start'], result['end']) or _overlaps_mask(result['start'], result['end'])
                if not skip: _add_mask(result)

    def _simple_phase(item_type: str, flag_name: str, pattern: str):
        def run() -> None:
            if not getattr(_cfg, flag_name):
                return
            for match in re.finditer(pattern, text):
                skip = _inside_skip(match.start(), match.end()) or _overlaps_mask(match.start(), match.end())
                if not skip: _add_mask({'type': item_type, 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})
        return run

    def _phase_brigade_number() -> None:
        if not _cfg.MASK_BRIGADES:
            return
        for match in _cfg.COMPILED_PATTERNS["brigade_number"].finditer(text):
            skip = _inside_skip(match.start(), match.end()) or _overlaps_mask(match.start(), match.end())
            if not skip: _add_mask({'type': 'brigade_number', 'full_text': match.group(0), 'number_part': match.group(1), 'start': match.start(), 'end': match.end()})

    def _legal_act_date(start: int) -> bool:
        window = text[max(0, start - 160):start]
        # Захищені фрази (exclusions.phrases, custom skip) тут — токени
        # ___KEEP…___; для пошуку назви акта повертаємо оригінал
        for token, original in kept or ():
            if token in window:
                window = window.replace(token, original)
        return _cfg.LEGAL_ACT_DATE_PREFIX.search(window) is not None

    def _phase_date() -> None:
        if not _cfg.MASK_DATES:
            return
        for match in _cfg.COMPILED_PATTERNS["date"].finditer(text):
            if _legal_act_date(match.start()):
                continue
            if is_valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3))):
                skip = _inside_skip(match.start(), match.end()) or _overlaps_mask(match.start(), match.end())
                if not skip: _add_mask({'type': 'date', 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})

    def _phase_date_text() -> None:
        if not _cfg.MASK_DATE_TEXT:
            return
        # Text dates: "06" жовтня 2025 року
        if "date_text" not in masking_dict["mappings"]:
            masking_dict["mappings"]["date_text"] = {}
        for match in _cfg.DATE_TEXT_PATTERN.finditer(text):
            if _legal_act_date(match.start()):
                continue
            skip = _inside_skip(match.start(), match.end()) or _overlaps_mask(match.start(), match.end())
            if not skip:
                _add_mask({'type': 'date_text', 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})

    # Фази шаблонних типів — у порядку router_rules.processing_order /
    # priority_overrides: при перекритті перемагає раніша фаза. Звання й ПІБ
    # розбирають рядок цілком і завжди йдуть після них (нижче)
    phases = {
        'custom': _phase_custom,
        'order_number': _phase_order_number,
        'br_number': _phase_br_number,
        # (?<!\d)…(?!\d) замість \b: «ІПН1234567890» теж маскується (v3.1.8)
        'ipn': _simple_phase('ipn', 'MASK_IPN', r'(?<!\d)\d{10}(?!\d)'),
        'passport_id': _simple_phase('passport_id', 'MASK_PASSPORT', r'(?<!\d)\d{9}(?!\d)'),
        # Серія: 2 великі літери (І/Ї/Є/Ґ теж) або малі з дефісом впритул
        # («мт-123456»); «до 150000» (слово + пробіл) — не серія
        'military_id': _simple_phase('military_id', 'MASK_MILITARY_ID',
                                     r"(?<![\w'])(?:[A-ZА-ЯІЇЄҐ]{2}[\s-]?|[a-zа-яіїєґ]{2}-)?\d{6}(?!\d)"),
        'military_unit': _simple_phase('military_unit', 'MASK_UNITS', r'\b[А-ЯA-Z] ?\d{4}\b'),
        'brigade_number': _phase_brigade_number,
        'date': _phase_date,
        'date_text': _phase_date_text,
    }
    for phase_name in _cfg.PROCESSING_ORDER:
        phases[phase_name]()

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
        elif item['type'] == 'custom':
            replacement = _custom.mask_custom(item['full_text'], masking_dict, instance_counters, text)
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
        # Заміни збираються як нумеровані плейсхолдери в РОБОЧІЙ копії рядка,
        # а не підставляються одразу в final_line через str.replace(x, mask, 1):
        # так «перше входження» могло влучити в уже вставлену маску. Приклад:
        # «рядового МАЗУРЕНКА та солдата КОВАЛЕНКА» → «рядового»→«старшого
        # солдата», далі «солдата»→«рядового» замінювало «солдата» всередині
        # щойно вставленого «старшого солдата» → «старшого рядового» (такого
        # звання немає), а справжнє «солдата» лишалось відкритим.
        current_line_for_parsing = line
        placeholders: List[Tuple[str, str]] = []

        def _hold(kind: str, value: str) -> str:
            token = f"___{kind}_MASKED_{len(placeholders) + 1}___"
            placeholders.append((token, value))
            return token

        def _replace_span(line: str, span: Tuple[int, int, List[str]], token: str) -> str:
            return line[:span[0]] + token + line[span[1]:]

        # Без жорсткого ліміту ПІБ на рядок (до 3.1.7 — 10: у списку з 12
        # осіб останні дві лишались відкритими); кожна ітерація або замінює
        # фрагмент плейсхолдером, або завершує цикл
        while iteration < 500:
            rank, pib, identifier = parse_hybrid_line(current_line_for_parsing)
            if not pib: break
            # ПІБ має бути в рядку (слова — з будь-якими роздільниками) —
            # інакше заміна не спрацює, а mask_* уже запишуть сміття в mapping
            pib_span = locate_words(current_line_for_parsing, pib)
            if pib_span is None:
                break
            # Плейсхолдер уже замаскованого фрагмента ніколи не є званням чи
            # частиною ПІБ (інакше маска загорнулась би в маску, а токен
            # потрапив у mapping і вихідний текст)
            if "___" in pib or (rank and "___" in rank):
                break

            if rank and _cfg.MASK_RANKS:
                rank_span = locate_words(current_line_for_parsing, rank)
                if rank_span is not None:
                    masked_rank_val = mask_rank_preserve_case(rank, masking_dict, instance_counters)
                    masked_rank_val = join_with_separators(masked_rank_val.split(), rank_span[2])
                    current_line_for_parsing = _replace_span(current_line_for_parsing, rank_span,
                                                             _hold("RANK", masked_rank_val))
                    pib_span = locate_words(current_line_for_parsing, pib)
                    if pib_span is None:
                        break

            if pib and (_cfg.MASK_NAMES or _cfg.MASK_SURNAMES or _cfg.MASK_PATRONYMICS):
                parts = pib.split()
                # Не маскуємо повторно те, що вже є маскою (наприклад,
                # прізвище, замасковане фазою ініціалів: «сержант Коваль П.П.»
                # → «Ковар К.К.», далі «сержант Ковар» давав «Ковк») — вкладену
                # маску unmask не розкручує за один прохід. Стосується і ПІБ
                # з одного слова після звання.
                # Лише маски ПРІЗВИЩ: вони гарантовано не збігаються з жодним
                # словом документа (surname.py), тож збіг = це справді маска.
                # Маски імен такої гарантії не мають («Олега» → «Олег»), і
                # справжній «Ґудзь Олег Олегович» далі в рядку вважався
                # замаскованим і лишався відкритим
                already_masked = {
                    info["masked_as"].lower()
                    for info in masking_dict["mappings"].get("surname", {}).values()
                    if isinstance(info, dict) and "masked_as" in info
                }
                original_pib_text = current_line_for_parsing[pib_span[0]:pib_span[1]]
                if any(p.lower() in already_masked for p in parts[:2]):
                    current_line_for_parsing = _replace_span(current_line_for_parsing, pib_span,
                                                             _hold("PIB", original_pib_text))
                    iteration += 1
                    continue
                # validation.strict_pib_format: лише повне «Прізвище Ім'я По батькові»
                if _cfg.STRICT_PIB_FORMAT and len(parts) < 3:
                    current_line_for_parsing = _replace_span(current_line_for_parsing, pib_span,
                                                             _hold("PIB", original_pib_text))
                    iteration += 1
                    continue
                if len(parts) >= 2:
                    # «Іван ПЕТРЕНКО» (прізвище виділене капсом) → ім'я перше.
                    # Але якщо ВЕСЬ ПІБ капсом — порядок стандартний
                    # (прізвище перше), інакше «ІВАНОВ ПЕТРО» плуталось місцями
                    if is_likely_surname_by_case(parts[1]) and not is_likely_surname_by_case(parts[0]):
                        name, surname = parts[0], parts[1]
                        patronymic = parts[2] if len(parts) >= 3 else ""
                        masked_surname = mask_surname(surname, masking_dict, instance_counters) if _cfg.MASK_SURNAMES else surname
                        masked_name = mask_name(name, masking_dict, instance_counters, gender_hint=detect_gender_by_patronymic(patronymic) if patronymic else None, patronymic_hint=patronymic) if _cfg.MASK_NAMES else name
                        masked_parts = [masked_name, masked_surname]
                    else:
                        surname, name = parts[0], parts[1]
                        patronymic = parts[2] if len(parts) >= 3 else ""
                        masked_surname = mask_surname(surname, masking_dict, instance_counters) if _cfg.MASK_SURNAMES else surname
                        masked_name = mask_name(name, masking_dict, instance_counters, gender_hint=detect_gender_by_patronymic(patronymic) if patronymic else None, patronymic_hint=patronymic) if _cfg.MASK_NAMES else name
                        masked_parts = [masked_surname, masked_name]

                    if patronymic:
                        gender = detect_gender_by_patronymic(patronymic) if patronymic else 'male'
                        masked_patronymic = mask_patronymic(patronymic, gender, masking_dict, instance_counters)
                        masked_parts.append(masked_patronymic)

                    # Роздільники між словами (таб, «|», подвійний пробіл) — як в оригіналі
                    masked_pib_str = join_with_separators(masked_parts, pib_span[2])
                    current_line_for_parsing = _replace_span(current_line_for_parsing, pib_span,
                                                             _hold("PIB", masked_pib_str))
                elif len(parts) == 1 and rank:
                    # Звання + лише прізвище («рядовий Іванов прибув») —
                    # раніше такий ПІБ узагалі не маскувався
                    masked_surname = mask_surname(parts[0], masking_dict, instance_counters) if _cfg.MASK_SURNAMES else parts[0]
                    current_line_for_parsing = _replace_span(current_line_for_parsing, pib_span,
                                                             _hold("PIB", masked_surname))
                else:
                    # Нічого не замінено (напр. один ПІБ-кандидат без звання) —
                    # сховати фрагмент, щоб цикл не крутився на тому ж місці
                    current_line_for_parsing = _replace_span(current_line_for_parsing, pib_span,
                                                             _hold("PIB", original_pib_text))
            else:
                current_line_for_parsing = _replace_span(current_line_for_parsing, pib_span,
                                                         _hold("PIB", current_line_for_parsing[pib_span[0]:pib_span[1]]))
            iteration += 1

        # У зворотному порядку: значення пізнішого плейсхолдера може містити
        # раніший токен (перестраховка — див. перевірку "___" вище)
        final_line = current_line_for_parsing
        for token, value in reversed(placeholders):
            final_line = final_line.replace(token, value, 1)
        masked_lines.append(final_line)

    text = '\n'.join(masked_lines)

    # Прізвища, вже замасковані в документі, — і там, де стоять самі
    text = _mask_known_surnames_standalone(text, masking_dict, instance_counters)

    # Звання-значення в лапках без ПІБ («молодший сержант») — після
    # основного циклу, з пропуском уже замаскованих форм
    text = _mask_quoted_ranks(text, masking_dict, instance_counters)

    return text

def mask_json_recursive(data: Any, masking_dict: Dict, instance_counters: Dict) -> Any:
    # Словник усього JSON-документа (не окремого рядка) — щоб маска прізвища
    # не збіглась зі словом з іншого поля
    _surname.enter_document(json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else str(data))
    try:
        return _mask_json_recursive_impl(data, masking_dict, instance_counters)
    finally:
        _surname.exit_document()


def _mask_json_recursive_impl(data: Any, masking_dict: Dict, instance_counters: Dict) -> Any:
    if isinstance(data, dict): return {key: _mask_json_recursive_impl(value, masking_dict, instance_counters) for key, value in data.items()}
    elif isinstance(data, list): return [_mask_json_recursive_impl(item, masking_dict, instance_counters) for item in data]
    elif isinstance(data, str): return mask_text_wrapper(data, masking_dict, instance_counters)
    else: return data

def mask_text_wrapper(text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    return mask_text_context_aware(text, masking_dict, instance_counters)
