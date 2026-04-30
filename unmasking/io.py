#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
File I/O and validation for unmasking operations.

Extracted from unmask_data.py during v2.5.1 refactoring.
"""

import json
import os
from pathlib import Path
from typing import Dict

from unmasking.helpers import validate_file_size
from unmasking.engine import is_chain_mapping

# Optional modules
SECURITY_AVAILABLE = False
try:
    from modules.security import MappingSecurityManager, is_encryption_available
    SECURITY_AVAILABLE = True
except ImportError:
    pass

REMASK_AVAILABLE = False
try:
    from modules.re_mask import ChainUnmasker, load_chain, get_chain_info
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
    if version and version.startswith("2"):
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
