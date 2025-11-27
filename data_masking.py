#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Masking Script v2.2.14
Локально узгоджене маскування конфіденційних даних з INSTANCE TRACKING

ОНОВЛЕНО В v2.2.14:
- 📚 Покращено документування коду
- 🔧 Додано docstrings до всіх функцій маскування
- 📝 Inline коментарі для складної логіки
- ✅ БЕЗ доктестів (для сумісності з IntelliJ IDEA)
- 📋 Покращено блокові коментарі секцій

ОНОВЛЕНО В v2.2.13:
- 🔄 Об'єднано версії data_masking.py (v2.2.10) та data_masking_v2_2_12_fixed.py
- ✅ Збережено всі виправлення багів з v2.2.12
- 📋 Підготовлено для документування в v2.2.14

ВИПРАВЛЕНО В v2.2.12:
- 🐛 БАГ #18 FIX: mask_rank() не зберігав Title Case для багатослівних звань
  "Старший Лейтенант" → "Майор" (Title Case), а не "майор" (lowercase)
  Додано перевірку all(word[0].isupper() for word in words)

ВИПРАВЛЕНО В v2.2.11:
- 🐛 БАГ #16 FIX: mask_rank() не зберігав регістр при використанні .title()
  Тепер "Капітан" → "Майор" (Title Case), а не "майор" (lowercase)
- 🐛 БАГ #17 FIX: mask_name() не застосовував регістр для існуючих в mapping імен
  Тепер "петро" → "павло" (lowercase), а не "Павло" (Title Case)
- ✅ Всі тести збереження регістру тепер проходять

ВИПРАВЛЕНО В v2.2.10:
- 🐛 БАГ #15 FIX: "старшого\nсержанта" -> "старшого старшого сержанта".
  Додано попередню нормалізацію розірваних звань (функція normalize_broken_ranks).
  Тепер звання, розірвані переносом рядка, склеюються перед обробкою.
- 📄 Відновлено повний формат звітів та статистики.

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.2.14
License: BSD 3-Clause "New" or "Revised" License
Year: 2025
"""

import json
import random
import hashlib
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from faker import Faker

# ============================================================================
# ІМПОРТ ДАНИХ З МОДУЛЯ
# ============================================================================
from rank_data import (
    RANK_DECLENSIONS,
    RANK_FEMININE_MAP,
    RANK_DECLENSIONS_FEMALE,
    RANK_TO_NOMINATIVE,
    ALL_RANK_FORMS,
    ARMY_RANKS,
    NAVAL_RANKS,
    LEGAL_RANKS,
    MEDICAL_RANKS,
    RANKS_LIST
)

# ============================================================================
# МЕТАДАНІ
# ============================================================================
__version__ = "2.2.14"
__author__ = "Vladyslav V. Prodan"
__contact__ = "github.com/click0"
__phone__ = "+38(099)6053340"
__license__ = "BSD 3-Clause"
__year__ = "2025"

fake_uk = Faker('uk_UA')
HASH_ALGORITHM = 'blake2b'

# ============================================================================
# НАЛАШТУВАННЯ МАСКУВАННЯ
# ============================================================================
MASK_NAMES = True
MASK_IPN = True
MASK_PASSPORT = True
MASK_MILITARY_ID = True
MASK_RANKS = True
MASK_BRIGADES = True
MASK_UNITS = True
MASK_ORDERS = True
MASK_BR_NUMBERS = True
MASK_DATES = True

DEBUG_MODE = False
PRESERVE_CASE = True

# ============================================================================
# СПИСКИ ТА КОНСТАНТИ
# ============================================================================

# Список абревіатур які НЕ повинні маскуватись у прізвищах
# Включає: військові організації, державні установи
# Використовується в mask_surname() для фільтрації
ABBREVIATION_WHITELIST = {
    'зсу', 'моу', 'всу', 'дпсу', 'нгу', 'дснс', 'сбу', 'гур', 'тцк', 'сп', 'кму', 'отцксп'
}

UKRAINIAN_DATE_PATTERN = r'\b\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}\b'

GOOD_UKRAINIAN_NAMES_MALE = [
    "андрій", "богдан", "віктор", "володимир", "дмитро",
    "ігор", "іван", "максим", "олег", "олексій",
    "петро", "сергій", "тарас", "юрій", "михайло",
    "василь", "роман", "артем", "денис", "євген",
    "костянтин", "павло", "станіслав", "ярослав"
]

GOOD_UKRAINIAN_NAMES_FEMALE = [
    "анна", "вікторія", "галина", "дарія", "ірина",
    "катерина", "марія", "наталія", "олена", "оксана",
    "світлана", "тетяна", "юлія", "людмила", "надія",
    "валентина", "лариса", "ольга", "софія", "діана",
    "алла", "ганна", "любов"
]

PROBLEMATIC_NAMES = [
    "макаліім", "серубаій", "аарон", "іїлія",
    "аадам", "іісус", "ааріон", "єєва",
    "мелхіор", "валтасар", "йосип", "євстахій",
    "еммануїл", "рафаїл", "самуїл", "ієремія",
]

# Список службових слів які НЕ повинні маскуватись
# Включає: юридичні терміни, назви посад, прийменники, числівники
# Використовується в looks_like_pib_line() для фільтрації помилкових розпізнавань
EXCLUDE_WORDS = [
    "Дійсним", "дійсним", "Відповідно", "відповідно", "Згідно", "згідно",
    "Відповідальний", "відповідальний", "Командир", "командир", "командира",
    "Начальник", "начальник", "Заступник", "заступник",
    "Виконуючий", "виконуючий", "обов'язки", "обав'язки",
    "доповідаю", "прошу", "наказую", "призначити", "звільнити",
    "проявив", "виконав", "оголосити", "оголосити",
    "про", "по", "від", "до", "за", "суті", "мною", "Вас", "вас",
    "зв'язку", "порушення", "вимог",
    "Збройних", "збройних", "України", "україни", "служби", "Служби",
    "військової", "Військової", "частини", "Частини", "взводу", "Взводу",
    "батальйону", "Батальйону", "роти", "Роти",
    "Статуту", "статуту", "Указу", "указу", "Закону", "закону",
    "Кодексу", "кодексу", "Положення", "положення",
    "Інструкції", "інструкції", "наказу", "Наказу", "наказом", "Наказом",
    "рапорту", "Рапорту", "статей", "Статей", "пункту", "Пункту",
    "неналежііе", "инутрішньої", "радіовіzUділення",
    "с~гатуту", "року", "Року", "числа", "місяця",
    "один", "два", "три", "чотири", "п'ять",
]

# Regex паттерни для виявлення звань різних типів служб
# army: базові військові звання (солдат, сержант, офіцери, генерали)
# naval: морські звання (матрос, капітан рангу, адмірали)
# legal: звання юридичної служби (юстиції)
# medical: звання медичної служби
RANK_PATTERNS = {
    "army": r"\b(рекрут|рядовий|солдат|старший солдат|ефрейтор|молодший сержант|сержант|старший сержант|головний сержант|штабс-сержант|майстер-сержант|старший майстер-сержант|головний майстер-сержант|прапорщик|старший прапорщик|молодший лейтенант|лейтенант|старший лейтенант|капітан|майор|підполковник|полковник|бригадний генерал|генерал-майор|генерал-лейтенант|генерал)\b",
    "naval": r"\b(матрос|моряк|старший матрос|старший моряк|молодший сержант|сержант|старший сержант|головний сержант|штабс-сержант|майстер-сержант|старший майстер-сержант|головний майстер-сержант|молодший лейтенант|лейтенант|старший лейтенант|капітан-лейтенант|капітан \d+-го рангу|контр-адмірал|віце-адмірал|адмірал)\b",
    "legal": r"\b(молодший сержант юстиції|сержант юстиції|старший сержант юстиції|головний сержант юстиції|штабс-сержант юстиції|молодший лейтенант юстиції|лейтенант юстиції|старший лейтенант юстиції|капітан юстиції|майор юстиції|підполковник юстиції|полковник юстиції|генерал-майор юстиції|генерал-лейтенант юстиції)\b",
    "medical": r"\b(молодший сержант медичної служби|сержант медичної служби|старший сержант медичної служби|головний сержант медичної служби|штабс-сержант медичної служби|молодший лейтенант медичної служби|лейтенант медичної служби|старший лейтенант медичної служби|капітан медичної служби|майор медичної служби|підполковник медичної служби|полковник медичної служби|генерал-майор медичної служби|генерал-лейтенант медичної служби)\b"
}

PATTERNS = {
    "ipn": r"\b\d{10}\b",
    "passport_id": r"\b\d{9}\b",
    "military_id": r"(?:[A-ZА-Я]{2}\s*-?\s*)?\d{6}\b",
    "military_unit": r"\b[А-ЯA-Z]\d{4}\b",
    "br_number_complex": r"№БР-?\d+(?:[/-]\d+)*(?:[/-][A-ZА-ЯЇІЄҐa-zа-яїієґ]+)+",
    "br_number_slash": r"№\d+(?:/\d+){2,}(?:дск|п|к)",
    "order_number_with_letters": r"№\s*\d+(?:[/-](?:[A-ZА-ЯЏІЄҐa-zа-яїієґ]+\d*|\d+[A-ZА-ЯЇІЄҐa-zа-яїієґ]+))+",
    "br_number": r"(?<!\d\.)(?<!\d\d\.)№?\d+(?:/\d+)*(?:дск|п|к)?(?!\.\d{1,2}\.\d{4})",
    "order_number": r"(?<!\d\.)(?<!\d\d\.)№\s*\d+(?:/\d+)*(?!\.\d{1,2}\.\d{4})",
    "brigade_number": r"\b(\d+)\s+(окремої механізованої бригади|омбр|ошп|ошбр|бригади|окремої штурмової бригади|десантно-штурмової бригади|дшб|танкової бригади|тбр)\b",
    "date": r"\b(\d{2})\.(\d{2})\.(\d{4})\b",
}

COMPILED_RANK_PATTERNS = {key: re.compile(pattern, re.IGNORECASE | re.UNICODE) for key, pattern in RANK_PATTERNS.items()}
COMPILED_PATTERNS = {key: re.compile(pattern, re.IGNORECASE | re.UNICODE) for key, pattern in PATTERNS.items()}

# ============================================================================
# ДОПОМІЖНІ ФУНКЦІЇ (БАЗОВІ)
# ============================================================================
# Функції загального призначення для роботи зі словниками,
# регістром літер та детермінованою генерацією seed'ів

def get_next_instance(masked_value: str, instance_counters: Dict[str, int]) -> int:
    """
    Повертає наступний номер екземпляра для даного замаскованого значення.

    Instance tracking: відстежуємо випадки коли різні оригінали
    маскуються в одне значення (колізії)
    """
    instance_counters.setdefault(masked_value, 0)
    instance_counters[masked_value] += 1
    return instance_counters[masked_value]

def add_to_mapping(masking_dict: Dict, instance_counters: Dict, category: str, original: str, masked: str) -> str:
    """
    Додає маппінг оригінал→маска до словника та оновлює статистику.

    Args:
        masking_dict: Словник з усіма маппінгами
        instance_counters: Лічильники екземплярів для instance tracking
        category: Категорія даних (ipn, surname, rank, тощо)
        original: Оригінальне значення
        masked: Замасковане значення

    Returns:
        Замасковане значення (може бути взято з існуючого mapping)

    Note:
        Статистика оновлюється тільки для УНІКАЛЬНИХ оригіналів
    """
    if original not in masking_dict["mappings"][category]:
        masking_dict["mappings"][category][original] = {
            "masked_as": masked,
            "instances": []
        }
        # Статистика оновлюється тільки для унікальних оригіналів
        masking_dict["statistics"][category] = masking_dict["statistics"].get(category, 0) + 1
    else:
        masked = masking_dict["mappings"][category][original]["masked_as"]

    # Instance tracking: зберігаємо кожне входження
    instance_num = get_next_instance(masked, instance_counters)
    masking_dict["mappings"][category][original]["instances"].append(instance_num)
    return masked

def _apply_original_case(original: str, masked: str) -> str:
    """
    Застосовує регістр оригінального тексту до замаскованого.

    Підтримує:
    - UPPER CASE (весь текст великими)
    - Title Case (перша велика, решта малі)
    - lower case (весь текст малими)

    Args:
        original: Оригінальний текст (для визначення регістру)
        masked: Замаскований текст (для застосування регістру)

    Returns:
        Замаскований текст з регістром оригіналу

    Note:
        Використовується для збереження регістру в Bug Fix #16, #17, #18
    """
    if not original or not masked: return masked
    if original.isupper(): return masked.upper()
    elif len(original) > 1 and original[0].isupper() and original[1:].islower(): return masked.capitalize()
    else: return masked.lower()

def normalize_string(s: str) -> str:
    if not s: return ""
    s_str = str(s).lower()
    s_str = s_str.replace("'", "'").replace('\xa0', ' ').replace(".", " ").replace(";", " ")
    return re.sub(r'\s+', ' ', s_str).strip()

def normalize_identifier(identifier: str) -> str:
    if not identifier: return ""
    identifier_str = str(identifier).upper()
    return re.sub(r'[\s\-.]', '', identifier_str).strip()

def is_pib_anchor(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    if not word or len(word) <= 2: return False
    word_lower = word.lower()
    if word_lower in [w.lower() for w in EXCLUDE_WORDS]: return False
    if word_lower in [r.lower() for r in RANKS_LIST]: return False
    return word[0].isupper()

# ============================================================================
# ФУНКЦІЇ АНАЛІЗУ КОНТЕКСТУ
# ============================================================================
# Функції для розпізнавання та аналізу різних типів даних у тексті:
# - Детермінована генерація seed'ів (для unmask)
# - Розпізнавання рядків з ПІБ
# - Аналіз граматичних форм імен та звань
# - Витягування звань та додаткових слів

def get_deterministic_seed(original: str) -> int:
    """
    Генерує детермінований seed для маскування на основі оригінального значення.

    Використовує hashlib (blake2b) для створення унікального, але повторюваного seed'а.
    Це гарантує що одне і те саме оригінальне значення завжди отримає одну і ту саму маску,
    що є критично важливим для можливості unmask (розмаскування).

    Детерміноване маскування означає:
    - "Петренко" завжди → seed 12345 → "Іваненко"
    - "Сидоренко" завжди → seed 67890 → "Коваленко"

    Без детермінованості unmask був би неможливим, оскільки при розмаскуванні
    ми повинні згенерувати точно ті самі маски що й при маскуванні.

    Args:
        original: Оригінальне значення (ІПН, прізвище, ім'я, тощо)

    Returns:
        Цілочисельний seed для random.seed()

    Note:
        Використовує глобальну константу HASH_ALGORITHM = 'blake2b'
    """
    if HASH_ALGORITHM == 'md5': hasher = hashlib.md5()
    elif HASH_ALGORITHM == 'sha1': hasher = hashlib.sha1()
    elif HASH_ALGORITHM == 'sha256': hasher = hashlib.sha256()
    elif HASH_ALGORITHM == 'blake2b': hasher = hashlib.blake2b()
    elif HASH_ALGORITHM == 'sha512': hasher = hashlib.sha512()
    else: raise ValueError(f"Unknown hash algorithm: {HASH_ALGORITHM}")
    hasher.update(original.encode('utf-8'))
    return int(hasher.hexdigest(), 16) % (2**32)

# ============================================================================
# МОВНІ ТА ЛОГІЧНІ ФУНКЦІЇ
# ============================================================================

def is_likely_surname_by_case(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    if not word or len(word) < 3: return False
    letters_only = re.sub(r"[-']", '', word)
    return letters_only.isupper() and len(letters_only) >= 3

def looks_like_name(word: str) -> bool:
    if word.startswith("___") and word.endswith("___"): return False
    clean_word = word.rstrip(',.!?;:')
    if len(clean_word) < 3: return False
    if clean_word in EXCLUDE_WORDS or clean_word.lower() in [w.lower() for w in EXCLUDE_WORDS]: return False
    if re.search(r'\d', clean_word): return False
    if clean_word.lower() in RANKS_LIST: return False
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
    if name_lower in PROBLEMATIC_NAMES: return False
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
    whitelist = GOOD_UKRAINIAN_NAMES_MALE if gender == 'male' else GOOD_UKRAINIAN_NAMES_FEMALE
    available = [n for n in whitelist if n[0].lower() == first_letter.lower()]
    if available:
        name = random.choice(available).capitalize()
        return name

    last_name = None
    for attempt in range(max_attempts):
        if gender == 'female': name = fake_uk.first_name_female()
        else: name = fake_uk.first_name_male()
        last_name = name
        if name[0].lower() != first_letter: continue
        if is_easy_to_decline(name, gender): return name

    if whitelist: return random.choice(whitelist).capitalize()
    return last_name if last_name else (fake_uk.first_name_female() if gender == 'female' else fake_uk.first_name_male())

# ============================================================================
# ФУНКЦІЇ АНАЛІЗУ КОНТЕКСТУ
# ============================================================================

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
    has_rank = any(rank in normalized for rank in RANKS_LIST)

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

    for rank_form in ALL_RANK_FORMS:
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
            pib_words.append(word)
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

# ============================================================================
# ФУНКЦІЇ МАСКУВАННЯ (ПЕРСОНАЛЬНІ ДАНІ)
# ============================================================================
# Функції для маскування ПІБ, ІПН, паспортів, військових ID

def mask_ipn(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує ІПН (Індивідуальний податковий номер).

    Формат: 10 цифр
    Логіка: Зберігає перші 3 та останню цифру, змінює середні 6 цифр

    Args:
        original: Оригінальний ІПН (10 цифр)
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замаскований ІПН у тому ж форматі
    """
    if original in masking_dict["mappings"]["ipn"]:
        masked = masking_dict["mappings"]["ipn"][original]["masked_as"]
    else:
        if len(original) != 10 or not original.isdigit(): return original
        seed = get_deterministic_seed(original)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        masked = original[:3] + middle + original[-1]
    return add_to_mapping(masking_dict, instance_counters, "ipn", original, masked)

def mask_passport_id(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує ID паспорту.

    Формат: 9 цифр
    Логіка: Зберігає перші 3 та останню цифру, змінює середні 5 цифр

    Args:
        original: Оригінальний ID паспорту (9 цифр)
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замаскований ID паспорту у тому ж форматі
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

    Логіка: Зберігає префікс (літери), перші 2 та останні 2 цифри, змінює середні 2

    Args:
        original: Оригінальний військовий ID
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замаскований військовий ID у тому ж форматі
    """
    if original in masking_dict["mappings"]["military_id"]:
        masked = masking_dict["mappings"]["military_id"][original]["masked_as"]
    else:
        normalized = normalize_identifier(original)
        prefix_match = re.match(r'^([A-ZА-Я]{2})?(\d{6})$', normalized)
        if not prefix_match: return original
        prefix = prefix_match.group(1) or ""
        digits = prefix_match.group(2)
        seed = get_deterministic_seed(original)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(2)])
        masked_digits = digits[:2] + middle + digits[-2:]
        if " " in original: masked = f"{prefix} {masked_digits}" if prefix else masked_digits
        elif "-" in original: masked = f"{prefix}-{masked_digits}" if prefix else masked_digits
        else: masked = prefix + masked_digits
    return add_to_mapping(masking_dict, instance_counters, "military_id", original, masked)

def mask_surname(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує прізвище.

    ЛОГІКА МАСКУВАННЯ:
    - Для коротких прізвищ (<5 символів): генерує нове через faker
    - Для довгих прізвищ (≥5 символів): зберігає початок (3) та кінець (2), змінює середину

    ЗБЕРЕЖЕННЯ ФОРМАТУ:
    - UPPER CASE → UPPER CASE
    - Title Case → Title Case
    - lower case → lower case

    ВИКЛЮЧЕННЯ:
    - Абревіатури з ABBREVIATION_WHITELIST НЕ маскуються (ЗСУ, МОУ, СБУ тощо)

    Args:
        original: Оригінальне прізвище
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замасковане прізвище зі збереженням регістру

    Note:
        Bug Fix #10: Коротці прізвища (<5 символів) тепер маскуються коректно
    """
    if original.lower() in ABBREVIATION_WHITELIST: return original
    if original in masking_dict["mappings"]["surname"]:
        masked = masking_dict["mappings"]["surname"][original]["masked_as"]
    else:
        is_upper = original.isupper()
        is_capitalize = original[0].isupper() and original[1:].islower()
        seed = get_deterministic_seed(original)
        random.seed(seed)
        fake_uk.seed_instance(seed)
        fake_surname = fake_uk.last_name()

        # Для коротких прізвищ генеруємо нове повністю
        if len(original) < 5:
            target_length = random.randint(max(3, len(original) - 1), min(6, len(original) + 2))
            masked = fake_surname[:target_length] if len(fake_surname) > target_length else fake_surname
        else:
            # Для довгих зберігаємо початок та кінець
            middle_len = min(random.randint(2, 7), len(fake_surname)-2)
            middle = fake_surname[1:1+middle_len] if len(fake_surname) > 4 else fake_surname[1:-1]
            masked = original[:3] + middle + original[-2:]

        # Застосовуємо регістр
        if is_upper: masked = masked.upper()
        elif is_capitalize: masked = masked.capitalize()
    return add_to_mapping(masking_dict, instance_counters, "surname", original, masked)

def mask_patronymic(patronymic: str, gender: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує по батькові з урахуванням роду.

    ОСОБЛИВОСТІ:
    - Генерує нове по батькові через faker.middle_name_male() або faker.middle_name_female()
    - Рід визначається автоматично з контексту (через параметр gender)
    - Зберігає регістр оригіналу

    ЗБЕРЕЖЕННЯ ФОРМАТУ:
    - UPPER CASE → UPPER CASE
    - Title Case → Title Case
    - lower case → lower case

    Args:
        patronymic: Оригінальне по батькові
        gender: Рід ('male' або 'female')
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замасковане по батькові відповідного роду зі збереженням регістру

    Note:
        Додано в v2.2.1 для коректного маскування повного ПІБ
    """
    if not MASK_NAMES or not patronymic: return patronymic
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
    seed = get_deterministic_seed(patronymic_lower)
    random.seed(seed)
    fake_uk.seed_instance(seed)
    fake_patronymic = fake_uk.middle_name_male() if gender == 'male' else fake_uk.middle_name_female()

    # Застосовуємо регістр
    if is_upper: fake_patronymic = fake_patronymic.upper()
    elif is_capitalize: fake_patronymic = fake_patronymic.capitalize()
    else: fake_patronymic = fake_patronymic.lower()

    return add_to_mapping(masking_dict, instance_counters, "patronymic", patronymic_lower, fake_patronymic)

def mask_name(original: str, masking_dict: Dict, instance_counters: Dict, gender_hint: str = None, patronymic_hint: str = None) -> str:
    """
    Маскує ім'я з автоматичним визначенням роду та відмінка.

    АЛГОРИТМ:
    1. Визначає рід з контексту (через patronymic_hint або аналіз закінчення)
    2. Визначає граматичний відмінок імені
    3. Генерує нове ім'я того ж роду з тією ж першою літерою
    4. Застосовує відмінок до згенерованого імені
    5. Зберігає оригінальний регістр

    ВИЗНАЧЕННЯ РОДУ:
    - Через gender_hint (якщо надано)
    - Через по батькові (patronymic_hint): "Петровичу" → чоловік, "Петрівні" → жінка
    - Через закінчення імені: "Олександр" → чоловік, "Ольга" → жінка

    ЗБЕРЕЖЕННЯ ФОРМАТУ:
    - Перша літера імені зберігається
    - Відмінок зберігається (називний, родовий, давальний, орудний)
    - Регістр зберігається (UPPER, Title, lower)

    Args:
        original: Оригінальне ім'я
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів
        gender_hint: Підказка роду ('male' або 'female'), опціонально
        patronymic_hint: Підказка по батькові для визначення роду, опціонально

    Returns:
        Замасковане ім'я з відповідним родом, відмінком та регістром

    Note:
        Bug Fix #17: Тепер коректно застосовує регістр для існуючих mapping записів
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

        # Пріоритет визначення роду: gender_hint → patronymic_hint → gender_from_name
        if gender_hint: gender = gender_hint
        elif patronymic_hint:
            gender = detect_gender_by_patronymic(patronymic_hint)
            if gender == 'unknown': gender = gender_from_name
        else: gender = gender_from_name
        if gender == 'unknown': gender = 'male'

        # Генеруємо нове ім'я з тією ж першою літерою
        first_letter = original[0].lower()
        seed = get_deterministic_seed(original)
        new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50)
        masked = apply_case_to_name(new_name, case, gender)

        # Уникаємо випадків коли ім'я мапиться саме на себе
        attempts = 0
        while masked.lower() == original.lower() and attempts < 10:
            seed = get_deterministic_seed(original + str(attempts))
            new_name = generate_easy_name(gender, first_letter, seed, max_attempts=50)
            masked = apply_case_to_name(new_name, case, gender)
            attempts += 1

    # БАГ #17 FIX: Застосовуємо регістр до masked ПЕРЕД add_to_mapping
    # Це гарантує правильний регістр навіть для існуючих записів
    if is_upper:
        masked = masked.upper()
    elif is_capitalize:
        masked = masked.capitalize()
    elif is_lower:
        masked = masked.lower()

    return add_to_mapping(masking_dict, instance_counters, "name", original, masked)

# ============================================================================
# ФУНКЦІЇ МАСКУВАННЯ (ВІЙСЬКОВІ ДАНІ)
# ============================================================================
# Функції для маскування звань, військових частин, номерів наказів та БР

def mask_military_unit(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує військову частину.

    Формат: A#### (одна велика літера + 4 цифри)
    Логіка: Зберігає літеру, змінює всі 4 цифри

    Приклади:
    - "А1234" → "А5678"
    - "В9876" → "В2345"

    Args:
        original: Оригінальна військова частина (формат: A####)
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замаскована військова частина у тому ж форматі
    """
    if original in masking_dict["mappings"]["military_unit"]:
        masked = masking_dict["mappings"]["military_unit"][original]["masked_as"]
    else:
        match = re.match(r'^([А-ЯA-Z])(\d{4})$', original)
        if not match: return original
        letter = match.group(1)
        seed = get_deterministic_seed(original)
        random.seed(seed)
        digits = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        masked = letter + digits
    return add_to_mapping(masking_dict, instance_counters, "military_unit", original, masked)

def mask_order_number(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує номер наказу.

    Формати:
    - № #### (з пробілом)
    - №#### (без пробілу)
    - ####/#### (з слешами)

    Логіка: Замінює всі цифри, зберігає формат (№, пробіли, слеші)

    Приклади:
    - "№ 123" → "№ 456"
    - "№456/2024" → "№789/2025"

    Args:
        original: Оригінальний номер наказу
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замаскований номер наказу у тому ж форматі
    """
    if original in masking_dict["mappings"]["order_number"]:
        masked = masking_dict["mappings"]["order_number"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = re.sub(r'\d', lambda _: str(random.randint(0, 9)), original)
    return add_to_mapping(masking_dict, instance_counters, "order_number", original, masked)

def mask_order_number_with_letters(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["order_number_with_letters"]:
        masked = masking_dict["mappings"]["order_number_with_letters"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = re.sub(r'\d', lambda _: str(random.randint(0, 9)), original)
    return add_to_mapping(masking_dict, instance_counters, "order_number_with_letters", original, masked)

def mask_br_number(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує БР номер.

    Формати:
    - БР-#### або БР ####
    - №БР-#### або №БР ####
    - ####дск, ####п, ####к (з суфіксами)
    - №####/####дск (комбіновані формати)

    Зберігає:
    - Префікс (№, БР)
    - Суфікс (дск, п, к)
    - Формат слешів (/) якщо були
    - Пробіли та дефіси

    Логіка: Замінює всі цифри, зберігає структуру

    Приклади:
    - "№123дск" → "№456дск"
    - "№456/789п" → "№123/456п"

    Args:
        original: Оригінальний БР номер
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замаскований БР номер у тому ж форматі

    Note:
        Bug Fix #7, #8: Коректна обробка префіксів та суфіксів
    """
    if original in masking_dict["mappings"]["br_number"]:
        masked = masking_dict["mappings"]["br_number"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)

        # Витягуємо суфікс (дск, п, к)
        suffix_match = re.search(r'(дск|п|к)$', original)
        suffix = suffix_match.group(1) if suffix_match else ""

        # Витягуємо префікс (№)
        prefix = ""
        number_part = original
        if original.startswith("№"):
            match = re.match(r'(№\s*)', original)
            if match:
                prefix = match.group(1)
                number_part = original[len(prefix):]
        if suffix: number_part = number_part[:-len(suffix)]

        # Обробляємо частини розділені слешами
        parts = re.split(r'(/)', number_part)
        masked_parts = []
        for part in parts:
            if part == '/': masked_parts.append(part)
            elif part and re.match(r'^\d', part):
                digit_match = re.match(r'(\d+)(.*)', part)
                if digit_match:
                    digits = digit_match.group(1)
                    rest = digit_match.group(2)
                    masked_digits = ''.join([str(random.randint(0, 9)) for _ in range(len(digits))])
                    masked_parts.append(masked_digits + rest)
                else: masked_parts.append(part)
            else: masked_parts.append(part)
        masked = prefix + ''.join(masked_parts) + suffix
    return add_to_mapping(masking_dict, instance_counters, "br_number", original, masked)

def mask_br_number_slash(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["br_number_slash"]:
        masked = masking_dict["mappings"]["br_number_slash"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        suffix_match = re.search(r'(дск|п|к)$', original)
        suffix = suffix_match.group(1) if suffix_match else ""
        prefix = ""
        number_part = original
        if original.startswith("№"):
            match = re.match(r'(№\s*)', original)
            if match:
                prefix = match.group(1)
                number_part = original[len(prefix):]
        if suffix: number_part = number_part[:-len(suffix)]

        parts = number_part.split('/')
        masked_parts = []
        for part in parts:
            if part.strip().isdigit():
                masked_parts.append(''.join([str(random.randint(0, 9)) for _ in range(len(part.strip()))]))
            else:
                masked_parts.append(part)
        masked = prefix + '/'.join(masked_parts) + suffix
    return add_to_mapping(masking_dict, instance_counters, "br_number_slash", original, masked)

def mask_br_number_complex(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["br_number_complex"]:
        masked = masking_dict["mappings"]["br_number_complex"][original]["masked_as"]
    else:
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = re.sub(r'\d', lambda _: str(random.randint(0, 9)), original)
    return add_to_mapping(masking_dict, instance_counters, "br_number_complex", original, masked)

def mask_brigade_number(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    if original in masking_dict["mappings"]["brigade_number"]:
        masked = masking_dict["mappings"]["brigade_number"][original]["masked_as"]
    else:
        match = re.match(r'(\d+)\s+(.+)', original)
        if not match: return original
        brigade_name = match.group(2)
        seed = get_deterministic_seed(original)
        random.seed(seed)
        masked = f"{random.randint(1, 160)} {brigade_name}"
    return add_to_mapping(masking_dict, instance_counters, "brigade_number", original, masked)

def is_valid_date(day: int, month: int, year: int) -> bool:
    if year < 2015 or year > 2035: return False
    try:
        datetime(year, month, day)
        return True
    except ValueError: return False

def mask_date(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує дату у форматі DD.MM.YYYY.

    ЛОГІКА МАСКУВАННЯ ДАТ:
    - Зміщує дату на випадкову кількість днів (±30 днів від оригіналу)
    - Обмежує роки діапазоном 2015-2035 (±10 років від поточного 2025)
    - Використовує детермінований seed для unmask

    ВАЛІДАЦІЯ:
    - Перевіряє що рік у межах 2015-2035
    - Високосні роки враховуються автоматично через datetime
    - Некоректні дати (наприклад, 31.02.2024) повертаються без змін

    ОБРОБКА ГРАНИЧНИХ ВИПАДКІВ:
    - Якщо зміщена дата < 2015 → встановлюється випадкова дата в 2015 році
    - Якщо зміщена дата > 2035 → встановлюється випадкова дата в 2035 році

    Приклади:
    - "15.03.2024" → "10.04.2024" (зміщення +26 днів)
    - "01.01.2015" → "15.01.2015" (не виходить за ліву межу)

    Args:
        original: Оригінальна дата (формат: DD.MM.YYYY)
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замаскована дата у форматі DD.MM.YYYY

    Note:
        Додано в v2.1.12 для повної анонімізації документів
    """
    if original in masking_dict["mappings"]["date"]:
        masked = masking_dict["mappings"]["date"][original]["masked_as"]
    else:
        try:
            match = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', original)
            if not match: return original

            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            if not is_valid_date(day, month, year): return original

            # Створюємо об'єкт дати та зміщуємо на ±30 днів
            date_obj = datetime(year, month, day)
            seed = get_deterministic_seed(original)
            random.seed(seed)
            new_date = date_obj + timedelta(days=random.randint(-30, 30))

            # Обмежуємо діапазон років 2015-2035
            if new_date.year < 2015:
                new_date = datetime(2015, 1, 1) + timedelta(days=random.randint(0, 365))
            elif new_date.year > 2035:
                new_date = datetime(2035, 12, 31) - timedelta(days=random.randint(0, 365))

            masked = new_date.strftime("%d.%m.%Y")
        except Exception:
            return original

    return add_to_mapping(masking_dict, instance_counters, "date", original, masked)

def get_rank_category_and_match(text: str) -> Tuple[Optional[str], Optional[str]]:
    text_lower = text.lower()
    for category, pattern in RANK_PATTERNS.items():
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match: return category, match.group(0)
    return None, None

def get_rank_info(rank_form: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    rank_lower = rank_form.lower()
    if rank_lower in RANK_TO_NOMINATIVE:
        return RANK_TO_NOMINATIVE[rank_lower]
    return None, None, None

def get_rank_in_case(nominative_rank: str, target_case: str) -> str:
    if nominative_rank not in RANK_DECLENSIONS: return nominative_rank
    return RANK_DECLENSIONS[nominative_rank].get(target_case, nominative_rank)

def mask_rank(original: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує звання (базова версія без case preservation).

    Основна логіка маскування звань:
    1. Визначає категорію звання (army, naval, legal, medical)
    2. Знаходить позицію у відповідній ієрархії
    3. Генерує нове звання зі зсувом ±1-2 позиції
    4. Зберігає граматичний відмінок

    Args:
        original: Звання для маскування
        masking_dict: Словник маппінгів
        instance_counters: Лічильники екземплярів

    Returns:
        Замасковане звання

    Note:
        Для кращого збереження контексту рекомендується використовувати
        mask_rank_preserve_case() замість цієї функції
    """
    original_key = original.lower()
    detected_base, detected_case, detected_gender = get_rank_info(original_key)

    # Instance tracking: перевіряємо чи це звання вже не є маскою іншого
    if original_key in masking_dict["mappings"]["rank"]:
        is_someone_else_mask = False
        for other_original, other_data in masking_dict["mappings"]["rank"].items():
            if isinstance(other_data, dict) and "masked_as" in other_data:
                if other_data["masked_as"].lower() == original_key and other_original != original_key:
                    is_someone_else_mask = True
                    break
        if not is_someone_else_mask:
            masked = masking_dict["mappings"]["rank"][original_key]["masked_as"]
            final_masked = add_to_mapping(masking_dict, instance_counters, "rank", original_key, masked)
            if PRESERVE_CASE: return _apply_original_case(original, final_masked)
            return final_masked

    # Визначаємо категорію та ієрархію звань
    category_name, matched = get_rank_category_and_match(original_key)
    if not matched: return original

    if category_name == "army": hierarchy = ARMY_RANKS
    elif category_name == "naval": hierarchy = NAVAL_RANKS
    elif category_name == "legal": hierarchy = LEGAL_RANKS
    elif category_name == "medical": hierarchy = MEDICAL_RANKS
    else: return original

    try: idx = [r.lower() for r in hierarchy].index(matched.lower())
    except ValueError: return original

    # Генеруємо нове звання зі зсувом позиції
    seed = get_deterministic_seed(original_key)
    random.seed(seed)
    shift = random.choice([-2, -1, 1, 2])
    new_idx = max(0, min(len(hierarchy) - 1, idx + shift))
    masked = hierarchy[new_idx]

    # Уникаємо випадків коли звання мапиться саме на себе
    attempts = 0
    while masked.lower() == original_key and attempts < 10:
        shift = random.choice([-2, -1, 1, 2])
        new_idx = max(0, min(len(hierarchy) - 1, idx + shift))
        masked = hierarchy[new_idx]
        attempts += 1

    # Застосовуємо граматичний відмінок якщо потрібно
    if detected_case and detected_case != "nominative":
        masked = get_rank_in_case(masked, detected_case)

    final_masked = add_to_mapping(masking_dict, instance_counters, "rank", original_key, masked)
    # БАГ #16 & #18 FIX: Застосовуємо регістр ПІСЛЯ add_to_mapping
    if PRESERVE_CASE:
        # Спеціальна обробка для складених звань (з дефісом або пробілом)
        if '-' in original and original.istitle():
            # "Штаб-Сержант" → "Майор" → "Майор".title() = "Майор"
            return final_masked.title()

        # БАГ #18 FIX: Перевірка для багатослівних звань у Title Case
        # "Старший Лейтенант" має кожне слово з великої → застосовуємо .title()
        words = original.split()
        if len(words) > 1:
            # Перевіряємо чи кожне слово починається з великої літери
            all_title = all(word and word[0].isupper() for word in words if word)
            if all_title:
                return final_masked.title()

        # Інакше використовуємо стандартну логіку збереження регістру
        return _apply_original_case(original, final_masked)
    return final_masked

def mask_rank_preserve_case(original_text: str, masking_dict: Dict, instance_counters: Dict) -> str:
    """
    Маскує звання зі збереженням регістру та граматичного відмінка (Bug Fix #16-18).

    ОСОБЛИВОСТІ:
    - Зберігає регістр літер (UPPER, Title Case, lower case)
    - Зберігає граматичний відмінок (називний, родовий, давальний, орудний)
    - Враховує рід звання (чоловічий/жіночий)
    - Підтримує складні звання: "капітан медичної служби у відставці"

    ВИПРАВЛЕНІ БАГИ:

    Bug #16: Некоректне застосування .title() на вже Title Case словах
    - Було: "Старший Сержант" → ".title()" → "Старший Сержант" (OK)
    - Було: "старший сержант" → ".title()" → "Старший Сержант" (OK)
    - Було: "СТАРШИЙ СЕРЖАНТ" → ".title()" → "Старший Сержант" (ПОМИЛКА!)
    - Виправлено: зберігаємо UPPER якщо оригінал був UPPER

    Bug #17: Втрата case для existing mappings
    - Було: якщо звання вже є в mapping, регістр не зберігався
    - Виправлено: застосовуємо _apply_original_case() для всіх випадків

    Bug #18: Некоректна обробка багатослівних звань у Title Case
    - Було: "Старший Лейтенант" → "старший капітан" → "Старший Капітан" (OK тільки перше слово)
    - Виправлено: правильна обробка кожного слова окремо

    АЛГОРИТМ:
    1. Витягує базове звання та додаткові слова ("у відставці", "медичної служби")
    2. Визначає граматичну форму через RANK_TO_NOMINATIVE
    3. Генерує нове звання з тим самим відмінком та родом
    4. Застосовує оригінальний регістр
    5. Додає назад додаткові слова

    Args:
        original_text: Текст звання для маскування (будь-який регістр, будь-який відмінок)
        masking_dict: Словник маппінгів для збереження відповідностей
        instance_counters: Лічильники екземплярів для instance tracking

    Returns:
        Замасковане звання з збереженням регістру, відмінка та роду

    Note:
        Використовує extract_base_rank() для розділення звання на частини
    """
    base_rank_text, additional_words = extract_base_rank(original_text)
    base_male_form, detected_case, gender = get_rank_info(base_rank_text)

    if not base_male_form:
        masked_result = mask_rank(base_rank_text, masking_dict, instance_counters)
        return f"{masked_result} {additional_words}" if additional_words else masked_result

    masked_base_male = mask_rank(base_male_form, masking_dict, instance_counters)
    final_rank = None

    if gender == 'female':
        if masked_base_male.lower() in RANK_FEMININE_MAP:
            masked_base_female = RANK_FEMININE_MAP[masked_base_male.lower()]
            if masked_base_female in RANK_DECLENSIONS_FEMALE and detected_case:
                final_rank = RANK_DECLENSIONS_FEMALE[masked_base_female].get(detected_case, masked_base_female)
            else: final_rank = masked_base_female
        else:
            if masked_base_male.lower() in RANK_DECLENSIONS and detected_case:
                final_rank = RANK_DECLENSIONS[masked_base_male.lower()].get(detected_case, masked_base_male)
            else: final_rank = masked_base_male
    else:
        if masked_base_male.lower() in RANK_DECLENSIONS and detected_case:
            final_rank = RANK_DECLENSIONS[masked_base_male.lower()].get(detected_case, masked_base_male)
        else: final_rank = masked_base_male

    if PRESERVE_CASE and final_rank:
        final_rank = _apply_original_case(base_rank_text, final_rank)
    result = final_rank if final_rank else masked_base_male
    return f"{result} {additional_words}" if additional_words else result

# ============================================================================
# MAIN LOGIC
# ============================================================================

def normalize_broken_ranks(text: str) -> str:
    """
    Нормалізує розірвані звання у тексті (Bug Fix #15).

    ПРОБЛЕМА:
    Звання може бути розірване переносом рядка в документах:
    - "старшого\nсержанта" → розпізнається як два окремі слова
    - "капітану\nмедичної служби" → втрачається зв'язок слів

    РІШЕННЯ:
    Функція склеює розірвані звання перед основною обробкою:
    - "старшого\nсержанта" → "старшого сержанта"
    - "капітану\nмедичної\nслужби" → "капітану медичної служби"

    АЛГОРИТМ:
    1. Шукає у тексті перший фрагмент звання (наприклад, "старшого")
    2. Перевіряє чи після \n йде другий фрагмент ("сержанта")
    3. Якщо так - видаляє \n між ними
    4. Повторює для всіх відомих звань з RANKS_LIST

    Args:
        text: Вхідний текст з можливими розірваними званнями

    Returns:
        Текст з нормалізованими (склеєними) званнями

    Note:
        Виконується ПЕРЕД основним маскуванням у mask_text_context_aware()
    """
    # Беремо тільки складені звання (ті, що містять пробіл)
    multi_word_ranks = [r for r in ALL_RANK_FORMS if ' ' in r]

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

    АЛГОРИТМ (покроково):

    1. НОРМАЛІЗАЦІЯ:
       - Викликає normalize_broken_ranks() для склеювання розірваних звань

    2. ОБРОБКА РЯДКІВ:
       - Розбиває текст на окремі рядки
       - Для кожного рядка:
         a) Перевіряє чи схожий на рядок з ПІБ (looks_like_pib_line)
         b) Якщо так - використовує parse_hybrid_line() для розпізнавання звання+ПІБ
         c) Ітеративно маскує звання та ПІБ (до 10 ітерацій на рядок)

    3. ІТЕРАТИВНЕ МАСКУВАННЯ (для кожного рядка):
       Цикл до 10 разів:
       - Шукає звання через ALL_RANK_FORMS
       - Шукає ПІБ через parse_hybrid_line()
       - Якщо нічого не знайдено - break
       - Якщо знайдено тільки звання без ПІБ - пропускає та шукає далі
       - Якщо знайдено звання + ПІБ:
         * Маскує звання через mask_rank_preserve_case()
         * Маскує ПІБ через mask_surname(), mask_name(), mask_patronymic()
         * Замінює в рядку
       - Продовжує до вичерпання звань/ПІБ

    4. МАСКУВАННЯ ІНШИХ ДАНИХ:
       - ІПН (10 цифр)
       - Паспорти (9 цифр)
       - Військові ID
       - Військові частини
       - Номери наказів та БР
       - Дати

    5. ОБ'ЄДНАННЯ:
       - З'єднує всі оброблені рядки назад в текст

    ЧОМУ ІТЕРАТИВНИЙ ПІДХІД:
    У деяких документах на одному рядку може бути кілька звань та ПІБ:
    "капітан Петренко та майор Сидоренко"
    Ітеративний підхід знаходить та маскує кожну пару послідовно.

    ПОРЯДОК МАСКУВАННЯ (критично важливий):
    1. Спочатку звання + ПІБ (найскладніше, потребує контексту)
    2. Потім окремі ідентифікатори (ІПН, паспорти, військові ID)
    3. Нарешті інші дані (номери, дати)

    Args:
        text: Вхідний текст для маскування
        masking_dict: Словник маппінгів для збереження відповідностей
        instance_counters: Лічильники екземплярів для instance tracking

    Returns:
        Повністю замаскований текст

    Note:
        - Використовує глобальні флаги MASK_* для вибіркового маскування
        - Зберігає форматування та структуру оригінального тексту
        - Підтримує Unicode (кирилицю)
    """
    # === ШАГ 0: Нормалізація розірваних звань (Щоб уникнути дублювання "старшого старшого")
    text = normalize_broken_ranks(text)

    items_to_mask = []
    items_to_skip = []

    if not MASK_DATES:
        for match in re.finditer(UKRAINIAN_DATE_PATTERN, text):
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

    if MASK_ORDERS or MASK_BR_NUMBERS:
        for match in re.finditer(r'№', text):
            result = analyze_number_sign_context(text, match)
            if result: items_to_mask.append(result)

    if MASK_BR_NUMBERS:
        for match in re.finditer(r'\bБР\b', text, re.IGNORECASE):
            result = analyze_br_keyword(text, match)
            if result:
                skip = any(result['start'] < item['end'] and result['end'] > item['start'] for item in items_to_skip)
                skip = skip or any(result['start'] < item['end'] and result['end'] > item['start'] for item in items_to_mask)
                if not skip: items_to_mask.append(result)

    for item_type, flag, pattern in [
        ('ipn', MASK_IPN, r'\b\d{10}\b'),
        ('passport_id', MASK_PASSPORT, r'\b\d{9}\b'),
        ('military_id', MASK_MILITARY_ID, r'\b[A-ZА-Я]{2}[\s-]?\d{6}\b'),
        ('military_unit', MASK_UNITS, r'\b[А-ЯA-Z]\d{4}\b')
    ]:
        if flag:
            for match in re.finditer(pattern, text, re.IGNORECASE if item_type == 'military_id' else 0):
                skip = any(match.start() >= item['start'] and match.end() <= item['end'] for item in items_to_skip)
                skip = skip or any(match.start() < item['end'] and match.end() > item['start'] for item in items_to_mask)
                if not skip: items_to_mask.append({'type': item_type, 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})

    if MASK_BRIGADES:
        for match in COMPILED_PATTERNS["brigade_number"].finditer(text):
            skip = any(match.start() >= item['start'] and match.end() <= item['end'] for item in items_to_skip)
            skip = skip or any(match.start() < item['end'] and match.end() > item['start'] for item in items_to_mask)
            if not skip: items_to_mask.append({'type': 'brigade_number', 'full_text': match.group(0), 'number_part': match.group(1), 'start': match.start(), 'end': match.end()})

    if MASK_DATES:
        for match in COMPILED_PATTERNS["date"].finditer(text):
            if is_valid_date(int(match.group(1)), int(match.group(2)), int(match.group(3))):
                skip = any(match.start() >= item['start'] and match.end() <= item['end'] for item in items_to_skip)
                skip = skip or any(match.start() < item['end'] and match.end() > item['start'] for item in items_to_mask)
                if not skip: items_to_mask.append({'type': 'date', 'full_text': match.group(0), 'number_part': match.group(0), 'start': match.start(), 'end': match.end()})

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

            if rank and MASK_RANKS:
                masked_rank_val = mask_rank_preserve_case(rank, masking_dict, instance_counters)
                final_line = final_line.replace(rank, masked_rank_val, 1)
                current_line_for_parsing = current_line_for_parsing.replace(rank, "___RANK_MASKED___", 1)

            if pib and MASK_NAMES:
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

def main():
    parser = argparse.ArgumentParser(description=f"Data Masking Script v{__version__}", formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-i", "--input", default="input.txt", help="Input file")
    parser.add_argument("-o", "--output", help="Output file")
    parser.add_argument("--no-report", action="store_true", help="No report")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    global DEBUG_MODE
    if args.debug: DEBUG_MODE = True

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {args.input} not found")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = random.randint(100, 999)
    is_json = input_path.suffix.lower() == '.json'

    if args.output: output_path = Path(args.output)
    else: output_path = Path(f"output_{timestamp}_{random_suffix}{'.json' if is_json else '.txt'}")

    map_path = Path(f"masking_map_{timestamp}_{random_suffix}.json")
    report_path = Path(f"masking_report_{timestamp}_{random_suffix}.txt")

    masking_dict = {
        "version": __version__, "timestamp": datetime.now().isoformat(), "input_file": str(input_path),
        "statistics": {},
        "mappings": {k: {} for k in ["ipn", "passport_id", "military_id", "surname", "name", "military_unit", "order_number", "order_number_with_letters", "br_number", "br_number_slash", "br_number_complex", "rank", "brigade_number", "date", "patronymic"]},
        "instance_tracking": {}
    }
    instance_counters = {}

    print(f"Processing {input_path}...")
    try:
        with open(input_path, 'r', encoding='utf-8', newline='') as f:
            if is_json: input_data = json.load(f)
            else: input_data = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    if is_json:
        masked_data = mask_json_recursive(input_data, masking_dict, instance_counters)
    else:
        masked_data = mask_text_context_aware(input_data, masking_dict, instance_counters)

    # ФОРМУВАННЯ ПОВНОЇ СТРУКТУРИ JSON
    masking_dict["instance_tracking"] = instance_counters

    total_unique = 0
    for category, mappings in masking_dict["mappings"].items():
        count = len(mappings)
        masking_dict["statistics"][category] = count
        total_unique += count
    masking_dict["statistics"]["total_masked"] = total_unique

    try:
        # Збереження результату
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            if is_json: json.dump(masked_data, f, ensure_ascii=False, indent=2)
            else: f.write(masked_data)

        # Збереження мапи
        with open(map_path, 'w', encoding='utf-8') as f:
            json.dump(masking_dict, f, ensure_ascii=False, indent=2)

        # ГЕНЕРАЦІЯ ДЕТАЛЬНОГО ЗВІТУ
        if not args.no_report:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\n")
                f.write("ЗВІТ МАСКУВАННЯ ДАНИХ\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"Дата та час: {masking_dict['timestamp']}\n")
                f.write(f"Вхідний файл: {input_path}\n")
                f.write(f"Вихідний файл: {output_path}\n\n")
                f.write("-" * 60 + "\n")
                f.write("СТАТИСТИКА МАСКУВАННЯ\n")
                f.write("-" * 60 + "\n\n")
                f.write(f"Загальна кількість УНІКАЛЬНИХ замаскованих елементів: {total_unique}\n\n")

                for key, value in sorted(masking_dict["statistics"].items()):
                    if key != "total_masked" and value > 0:
                        f.write(f"  • {key}: {value} (унікальних оригіналів)\n")

                f.write("\n" + "=" * 60 + "\n")
                f.write("СТАТИСТИКА ВХОДЖЕНЬ (Instance Tracking)\n")
                f.write("-" * 60 + "\n\n")
                for masked_val, count in sorted(masking_dict["instance_tracking"].items()):
                    f.write(f"  • '{masked_val}': {count} входжень\n")
                f.write("\n" + "=" * 60 + "\n")

        # ДЕТАЛЬНИЙ ВИВІД У КОНСОЛЬ
        print()
        print("✅ Маскування завершено успішно!")
        print()
        print(f"📊 Статистика:")
        print(f"   Загальна кількість УНІКАЛЬНИХ замаскованих елементів: {total_unique}")
        for key, value in sorted(masking_dict["statistics"].items()):
            if key != "total_masked" and value > 0:
                print(f"   • {key}: {value} (унікальних оригіналів)")
        print()
        print(f"   Статистика входжень (Instance Tracking):")
        # Виводимо тільки топ-10 для консолі, щоб не засмічувати
        sorted_instances = sorted(masking_dict["instance_tracking"].items(), key=lambda x: x[1], reverse=True)
        for masked_val, count in sorted_instances[:10]:
            print(f"   • '{masked_val}': {count} входжень")
        if len(sorted_instances) > 10:
            print(f"   ... та ще {len(sorted_instances) - 10} записів")

        print()
        print(f"📁 Файли збережено:")
        print(f"   • Замасковані дані: {output_path.absolute()}")
        print(f"   • Словник замін: {map_path.absolute()}")
        if not args.no_report:
            print(f"   • Звіт: {report_path.absolute()}")

    except Exception as e:
        print(f"❌ Помилка збереження файлів: {e}")

if __name__ == "__main__":
    main()