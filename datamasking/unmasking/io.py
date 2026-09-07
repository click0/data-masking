#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File I/O and validation for unmasking operations.

Extracted from unmask_data.py during the package refactoring (v2.5.0).
"""

import json
import os
import re
from pathlib import Path
from typing import Dict

from datamasking.unmasking.helpers import validate_file_size
from datamasking.unmasking.engine import is_chain_mapping

# Optional modules
SECURITY_AVAILABLE = False
try:
    from datamasking.extras.security import MappingSecurityManager, is_encryption_available
    SECURITY_AVAILABLE = True
except ImportError:
    pass

REMASK_AVAILABLE = False
try:
    from datamasking.extras.re_mask import ChainUnmasker, load_chain, get_chain_info
    REMASK_AVAILABLE = True
except ImportError:
    pass


def load_mapping_file(map_path: Path, password: str = None) -> Dict:
    """
    Завантажує mapping файл з підтримкою шифрування.

    Підтримує:
        - .json файли (звичайний JSON)
        - .enc файли (AES-256-GCM зашифровані)
    """
    if not map_path.exists():
        raise FileNotFoundError(f"Файл маппінгу не знайдено: {map_path}")

    if map_path.suffix == '.enc':
        if not SECURITY_AVAILABLE:
            raise ValueError(
                "Для роботи з .enc файлами потрібен модуль security. "
                "Встановіть: pip install cryptography"
            )

        # Єдина змінна з боком маскування — DATA_MASKING_PASSWORD;
        # старі назви лишаються як fallback для сумісності
        if not password:
            for env_name in ('DATA_MASKING_PASSWORD', 'MASKING_PASSWORD', 'UNMASK_PASSWORD'):
                password = os.environ.get(env_name, '')
                if password:
                    break
        if not password:
            raise ValueError(
                "Для дешифрування .enc файлу потрібен пароль. "
                "Вкажіть --password / --password-env або встановіть DATA_MASKING_PASSWORD"
            )

        validate_file_size(map_path)
        # v2.5–3.0.0: викликалось MappingSecurityManager(password) — клас без
        # __init__ → TypeError на кожному .enc; шифровані mapping не читались
        return MappingSecurityManager().decrypt_mapping(map_path, password)
    else:
        validate_file_size(map_path)
        with open(map_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def validate_mapping_schema(mapping: Dict) -> None:
    """
    Валідує структуру mapping-файлу.

    Raises:
        ValueError: якщо структура mapping невалідна
    """
    if not isinstance(mapping, dict):
        raise ValueError("Mapping file must be a JSON object")

    if "passes" in mapping and "total_passes" in mapping:
        if not isinstance(mapping["passes"], list):
            raise ValueError("Chain mapping 'passes' must be a list")
        return

    version = mapping.get("version")
    _major = re.match(r"v?(\d+)\.", version) if version else None
    if _major and int(_major.group(1)) >= 2:
        if "mappings" not in mapping:
            raise ValueError(
                f"Mapping v{version} must contain 'mappings' key"
            )
        if not isinstance(mapping["mappings"], dict):
            raise ValueError("'mappings' must be a dictionary")
        return


def show_chain_info(masking_map: Dict) -> None:
    """
    Показує інформацію про ланцюг перемаскування.
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
