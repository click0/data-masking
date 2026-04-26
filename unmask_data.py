#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Unmasking Script v2.4.0
Відновлення оригінальних даних з замаскованого файлу

ОНОВЛЕНО В v2.4.0:
- Рефакторинг: розбито на пакет unmasking/ (helpers, engine, io, cli)
- Додано __main__.py для запуску через python -m
- Зворотна сумісність: всі імпорти з unmask_data продовжують працювати

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.4.0
License: BSD 3-Clause "New" or "Revised" License
Year: 2025-2026
"""

# ============================================================================
# Re-exports from unmasking package for backward compatibility
# ============================================================================

from unmasking.cli import __version__

__author__ = "Vladyslav V. Prodan"
__contact__ = "github.com/click0"
__phone__ = "+38(099)6053340"
__license__ = "BSD 3-Clause"
__year__ = "2025-2026"

from unmasking.helpers import (
    validate_file_size,
    get_rank_info, find_file_pairs, auto_find_latest_pair,
    check_mapping_version, find_all_occurrences,
    build_instance_map, _apply_original_case,
    is_real_mask, extract_base_rank,
    SEARCH_DIRECTORIES, MAX_INPUT_FILE_SIZE,
)

from unmasking.engine import (
    unmask_ranks_gender_aware, unmask_other_data,
    unmask_text_v2, unmask_text_v1,
    unmask_json_recursive,
    unmask_chain, unmask_json_chain, is_chain_mapping,
)

from unmasking.io import (
    load_mapping_file, validate_mapping_schema, show_chain_info,
    SECURITY_AVAILABLE, REMASK_AVAILABLE,
)

from unmasking.cli import (
    CONFIG_AVAILABLE, LOGGING_AVAILABLE,
    main,
)

if __name__ == "__main__":
    main()
