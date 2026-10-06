#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Masking constants, patterns, and configuration flags.

Extracted from data_masking.py during the package refactoring (v2.5.0).
"""

import re
from faker import Faker

from datamasking.rank_data import (
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
from datamasking._version import __version__  # єдине джерело версії
__author__ = "Vladyslav V. Prodan"
__contact__ = "github.com/click0"
__phone__ = "+38(099)6053340"
__license__ = "BSD 3-Clause"
__year__ = "2025-2026"

# Локаль faker для синтетичних прізвищ/імен/по батькові. Перевизначається
# конфігом (system.faker_locale / DATA_MASKING_FAKER_LOCALE) через
# set_faker_locale(); морфологія (закінчення, відмінки, рід) лишається
# українською — інша локаль змінює лише словники.
FAKER_LOCALE = 'uk_UA'
fake_uk = Faker(FAKER_LOCALE)
# Запасний uk_UA-генератор для по батькові: більшість локалей faker не мають
# middle_name_* (є лише в uk/ru)
fake_uk_fallback = fake_uk

# Скільки перших символів оригінального прізвища зберігати в масці
# (0 = не зберігати). Разом зі збереженим закінченням — не більше половини
# прізвища (Коваль → 3, Іванов → 1, Петренко → 0; див. surname.prefix_length_for).
# Конфіг: masking_rules.surname_prefix_length / DATA_MASKING_SURNAME_PREFIX_LENGTH
SURNAME_PREFIX_LENGTH = 3

HASH_ALGORITHM = 'blake2b'


def set_faker_locale(locale: str) -> None:
    """Перемикає локаль faker (валідує; невідома локаль → ValueError)."""
    global fake_uk, FAKER_LOCALE
    locale = (locale or "").strip()
    if not locale:
        raise ValueError("faker locale must be a non-empty string, e.g. 'uk_UA'")
    try:
        instance = Faker(locale)
        instance.last_name()  # локаль без провайдера імен — теж помилка
    except (AttributeError, ValueError, ImportError) as exc:
        raise ValueError(f"Unknown or unsupported faker locale: {locale!r}") from exc
    fake_uk = instance
    FAKER_LOCALE = locale

# ============================================================================
# НАЛАШТУВАННЯ МАСКУВАННЯ
# ============================================================================
MASK_NAMES = True
# Окремо прізвища і по батькові (config: masking_rules.enable_surnames /
# enable_patronymics; за замовчуванням — як enable_names). MASK_NAMES — імена.
MASK_SURNAMES = True
MASK_PATRONYMICS = True
# Номери документів «№ N» не після слова «наказ…» (довідка, рапорт, протокол);
# config: masking_rules.enable_document_numbers (за замовчуванням — як MASK_ORDERS)
MASK_DOCUMENT_NUMBERS = True
MASK_IPN = True
MASK_PASSPORT = True
MASK_MILITARY_ID = True
MASK_RANKS = True
MASK_BRIGADES = True
MASK_UNITS = True
MASK_ORDERS = True
MASK_BR_NUMBERS = True
MASK_DATES = True
# Текстові дати («06» жовтня 2025 року); config: masking_rules.enable_date_text
# (за замовчуванням дорівнює MASK_DATES)
MASK_DATE_TEXT = True
# Склеювати звання, розірвані переносом рядка; config: masking_rules.rank_line_break_fix
RANK_LINE_BREAK_FIX = True
# Верхня межа --re-mask; config: remask.max_passes (не більше 10)
REMASK_MAX_PASSES = 10
# Оригінали у виводі налагодження (logging.log_sensitive_data); за замовчуванням ні
LOG_SENSITIVE_DATA = False
# Час етапів у лог (logging.log_performance)
LOG_PERFORMANCE = False
# Розмір дайджесту blake2b, байт (system.hash_digest_size). 64 — стандартний;
# будь-яке інше значення змінює ВСІ маски
HASH_DIGEST_SIZE = 64
# Маска ІПН з коректною контрольною цифрою (validation.validate_ipn_checksum).
# Змінює маски ІПН, тому за замовчуванням вимкнено
VALIDATE_IPN_CHECKSUM = False
# Довжина слова-кандидата в ПІБ (validation.min_name_length / max_name_length);
# 0 у максимумі — без обмеження
NAME_MIN_LENGTH = 3
NAME_MAX_LENGTH = 0
# ПІБ з ініціалами («Іванов І.І.») — validation.allow_abbreviated_patronymic
ALLOW_ABBREVIATED_PATRONYMIC = True
# Лише повний ПІБ із трьох слів — validation.strict_pib_format
STRICT_PIB_FORMAT = False
# Рід маски імені / по батькові = реальний рід (masking_rules.preserve_gender);
# false — псевдовипадковий (маска не видає стать)
PRESERVE_GENDER = True
# Власні шаблони (masking_rules.custom_patterns) — кортеж CustomPattern
CUSTOM_PATTERNS: tuple = ()
# Порядок фаз шаблонних типів (router_rules.processing_order /
# priority_overrides): при перекритті перемагає раніша. Звання й ПІБ —
# завжди після них
DEFAULT_PROCESSING_ORDER = ("custom", "order_number", "br_number", "ipn", "passport_id",
                            "military_id", "military_unit", "brigade_number", "date", "date_text")
PROCESSING_ORDER: "tuple[str, ...]" = DEFAULT_PROCESSING_ORDER
# Кодування вхідного файлу (system.encoding) і кандидати для "auto"
# (validation.allowed_encodings); вихід пишеться тим самим кодуванням
INPUT_ENCODING = "utf-8"
ALLOWED_ENCODINGS: "tuple[str, ...]" = ("utf-8", "cp1251", "latin-1")

# Rank masking: allowed shift values for rank position offset
RANK_SHIFT_OPTIONS = [-2, -1, 1, 2]

# Дати ДД.ММ.РРРР: які роки розпізнаються як дата (маскуються), і в яких
# межах лишаються дати документів після зсуву. До 3.0.22 межі зсуву
# використовувались і для розпізнавання — дати народження не маскувались.
DATE_DETECT_YEAR_MIN = 1900
DATE_DETECT_YEAR_MAX = 2100
DATE_SHIFT_YEAR_MIN = 2015
DATE_SHIFT_YEAR_MAX = 2035

# Дата одразу після назви нормативного акта — реквізит закону, а не
# персональні дані: «Закону України від 06.12.1991 № 1932-XII»,
# «Кодексу …», «Указу Президента …», «постанови Кабінету Міністрів …».
# Її не зсуваємо (інакше ламаються юридичні посилання).
LEGAL_ACT_DATE_PREFIX = re.compile(
    r"(?:закон\w*|кодекс\w*|конституці\w*|указ\w*\s+президента|"
    r"постанов\w*\s+(?:кабінету\s+міністрів|верховної\s+ради|км[уy]))"
    r"[^\n.;]{0,80}?\bвід\s*$",
    re.IGNORECASE,
)

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

# Pattern for text dates like: "06" жовтня 2025 року / «06» жовтня 2025 року / 06 жовтня 2025 року
_MONTHS_UA = (
    r'січня|лютого|березня|квітня|травня|червня|'
    r'липня|серпня|вересня|жовтня|листопада|грудня'
)
DATE_TEXT_PATTERN = re.compile(
    r'(?:["\u201c\u201e«]?\s*)?'         # optional opening quote
    r'(\d{1,2})'                          # day
    r'(?:\s*["\u201d\u201c»]?\s*)'        # optional closing quote + space
    r'(' + _MONTHS_UA + r')'              # month name
    r'\s+(\d{4})'                         # year
    r'(?:\s+року)?',                      # optional "року"
    re.IGNORECASE
)

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
    "Вам", "вам", "Вами", "вами", "Ваш", "ваш", "Ваша", "ваша", "Ваше", "ваше",
    "Повідомляємо", "повідомляємо", "Просимо", "просимо",
    "Направляємо", "направляємо", "Надаємо", "надаємо",
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
    # Службові маркери-мітки (щоб не плутались із самим ПІБ у форматах
    # "ПІБ: Петренко..." чи логах "ПІБ «138» → «Міронов...»")
    "ПІБ", "піб", "Піб", "звання", "Звання", "ЗВАННЯ",
    "ІПН", "іпн", "Іпн", "РНОКПП", "паспорт", "Паспорт",
    # «Кабінет Міністрів» у всіх відмінках — не ПІБ («постанови Кабінету
    # Міністрів» маскувалось як «Кабалу Михайло»). Змінюється лише перше
    # слово: Кабінет / Кабінету / Кабінетом / Кабінеті / Кабінете + Міністрів
    "Кабінет", "Кабінету", "Кабінетові", "Кабінетом", "Кабінеті", "Кабінете",
    "Міністрів",
]

# Regex паттерни для виявлення звань різних типів служб
RANK_PATTERNS = {
    "army": r"\b(рядовий|солдат|старший солдат|ефрейтор|молодший сержант|сержант|старший сержант|головний сержант|штабс-сержант|майстер-сержант|старший майстер-сержант|головний майстер-сержант|прапорщик|старший прапорщик|молодший лейтенант|лейтенант|старший лейтенант|капітан|майор|підполковник|полковник|бригадний генерал|генерал-майор|генерал-лейтенант|генерал)\b",
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

# Ukrainian month names in genitive case (for text date parsing)
MONTHS_GENITIVE = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12
}
MONTHS_GENITIVE_BY_NUM = {v: k for k, v in MONTHS_GENITIVE.items()}
MONTHS_GENITIVE_PATTERN = '|'.join(re.escape(m) for m in MONTHS_GENITIVE.keys())

# Maximum input file size in bytes (default: 100 MB)
# Лапки всіх стилів (українські «», німецькі „“, англійські "" '', ‟).
# Значення в лапках («сержант», «Петренко») мають розпізнаватись і маскуватись.
QUOTE_CHARS = '«»„“”‟“”„"\''

MAX_INPUT_FILE_SIZE = 100 * 1024 * 1024

EXCLUDE_WORDS_LOWER = frozenset(w.lower() for w in EXCLUDE_WORDS)
RANKS_LIST_LOWER = frozenset(r.lower() for r in RANKS_LIST)
# Усі граматичні форми звань (для точного збігу вмісту лапок «...»)
ALL_RANK_FORMS_LOWER = frozenset(f.lower() for f in ALL_RANK_FORMS)

_MONTHS_UA_LIST = [
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"
]
