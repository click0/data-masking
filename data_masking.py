#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Masking Script v2.5.1
Локально узгоджене маскування конфіденційних даних з INSTANCE TRACKING

ОНОВЛЕНО В v2.5.1:
- Рефакторинг: розбито на пакет masking/ (constants, helpers, language,
  context, mask_personal, mask_military, engine, cli)
- Додано __main__.py для запуску через python -m
- Зворотна сумісність: всі імпорти з data_masking продовжують працювати

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.5.1
License: BSD 3-Clause "New" or "Revised" License
Year: 2025-2026
"""

# ============================================================================
# Re-exports from masking package for backward compatibility
# ============================================================================

from masking.constants import (
    __version__, __author__, __contact__, __phone__, __license__, __year__,
    fake_uk, HASH_ALGORITHM,
    MASK_NAMES, MASK_IPN, MASK_PASSPORT, MASK_MILITARY_ID, MASK_RANKS,
    MASK_BRIGADES, MASK_UNITS, MASK_ORDERS, MASK_BR_NUMBERS, MASK_DATES,
    RANK_SHIFT_OPTIONS, DEBUG_MODE, PRESERVE_CASE,
    ABBREVIATION_WHITELIST, UKRAINIAN_DATE_PATTERN, DATE_TEXT_PATTERN,
    GOOD_UKRAINIAN_NAMES_MALE, GOOD_UKRAINIAN_NAMES_FEMALE, PROBLEMATIC_NAMES,
    EXCLUDE_WORDS,
    RANK_PATTERNS, PATTERNS,
    COMPILED_RANK_PATTERNS, COMPILED_PATTERNS,
    MONTHS_GENITIVE, MONTHS_GENITIVE_BY_NUM, MONTHS_GENITIVE_PATTERN,
    MAX_INPUT_FILE_SIZE,
    _MONTHS_UA_LIST,
)

from masking.constants import (
    RANK_DECLENSIONS, RANK_FEMININE_MAP, RANK_DECLENSIONS_FEMALE,
    RANK_TO_NOMINATIVE, ALL_RANK_FORMS,
    ARMY_RANKS, NAVAL_RANKS, LEGAL_RANKS, MEDICAL_RANKS, RANKS_LIST,
)

from masking.helpers import (
    validate_file_size, get_next_instance, add_to_mapping,
    _apply_original_case, normalize_string, normalize_identifier,
    is_pib_anchor, get_deterministic_seed,
)

from masking.language import (
    is_likely_surname_by_case, looks_like_name,
    detect_gender_by_patronymic, detect_name_case_and_gender,
    is_easy_to_decline, apply_case_to_name, generate_easy_name,
)

from masking.context import (
    analyze_number_sign_context, analyze_br_keyword,
    clean_line_before_parsing, extract_identifier_from_line,
    extract_base_rank, looks_like_pib_line, parse_hybrid_line,
)

from masking.mask_personal import (
    mask_ipn, mask_passport_id, mask_military_id,
    mask_surname, mask_patronymic, mask_name,
)

from masking.mask_military import (
    mask_military_unit, mask_order_number, mask_order_number_with_letters,
    mask_br_number, mask_br_number_slash, mask_br_number_complex,
    mask_brigade_number, is_valid_date, mask_date, mask_date_text,
    _mask_date_text,
    get_rank_category_and_match, get_rank_info, get_rank_in_case,
    mask_rank, mask_rank_preserve_case,
)

from masking.engine import (
    normalize_broken_ranks, mask_text_context_aware,
    mask_json_recursive, mask_text_wrapper,
)

from masking.cli import (
    generate_default_config, generate_password_from_config,
    _build_parser, _load_config, _setup_logger,
    _apply_selective_filters, _apply_config_settings,
    _prepare_output_paths, _read_input,
    _run_masking, _run_multi_pass_masking, _run_single_pass_masking,
    _handle_encryption, _write_report, _print_summary, _save_results,
    SELECTIVE_AVAILABLE, REMASK_AVAILABLE, SECURITY_AVAILABLE,
    CONFIG_AVAILABLE, LOGGING_AVAILABLE, PASSWORD_GENERATOR_AVAILABLE,
    main,
)

if __name__ == "__main__":
    main()
