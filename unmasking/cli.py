#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI entry point for data unmasking.

Extracted from unmask_data.py during v2.5.1 refactoring.
"""

import json
import sys
import argparse
import os
import time
from pathlib import Path
from datetime import datetime
from typing import Dict

from unmasking.helpers import (
    validate_file_size, auto_find_latest_pair, check_mapping_version,
)
from unmasking.engine import (
    unmask_text_v2, unmask_text_v1,
    unmask_json_recursive, unmask_chain, unmask_json_chain,
    is_chain_mapping,
)
from unmasking.io import (
    load_mapping_file, validate_mapping_schema, show_chain_info,
    SECURITY_AVAILABLE, REMASK_AVAILABLE,
)

# ============================================================================
# OPTIONAL MODULES
# ============================================================================

CONFIG_AVAILABLE = False
try:
    from modules.config import load_config, ConfigLoader
    CONFIG_AVAILABLE = True
except ImportError:
    import logging as _logging
    _logging.getLogger(__name__).debug("modules.config not available — YAML config disabled")

LOGGING_AVAILABLE = False
try:
    from modules.masking_logger import MaskingLogger, setup_logging
    LOGGING_AVAILABLE = True
except ImportError:
    import logging as _logging
    _logging.getLogger(__name__).debug("modules.masking_logger not available — structured logging disabled")

# Re-mask (for --to-version and --chain-info CLI args)
try:
    from modules.re_mask import ChainUnmasker, load_chain, get_chain_info
except ImportError:
    pass

# ============================================================================
# МЕТАДАНІ
# ============================================================================
__version__ = "2.5.1"


def main():
    """
    Головна функція CLI для unmask.
    """
    # Fix Unicode output on Windows (PyInstaller cp1252 issue)
    if sys.platform == 'win32' and getattr(sys.stdout, 'encoding', 'utf-8').lower().replace('-', '') != 'utf8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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

    if SECURITY_AVAILABLE:
        security_group = parser.add_argument_group('security options')
        security_group.add_argument('--password', help='Password for encrypted mapping files')
        security_group.add_argument('--password-env', metavar='VAR',
                                    help='Environment variable name containing password')

    if REMASK_AVAILABLE:
        remask_group = parser.add_argument_group('re-mask options')
        remask_group.add_argument('--to-version', metavar='VERSION',
                                  help='Convert mapping to specified version')
        remask_group.add_argument('--chain-info', action='store_true',
                                  help='Show chain mapping information and exit')

    if CONFIG_AVAILABLE:
        config_group = parser.add_argument_group('config options')
        config_group.add_argument('-c', '--config', metavar='FILE',
                                  help='Configuration file (.yaml or .json)')

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
        except (FileNotFoundError, PermissionError, ValueError, OSError) as e:
            print(f"❌ Помилка завантаження конфігурації: {e}")
            log_error(f"Помилка завантаження конфігурації: {e}")
            return

    # ========================================================================
    # ВИЗНАЧЕННЯ ПАРОЛЯ
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
        result = auto_find_latest_pair()
        if result is None:
            return
        masked_path, map_path, output_path = result
        log_info(f"Автоматичний режим: {masked_path.name}")
    else:
        masked_path = Path(args.masked_file)
        if not masked_path.exists():
            print(f"❌ Файл не знайдено: {masked_path}")
            log_error(f"Файл не знайдено: {masked_path}")
            return

        if args.map_file:
            map_path = Path(args.map_file)
        else:
            filename = masked_path.stem
            if filename.startswith('output_'):
                map_path = masked_path.parent / f"masking_map_{filename[7:]}.json"
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

        if args.output:
            output_path = Path(args.output)
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = masked_path.parent / f"input_recovery_{timestamp}{masked_path.suffix}"

    # ========================================================================
    # ЗАВАНТАЖЕННЯ ФАЙЛІВ
    # ========================================================================

    try:
        masking_map = load_mapping_file(map_path, password=password)
        validate_mapping_schema(masking_map)
        log_info(f"Mapping завантажено: {map_path.name}")

        if REMASK_AVAILABLE and getattr(args, 'chain_info', False):
            show_chain_info(masking_map)
            return

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
            except (KeyError, ValueError, TypeError, OSError) as e:
                print(f"❌ Помилка конвертації: {e}")
                log_error(f"Помилка конвертації: {e}")
                return

        validate_file_size(masked_path)
        with open(masked_path, 'r', encoding='utf-8', newline='') as f:
            if masked_path.suffix == '.json':
                masked_data = json.load(f)
            else:
                masked_data = f.read()

        log_debug(f"Замасковані дані завантажено: {masked_path.name}")

    except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"❌ Помилка читання: {e}")
        log_error(f"Помилка читання: {e}")
        return

    # ========================================================================
    # ПРОЦЕС UNMASK
    # ========================================================================

    start_time = time.time()

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

    except (OSError, PermissionError, UnicodeEncodeError) as e:
        print(f"❌ Помилка збереження: {e}")
        log_error(f"Помилка збереження: {e}")
