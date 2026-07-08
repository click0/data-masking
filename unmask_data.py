#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Unmasking Script v2.6.0
Відновлення оригінальних даних з замаскованого файлу

ОНОВЛЕНО В v2.6.0:
- Відновлення ініціалів (категорія initials у mapping)
- Повторні текстові дати відновлюються всі (instance tracking)
- Розпізнавання mapping-файлів усіх версій 2.x (раніше 2.3+ падали у v1-логіку)
- O(n) заміни замість O(n^2) на великих файлах

Архітектура (з v2.5.0): тонка обгортка над пакетом unmasking/
(helpers, engine, io, cli); запуск з кореня репо — python . unmask

Author: Vladyslav V. Prodan
Contact: github.com/click0
Phone: +38(099)6053340
Version: 2.6.0
License: BSD 3-Clause "New" or "Revised" License
Year: 2025-2026
"""

# ============================================================================
# Re-exports from unmasking package for backward compatibility
# ============================================================================

from datamasking.unmasking.cli import __version__

__author__ = "Vladyslav V. Prodan"
__contact__ = "github.com/click0"
__phone__ = "+38(099)6053340"
__license__ = "BSD 3-Clause"
__year__ = "2025-2026"

from datamasking.unmasking.helpers import (
    validate_file_size,
    get_rank_info, find_file_pairs, auto_find_latest_pair,
    check_mapping_version, find_all_occurrences,
    build_instance_map, _apply_original_case,
    is_real_mask, extract_base_rank,
    SEARCH_DIRECTORIES, MAX_INPUT_FILE_SIZE,
)

from datamasking.unmasking.engine import (
    unmask_ranks_gender_aware, unmask_other_data,
    unmask_text_v2, unmask_text_v1,
    unmask_json_recursive,
    unmask_chain, unmask_json_chain, is_chain_mapping,
)

from datamasking.unmasking.io import (
    load_mapping_file, validate_mapping_schema, show_chain_info,
    SECURITY_AVAILABLE, REMASK_AVAILABLE,
)

from datamasking.unmasking.cli import (
    CONFIG_AVAILABLE, LOGGING_AVAILABLE,
    main,
)

if __name__ == "__main__":
    main()
