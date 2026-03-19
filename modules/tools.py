#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tools API Module v2.3.1

Provides atomic masking functions for programmatic use (without CLI).
Each function is self-contained and operates on a single value, updating
the shared masking_dict and instance_counters.

This module is the recommended entry point for integrating data masking
into external Python applications, pipelines, and services.

Atomic masking functions:
    - mask_ipn_direct         Mask a 10-digit IPN
    - mask_passport_direct    Mask a 9-digit passport ID
    - mask_date_direct        Mask a date (DD.MM.YYYY)
    - mask_surname_direct     Mask a surname (faker-based)
    - mask_name_direct        Mask a first name
    - mask_patronymic_direct  Mask a patronymic
    - mask_pib_force          Mask a full PIB (Surname Name Patronymic)
    - mask_rank_direct        Mask a military rank
    - mask_military_unit_direct  Mask a military unit code

Universal function:
    - mask_value              Dispatch masking by data_type string

Utilities:
    - is_tools_available      Always True when module is loaded
    - is_faker_available      True when Faker is importable

Helper functions:
    - get_deterministic_seed  Deterministic seed from a value
    - _apply_original_case    Apply per-character case of original to masked
    - get_next_instance       Instance tracking counter
    - add_to_mapping          Insert into masking_dict with instance tracking
    - init_masking_dict       Create a fresh masking dictionary
    - init_instance_counters  Create a fresh instance counters dictionary

Author: Vladyslav V. Prodan
Contact: github.com/click0
License: BSD 3-Clause
Year: 2025-2026
"""

import hashlib
import random
import re
from datetime import datetime, timedelta
from typing import Dict, Optional

# ============================================================================
# METADATA
# ============================================================================
__version__ = "2.3.1"
__author__ = "Vladyslav V. Prodan"
__contact__ = "github.com/click0"
__license__ = "BSD 3-Clause"
__year__ = "2025-2026"

# ============================================================================
# OPTIONAL DEPENDENCY: Faker
# ============================================================================
try:
    from faker import Faker
    fake_uk = Faker('uk_UA')
    FAKER_AVAILABLE = True
except ImportError:
    fake_uk = None
    FAKER_AVAILABLE = False

# ============================================================================
# RANK DATA IMPORT
# ============================================================================
try:
    from rank_data import (
        RANK_DECLENSIONS,
        RANK_TO_NOMINATIVE,
        ARMY_RANKS,
        NAVAL_RANKS,
        LEGAL_RANKS,
        MEDICAL_RANKS,
    )
    RANK_DATA_AVAILABLE = True
except ImportError:
    try:
        from .rank_data import (
            RANK_DECLENSIONS,
            RANK_TO_NOMINATIVE,
            ARMY_RANKS,
            NAVAL_RANKS,
            LEGAL_RANKS,
            MEDICAL_RANKS,
        )
        RANK_DATA_AVAILABLE = True
    except ImportError:
        RANK_DECLENSIONS = {}
        RANK_TO_NOMINATIVE = {}
        ARMY_RANKS = []
        NAVAL_RANKS = []
        LEGAL_RANKS = []
        MEDICAL_RANKS = []
        RANK_DATA_AVAILABLE = False

# ============================================================================
# CONSTANTS
# ============================================================================
RANK_SHIFT_OPTIONS = [-2, -1, 1, 2]

# Rank category patterns (simplified for direct-mode usage)
RANK_PATTERNS = {
    "army": re.compile(
        r"\b(рекрут|рядовий|солдат|старший солдат|ефрейтор|"
        r"молодший сержант|сержант|старший сержант|головний сержант|"
        r"штабс-сержант|майстер-сержант|старший майстер-сержант|"
        r"головний майстер-сержант|прапорщик|старший прапорщик|"
        r"молодший лейтенант|лейтенант|старший лейтенант|капітан|"
        r"майор|підполковник|полковник|бригадний генерал|"
        r"генерал-майор|генерал-лейтенант|генерал)\b",
        re.IGNORECASE | re.UNICODE,
    ),
    "naval": re.compile(
        r"\b(матрос|моряк|старший матрос|старший моряк|"
        r"молодший сержант|сержант|старший сержант|головний сержант|"
        r"штабс-сержант|майстер-сержант|старший майстер-сержант|"
        r"головний майстер-сержант|молодший лейтенант|лейтенант|"
        r"старший лейтенант|капітан-лейтенант|капітан \d+-го рангу|"
        r"контр-адмірал|віце-адмірал|адмірал)\b",
        re.IGNORECASE | re.UNICODE,
    ),
    "legal": re.compile(
        r"\b(молодший сержант юстиції|сержант юстиції|"
        r"старший сержант юстиції|головний сержант юстиції|"
        r"штабс-сержант юстиції|молодший лейтенант юстиції|"
        r"лейтенант юстиції|старший лейтенант юстиції|"
        r"капітан юстиції|майор юстиції|підполковник юстиції|"
        r"полковник юстиції|генерал-майор юстиції|"
        r"генерал-лейтенант юстиції)\b",
        re.IGNORECASE | re.UNICODE,
    ),
    "medical": re.compile(
        r"\b(молодший сержант медичної служби|сержант медичної служби|"
        r"старший сержант медичної служби|головний сержант медичної служби|"
        r"штабс-сержант медичної служби|молодший лейтенант медичної служби|"
        r"лейтенант медичної служби|старший лейтенант медичної служби|"
        r"капітан медичної служби|майор медичної служби|"
        r"підполковник медичної служби|полковник медичної служби|"
        r"генерал-майор медичної служби|"
        r"генерал-лейтенант медичної служби)\b",
        re.IGNORECASE | re.UNICODE,
    ),
}

# Standard mapping categories used by data_masking.py
MAPPING_CATEGORIES = [
    "ipn", "passport_id", "military_id", "surname", "name",
    "military_unit", "order_number", "order_number_with_letters",
    "br_number", "br_number_slash", "br_number_complex",
    "rank", "brigade_number", "date", "patronymic",
]

# Ukrainian male names (for name masking without Faker)
GOOD_UKRAINIAN_NAMES_MALE = [
    "андрій", "богдан", "віктор", "володимир", "дмитро",
    "ігор", "іван", "максим", "олег", "олексій",
    "петро", "сергій", "тарас", "юрій", "михайло",
    "василь", "роман", "артем", "денис", "євген",
    "костянтин", "павло", "станіслав", "ярослав",
]

GOOD_UKRAINIAN_NAMES_FEMALE = [
    "анна", "вікторія", "галина", "дарія", "ірина",
    "катерина", "марія", "наталія", "олена", "оксана",
    "світлана", "тетяна", "юлія", "людмила", "надія",
    "валентина", "лариса", "ольга", "софія", "діана",
    "алла", "ганна", "любов",
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_deterministic_seed(value: str, algorithm: str = 'blake2b') -> int:
    """Generate a deterministic integer seed from a string value.

    The seed is derived via a cryptographic hash so that the same input
    always produces the same output (critical for unmask / round-trip).

    Args:
        value: Arbitrary string (IPN, surname, date, etc.).
        algorithm: Hash algorithm name. Supported: md5, sha1, sha256,
                   sha512, blake2b (default).

    Returns:
        An integer in range [0, 2**32) suitable for ``random.seed()``.
    """
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    elif algorithm == 'sha256':
        hasher = hashlib.sha256()
    elif algorithm == 'blake2b':
        hasher = hashlib.blake2b()
    elif algorithm == 'sha512':
        hasher = hashlib.sha512()
    else:
        raise ValueError(f"Unknown hash algorithm: {algorithm}")
    hasher.update(value.encode('utf-8'))
    return int(hasher.hexdigest(), 16) % (2 ** 32)


def _apply_original_case(original: str, masked: str) -> str:
    """Apply the case pattern of *original* to *masked* character by character.

    Rules applied in order:
    1. If *original* is all-uppercase -> return ``masked.upper()``.
    2. If *original* is Title Case (first upper, rest lower) ->
       return ``masked.capitalize()``.
    3. Otherwise, iterate character-by-character:
       - If the corresponding original character is uppercase, the masked
         character is uppercased.
       - If it is lowercase, the masked character is lowercased.
       - Characters beyond the length of *original* keep their existing case.

    Args:
        original: The text whose case pattern is the reference.
        masked: The text to transform.

    Returns:
        *masked* with case adjusted to match *original*.
    """
    if not original or not masked:
        return masked

    # Fast paths
    if original.isupper():
        return masked.upper()
    if original.islower():
        return masked.lower()
    if len(original) > 1 and original[0].isupper() and original[1:].islower():
        return masked.capitalize()

    # Per-character case transfer
    result = []
    for i, ch in enumerate(masked):
        if i < len(original):
            if original[i].isupper():
                result.append(ch.upper())
            elif original[i].islower():
                result.append(ch.lower())
            else:
                result.append(ch)
        else:
            result.append(ch)
    return ''.join(result)


def get_next_instance(masked_value: str, instance_counters: Dict[str, int]) -> int:
    """Return the next instance number for *masked_value*.

    Instance tracking detects collisions where different originals map
    to the same masked value.

    Args:
        masked_value: The masked string to track.
        instance_counters: Mutable mapping of masked values to counts.

    Returns:
        The incremented instance number (starting from 1).
    """
    instance_counters.setdefault(masked_value, 0)
    instance_counters[masked_value] += 1
    return instance_counters[masked_value]


def add_to_mapping(
    masking_dict: Dict,
    instance_counters: Dict,
    entity_type: str,
    original: str,
    masked: str,
) -> str:
    """Insert or retrieve a mapping entry and update instance tracking.

    If *original* already exists in the mapping for *entity_type*, the
    previously stored masked value is returned (and the instance counter
    is incremented).  Otherwise a new entry is created.

    Args:
        masking_dict: The shared masking dictionary (mutated in place).
        instance_counters: Instance tracking counters (mutated in place).
        entity_type: Category key (e.g. ``"ipn"``, ``"surname"``).
        original: Original (cleartext) value.
        masked: Proposed masked value.

    Returns:
        The masked value stored in the mapping (may differ from *masked*
        if *original* was already mapped).
    """
    # Ensure category structures exist
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}
    if "statistics" not in masking_dict:
        masking_dict["statistics"] = {}
    if "instance_tracking" not in masking_dict:
        masking_dict["instance_tracking"] = {}

    if original not in masking_dict["mappings"][entity_type]:
        masking_dict["mappings"][entity_type][original] = {
            "masked_as": masked,
            "instances": [],
        }
        masking_dict["statistics"][entity_type] = (
            masking_dict["statistics"].get(entity_type, 0) + 1
        )
    else:
        masked = masking_dict["mappings"][entity_type][original]["masked_as"]

    instance_num = get_next_instance(masked, instance_counters)
    masking_dict["mappings"][entity_type][original]["instances"].append(
        instance_num
    )
    return masked


def init_masking_dict() -> Dict:
    """Create a fresh, empty masking dictionary with all required keys.

    Returns:
        A dictionary ready to be passed to any ``mask_*_direct`` function.
    """
    return {
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "statistics": {},
        "mappings": {k: {} for k in MAPPING_CATEGORIES},
        "instance_tracking": {},
    }


def init_instance_counters() -> Dict:
    """Create a fresh, empty instance counters dictionary.

    Returns:
        An empty ``dict`` ready to be passed to any ``mask_*_direct``
        function.
    """
    return {}


# ============================================================================
# INTERNAL RANK HELPERS
# ============================================================================

def _get_rank_category_and_match(text: str):
    """Detect the rank category and matched text from *text*.

    Returns:
        A tuple ``(category_name, matched_text)`` or ``(None, None)``
        if no rank pattern matches.
    """
    text_lower = text.lower()
    for category, pattern in RANK_PATTERNS.items():
        match = pattern.search(text_lower)
        if match:
            return category, match.group(0)
    return None, None


def _get_rank_info(rank_form: str):
    """Look up a rank form in RANK_TO_NOMINATIVE.

    Args:
        rank_form: Any grammatical form of a rank.

    Returns:
        A tuple ``(nominative_rank, case_name, gender)`` or
        ``(None, None, None)`` if not found.
    """
    rank_lower = rank_form.lower()
    if rank_lower in RANK_TO_NOMINATIVE:
        return RANK_TO_NOMINATIVE[rank_lower]
    return None, None, None


def _get_rank_in_case(nominative_rank: str, target_case: str) -> str:
    """Return *nominative_rank* declined to *target_case*.

    Falls back to the nominative form when the rank or case is not
    found in RANK_DECLENSIONS.
    """
    if nominative_rank not in RANK_DECLENSIONS:
        return nominative_rank
    return RANK_DECLENSIONS[nominative_rank].get(target_case, nominative_rank)


# ============================================================================
# ATOMIC MASKING FUNCTIONS
# ============================================================================

def mask_ipn_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
) -> str:
    """Mask a 10-digit IPN (Individual Tax Number).

    Logic: keeps the first 3 and last digit, randomises the middle 6.

    Args:
        value: 10-digit IPN string.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).

    Returns:
        Masked IPN string of the same length and format.
    """
    entity_type = "ipn"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    if value in masking_dict["mappings"][entity_type]:
        masked = masking_dict["mappings"][entity_type][value]["masked_as"]
    else:
        if len(value) != 10 or not value.isdigit():
            return value
        seed = get_deterministic_seed(value)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        masked = value[:3] + middle + value[-1]
    return add_to_mapping(masking_dict, instance_counters, entity_type,
                          value, masked)


def mask_passport_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
) -> str:
    """Mask a 9-digit passport ID.

    Logic: keeps the first 3 and last digit, randomises the middle 5.

    Args:
        value: 9-digit passport ID string.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).

    Returns:
        Masked passport ID string of the same length and format.
    """
    entity_type = "passport_id"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    if value in masking_dict["mappings"][entity_type]:
        masked = masking_dict["mappings"][entity_type][value]["masked_as"]
    else:
        if len(value) != 9 or not value.isdigit():
            return value
        seed = get_deterministic_seed(value)
        random.seed(seed)
        middle = ''.join([str(random.randint(0, 9)) for _ in range(5)])
        masked = value[:3] + middle + value[-1]
    return add_to_mapping(masking_dict, instance_counters, entity_type,
                          value, masked)


def mask_date_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
) -> str:
    """Mask a date string in DD.MM.YYYY format.

    Logic:
    - Shifts the date by a random offset in the range [-30, +30] days.
    - Clamps the result to the year range [2015, 2035].
    - Uses a deterministic seed so that the same input always produces
      the same output (required for unmask round-trip).

    Args:
        value: Date string in ``DD.MM.YYYY`` format.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).

    Returns:
        Masked date string in the same format.
    """
    entity_type = "date"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    if value in masking_dict["mappings"][entity_type]:
        masked = masking_dict["mappings"][entity_type][value]["masked_as"]
    else:
        try:
            match = re.match(r'(\d{2})\.(\d{2})\.(\d{4})', value)
            if not match:
                return value

            day = int(match.group(1))
            month = int(match.group(2))
            year = int(match.group(3))

            # Validate year range
            if year < 2015 or year > 2035:
                return value

            # Validate date
            try:
                date_obj = datetime(year, month, day)
            except ValueError:
                return value

            seed = get_deterministic_seed(value)
            random.seed(seed)
            new_date = date_obj + timedelta(days=random.randint(-30, 30))

            # Clamp to [2015, 2035]
            if new_date.year < 2015:
                new_date = datetime(2015, 1, 1) + timedelta(
                    days=random.randint(0, 365)
                )
            elif new_date.year > 2035:
                new_date = datetime(2035, 12, 31) - timedelta(
                    days=random.randint(0, 365)
                )

            masked = new_date.strftime("%d.%m.%Y")
        except (ValueError, OverflowError):
            return value
        except Exception:
            return value

    return add_to_mapping(masking_dict, instance_counters, entity_type,
                          value, masked)


def mask_surname_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
) -> str:
    """Mask a surname using Faker, preserving case.

    For short surnames (< 5 characters) a wholly new faker surname is
    generated.  For longer surnames the first 3 and last 5 characters
    are kept and the middle is replaced with faker-derived characters.

    Case preservation:
    - UPPER CASE -> UPPER CASE
    - Title Case -> Title Case
    - lower case -> lower case

    Args:
        value: Surname string.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).

    Returns:
        Masked surname with case preserved.
    """
    entity_type = "surname"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    if value in masking_dict["mappings"][entity_type]:
        masked = masking_dict["mappings"][entity_type][value]["masked_as"]
    else:
        if not FAKER_AVAILABLE:
            return value

        is_upper = value.isupper()
        is_capitalize = (
            len(value) > 1
            and value[0].isupper()
            and value[1:].islower()
        )

        seed = get_deterministic_seed(value)
        random.seed(seed)
        fake_uk.seed_instance(seed)
        fake_surname = fake_uk.last_name()

        if len(value) < 5:
            target_length = random.randint(
                max(3, len(value) - 1),
                min(6, len(value) + 2),
            )
            masked = (
                fake_surname[:target_length]
                if len(fake_surname) > target_length
                else fake_surname
            )
        else:
            middle_len = min(random.randint(2, 7), len(fake_surname) - 2)
            middle = (
                fake_surname[1:1 + middle_len]
                if len(fake_surname) > 4
                else fake_surname[1:-1]
            )
            masked = value[:3] + middle + value[-5:]

        # Apply case
        if is_upper:
            masked = masked.upper()
        elif is_capitalize:
            masked = masked.capitalize()

    return add_to_mapping(masking_dict, instance_counters, entity_type,
                          value, masked)


def mask_name_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
    gender: str = 'male',
) -> str:
    """Mask a first name, preserving case and respecting gender.

    If Faker is available, a name of the same gender is generated.
    Otherwise a name is picked from a built-in list filtered by the
    first letter of the original name.

    Args:
        value: First name string.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).
        gender: ``'male'`` (default) or ``'female'``.

    Returns:
        Masked first name with case preserved.
    """
    entity_type = "name"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    if value in masking_dict["mappings"][entity_type]:
        masked = masking_dict["mappings"][entity_type][value]["masked_as"]
    else:
        if not value:
            return value

        is_upper = value.isupper()
        is_capitalize = (
            value[0].isupper()
            and (len(value) == 1 or value[1:].islower())
        )
        is_lower = value.islower()

        first_letter = value[0].lower()
        seed = get_deterministic_seed(value)
        random.seed(seed)

        if FAKER_AVAILABLE:
            fake_uk.seed_instance(seed)
            if gender == 'female':
                new_name = fake_uk.first_name_female()
            else:
                new_name = fake_uk.first_name_male()
        else:
            # Fallback: pick from built-in lists
            name_pool = (
                GOOD_UKRAINIAN_NAMES_FEMALE
                if gender == 'female'
                else GOOD_UKRAINIAN_NAMES_MALE
            )
            candidates = [n for n in name_pool if n[0] == first_letter]
            if not candidates:
                candidates = name_pool
            new_name = random.choice(candidates)

        masked = new_name.lower()

        # Avoid mapping a name to itself
        attempts = 0
        while masked.lower() == value.lower() and attempts < 10:
            seed = get_deterministic_seed(value + str(attempts))
            random.seed(seed)
            if FAKER_AVAILABLE:
                fake_uk.seed_instance(seed)
                if gender == 'female':
                    new_name = fake_uk.first_name_female()
                else:
                    new_name = fake_uk.first_name_male()
            else:
                masked_candidate = random.choice(
                    GOOD_UKRAINIAN_NAMES_FEMALE
                    if gender == 'female'
                    else GOOD_UKRAINIAN_NAMES_MALE
                )
                new_name = masked_candidate
            masked = new_name.lower()
            attempts += 1

        # Apply case
        if is_upper:
            masked = masked.upper()
        elif is_capitalize:
            masked = masked.capitalize()
        elif is_lower:
            masked = masked.lower()

    return add_to_mapping(masking_dict, instance_counters, entity_type,
                          value, masked)


def mask_patronymic_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
    gender: str = 'male',
) -> str:
    """Mask a patronymic, preserving case and respecting gender.

    Uses ``Faker.middle_name_male()`` / ``Faker.middle_name_female()``
    when Faker is available.

    Args:
        value: Patronymic string.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).
        gender: ``'male'`` (default) or ``'female'``.

    Returns:
        Masked patronymic with case preserved.
    """
    entity_type = "patronymic"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    if not value:
        return value

    is_upper = value.isupper()
    is_capitalize = (
        len(value) > 1
        and value[0].isupper()
        and value[1:].islower()
    )

    value_lower = value.lower()

    if value_lower in masking_dict["mappings"][entity_type]:
        masked = masking_dict["mappings"][entity_type][value_lower][
            "masked_as"
        ]
        masked_with_case = _apply_original_case(value, masked)
        instance_num = get_next_instance(masked, instance_counters)
        masking_dict["mappings"][entity_type][value_lower][
            "instances"
        ].append(instance_num)
        return masked_with_case

    if not FAKER_AVAILABLE:
        return value

    seed = get_deterministic_seed(value_lower)
    random.seed(seed)
    fake_uk.seed_instance(seed)
    fake_patronymic = (
        fake_uk.middle_name_male()
        if gender == 'male'
        else fake_uk.middle_name_female()
    )

    # Apply case
    if is_upper:
        fake_patronymic = fake_patronymic.upper()
    elif is_capitalize:
        fake_patronymic = fake_patronymic.capitalize()
    else:
        fake_patronymic = fake_patronymic.lower()

    return add_to_mapping(
        masking_dict, instance_counters, entity_type,
        value_lower, fake_patronymic,
    )


def mask_pib_force(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
    gender: Optional[str] = None,
) -> str:
    """Mask a full PIB (Surname Name Patronymic).

    Splits *value* into exactly three parts and masks each component
    individually.  Gender is auto-detected from the patronymic ending
    when *gender* is ``None``.

    Args:
        value: Full name string ``"Surname Name Patronymic"``.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).
        gender: Optional explicit gender (``'male'`` / ``'female'``).
                When ``None``, detected from the patronymic.

    Returns:
        Masked PIB string with three space-separated components.
        If the input does not contain exactly three parts, it is
        returned unchanged.
    """
    parts = value.split()
    if len(parts) != 3:
        return value

    surname, name, patronymic = parts

    # Auto-detect gender from patronymic
    if gender is None:
        patronymic_lower = patronymic.lower()
        if (patronymic_lower.endswith("ович")
                or patronymic_lower.endswith("йович")):
            gender = "male"
        elif (patronymic_lower.endswith("івна")
              or patronymic_lower.endswith("ївна")):
            gender = "female"
        else:
            gender = "male"

    masked_surname = mask_surname_direct(surname, masking_dict,
                                         instance_counters)
    masked_name = mask_name_direct(name, masking_dict, instance_counters,
                                   gender=gender)
    masked_patronymic = mask_patronymic_direct(patronymic, masking_dict,
                                               instance_counters,
                                               gender=gender)

    return f"{masked_surname} {masked_name} {masked_patronymic}"


def mask_rank_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
) -> str:
    """Mask a military rank, shifting +/-1-2 in its hierarchy.

    Logic:
    1. Detect the rank category (army, naval, legal, medical).
    2. Find the rank position in the corresponding hierarchy list.
    3. Generate a deterministic shift of +/-1 or +/-2 positions.
    4. Preserve grammatical case (nominative, genitive, dative,
       instrumental).
    5. Preserve letter case (UPPER, Title, lower).

    Args:
        value: Rank string (any grammatical form / case).
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).

    Returns:
        Masked rank string with case and grammatical form preserved.
    """
    entity_type = "rank"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    original_key = value.lower()
    detected_base, detected_case, detected_gender = _get_rank_info(
        original_key
    )

    # Check existing mapping (but avoid re-using another value's mask)
    if original_key in masking_dict["mappings"][entity_type]:
        is_someone_else_mask = False
        for other_original, other_data in masking_dict["mappings"][
            entity_type
        ].items():
            if isinstance(other_data, dict) and "masked_as" in other_data:
                if (other_data["masked_as"].lower() == original_key
                        and other_original != original_key):
                    is_someone_else_mask = True
                    break
        if not is_someone_else_mask:
            masked = masking_dict["mappings"][entity_type][original_key][
                "masked_as"
            ]
            final_masked = add_to_mapping(
                masking_dict, instance_counters, entity_type,
                original_key, masked,
            )
            return _apply_original_case(value, final_masked)

    # Determine category and hierarchy
    category_name, matched = _get_rank_category_and_match(original_key)
    if not matched:
        return value

    hierarchy_map = {
        "army": ARMY_RANKS,
        "naval": NAVAL_RANKS,
        "legal": LEGAL_RANKS,
        "medical": MEDICAL_RANKS,
    }
    hierarchy = hierarchy_map.get(category_name)
    if hierarchy is None:
        return value

    try:
        idx = [r.lower() for r in hierarchy].index(matched.lower())
    except ValueError:
        return value

    # Generate shifted rank
    seed = get_deterministic_seed(original_key)
    random.seed(seed)
    shift = random.choice(RANK_SHIFT_OPTIONS)
    new_idx = max(0, min(len(hierarchy) - 1, idx + shift))
    masked = hierarchy[new_idx]

    # Avoid self-mapping
    attempts = 0
    while masked.lower() == original_key and attempts < 10:
        shift = random.choice(RANK_SHIFT_OPTIONS)
        new_idx = max(0, min(len(hierarchy) - 1, idx + shift))
        masked = hierarchy[new_idx]
        attempts += 1

    # Apply grammatical case
    if detected_case and detected_case != "nominative":
        masked = _get_rank_in_case(masked, detected_case)

    final_masked = add_to_mapping(
        masking_dict, instance_counters, entity_type,
        original_key, masked,
    )

    # Apply letter case
    # Special handling for multi-word Title Case and hyphenated ranks
    if '-' in value and value.istitle():
        return final_masked.title()

    words = value.split()
    if len(words) > 1:
        all_title = all(
            word and word[0].isupper() for word in words if word
        )
        if all_title:
            return final_masked.title()

    return _apply_original_case(value, final_masked)


def mask_military_unit_direct(
    value: str,
    masking_dict: Dict,
    instance_counters: Dict,
) -> str:
    """Mask a military unit code (format: one letter + 4 digits).

    Logic: preserves the letter, randomises all 4 digits.

    Examples:
    - ``"А1234"`` -> ``"А5678"``
    - ``"B9876"`` -> ``"B2345"``

    Args:
        value: Military unit string (format ``A####``).
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).

    Returns:
        Masked military unit string in the same format.
    """
    entity_type = "military_unit"
    if "mappings" not in masking_dict:
        masking_dict["mappings"] = {}
    if entity_type not in masking_dict["mappings"]:
        masking_dict["mappings"][entity_type] = {}

    if value in masking_dict["mappings"][entity_type]:
        masked = masking_dict["mappings"][entity_type][value]["masked_as"]
    else:
        match = re.match(r'^([А-ЯA-Z])(\d{4})$', value)
        if not match:
            return value
        letter = match.group(1)
        seed = get_deterministic_seed(value)
        random.seed(seed)
        digits = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        masked = letter + digits
    return add_to_mapping(masking_dict, instance_counters, entity_type,
                          value, masked)


# ============================================================================
# UNIVERSAL DISPATCH FUNCTION
# ============================================================================

def mask_value(
    value: str,
    data_type: str,
    masking_dict: Dict,
    instance_counters: Dict,
    **kwargs,
) -> str:
    """Mask *value* according to *data_type*, dispatching to the
    appropriate atomic masking function.

    Supported *data_type* values:
    - ``"ipn"``            -> :func:`mask_ipn_direct`
    - ``"passport_id"``    -> :func:`mask_passport_direct`
    - ``"date"``           -> :func:`mask_date_direct`
    - ``"surname"``        -> :func:`mask_surname_direct`
    - ``"name"``           -> :func:`mask_name_direct`
    - ``"patronymic"``     -> :func:`mask_patronymic_direct`
    - ``"pib"``            -> :func:`mask_pib_force`
    - ``"rank"``           -> :func:`mask_rank_direct`
    - ``"military_unit"``  -> :func:`mask_military_unit_direct`

    Additional keyword arguments are forwarded to the underlying
    function (e.g. ``gender='female'`` for name / patronymic masking).

    Args:
        value: The cleartext value to mask.
        data_type: One of the supported type strings.
        masking_dict: Shared masking dictionary (mutated).
        instance_counters: Instance tracking counters (mutated).
        **kwargs: Extra keyword arguments forwarded to the masking
                  function.

    Returns:
        The masked value.

    Raises:
        ValueError: If *data_type* is not recognised.
    """
    dispatch = {
        "ipn": mask_ipn_direct,
        "passport_id": mask_passport_direct,
        "passport": mask_passport_direct,
        "date": mask_date_direct,
        "surname": mask_surname_direct,
        "name": mask_name_direct,
        "patronymic": mask_patronymic_direct,
        "pib": mask_pib_force,
        "rank": mask_rank_direct,
        "military_unit": mask_military_unit_direct,
    }

    func = dispatch.get(data_type)
    if func is None:
        raise ValueError(
            f"Unknown data_type: {data_type!r}. "
            f"Supported types: {sorted(dispatch.keys())}"
        )

    # Filter kwargs to only those accepted by the target function
    import inspect
    sig = inspect.signature(func)
    valid_params = set(sig.parameters.keys())
    # Remove the three standard positional arguments
    valid_params -= {"value", "masking_dict", "instance_counters"}
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in valid_params}

    return func(value, masking_dict, instance_counters, **filtered_kwargs)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def is_tools_available() -> bool:
    """Return ``True`` if this module has been successfully imported.

    Always returns ``True`` -- the function exists solely as a
    convenient availability probe for callers that do a conditional
    import.
    """
    return True


def is_faker_available() -> bool:
    """Return ``True`` if the Faker library is importable.

    When Faker is not installed, surname / name / patronymic masking
    functions will return their input unchanged.
    """
    return FAKER_AVAILABLE
