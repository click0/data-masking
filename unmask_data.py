#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Unmasking Script v2.3.2
Відновлення оригінальних даних з замаскованого файлу

Цей скрипт виконує зворотну операцію до data_masking.py: відновлює оригінальні
дані з замаскованих файлів, використовуючи збережений словник маппінгів.

ОНОВЛЕНО В v2.3.0:
- 🔐 Підтримка AES-256-GCM шифрування mapping файлів (.enc)
- 🔄 --to-version для конвертації між версіями маппінгів
- 📊 Структуроване логування через MaskingLogger
- ⚙️ Підтримка конфігураційних файлів (.yaml/.json)

ОНОВЛЕНО В v2.2.9:
- 🔧 Виправлено імпорти (datetime)
- 🔨 Синхронізація з rank_data.py
- 📄 Детальні коментарі та покращена структура

ФОРМАТ ВХІДНИХ ДАНИХ:
    1. Замаскований файл (output_TIMESTAMP.txt/json)
    2. Словник маппінгів (masking_map_TIMESTAMP.json або .enc)

ПРИКЛАД ВИКОРИСТАННЯ:
    # Автоматичний режим (шукає останню пару файлів)
    python unmask_data.py

    # Ручний режим з вказанням файлів
    python unmask_data.py output_20250101_120000_123.txt --map masking_map_20250101_120000_123.json

    # З вказанням output файлу
    python unmask_data.py output_20250101_120000_123.txt -o recovered_input.txt

    # З шифрованим mapping файлом
    python unmask_data.py output.txt --map masking_map.enc --password mypassword

    # З конфігураційним файлом
    python unmask_data.py -c config.yaml

Author: Vladyslav V. Prodan
Contact: github.com/click0
Version: 2.3.2
License: BSD 3-Clause
Year: 2025-2026
"""

import json
import sys
import argparse
import os
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Fix Unicode output on Windows (PyInstaller cp1252 issue)
if sys.platform == 'win32' and getattr(sys.stdout, 'encoding', 'utf-8').lower().replace('-', '') != 'utf8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================================
# МОДУЛІ v2.3.0
# ============================================================================

# Безпека (шифрування mapping файлів)
SECURITY_AVAILABLE = False
try:
    from modules.security import MappingSecurityManager, is_encryption_available
    SECURITY_AVAILABLE = True
except ImportError:
    pass

# Re-mask (ланцюгове перемаскування)
REMASK_AVAILABLE = False
try:
    from modules.re_mask import ChainUnmasker, load_chain, get_chain_info
    REMASK_AVAILABLE = True
except ImportError:
    pass

# Конфігурація
CONFIG_AVAILABLE = False
try:
    from modules.config import load_config, ConfigLoader
    CONFIG_AVAILABLE = True
except ImportError:
    pass

# Логування
LOGGING_AVAILABLE = False
try:
    from modules.masking_logger import MaskingLogger, setup_logging
    LOGGING_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# ІМПОРТ ДАНИХ З МОДУЛЯ
# ============================================================================
try:
    from rank_data import (
        RANK_DECLENSIONS,          # Відмінки чоловічих звань
        RANK_FEMININE_MAP,         # Мапа чоловічих → жіночих звань
        RANK_DECLENSIONS_FEMALE,   # Відмінки жіночих звань
        RANK_TO_NOMINATIVE,        # Зворотний індекс форм звань
        ALL_RANK_FORMS             # Відсортований список всіх форм
    )
except ImportError:
    from modules.rank_data import (
        RANK_DECLENSIONS,
        RANK_FEMININE_MAP,
        RANK_DECLENSIONS_FEMALE,
        RANK_TO_NOMINATIVE,
        ALL_RANK_FORMS
    )

# ============================================================================
# МЕТАДАНІ
# ============================================================================
__version__ = "2.3.2"
__author__ = "Vladyslav V. Prodan"
__contact__ = "github.com/click0"
__phone__ = "+38(099)6053340"
__license__ = "BSD 3-Clause"
__year__ = "2025-2026"

# ============================================================================
# КОНФІГУРАЦІЯ ПОШУКУ ФАЙЛІВ
# ============================================================================
# Директорії для автоматичного пошуку пар файлів (output + mapping)
SEARCH_DIRECTORIES = [
    Path('.'),          # Поточна директорія
    Path('./output'),   # Підтека output
    Path('./result')    # Підтека result
]

# ============================================================================
# ДОПОМІЖНІ ФУНКЦІЇ - АНАЛІЗ ТА РОЗПІЗНАВАННЯ
# ============================================================================

def get_rank_info(rank_form: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Отримує інформацію про звання за його граматичною формою.

    Використовує зворотний індекс RANK_TO_NOMINATIVE для швидкого пошуку.

    Args:
        rank_form: Будь-яка форма звання (наприклад, "солдату", "сержантці")

    Returns:
        Tuple з трьох елементів:
            - базова_форма: називний відмінок чоловічого роду ("солдат", "сержант")
            - відмінок: назва відмінка ('nominative', 'genitive', 'dative', 'instrumental')
            - рід: 'male' або 'female'

        Або (None, None, None) якщо звання не розпізнано

    """
    rank_lower = rank_form.lower()
    if rank_lower in RANK_TO_NOMINATIVE:
        return RANK_TO_NOMINATIVE[rank_lower]
    return None, None, None


def find_file_pairs(directories: List[Path]) -> List[Tuple[Path, Path, str]]:
    """
    Шукає пари файлів output + mapping для автоматичного unmask.

    Алгоритм:
        1. Сканує вказані директорії
        2. Знаходить файли з шаблоном output_TIMESTAMP.*
        3. Витягує timestamp з назви файлу
        4. Шукає відповідний masking_map_TIMESTAMP.json
        5. Повертає пари, відсортовані за timestamp (найновіші першими)

    Args:
        directories: Список директорій для пошуку

    Returns:
        Список tuple: (output_file_path, map_file_path, timestamp_string)
        Відсортовано за timestamp у зворотному порядку (найновіші першими)

    """
    pairs = []

    for directory in directories:
        # Пропускаємо неіснуючі або не-директорії
        if not directory.exists() or not directory.is_dir():
            continue

        # Знаходимо всі output файли (txt та json)
        output_files = list(directory.glob('output_*.txt')) + list(directory.glob('output_*.json'))

        for output_file in output_files:
            # Витягуємо timestamp з назви файлу
            # Формат: output_YYYYMMDD_HHMMSS_RRR.ext
            match = re.match(r'output_(\d{8}_\d{6}_\d{3})', output_file.stem)
            if not match:
                continue

            timestamp_suffix = match.group(1)

            # Шукаємо відповідний файл маппінгу
            map_file = directory / f"masking_map_{timestamp_suffix}.json"

            if map_file.exists():
                pairs.append((output_file, map_file, timestamp_suffix))

    # Сортуємо за timestamp у зворотному порядку (найновіші першими)
    pairs.sort(key=lambda x: x[2], reverse=True)
    return pairs


def auto_find_latest_pair() -> Optional[Tuple[Path, Path, Path]]:
    """
    Автоматично знаходить та вибирає останню пару файлів для unmask.

    Використовується коли користувач не вказав файли вручну.

    Returns:
        Tuple з трьох елементів:
            - output_file: шлях до замаскованого файлу
            - map_file: шлях до словника маппінгів
            - recovery_file: шлях для збереження відновленого файлу

        Або None якщо файли не знайдено

    Output:
        Виводить у консоль статус пошуку та знайдені файли
    """
    print("❗ Автоматичний режим")
    print("🔍 Шукаю пари файлів...\n")

    pairs = find_file_pairs(SEARCH_DIRECTORIES)

    if not pairs:
        print("❌ Не знайдено файлів!")
        return None

    print(f"✅ Знайдено {len(pairs)} пар")

    # Беремо найновіший (перший у списку після сортування)
    output_file, map_file, timestamp_suffix = pairs[0]
    print(f"\n⏰ Вибрано: {output_file.name}\n")

    # Формуємо ім'я для відновленого файлу
    extension = output_file.suffix
    recovery_file = output_file.parent / f"input_recovery_{timestamp_suffix}{extension}"

    return output_file, map_file, recovery_file


def check_mapping_version(masking_map: Dict) -> str:
    """
    Визначає версію структури mapping файлу.

    Різні версії data_masking.py використовують різні формати словників.
    Unmask має адаптуватися до версії для правильного відновлення.

    Args:
        masking_map: Завантажений словник маппінгів

    Returns:
        Версія логіки: 'v2.1', 'v2.0' або 'v1'

    Version differences:
        - v2.1+: Повна підтримка instance tracking, gender-aware ranks
        - v2.0: Базовий instance tracking
        - v1: Проста заміна рядків (без instance tracking)
    """
    version = masking_map.get("version", "1.0.0")

    if version.startswith("2.2") or version.startswith("2.1"):
        return "v2.1"
    elif version.startswith("2.0"):
        return "v2.0"
    else:
        return "v1"


def find_all_occurrences(text: str, pattern: str) -> List[Tuple[int, int]]:
    """
    Знаходить всі входження шаблону в тексті (case-insensitive).

    Використовує word boundaries для точного пошуку цілих слів.

    Args:
        text: Текст для пошуку
        pattern: Шаблон для пошуку (буде екрановано)

    Returns:
        Список tuple (start_position, end_position) для кожного входження

    Note:
        Пошук регістронезалежний (case-insensitive) для зручності
        Має fallback для складних символів, які можуть викликати regex помилки

    """
    occurrences = []

    # Використовуємо word boundaries (\b) для точного пошуку слів
    try:
        regex_pattern = r'(?<!\w)' + re.escape(pattern) + r'(?!\w)'
        for match in re.finditer(regex_pattern, text, re.IGNORECASE):
            occurrences.append((match.start(), match.end()))
    except re.error as e:
        # Fallback for complex characters that may cause regex errors
        print(f"Warning: invalid regex pattern for '{pattern}': {e}")

    return occurrences


def build_instance_map(masking_map: Dict) -> Dict[str, Dict[int, str]]:
    """
    Створює мапу для instance tracking при unmask.

    Instance tracking дозволяє відновити правильний оригінал при колізіях,
    коли різні оригінальні значення були замасковані в одне і те саме значення.

    ПРОБЛЕМА БЕЗ INSTANCE TRACKING:
        Original1: "Петренко" → Masked: "Іваненко" (instance 1)
        Original2: "Сидоренко" → Masked: "Іваненко" (instance 2)

        При unmask без tracking: всі "Іваненко" → "Петренко" (ПОМИЛКА!)
        З instance tracking: перший "Іваненко" → "Петренко", другий → "Сидоренко" ✓

    Структура мапи:
        {
            'Іваненко': {
                1: 'Петренко',   # перше входження
                2: 'Сидоренко'   # друге входження
            },
            'Коваленко': {
                1: 'Шевченко'
            }
        }

    Args:
        masking_map: Словник маскування у форматі v2.x

    Returns:
        Словник {masked_value: {instance_num: original_value}}

    """
    instance_map = {}
    mappings_data = masking_map.get("mappings", {})

    # Перебираємо всі категорії (surname, name, rank, ipn тощо)
    for category, mappings in mappings_data.items():
        for original, mask_info in mappings.items():
            # Формат v2.x: {"masked_as": "...", "instances": [1, 2, ...]}
            if isinstance(mask_info, dict) and "masked_as" in mask_info:
                masked_value = mask_info["masked_as"]
                instances = mask_info.get("instances", [])

                # Ініціалізуємо підсловник для цієї маски
                if masked_value not in instance_map:
                    instance_map[masked_value] = {}

                # Зберігаємо зв'язок: instance_num → original_value
                for instance_num in instances:
                    instance_map[masked_value][instance_num] = original

    return instance_map


def _apply_original_case(original: str, masked: str) -> str:
    """
    Відновлює регістр літер оригіналу на маскованому значенні.

    Зберігає три типи регістру:
        - UPPER CASE (всі великі)
        - Title Case (перша велика)
        - lower case (всі малі)

    Args:
        original: Оригінальний текст з регістром для відновлення
        masked: Текст для застосування регістру

    Returns:
        Текст з відновленим регістром

    """
    if not original or not masked:
        return masked

    # Всі великі
    if original.isupper():
        return masked.upper()
    # Перша велика, решта малі (Title Case)
    elif len(original) > 1 and original[0].isupper() and original[1:].islower():
        return masked.capitalize()
    # Всі малі
    else:
        return masked.lower()


def is_real_mask(value: str, masking_map: Dict, all_masked_values: set = None) -> bool:
    """
    Перевіряє, чи є слово реальною маскою (а не випадковим збігом з оригіналом).

    ПРОБЛЕМА:
        Якщо оригінал "Іваненко" був замаскований як "Петренко",
        а в тексті є реальне ім'я "Петренко" (не маска), то unmask може
        помилково спробувати його розмаскувати.

    РІШЕННЯ:
        Перевіряємо чи значення справді є маскою зі словника, а не оригіналом.

    Args:
        value: Значення для перевірки
        masking_map: Словник маппінгів
        all_masked_values: Опціонально, набір всіх масок для швидкої перевірки

    Returns:
        True якщо value є маскою, False якщо це оригінальне значення
    """
    value_lower = value.lower()

    # Швидка перевірка через попередньо створений набір
    if all_masked_values is not None:
        return value_lower in all_masked_values

    # Повільна перевірка через весь словник
    mappings = masking_map.get("mappings", {})
    for category, items in mappings.items():
        for original, mask_info in items.items():
            if isinstance(mask_info, dict) and "masked_as" in mask_info:
                if mask_info["masked_as"].lower() == value_lower:
                    return True

    return False


def extract_base_rank(full_rank_text: str) -> tuple:
    """
    Виділяє базове звання та додаткові слова зі складеного звання.

    Складені звання можуть містити:
        - Тип служби: "медичної служби", "юстиції"
        - Статус: "у відставці", "в запасі", "у запасі"

    Функція розділяє звання на:
        - Базове звання (для unmask через словник)
        - Додаткові слова (для додавання назад після unmask)

    Args:
        full_rank_text: Повний текст звання з можливими додатковими словами

    Returns:
        Tuple (базове_звання, додаткові_слова)

    Algorithm:
        1. Спочатку шукає тип служби (медична, юстиція)
        2. Потім шукає статус (відставка, запас)
        3. Зберігає обидві частини як додаткові слова
        4. Базове звання = все що залишилося
    """
    if not full_rank_text:
        return full_rank_text, ""

    # Можливі типи служб
    service_type_phrases = ['медичної служби', 'юстиції']

    # Можливі статуси військовослужбовця
    status_phrases = [
        'у відставці', 'в запасі', 'у запасі',
        'на пенсії', 'в резерві', 'у резерві'
    ]

    full_rank_lower = full_rank_text.lower()
    base_rank = full_rank_text
    additional_parts = []

    # 1. Шукаємо та виділяємо тип служби
    for phrase in service_type_phrases:
        if phrase in full_rank_lower:
            phrase_index = full_rank_lower.find(phrase)
            # Базове звання = все до типу служби
            base_rank = full_rank_text[:phrase_index].strip()
            # Зберігаємо тип служби зі збереженням регістру оригіналу
            additional_parts.append(full_rank_text[phrase_index:phrase_index + len(phrase)])

            # Видаляємо знайдене для подальшого пошуку статусу
            remaining_text = full_rank_text[phrase_index + len(phrase):].strip()
            full_rank_lower = remaining_text.lower()
            full_rank_text = remaining_text
            break

    # 2. Шукаємо та виділяємо статус
    for phrase in status_phrases:
        if phrase in full_rank_lower:
            # Якщо ще не знайшли тип служби, оновлюємо базове звання
            if not additional_parts:
                phrase_index = full_rank_text.lower().find(phrase)
                base_rank = full_rank_text[:phrase_index].strip()

            # Зберігаємо статус зі збереженням регістру
            phrase_start = full_rank_text.lower().find(phrase)
            additional_parts.append(full_rank_text[phrase_start:phrase_start + len(phrase)])
            break

    # Об'єднуємо додаткові частини через пробіл
    additional = ' '.join(additional_parts) if additional_parts else ""
    return base_rank, additional

# ============================================================================
# ГОЛОВНІ ФУНКЦІЇ UNMASK
# ============================================================================

def unmask_ranks_gender_aware(masked_text: str, masking_map: Dict) -> Tuple[str, Dict]:
    """
    Відновлення звань з урахуванням гендеру та граматичних відмінків.

    Це найскладніша функція unmask, яка враховує:
        1. Instance tracking (колізії маскування)
        2. Гендерну узгодженість (чоловічі/жіночі форми)
        3. Граматичні відмінки (називний, родовий, давальний, орудний)
        4. Збереження регістру літер (UPPER, Title, lower)
        5. Додаткові слова ("у відставці", "медичної служби")

    Алгоритм:
        1. Знаходить всі входження звань у тексті (зі словника ALL_RANK_FORMS)
        2. Додає fallback пошук для звань, яких немає у словнику
        3. Сортує знайдені звання за порядком у тексті
        4. Для кожного звання:
           a) Витягує базове звання та додаткові слова
           b) Визначає відмінок та рід через RANK_TO_NOMINATIVE
           c) Знаходиє оригінал через instance tracking
           d) Відновлює граматичну форму через RANK_DECLENSIONS
           e) Застосовує оригінальний регістр
        5. Виконує заміни з кінця тексту до початку (щоб не збити індекси)

    Args:
        masked_text: Замаскований текст
        masking_map: Словник маппінгів з data_masking.py

    Returns:
        Tuple (відновлений_текст, статистика)
        Статистика: {"restored_count": int, "skipped_count": int}

    """
    restored_text = masked_text
    stats = {"restored_count": 0, "skipped_count": 0}

    # Будуємо мапу тільки для звань (оптимізація)
    mappings = masking_map.get("mappings", {})
    temp_map_for_ranks = {"mappings": {"rank": mappings.get("rank", {})}}
    rank_instance_map = build_instance_map(temp_map_for_ranks)

    # Створюємо набір всіх замаскованих звань для швидкої перевірки is_real_mask
    all_masked_ranks = set()
    for original, mask_info in mappings.get("rank", {}).items():
        if isinstance(mask_info, dict) and "masked_as" in mask_info:
            all_masked_ranks.add(mask_info["masked_as"].lower())

    # ========================================================================
    # КРОК 1: ПОШУК ВСІХ ЗВАНЬ У ТЕКСТІ
    # ========================================================================

    # 1.A. Знаходимо звання зі словника (найточніший метод)
    all_found_ranks = []
    for rank_form in ALL_RANK_FORMS:
        pattern = r'\b' + re.escape(rank_form) + r'\b'
        for match in re.finditer(pattern, restored_text, re.IGNORECASE):
            all_found_ranks.append({
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0)
            })

    # 1.B. Fallback: знаходимо звання, які є масками, але не в словнику
    # (може статися якщо звання було замасковане, але немає у RANK_DECLENSIONS)
    for masked_rank in all_masked_ranks:
        pattern = r'\b' + re.escape(masked_rank) + r'\b'
        for match in re.finditer(pattern, restored_text, re.IGNORECASE):
            # Перевіряємо, чи не перекривається з вже знайденим звання
            overlaps = any(
                match.start() < found["end"] and match.end() > found["start"]
                for found in all_found_ranks
            )

            if not overlaps:
                all_found_ranks.append({
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "simple": True  # Позначка для простої заміни
                })

    # Сортуємо за порядком у тексті (зліва направо)
    all_found_ranks.sort(key=lambda x: x['start'])

    # ========================================================================
    # КРОК 2: ОБРОБКА КОЖНОГО ЗНАЙДЕНОГО ЗВАННЯ
    # ========================================================================

    replacements_to_do = []  # Список замін (start, end, replacement_text)
    instance_counters = {}    # Лічильники для instance tracking

    for found in all_found_ranks:
        # ====================================================================
        # ЛОГІКА A: ПРОСТА ЗАМІНА (без відновлення відмінка)
        # ====================================================================
        # Використовується для звань, яких немає у словнику RANK_DECLENSIONS

        if found.get("simple", False):
            full_rank_text = found["text"]
            base_rank, additional_words = extract_base_rank(full_rank_text)
            masked_rank_lower = base_rank.lower()

            # Instance tracking: рахуємо, яке це входження цієї маски
            instance_counters.setdefault(masked_rank_lower, 0)
            instance_counters[masked_rank_lower] += 1
            instance_num = instance_counters[masked_rank_lower]

            # Шукаємо оригінал для цього екземпляра
            if masked_rank_lower in rank_instance_map and instance_num in rank_instance_map[masked_rank_lower]:
                original_rank = rank_instance_map[masked_rank_lower][instance_num]

                # Перевіряємо що це справді маска (не випадковий збіг)
                if not is_real_mask(masked_rank_lower, masking_map, all_masked_ranks):
                    stats["skipped_count"] += 1
                    continue

                # Застосовуємо оригінальний регістр
                original_rank = _apply_original_case(base_rank, original_rank)

                # Додаємо назад додаткові слова ("у відставці" тощо)
                restored_full_rank = f"{original_rank} {additional_words}" if additional_words else original_rank

                replacements_to_do.append((found["start"], found["end"], restored_full_rank))
                stats["restored_count"] += 1
            else:
                stats["skipped_count"] += 1
            continue

        # ====================================================================
        # ЛОГІКА B: РОЗУМНА ЗАМІНА (з відновленням відмінку та роду)
        # ====================================================================
        # Використовується для звань зі словника RANK_DECLENSIONS

        full_rank_text = found["text"]
        base_rank_text, additional_words = extract_base_rank(full_rank_text)

        # Визначаємо базову форму, відмінок та рід через словник
        base_masked_form, case, gender = get_rank_info(base_rank_text)

        if not base_masked_form:
            continue  # Звання не знайдено у словнику

        # Instance tracking
        instance_counters.setdefault(base_masked_form, 0)
        instance_counters[base_masked_form] += 1
        instance_num = instance_counters[base_masked_form]

        # Шукаємо оригінал для цього екземпляра
        if base_masked_form in rank_instance_map and instance_num in rank_instance_map[base_masked_form]:
            original_base_form = rank_instance_map[base_masked_form][instance_num]

            # Перевіряємо що це справді маска
            if not is_real_mask(base_masked_form, masking_map, all_masked_ranks):
                stats["skipped_count"] += 1
                continue

            # Відновлюємо граматичну форму оригіналу
            reconstructed_form = original_base_form

            # Жіноча форма: шукаємо у RANK_DECLENSIONS_FEMALE
            if gender == 'female':
                if original_base_form in RANK_FEMININE_MAP:
                    base_female = RANK_FEMININE_MAP[original_base_form]
                    if base_female in RANK_DECLENSIONS_FEMALE:
                        # Застосовуємо потрібний відмінок
                        reconstructed_form = RANK_DECLENSIONS_FEMALE[base_female].get(case, base_female)

            # Чоловіча форма: шукаємо у RANK_DECLENSIONS
            else:
                if original_base_form in RANK_DECLENSIONS:
                    # Застосовуємо потрібний відмінок
                    reconstructed_form = RANK_DECLENSIONS[original_base_form].get(case, original_base_form)

            # Застосовуємо оригінальний регістр
            reconstructed_form = _apply_original_case(base_rank_text, reconstructed_form)

            # Додаємо назад додаткові слова
            restored_full_rank = f"{reconstructed_form} {additional_words}" if additional_words else reconstructed_form

            replacements_to_do.append((found["start"], found["end"], restored_full_rank))
            stats["restored_count"] += 1
        else:
            stats["skipped_count"] += 1

    # ========================================================================
    # КРОК 3: ВИКОНАННЯ ЗАМІН
    # ========================================================================
    # Заміни виконуються з кінця до початку, щоб не збивати індекси позицій

    replacements_to_do.sort(key=lambda x: x[0], reverse=True)
    for start, end, original in replacements_to_do:
        restored_text = restored_text[:start] + original + restored_text[end:]

    return restored_text, stats


def unmask_other_data(masked_text: str, masking_map: Dict) -> Tuple[str, Dict]:
    """
    Відновлення інших типів даних (окрім звань).

    Обробляє всі категорії даних: ІПН, паспорти, прізвища, імена, військові ID,
    номери наказів, БР номери, дати тощо.

    Використовує просту логіку instance tracking без граматичних відмінків.

    Args:
        masked_text: Замаскований текст
        masking_map: Словник маппінгів (без категорії "rank")

    Returns:
        Tuple (відновлений_текст, статистика)

    Algorithm:
        1. Створює instance map для всіх категорій окрім звань
        2. Для кожної маски знаходить всі входження в тексті
        3. Застосовує instance tracking для правильного відновлення
        4. Зберігає оригінальний регістр літер
        5. Виконує заміни з кінця тексту
    """
    restored_text = masked_text

    # Копіюємо маппінг без звань (звання обробляються окремо)
    mappings_copy = masking_map.get("mappings", {}).copy()
    if "rank" in mappings_copy:
        del mappings_copy["rank"]

    # Будуємо instance map для всіх категорій окрім звань
    instance_map = build_instance_map({"mappings": mappings_copy})

    stats = {"restored_count": 0, "skipped_count": 0}
    replacements_to_do = []

    # Обробляємо кожну маску
    for masked_value, instance_to_original in instance_map.items():
        # Знаходимо всі входження цієї маски в тексті
        occurrences = find_all_occurrences(restored_text, masked_value)

        # Для кожного входження визначаємо номер екземпляра
        for instance_num, (start_pos, end_pos) in enumerate(occurrences, 1):
            if instance_num in instance_to_original:
                original_value = instance_to_original[instance_num]
                replacements_to_do.append((start_pos, end_pos, original_value, masked_value))
                stats["restored_count"] += 1
            else:
                stats["skipped_count"] += 1

    # Виконуємо заміни з кінця до початку
    replacements_to_do.sort(key=lambda x: x[0], reverse=True)
    for start_pos, end_pos, original_value, masked_value in replacements_to_do:
        # Перевіряємо що маска на своєму місці (case-insensitive)
        if restored_text[start_pos:end_pos].lower() == masked_value.lower():
            masked_segment = restored_text[start_pos:end_pos]
            # Зберігаємо оригінальний регістр
            original_value = _apply_original_case(masked_segment, original_value)
            restored_text = restored_text[:start_pos] + original_value + restored_text[end_pos:]

    return restored_text, stats


def unmask_text_v2(masked_text: str, masking_map: Dict, map_version: str) -> Tuple[str, Dict]:
    """
    Основна функція unmask для версій 2.x маппінгів.

    Координує процес unmask у правильному порядку:
        1. Спочатку звання (найскладніші, з граматикою)
        2. Потім все інше (прізвища, імена, ІПН тощо)

    Args:
        masked_text: Замаскований текст
        masking_map: Словник маппінгів
        map_version: Версія логіки ('v2.1', 'v2.0')

    Returns:
        Tuple (відновлений_текст, об'єднана_статистика)
    """
    # Перевірка на re-mask (багатопрохідне маскування)
    if "re_mask_passes" in masking_map:
        passes = masking_map["re_mask_passes"]
        total_stats = {"restored_count": 0, "skipped_count": 0}
        text = masked_text
        # Зворотний порядок: спочатку скасовуємо останній прохід
        for pass_map in reversed(passes):
            pass_version = check_mapping_version(pass_map)
            text, stats = unmask_text_v2(text, pass_map, pass_version)
            total_stats["restored_count"] += stats.get("restored_count", 0)
            total_stats["skipped_count"] += stats.get("skipped_count", 0)
        return text, total_stats

    if map_version == "v2.1":
        # Крок 1: Відновлюємо звання (з граматикою та гендером)
        text_after_ranks, rank_stats = unmask_ranks_gender_aware(masked_text, masking_map)

        # Крок 2: Відновлюємо все інше
        final_text, other_stats = unmask_other_data(text_after_ranks, masking_map)

        # Об'єднуємо статистику
        return final_text, {
            "restored_count": rank_stats["restored_count"] + other_stats["restored_count"],
            "skipped_count": rank_stats["skipped_count"] + other_stats["skipped_count"]
        }
    else:
        # Для v2.0 використовуємо просту логіку без звань
        return unmask_other_data(masked_text, masking_map)


def unmask_text_v1(masked_text: str, masking_map: Dict) -> Tuple[str, Dict]:
    """
    Unmask для старих версій 1.x (проста заміна рядків).

    Стара логіка без instance tracking - просто заміна усіх входжень.
    Може давати некоректні результати при колізіях маскування.

    Args:
        masked_text: Замаскований текст
        masking_map: Словник маппінгів v1.x

    Returns:
        Tuple (відновлений_текст, статистика)
    """
    restored_text = masked_text
    stats = {"restored_count": 0, "skipped_count": 0}
    all_replacements = []

    # Збираємо всі пари (маска, оригінал)
    for category, cat_mappings in masking_map.get("mappings", {}).items():
        for original, masked in cat_mappings.items():
            if isinstance(masked, str):
                all_replacements.append((masked, original))

    # Сортуємо за довжиною (довші першими, щоб уникнути часткових замін)
    all_replacements.sort(key=lambda x: len(x[0]), reverse=True)

    # Виконуємо заміни
    for masked, original in all_replacements:
        if masked in restored_text:
            stats["restored_count"] += restored_text.count(masked)
            restored_text = restored_text.replace(masked, original)

    return restored_text, stats


def unmask_json_recursive(masked_data: Any, masking_map: Dict, map_version: str) -> Any:
    """
    Рекурсивний unmask для JSON структур.

    Обробляє вкладені словники та списки, застосовуючи unmask до всіх рядків.

    Args:
        masked_data: Замасковані дані (dict, list, str або інше)
        masking_map: Словник маппінгів
        map_version: Версія логіки unmask

    Returns:
        Відновлені дані з тією ж структурою

    """
    if isinstance(masked_data, dict):
        # Рекурсивно обробляємо всі значення словника
        return {k: unmask_json_recursive(v, masking_map, map_version) for k, v in masked_data.items()}

    elif isinstance(masked_data, list):
        # Рекурсивно обробляємо всі елементи списку
        return [unmask_json_recursive(item, masking_map, map_version) for item in masked_data]

    elif isinstance(masked_data, str):
        # Застосовуємо unmask до рядків
        if map_version.startswith("v2"):
            restored, _ = unmask_text_v2(masked_data, masking_map, map_version)
        else:
            restored, _ = unmask_text_v1(masked_data, masking_map)
        return restored

    else:
        # Інші типи (int, bool, None) повертаємо без змін
        return masked_data

# ============================================================================
# CHAIN UNMASK (multi-pass reverse restoration)
# ============================================================================

def unmask_chain(masked_text: str, chain_data: Dict) -> Tuple[str, Dict]:
    """
    Unmask a multi-pass (re-mask chain) masked text by reversing passes.

    Applies unmask in reverse order: last pass first, then second-to-last, etc.
    This correctly restores the original text through the chain of mappings.

    Args:
        masked_text: Text masked with multiple passes
        chain_data: Chain mapping dict with "passes" list

    Returns:
        Tuple (restored_text, combined_stats)
    """
    passes = chain_data.get("passes", [])
    if not passes:
        return masked_text, {"restored_count": 0, "skipped_count": 0}

    total_stats = {"restored_count": 0, "skipped_count": 0}
    text = masked_text

    # Reverse order: undo last pass first
    for pass_data in reversed(passes):
        pass_version = check_mapping_version(pass_data)
        text, stats = unmask_text_v2(text, pass_data, pass_version)
        total_stats["restored_count"] += stats.get("restored_count", 0)
        total_stats["skipped_count"] += stats.get("skipped_count", 0)

    return text, total_stats


def unmask_json_chain(masked_data, chain_data: Dict):
    """
    Unmask JSON data masked with multiple passes (chain).

    Args:
        masked_data: JSON data (dict, list, str)
        chain_data: Chain mapping dict with "passes" list

    Returns:
        Restored JSON data
    """
    passes = chain_data.get("passes", [])
    if not passes:
        return masked_data

    data = masked_data
    for pass_data in reversed(passes):
        pass_version = check_mapping_version(pass_data)
        data = unmask_json_recursive(data, pass_data, pass_version)

    return data


def is_chain_mapping(masking_map: Dict) -> bool:
    """Check if a mapping dict is a chain (multi-pass) mapping."""
    return "passes" in masking_map and isinstance(masking_map["passes"], list)


# ============================================================================
# ЗАВАНТАЖЕННЯ ТА УТИЛІТИ v2.3.0
# ============================================================================

def load_mapping_file(map_path: Path, password: str = None) -> Dict:
    """
    Завантажує mapping файл з підтримкою шифрування.

    Підтримує:
        - .json файли (звичайний JSON)
        - .enc файли (AES-256-GCM зашифровані)

    Пріоритет пароля:
        1. Параметр password (з --password)
        2. Змінна оточення MASKING_PASSWORD
        3. Змінна оточення UNMASK_PASSWORD

    Args:
        map_path: Шлях до mapping файлу (.json або .enc)
        password: Опціональний пароль для дешифрування

    Returns:
        Словник маппінгів

    Raises:
        ValueError: Якщо .enc файл, але шифрування недоступне або пароль не вказано
        FileNotFoundError: Якщо файл не знайдено
    """
    if not map_path.exists():
        raise FileNotFoundError(f"Файл маппінгу не знайдено: {map_path}")

    if map_path.suffix == '.enc':
        if not SECURITY_AVAILABLE:
            raise ValueError(
                "Для роботи з .enc файлами потрібен модуль security. "
                "Встановіть: pip install cryptography"
            )

        # Пріоритет пароля: параметр → MASKING_PASSWORD → UNMASK_PASSWORD
        if not password:
            password = os.environ.get('MASKING_PASSWORD', '')
        if not password:
            password = os.environ.get('UNMASK_PASSWORD', '')
        if not password:
            raise ValueError(
                "Для дешифрування .enc файлу потрібен пароль. "
                "Вкажіть --password або встановіть MASKING_PASSWORD / UNMASK_PASSWORD"
            )

        security_mgr = MappingSecurityManager(password)
        return security_mgr.decrypt_mapping(map_path)
    else:
        with open(map_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def show_chain_info(masking_map: Dict) -> None:
    """
    Показує інформацію про ланцюг перемаскування.

    Args:
        masking_map: Словник маппінгів (може бути chain)
    """
    if REMASK_AVAILABLE:
        info = get_chain_info(masking_map)
        if info:
            print(f"📋 Інформація про ланцюг:")
            for key, value in info.items():
                print(f"   {key}: {value}")
        else:
            print("ℹ️ Це не ланцюговий mapping файл")
    else:
        if is_chain_mapping(masking_map):
            passes = masking_map.get("passes", [])
            print(f"📋 Ланцюг з {len(passes)} проходів")
            for i, p in enumerate(passes, 1):
                v = p.get("version", "?")
                print(f"   Прохід {i}: v{v}")
        else:
            print("ℹ️ Це не ланцюговий mapping файл")


# ============================================================================
# ГОЛОВНА ФУНКЦІЯ (ENTRY POINT)
# ============================================================================

def main():
    """
    Головна функція CLI для unmask.

    Підтримує режими:
        1. Автоматичний: шукає останню пару файлів
        2. Ручний: користувач вказує файли
        3. З конфігурацією: параметри з config файлу
        4. З шифруванням: підтримка .enc mapping файлів
    """
    # ========================================================================
    # ПАРСИНГ АРГУМЕНТІВ
    # ========================================================================

    epilog_text = """
Examples:
  %(prog)s                                          # Auto mode
  %(prog)s output.txt --map masking_map.json        # Manual mode
  %(prog)s output.txt -o recovered.txt              # With output file
  %(prog)s output.txt --map map.enc --password pwd  # Encrypted mapping
  %(prog)s -c config.yaml                           # With config file
  %(prog)s output.txt --chain-info                  # Chain info
"""

    parser = argparse.ArgumentParser(
        description=f'Data Unmasking Script v{__version__}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=epilog_text
    )
    parser.add_argument('masked_file', nargs='?', help='Masked file path')
    parser.add_argument('--map', '-m', dest='map_file', help='Mapping file (.json or .enc)')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('-V', '--version', action='version',
                        version=f'%(prog)s {__version__}')

    # Аргументи шифрування (якщо модуль доступний)
    if SECURITY_AVAILABLE:
        security_group = parser.add_argument_group('security options')
        security_group.add_argument('--password', help='Password for encrypted mapping files')
        security_group.add_argument('--password-env', metavar='VAR',
                                    help='Environment variable name containing password')

    # Аргументи re-mask (якщо модуль доступний)
    if REMASK_AVAILABLE:
        remask_group = parser.add_argument_group('re-mask options')
        remask_group.add_argument('--to-version', metavar='VERSION',
                                  help='Convert mapping to specified version')
        remask_group.add_argument('--chain-info', action='store_true',
                                  help='Show chain mapping information and exit')

    # Аргумент конфігурації (якщо модуль доступний)
    if CONFIG_AVAILABLE:
        config_group = parser.add_argument_group('config options')
        config_group.add_argument('-c', '--config', metavar='FILE',
                                  help='Configuration file (.yaml or .json)')

    # Аргументи логування (якщо модуль доступний)
    if LOGGING_AVAILABLE:
        log_group = parser.add_argument_group('logging options')
        log_group.add_argument('--log-level', default='INFO',
                               choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                               help='Logging level (default: INFO)')
        log_group.add_argument('--log-file', metavar='FILE',
                               help='Log file path')

    args = parser.parse_args()

    # ========================================================================
    # ІНІЦІАЛІЗАЦІЯ ЛОГЕРА
    # ========================================================================

    logger = None
    if LOGGING_AVAILABLE:
        log_level = getattr(args, 'log_level', 'INFO')
        log_file = getattr(args, 'log_file', None)
        logger = setup_logging(level=log_level, log_file=log_file)
        logger.info(f"Data Unmasking Script v{__version__}")

    def log_info(msg):
        if logger:
            logger.info(msg)

    def log_error(msg):
        if logger:
            logger.error(msg)

    def log_debug(msg):
        if logger:
            logger.debug(msg)

    # ========================================================================
    # ЗАВАНТАЖЕННЯ КОНФІГУРАЦІЇ
    # ========================================================================

    config = {}
    if CONFIG_AVAILABLE and getattr(args, 'config', None):
        try:
            config = load_config(args.config)
            log_info(f"Конфігурацію завантажено з {args.config}")
        except Exception as e:
            print(f"❌ Помилка завантаження конфігурації: {e}")
            log_error(f"Помилка завантаження конфігурації: {e}")
            return

    # ========================================================================
    # ВИЗНАЧЕННЯ ПАРОЛЯ (пріоритет: --password > --password-env > config > env)
    # ========================================================================

    password = None
    if SECURITY_AVAILABLE:
        if getattr(args, 'password', None):
            password = args.password
        elif getattr(args, 'password_env', None):
            password = os.environ.get(args.password_env, '')
        elif config.get('password'):
            password = config['password']

    # ========================================================================
    # ЛОГІКА ПОШУКУ ТА ВИБОРУ ФАЙЛІВ
    # ========================================================================

    if not args.masked_file:
        # Автоматичний режим
        result = auto_find_latest_pair()
        if result is None:
            return
        masked_path, map_path, output_path = result
        log_info(f"Автоматичний режим: {masked_path.name}")
    else:
        # Ручний режим
        masked_path = Path(args.masked_file)
        if not masked_path.exists():
            print(f"❌ Файл не знайдено: {masked_path}")
            log_error(f"Файл не знайдено: {masked_path}")
            return

        # Визначаємо шлях до mapping файлу
        if args.map_file:
            map_path = Path(args.map_file)
        else:
            # Спроба вгадати ім'я мапи за ім'ям output файлу
            filename = masked_path.stem
            if filename.startswith('output_'):
                # output_20250101_120000_123 → masking_map_20250101_120000_123
                map_path = masked_path.parent / f"masking_map_{filename[7:]}.json"
                # Автоматичне виявлення .enc файлу поруч з .json
                enc_path = map_path.with_suffix('.enc')
                if not map_path.exists() and enc_path.exists():
                    map_path = enc_path
                    log_info(f"Знайдено шифрований mapping: {enc_path.name}")
            else:
                print("❌ Будь ласка, вкажіть файл маппінгу через --map")
                log_error("Файл маппінгу не вказано")
                return

        if not map_path.exists():
            print(f"❌ Файл маппінгу не знайдено: {map_path}")
            log_error(f"Файл маппінгу не знайдено: {map_path}")
            return

        # Визначаємо шлях для output файлу
        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = masked_path.parent / f"input_recovery_{timestamp}{masked_path.suffix}"

    # ========================================================================
    # ЗАВАНТАЖЕННЯ ФАЙЛІВ
    # ========================================================================

    try:
        # Завантажуємо словник маппінгів (з підтримкою шифрування)
        masking_map = load_mapping_file(map_path, password=password)
        log_info(f"Mapping завантажено: {map_path.name}")

        # Обробка --chain-info (показати інформацію та вийти)
        if REMASK_AVAILABLE and getattr(args, 'chain_info', False):
            show_chain_info(masking_map)
            return

        # Обробка --to-version (конвертація версії)
        if REMASK_AVAILABLE and getattr(args, 'to_version', None):
            try:
                chain_unmasker = ChainUnmasker(masking_map)
                converted = chain_unmasker.convert_to_version(args.to_version)
                output_converted = map_path.with_suffix(f'.v{args.to_version}.json')
                with open(output_converted, 'w', encoding='utf-8') as f:
                    json.dump(converted, f, ensure_ascii=False, indent=2)
                print(f"✅ Конвертовано до версії {args.to_version}: {output_converted}")
                log_info(f"Конвертовано до версії {args.to_version}")
                return
            except Exception as e:
                print(f"❌ Помилка конвертації: {e}")
                log_error(f"Помилка конвертації: {e}")
                return

        # Завантажуємо замасковані дані (JSON або текст)
        with open(masked_path, 'r', encoding='utf-8', newline='') as f:
            if masked_path.suffix == '.json':
                masked_data = json.load(f)
            else:
                masked_data = f.read()

        log_debug(f"Замасковані дані завантажено: {masked_path.name}")

    except Exception as e:
        print(f"❌ Помилка читання: {e}")
        log_error(f"Помилка читання: {e}")
        return

    # ========================================================================
    # ПРОЦЕС UNMASK
    # ========================================================================

    start_time = time.time()

    # Check if this is a chain mapping (multi-pass)
    if is_chain_mapping(masking_map):
        total_passes = masking_map.get("total_passes", len(masking_map["passes"]))
        print(f"🔄 Розмаскування {masked_path.name} (ланцюг з {total_passes} проходів)...")
        log_info(f"Розмаскування ланцюга з {total_passes} проходів")

        if masked_path.suffix == '.json':
            restored_data = unmask_json_chain(masked_data, masking_map)
            stats = {"restored_count": 0, "skipped_count": 0}
        else:
            restored_data, stats = unmask_chain(masked_data, masking_map)
    else:
        # Single-pass unmask (original logic)
        map_version = check_mapping_version(masking_map)
        print(f"🔄 Розмаскування {masked_path.name} (логіка {map_version})...")
        log_info(f"Розмаскування {masked_path.name} (логіка {map_version})")

        if masked_path.suffix == '.json':
            restored_data = unmask_json_recursive(masked_data, masking_map, map_version)
            stats = {"restored_count": 0, "skipped_count": 0}
        else:
            if map_version.startswith("v2"):
                restored_data, stats = unmask_text_v2(masked_data, masking_map, map_version)
            else:
                restored_data, stats = unmask_text_v1(masked_data, masking_map)

    # ========================================================================
    # ЗБЕРЕЖЕННЯ РЕЗУЛЬТАТУ
    # ========================================================================

    try:
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            if masked_path.suffix == '.json':
                json.dump(restored_data, f, ensure_ascii=False, indent=2)
            else:
                f.write(restored_data)

        elapsed = time.time() - start_time
        print(f"✅ Готово! Збережено у: {output_path}")
        print(f"⏱️ Час виконання: {elapsed:.2f} сек")
        log_info(f"Збережено у: {output_path} ({elapsed:.2f} сек)")
        log_info(f"Статистика: відновлено={stats.get('restored_count', 0)}, "
                 f"пропущено={stats.get('skipped_count', 0)}")

    except Exception as e:
        print(f"❌ Помилка збереження: {e}")
        log_error(f"Помилка збереження: {e}")


if __name__ == "__main__":
    main()
